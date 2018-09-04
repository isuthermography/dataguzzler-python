import sys
import os
import time
from .pydg import Module as pydg_Module
from .pydg import CurContext

from threading import Thread,Lock

cimport cpython.pycapsule as pycapsule
from cpython.ref cimport PyObject
from libc.stdlib cimport calloc,free
from libc.string cimport strdup

cdef extern from "sys/poll.h":
     pass

cdef extern from "dg_units.h":
     pass
     

cdef extern from "dg_linklist.h":
     cdef struct dgl_List:
         pass
     cdef struct dgl_Node:
         pass
     void dgl_NewList(dgl_List *)
     void dgl_AddTail(dgl_List *,dgl_Node *)
     dgl_Node *dgl_RemHead(dgl_List *)
     pass

cdef extern from "dataguzzler.h":
    pass

cdef extern from "dg_file.h":
    pass     

cdef extern from "conn.h":
    pass

cdef extern from "util.h":
     pass

cdef extern from "main.h":
     pass

cdef extern from "dg_stringbuf.h":
     pass
 
cdef extern from "init.h":
     pass
 
cdef extern from "mod.h":
    pass

cdef extern from "library.h":
    pass
    
cdef extern from "wfmstore.h":
    struct Wfm:
        pass
    
    struct Channel:
        pass

    struct WfmNotify:
        pass

    void StartTransaction()
    void EndTransaction()
    void NotifyChannel(Channel *Chan,Wfm *Wfm,int WfmReady)
    Channel *FindChannel(char *Name)

    # Find the specified channel. If it doesn't exist, create it with the "Deleted" flag set 
    Channel *FindChannelMakeDeleted(char *Name);

    int DeleteChannel(Channel *Chan,char *CreatorMatch); # returns non-zero if error. If CreatorMatch != NULL, Only deletes if CreatorMatch is Chan->Creator 
    Channel *CreateChannel(char *Name,char *Creator, int Volatile, void (*Destructor)(Channel *Chan),int structsize); # This adds the newly created Channel to the ChanList.
    
    # if the channel of the specified name is owned by the specifed module,
    # return the channel, otherwise NULL 

    Channel *ChanIsMine(char *ChanName,char *ModName)
  


    void CreateWfmFromPtr(Channel *Chan,Wfm *Wfm, void (*Destructor)(Wfm *Wfm)); # CreateWfm where Wfm structure is preallocated 

    Wfm *CreateWfm(Channel *Chan,int Size,void (*Destructor)(Wfm *Wfm)); # Create a new waveform on the specified channel and add it to the master list 

    

    void DeleteWfm(Wfm *Wfm); # This removes Wfm from master list 
    Wfm *FindWfmRevision(char *ChannelName,unsigned long long revision); # does not increment refcount 
    Wfm *FindWfmRevisionChan(Channel *Chan,unsigned long long revision)

    # MetaDatum routines may be called from another thread to create metadata for a Wfm with ReadyFlag==0  

    void WfmClone(Wfm *OldWfm,Wfm *NewWfm);
    void WfmCloneExtend(Wfm *OldWfm,Wfm *NewWfm,size_t newlen,size_t excesslengthhint);
    void WfmAlloc(Wfm *Wfm,size_t len,unsigned ndim,size_t *dimlen);
    void WfmAllocOversize(Wfm *Wfm,size_t len,unsigned ndim,size_t *dimlen,size_t oversizelen);
    void WfmAllocOversizeGivenFd(int fd, Wfm *Wfm, size_t len, unsigned ndim, size_t *dimlen, size_t oversizelen); #The file descriptor will be automatically closed when the region is munmap'd
    
    void DeleteWfmNotify(WfmNotify *N); #  Must have already been removed from any lists 
    WfmNotify *CreateWfmNotify(void (*Notify)(Channel *Chan, Wfm *Wfm,int WfmReady, void *NotifyData),void *NotifyData);
    #void *AbortWaitGlobalrevComputation( GlobalrevCompWait *Comp);
    # struct GlobalrevCompWait *WaitGlobalrevComputation(unsigned long long globalrev,void *UserData,void (*DoneCallback)(struct GlobalrevCompWait *Comp,unsigned long long globalrev, void *UserData));
    
    Wfm *FindLatestReadyRev(Channel *Chan);
    

    pass

cdef extern from "dgold_locking_c.h":
    void dg_enter_main_context() nogil
    void dg_leave_main_context() nogil
    void dg_main_context_init() nogil 
    pass



cdef extern from "savewfm_c.h":
    struct SaveWfmNode:
        char *Name
        Wfm *Wfm
        pass
    char *loadwfms_c(char *Filename,char *ModName,dgl_List *WfmList) nogil
    char *savewfms_c(char *Filename,dgl_List *WfmList) nogil
 
    pass


class savewfm(object,metaclass=pydg_Module):
    Name=None

    def __init__(self,Name):
        self.Name=Name
        pass


    def savewfms(self,path, name, waveforms):
        # waveforms is list of waveform names
        cdef SaveWfmNode *WfmNode;
        cdef dgl_List WfmList
        cdef char *errmsg
        cdef bytes namebytes
        dgl_NewList(&WfmList); 
        
        waveformnames = [ waveformname.encode('utf8') for waveformname in waveforms ]
         
        # Assemble list of waveforms
        for waveform in waveformnames:
            WfmNode=<SaveWfmNode *>calloc(sizeof(SaveWfmNode),1)
            namebytes=waveform
            WfmNode.Name=strdup(<char *>namebytes)
            dgl_AddTail(&WfmList,<dgl_Node *>WfmNode)
            pass
        Filename=os.path.join(path,name).encode('utf8')
        # Perform save
        errmsg=savewfms_c(Filename,&WfmList)
 
        WfmNode=<SaveWfmNode *>dgl_RemHead(&WfmList)
        while WfmNode is not NULL:
            free(WfmNode.Name)
            free(WfmNode)
            WfmNode=<SaveWfmNode *>dgl_RemHead(&WfmList)
            pass
        pass
        if errmsg is not NULL:
            raise IOError(errmsg)
        pass

    def loadwfms(self,path, name):
        # waveforms is list of waveform names
        cdef SaveWfmNode *WfmNode;
        cdef dgl_List WfmList
        cdef char *errmsg
        cdef char *Filename_ptr
        cdef char *Modname_tr
        cdef bytes Modname_bytes 
        
        dgl_NewList(&WfmList);

        Filename=os.path.join(path,name).encode('utf8')
        Filename_ptr=<char *>Filename
        Modname_bytes=self.Name.encode('utf-8')
        Modname_ptr=<char *>Modname_bytes
 
        # Perform load
        with nogil: 
            errmsg=loadwfms_c(Filename_ptr,Modname_ptr,&WfmList)
            pass

        WfmNode=<SaveWfmNode *>dgl_RemHead(&WfmList)
        while WfmNode is not NULL:
            free(WfmNode)
            WfmNode=<SaveWfmNode *>dgl_RemHead(&WfmList)
            pass
        pass
        if errmsg is not NULL:
            raise IOError(errmsg)
        pass

    def deletewfm(self,channame):
        cdef Channel *Chan
        cdef bytes channame_bytes,modname_bytes
        

        channame_bytes=channame.encode('utf-8')
        modname_bytes=self.Name.encode('utf-8')

        dg_enter_main_context()
        Chan=ChanIsMine(<char *>channame_bytes,<char *>modname_bytes)
        if Chan != NULL:
            DeleteChannel(Chan,modname_bytes)
            pass
        dg_leave_main_context()
        
        pass

    pass

