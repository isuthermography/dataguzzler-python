/*
    Dataguzzler: A Platform for High Performance Laboratory Data Acquisition 
    Copyright (C) 2005-2006 Iowa State University

    This library is free software; you can redistribute it and/or
    modify it under the terms of the GNU Lesser General Public
    License as published by the Free Software Foundation; either
    version 2.1 of the License, or (at your option) any later version.

    This library is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public
    License along with this library; if not, write to the Free Software
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA

    As a special exception, third party data acquisition libraries
    or hardware drivers may be treated as if they were a major component
    of the operating system; therefore the special exception in GPLV2,
    section 3 applies to them.
*/

#include <stdio.h>
#include <stdarg.h>
#include <assert.h>
#include <stdlib.h>
#include <stddef.h>
#include <string.h>
#include <sys/poll.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/socket.h>
#include <fcntl.h>
#include <errno.h>
#include <time.h>
#include <Python.h>
#include "dg_linklist.h"
#include "dg_internal/util.h"
#include "dg_internal/conn.h"
#include "dg_internal/mod.h"
#include "dg_internal/main.h"
#include "dg_internal/rpc.h"

#include "dgold_locking_c.h"

struct RPC_Asynchronous { /* RPC asynchronous ConnCloseNotify */

};


void *RPCAP_CCNotify_GetParam(struct ConnCloseNotify *CCNotify)
{
  return NULL;
}

void rpc_asynchronous_abort(struct RPC_Asynchronous *RPCA)
{
  /* not needed in this context */
}



/* do a call asynchronously using a (possibly) persistent dummy connection, so that we can reuse the dummy connection and inhibit routines that 
   check for connections dying from thinking the connection has died until we're finally done */
/* persistency in enabled by PersistentFlag */
/* if PersistentFlag is FALSE then DummyConn will be automatically be removed from its list and destroyed. Otherwise you will have to destroy it manually */

/* Note that you can't reuse DummyConn until you get your continuation (or destructor) callback */
/* This uses and may ultimately (once the call back is done) clear the DummyConn's EmptyNotify and EmptyNotifyParam */
/* Use CreateDummyConn() to build DummyConn. You will also need to use CreateConnBuf() to create DummyConn->InStream and
   add DummyConn to the master ConnList */
/* ***!!! MUST BE CALLED WHILE HOLDING THE MAIN CONTEXT LOCK... 
   i.e. inside a dg_enter_main_context_c() block */
struct RPC_Asynchronous *rpc_asynchronous_str_persistent(struct Module *Mod,struct Conn *Conn,int ImmediateOK,struct Conn *DummyConn,int PersistentFlag,void *Param,void (*Continuation)(int retval,unsigned char *res,struct Module *Mod,struct Conn *Conn,void *Param),void (*ConnDestructor)(struct Module *Mod,struct Conn *Conn,void *Param),unsigned char *str)
{
  int retval;
  int rc;
  struct RPC_Asynchronous *Notify=NULL;
  //#struct RPCAP_CCNotify *PNotify;
  struct ConnCloseNotify *PNotify;
  struct timespec timeout,curtime;
  struct pollfd WakeupFd;

  if (PersistentFlag) {
    ResetConnBuf(DummyConn->CurResult);
    ResetConnBuf(DummyConn->InStream);
  }

  PushDataToConn(str,strlen((char *)str),DummyConn->InStream);
  PushDataToConn((unsigned char *)"\n",1,DummyConn->InStream);

  ObtainCommand(DummyConn);


  retval=1;
  while (DummyConn->CurCommand->Len) {
    retval=ExecuteCommand(DummyConn);
    while (!retval) {
      if (!DummyConn->WakeupFlag) {
	// wait for DummyConn->WakeupTime (timespec) or DummyConn->WakeupFd (pollfd)

	timeout.tv_sec=1; /* wake up every second unless otherwise specificed */
	timeout.tv_nsec=0;
	if (DummyConn->WakeupTime.tv_sec) {
	  curtime.tv_sec=0;
	  curtime.tv_nsec=0;
	  clock_gettime(dg_PosixClock,&curtime); /* update current time */
	  //fprintf(stderr,"curtime.tv_sec=%ld\n",(long)curtime.tv_sec);
	  if (PTimeDiff(&DummyConn->WakeupTime,&curtime) <= 0) {
	    timeout.tv_sec=0;
	    timeout.tv_nsec=0; // wake up immediately 
	  }
	  else {
	    timeout.tv_sec=DummyConn->WakeupTime.tv_sec-curtime.tv_sec;
	    timeout.tv_nsec=DummyConn->WakeupTime.tv_nsec-curtime.tv_nsec;
	    if (timeout.tv_nsec < 0) {
	      timeout.tv_sec--;
	      timeout.tv_nsec+=1000000000;
	    }
	  }
	}
	if (timeout.tv_sec > 1) timeout.tv_sec=1; // always wake up at least every few seconds

	WakeupFd=DummyConn->WakeupFd;
	
	/* Release the main context so that other stuff can happen */
	dg_leave_main_context_c();

	poll(&WakeupFd,(WakeupFd.fd < 0) ? 0:1,timeout.tv_sec*1000+timeout.tv_nsec/1000000);

	/* reacquire main context */
	dg_enter_main_context_c();

	
	DummyConn->WakeupFd.revents=WakeupFd.revents;
	
      } else {
	/* Got wakeupflag... clear it */
	DummyConn->WakeupFlag=0; 
      }
      retval=ExecuteCommand(DummyConn);
    }
    if (DummyConn->CurCommandContinues)
      ObtainCommand(DummyConn); /* extract the next portion of the command */
  }

  rc=DummyConn->LastErrorCode;
  if (Continuation) (*Continuation)(rc,DummyConn->CurResult->Data,Mod,Conn,Param);
    
  /* Delete DummyConn, calling any closenotifies that might be necessary */
  // DeleteConn(DummyConn); (DummyConn deleted in main loop)
  if (!PersistentFlag) DummyConn->Closing=1;
  return NULL;
 }

/* !!! VERY IMPORTANT !!! 
Need to verify that this routine  guarantees that consecutive RPC's from the same source to the same 
destination are dispatched in the order received (it does)
*/


struct RPC_Asynchronous *rpc_asynchronous_str(struct Module *Mod,struct Conn *Conn,int ImmediateOK,void *Param,void (*Continuation)(int retval,unsigned char *res,struct Module *Mod,struct Conn *Conn,void *Param),void (*ConnDestructor)(struct Module *Mod,struct Conn *Conn,void *Param),unsigned char *str)
{

  struct Conn *DummyConn;
  
  DummyConn=CreateDummyConn();
  DummyConn->InStream=CreateConnBuf(strlen((char *)str)+3);

  /* Add connection to main list */
  /* (delete connection when done by setting dummyflag)  */ 
  // DummyConn->DummyFlag=1; (no longer necessary as Closing flag is automatically set

  // with PersistentFlag==0 (parameter after DummyConn) 
  dgl_AddTail(&ConnList,(struct dgl_Node *)DummyConn); 
  

  return rpc_asynchronous_str_persistent(Mod,Conn,ImmediateOK,DummyConn,0,Param,Continuation,ConnDestructor,str);
}



struct RPC_Asynchronous *rpc_asynchronous(struct Module *Mod,struct Conn *Conn,int ImmediateOK,void *Param,void (*Continuation)(int retval,unsigned char *res,struct Module *Mod,struct Conn *Conn,void *Param),void (*ConnDestructor)(struct Module *Mod,struct Conn *Conn,void *Param),char *fmt,...)
{
  va_list ap;
  char *buf;
  int size=1000;
  int ret;
  struct RPC_Asynchronous *retval;

  
  do {
    buf=malloc(size);
    va_start(ap,fmt);
    ret=vsnprintf(buf,size,fmt,ap);
    if (ret < 0 || ret >= size) {
      free(buf);
      size*=2;
      buf=NULL;
    }
  
    va_end(ap);
  } while (!buf);
  retval=rpc_asynchronous_str(Mod,Conn,ImmediateOK,Param,Continuation,ConnDestructor,(unsigned char *)buf);

  free(buf);
  return retval;
}




int rpc_synchronous_str(char **res,unsigned char *str)
/* should free(*res) upon return */
{
  struct Conn *DummyConn;
  int retval;
  char *junk=NULL;

  if (!res) res=&junk;
  
  DummyConn=CreateDummyConn();

  DummyConn->InStream=CreateConnBuf(strlen((char *)str)+3);
  PushDataToConn(str,strlen((char *)str),DummyConn->InStream);
  PushDataToConn((unsigned char *)"\n",1,DummyConn->InStream);
  ObtainCommand(DummyConn);


  retval=1;
  while (DummyConn->CurCommand->Len) {
    retval=ExecuteCommand(DummyConn);
    if (!retval) break; /* command requires waiting */
    if (DummyConn->CurCommandContinues)
      ObtainCommand(DummyConn); /* extract the next portion of the command */
  }
  

#ifdef VM_CONNBUFS 
  /* not allowed to steal pointer in this case */
  *res=malloc(DummyConn->CurResult->Len+1);
  memcpy(*res,DummyConn->CurResult->Data,DummyConn->CurResult->Len+1);
#else  /* VM_CONNBUFS */
  *res=(char *)DummyConn->CurResult->Data; /* steal memory from the ConnBuf */
  DummyConn->CurResult->Data=NULL;
#endif /* VM_CONNBUFS */
  
  /* Delete DummyConn, calling any closenotifies that might be necessary */
  DeleteConn(DummyConn);

  if (junk) free(junk);

  return retval;
}

int rpc_synchronous(char **res,char *fmt,...)
{
  va_list ap;
  char *buf;
  int size=1000;
  int ret;
  int retval;

  
  do {
    buf=malloc(size);
    va_start(ap,fmt);
    ret=vsnprintf(buf,size,fmt,ap);
    if (ret < 0 || ret >= size) {
      free(buf);
      size*=2;
      buf=NULL;
    }
  
    va_end(ap);
  } while (!buf);
  retval=rpc_synchronous_str(res,(unsigned char *)buf);
  free(buf);

  return retval;
}

