from dataguzzler cimport linklist as dgl
cimport dataguzzler as dg
from .dg_internal cimport Module

# ***!!! NOTE: These functions my not require the GIL
# but they must be wrapped with
# dg_enter_main_context()/dg_leave_main_context() if you hold the GIL
# or dg_enter_main_context_c()/dg_leave_main_context_c() if you don't
cdef extern from "dg_internal/wfmstore.h" nogil:
    cdef struct Wfm:
        dg.dg_wfminfo Info
        unsigned long long globalrev
        char *Creator
        void *ModSpecific
        # Other members not exposed to Cython
        pass

    cdef struct Channel:
        dgl.dgl_Node Node # on ChannelList 
        char *ChannelName # Channel name (separate alloc) 
        unsigned long long latestrevision # increment on every update (including delete) 
        int Deleted # if non-zero, this waveform is deleted (but the structure is only
	            # freed or removed from the ChannelList when it is recreated). If a waveform of the same name
		    # is ever recreated, then store latestrevision, destroy this channel and create a new one with latestrevision incremented and NotifyList copied 
        dgl.dgl_List WfmList # list of waveforms in this channel, later revisions later 
        dgl.dgl_List NotifyList #  List of notifications (struct WfmNotify) to make 
	# if new waveform is created or becomes ready 
        int Volatile # does not need to be saved (OBSOLETE -- NOT USED) 
        char *Creator #  Creator module name 
        void (*Destructor)(Channel *Chan) # call this when channel deleted if not NULL 
        void *ModSpecific # data owned  by creator -- alternative to extending the structure 
        int Hidden #  if TRUE, this channel is hidden 
        # may have creator-specific data beyond this point 
        pass
    
    cdef struct GlobalRevisionNotify:
        pass

    cdef struct WfmNotify:
        pass

    cdef struct GlobalRevState:
        pass

    cdef struct GlobalrevCompWaitNode:
        pass

    cdef struct GlobalrevCompWait:
        pass

    GlobalRevState *GetGlobalRevCurState() # Can't use returned pointer past a WfmNotify (and don't free() it!) (may return NULL) 
    GlobalRevState *GetGlobalRevReadyState() # Can't use returned pointer past a WfmNotify (and don't free() it!) (may return NULL) 
    GlobalRevState *FindGlobalRev(unsigned long long grev)

    GlobalRevisionNotify *AddGlobalRevisionNotify(int structlen, int ReadyFlag,unsigned long long waitrevision,void (*GlobalRevNotification)(GlobalRevisionNotify *Not,unsigned long long newrevision),void *UserPtr) 
    
    void RemoveGlobalRevisionNotify(GlobalRevisionNotify *G)
    void LockGlobalRev(GlobalRevState *State)
    void UnlockGlobalRev(GlobalRevState *State)

    void IncGlobalRevision()
    void CullGlobalRevStateList()
    void StartTransaction()
    void EndTransaction()
    void NotifyChannel(Channel *Chan, Wfm *Wfm,int WfmReady)
    Channel *FindChannel(char *Name)
    
    # Find the specified channel. If it doesn't exist, create it with the "Deleted" flag set 
    Channel *FindChannelMakeDeleted(char *Name)
    
    int DeleteChannel(Channel *Chan,char *CreatorMatch); # returns non-zero if error. If CreatorMatch != NULL, Only deletes if CreatorMatch is Chan->Creator 
    Channel *CreateChannel(char *Name,char *Creator, int Volatile, void (*Destructor)(Channel *Chan),int structsize); # This adds the newly created Channel to the ChanList. 
    
    # if the channel of the specified name is owned by the specifed module,
    # return the channel, otherwise NULL 
    Channel *ChanIsMine(char *ChanName,char *ModName)
    
    void CreateWfmFromPtr(Channel *Chan,Wfm *Wfm, void (*Destructor)(Wfm *Wfm)) #  CreateWfm where Wfm structure is preallocated 
    
    # Note: This performs a NotifyChannel with WfmReady==0 
    # increments the refcount because this waveform is current, 
    # and finds the previous revision and decrements its refcount 
    # NOTE: Size is the size of the desired structure (0 gives sizeof(struct Wfm)). 
    # YOU NEED TO CALL WfmAlloc() to actually allocate space to store the waveform data 
    Wfm *CreateWfm(Channel *Chan,int Size,void (*Destructor)(Wfm *Wfm)) # Create a new waveform on the specified channel and add it to the master list 
     
     
     
    void DeleteWfm(Wfm *Wfm) #  This removes Wfm from master list 
    Wfm *FindWfmRevision(char *ChannelName,unsigned long long revision) # does not increment refcount 
    Wfm *FindWfmRevisionChan(Channel *Chan,unsigned long long revision)
     
    # MetaDatum routines may be called from another thread to create metadata for a Wfm with ReadyFlag==0 
 
    
    void WfmClone(Wfm *OldWfm,Wfm *NewWfm)
    void WfmCloneExtend(Wfm *OldWfm,Wfm *NewWfm,size_t newlen,size_t excesslengthhint)
    void WfmAlloc(Wfm *Wfm,size_t len,unsigned ndim,size_t *dimlen)
    void WfmAllocOversize(Wfm *Wfm,size_t len,unsigned ndim,size_t *dimlen,size_t oversizelen)
    void WfmAllocOversizeGivenFd(int fd,Wfm *Wfm, size_t len, unsigned ndim, size_t *dimlen, size_t oversizelen) # The file descriptor will be automatically closed when the region is munmap'd
     
    void DeleteWfmNotify(WfmNotify *N) # Must have already been removed from any lists 
    WfmNotify *CreateWfmNotify(void (*Notify)(Channel *Chan, Wfm *Wfm,int WfmReady, void *NotifyData),void *NotifyData)
    void *AbortWaitGlobalrevComputation(GlobalrevCompWait *Comp)
    GlobalrevCompWait *WaitGlobalrevComputation(unsigned long long globalrev,void *UserData,void (*DoneCallback)(GlobalrevCompWait *Comp,unsigned long long globalrev, void *UserData))
     
    Wfm *FindLatestReadyRev(Channel *Chan)

     

    void WfmReference(Wfm *Wfm) # OK to tall WfmReference() from alternate threads 
    void WfmUnreference(Wfm *Wfm); # OK to tall WfmUnreference() from alternate threads... DeleteWfm() calls
    # are queued up and handled by the parent thread 

    
    dgl.dgl_List ChanList;
    unsigned long long globalrevision
    pass

