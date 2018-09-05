from dataguzzler.linklist cimport dgl_List, dgl_NewList


cdef extern from "sys/poll.h" nogil:
     pass

cdef extern from "dg_internal/conn.h" nogil:
    cdef struct Conn:
        ConnBuf *InStream
        int Auth
        pass
    cdef struct ConnBuf:
        pass

    Conn *CreateDummyConn()
    ConnBuf *CreateConnBuf(size_t initialsize)
    void DeleteConn(Conn *)    
    pass

cdef extern from "dg_internal/util.h" nogil:
     pass

cdef extern from "dg_internal/main.h" nogil:
     struct AtExitFunc:
         pass
     pass
#ctypedef void (*AtExitFuncCallback)(AtExitFunc *, void *Param)

cdef extern from "dg_stringbuf.h" nogil:
     struct dg_StringBuf:
         pass
     dg_StringBuf *dgsb_CreateStringBuf(int initialsize) 
     void dgsb_StringBufAppend(dg_StringBuf *c,char *str)
     pass
 
cdef extern from "dg_internal/init.h" nogil:
     struct InitAction:
         int Type
         char *Name
         dg_StringBuf *Params
         char *SOName
         dgl_List *ParenParams
         pass
     int IAT_LIBRARY
     int IAT_MODULE
     pass
 
cdef extern from "dg_internal/mod.h" nogil:
    cdef struct Module:
        pass
    void StartModule(InitAction *Init,char *dg_bindir);
    pass

ctypedef void (*ContinuationFunction)(int retval,unsigned char *res,Module *Mod,Conn *Conn,void *Param)
ctypedef void (*ConnDestructor)(Module Mod, Conn C, void *Param)

cdef extern from "dg_internal/library.h" nogil:
    void StartLibrary(InitAction *Init,char *dg_bindir)
    pass



cdef extern from "dg_internal/rpc.h" nogil:
    cdef struct RPC_Asynchronous:
        pass


    RPC_Asynchronous *rpc_asynchronous_str_persistent(Module *Mod,Conn *Conn,int ImmediateOK,Conn *DummyConn,int PersistentFlag,void *Param,ContinuationFunction Continuation,ConnDestructor CD,unsigned char *str)
    pass


