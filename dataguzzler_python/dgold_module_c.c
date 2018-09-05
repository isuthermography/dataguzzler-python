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
#include "dg_internal/multipoll.h"
#include "dgold_module_c.h"
#include "dgold_locking_c.h"

#define DG_MAX_FDS 1000 /* max # of file descriptors for poll() */

#define ADD_POLLUFD(ufd,uevents) if (npollufds < DG_MAX_FDS-1) {pollufds[npollufds].fd=ufd;pollufds[npollufds].events=uevents;pollufds[npollufds].revents=0;npollufds++;} else {fprintf(stderr,"%s Internal error: DG_MAX_FDS too small\n",commandname);}


void ModWakeupLoop(void)
// ModWakeupLoop is a NOGIL function. Must be called WITHOUT the gil
{
  struct Module *Mod;
  struct pollfd pollufds[DG_MAX_FDS];
  unsigned npollufds;
  double maxtimeout=50e-3; /* max timeout in seconds */
  double timeoutms;
  short gotevents;
  struct timespec wakeuptime,maxtimeoutspec,timeout,curtime;
  maxtimeoutspec.tv_sec=(int)maxtimeout;
  maxtimeoutspec.tv_nsec=(int)((maxtimeout-maxtimeoutspec.tv_sec)*1e9);


  dg_enter_main_context_c();
  for (;;) {
    npollufds=0;
    wakeuptime.tv_sec=0;
    wakeuptime.tv_nsec=0;
    

    //fprintf(stderr,"ModWakeupLoop() looping\n");
    /* check if read data is available for any module */
    for (Mod=(struct Module *)ModuleList.lh_Head;Mod->Node.ln_Succ;Mod=(struct Module *)Mod->Node.ln_Succ) {
      if (Mod->WakeupEvent.fd >= 0) {
	ADD_POLLUFD(Mod->WakeupEvent.fd,Mod->WakeupEvent.events);
      }      
      if (Mod->WakeupEvent2.fd >= 0) {
	ADD_POLLUFD(Mod->WakeupEvent2.fd,Mod->WakeupEvent2.events);
      }      
    }
    
    
    /* see if any modules are asking for a wakeup. Reduce wakeuptime as appropriate */
    for (Mod=(struct Module *)ModuleList.lh_Head;Mod->Node.ln_Succ;Mod=(struct Module *)Mod->Node.ln_Succ) {
      if (Mod->WakeupTime.tv_sec) {
	if (!wakeuptime.tv_sec) {
	  wakeuptime=Mod->WakeupTime;
	  //fprintf(stderr,"Wakeup by module %s\n",Mod->Name);
	}
	else {
	  if (PTimeDiff(&wakeuptime,&Mod->WakeupTime) > 0) {
	    wakeuptime=Mod->WakeupTime;	
	    //fprintf(stderr,"Wakeup by module %s\n",Mod->Name);
	  }
	    
	}
      }
    }

    clock_gettime(dg_PosixClock,&curtime); /* update current time */

    if (wakeuptime.tv_sec) {
      if (PTimeDiff(&wakeuptime,&curtime) <= 0) {
	timeout.tv_sec=0;
	timeout.tv_nsec=0; /* wake up immediately */
      }
      else {
	timeout.tv_sec=wakeuptime.tv_sec-curtime.tv_sec;
	timeout.tv_nsec=wakeuptime.tv_nsec-curtime.tv_nsec;
	if (timeout.tv_nsec < 0) {
	  timeout.tv_sec--;
	  timeout.tv_nsec+=1000000000;
	}
      }
    } else timeout=maxtimeoutspec;
    if (PTimeDiff(&maxtimeoutspec,&timeout) < 0) {
      timeout=maxtimeoutspec;
    }
   

#ifdef USE_BUSYLOOP_FOR_SHORT_POLL      
    if (timeout.tv_sec == 0 && timeout.tv_nsec < BUSYLOOP_THRESHOLD) {
      /* busyloop on select */
      timeout.tv_sec=0;
      timeout.tv_nsec=0;	
    }
#endif /* USE_BUSYLOOP_FOR_SHORT_POLL */
 
    if (timeout.tv_sec==0 && timeout.tv_nsec==0) timeoutms=0;
    else {
      timeoutms=timeout.tv_sec*1000+timeout.tv_nsec/1000000 + 1;
    }

    //#fprintf(stderr,"ModWakeupLoop() calling multipoll\n");

    //Py_BEGIN_ALLOW_THREADS;
    dg_leave_main_context_c();
    multipoll(pollufds,&npollufds,timeoutms);
    dg_enter_main_context_c();
    //Py_END_ALLOW_THREADS;
    
    /* Repoll with zero timeout to update pollufds now that we have
       the main context lock */
    if (timeoutms != 0) {
      multipoll(pollufds,&npollufds,0);
    }
  

    for (Mod=(struct Module *)ModuleList.lh_Head;Mod->Node.ln_Succ;Mod=(struct Module *)Mod->Node.ln_Succ) {
      /* Check for a WakeupEvent() for this module */
      if ((gotevents=GotPollFd(Mod->WakeupEvent.fd,pollufds,npollufds,~0))) {
	(*Mod->WakeupJob)(Mod,gotevents);
	//fprintf(stderr,"Got WakeupJob %s\n",Mod->Name);
      }
      if ((gotevents=GotPollFd(Mod->WakeupEvent2.fd,pollufds,npollufds,~0))) {
	(*Mod->WakeupJob2)(Mod,gotevents);
	//fprintf(stderr,"Got WakeupJob2 %s\n",Mod->Name);
      }
      /* execute the BackgroundJob() of each module */
      if (Mod->BackgroundJob) (*Mod->BackgroundJob)(Mod);
    }
  }
  
  dg_leave_main_context_c();
}
