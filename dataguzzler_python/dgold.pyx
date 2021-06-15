import sys
import time
from .dgpy import Module as dgpy_Module
from .dgpy import CurContext

from threading import Thread,Lock

cimport cpython.pycapsule as pycapsule
from cpython.ref cimport PyObject

cimport libc.time
cimport posix.time
from libc.string cimport strdup
from dataguzzler.linklist cimport dgl_List, dgl_NewList

from .dg_internal cimport Conn,ConnBuf,CreateDummyConn,CreateConnBuf,DeleteConn,AtExitFunc,dg_StringBuf,dgsb_CreateStringBuf,dgsb_StringBufAppend,InitAction,IAT_LIBRARY,IAT_MODULE,Module,StartModule,StartLibrary,rpc_asynchronous_str_persistent

#cdef extern from "dg_units.h":
#     pass
     


cdef extern from "dgold_module_c.h":
    void ModWakeupLoop() nogil
    pass

cimport dgold




cdef public char *SetQueryPrefix
cdef public char *SetQueryPostfix
cdef public int dg_PosixClock
cdef public Module *DefaultModule
cdef public char *commandname


cdef public dgl_List InitActionList
cdef public dgl_List ConnList
cdef public dgl_List ModuleList

SetQueryPrefix=NULL
SetQueryPostfix=NULL
dg_PosixClock=posix.time.CLOCK_REALTIME
DefaultModule=NULL
commandname_py=sys.argv[0].encode('utf-8')
commandname=<char *>strdup(commandname_py)


dgl_NewList(&InitActionList)
dgl_NewList(&ConnList)
dgl_NewList(&ModuleList)

dgmainloop_started=False

with nogil: 
     dgold.dg_main_context_init()
     pass


class DataguzzlerError(Exception):
    pass


cdef void DummyConnCapsule_Destructor(object capsule):
    cdef Conn *dummyconn=<Conn *>pycapsule.PyCapsule_GetPointer(capsule,NULL)
    DeleteConn(dummyconn)
    pass


cdef void dgold_rpc_continuation_core(int retval, unsigned char *res, Module *Mod, Conn *conn,void *param):
    cdef bytes py_bytes
    cdef PyObject *param_pyobj
    cdef object paramobj
    
    param_pyobj=<PyObject *>param
    paramobj=<object>param  # actually a list
    py_bytes=res
    paramobj.append(retval)
    paramobj.append(py_bytes)


    pass

cdef void dgold_rpc_continuation(int retval, unsigned char *res, Module *Mod, Conn *conn,void *param) nogil:

    dgold.dg_leave_main_context_c()    
    with gil:
        dgold_rpc_continuation_core(retval,res,Mod,conn,param)
        pass
    dgold.dg_enter_main_context_c()
    pass

# FIXME: Should use AddAtExitFunc to enable cleanups of stuff in /dev/shm
cdef public AtExitFunc *AddAtExitFunc(void (*Func)(AtExitFunc *, void *Param),void *UserData) nogil: 
    return NULL

cdef public void QuitError() nogil:
    with gil:
        exit(1)
        pass
    pass


def rpc_authenticated(context):
    if hasattr(context,"_dgpy_dgold_rpc_dummyconn"):
        dccapsule=context._dgpy_dgold_rpc_dummyconn
        dummyconn=<Conn *>pycapsule.PyCapsule_GetPointer(dccapsule,NULL)
        return bool(dummyconn.Auth)
    return False

def rpc_async(context,bytes cmdbytes):
    cdef Conn *dummyconn
    cdef object retlistobj
    cdef void *restlistptr
    cdef unsigned char *cmdbytesptr

    try:
        dccapsule=object.__getattribute__(context,"_dgpy_dgold_rpc_dummyconn")
        dummyconn=<Conn *>pycapsule.PyCapsule_GetPointer(dccapsule,NULL)
        pass
    except AttributeError:        
        dummyconn=CreateDummyConn()
        dummyconn.InStream=CreateConnBuf(1024)
        
        dccapsule=pycapsule.PyCapsule_New(<void *>dummyconn,NULL,DummyConnCapsule_Destructor)
        object.__setattr__(context,"_dgpy_dgold_rpc_dummyconn",dccapsule)
        pass

    retlist=[]
    retlistobj=retlist
    retlistptr=<void*>retlistobj
    cmdbytesptr=cmdbytes
    with nogil:
        dgold.dg_enter_main_context_c()
        rpc_asynchronous_str_persistent(NULL,NULL,1,dummyconn,1,retlistptr,dgold_rpc_continuation,NULL,cmdbytesptr)
        dgold.dg_leave_main_context_c()
        pass

    retval=retlist[0]
    retbytes=retlist[1]

    return (retval,retbytes)

def _rawcmd(cmdstr):
    # shorthand for rpc_async(CurContext()[0],cmdstr.encode('utf-8'))
    (retval,retbytes)=rpc_async(CurContext()[0],cmdstr.encode('utf-8'))
    return (retval,retbytes.decode('utf-8'))

def dgmainloop():
    with nogil:
        ModWakeupLoop()
        pass
    pass


def start_mainloop_thread():
    thread=Thread(target=dgmainloop,daemon=True)
    thread.start()
    return thread



def cmd(cmdstr):
    """ ***!!! WARNING: This does not change context, and should probably be modified to 
    identify the modules being reference and shift into their contexts!
    For the moment all traditional dataguzzler modules are protected 
    by the Python GIL... so it module context probably doesn't really 
    matter. Nevertheless it would be nice to insert a hook into the 
    command processor to correctly set the context. 
    Once wfmstore and similar libraries are thread-safe based on 
    their own locks then it would be possible to release the GIL and 
    let dataguzzler modules multi-thread. """
    return _rawcmd(cmdstr)

def library(SOName,initparams=""):
    cdef InitAction Action
    cdef dg_StringBuf *Buf
    
    SONameBytes=SOName.encode('utf-8')
    initparamsbytes=initparams.encode('utf-8')
    
    Buf=dgsb_CreateStringBuf(len(initparamsbytes)+10)
    dgsb_StringBufAppend(Buf,<char *>initparamsbytes)
    
    Action.Type=IAT_LIBRARY
    Action.Name=NULL
    Action.Params=Buf
    Action.SOName=<char *>SONameBytes
    Action.ParenParams=NULL

    dgold.dg_enter_main_context()
    with nogil:
        StartLibrary(&Action,"/usr/local/dataguzzler/libraries")
        pass
    dgold.dg_leave_main_context()

    pass

class DGModule(object,metaclass=dgpy_Module):
    Name=None
    
    def __init__(self,Name,SOName,ModParams):
        # NOTE: Does not support ParenParams (only used by subproc.so)
        cdef InitAction Action
        cdef dg_StringBuf *Buf

        self.Name=Name
        
        
        if not(dgmainloop_started):  # NOTE: OK to access globals because class definitions should only be run during initial configuration (single-threaded)
            start_mainloop_thread()
            global dgmainloop_started
            dgmainloop_started=True
            pass

        NameBytes=Name.encode('utf-8')
        SONameBytes=SOName.encode('utf-8')
        ModParamsBytes=ModParams.encode('utf-8')

        Buf=dgsb_CreateStringBuf(len(ModParamsBytes)+10)
        dgsb_StringBufAppend(Buf,<char *>ModParamsBytes)

        Action.Type=IAT_MODULE
        Action.Name=NameBytes
        Action.Params=Buf
        Action.SOName=<char *>SONameBytes
        Action.ParenParams=NULL

        dgold.dg_enter_main_context()
        with nogil:
            StartModule(&Action,"/usr/local/dataguzzler/modules")
            pass
        dgold.dg_leave_main_context()
        pass

    # Limited support of arbitrary attributes
    def __getattr__(self,attrname):
        #sys.stderr.write("DGModule_Getattr()\n")
        #sys.stderr.flush()
        try:
            attr=object.__getattribute__(self,attrname)
            
            #sys.stderr.write("__getattribute__ succeeded\n")
            #sys.stderr.flush()
            #return object.__getattr__(self,attrname)
            return attr
        except AttributeError:
            pass
     
        if attrname.startswith("__"):
            raise AttributeError(attrname)
       
       
        #sys.stderr.write("__getattribute__ failed\n")
        #sys.stderr.flush()

         
        (retcode,retval)=_rawcmd("%s:%s?" % (self.Name,attrname))

        #sys.stderr.write("called cmd...\n")
        #sys.stderr.flush()
 
        if retcode > 299:
            raise DataguzzlerError(retval)
        return retval

    def __setattr__(self,attrname,attrvalue):
        try:
            attr=object.__getattribute__(self,attrname)
            return object.__setattr__(self,attrname,attrvalue)
        except AttributeError:
            (retcode,retval)=_rawcmd("%s:%s %s" % (self.Name,attrname,str(attrvalue)))
        
            if retcode > 299:
                raise DataguzzlerError(retval)
            pass
        
        return retval

    def cmd(self,cmdstr):
        (retcode,retval)=_rawcmd("%s:%s" % (self.Name,cmdstr))
        
        if retcode > 299:
            raise DataguzzlerError(retval)
        return retval
    
    pass


