import sys
from .pydg import Module as pydg_Module
from .pydg import CurContext

cimport cpython.pycapsule as pycapsule
from cpython.ref cimport PyObject

cimport libc.time
cimport posix.time
from libc.string cimport strdup
from dataguzzler.linklist cimport dgl_List, dgl_NewList

from .dg_internal cimport Conn,ConnBuf,CreateDummyConn,CreateConnBuf,DeleteConn,AtExitFunc,dg_StringBuf,dgsb_CreateStringBuf,dgsb_StringBufAppend,InitAction,IAT_LIBRARY,IAT_MODULE,Module,StartModule,StartLibrary,rpc_asynchronous_str_persistent


     


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


class DataguzzlerError(Exception):
    pass


cdef void DummyConnCapsule_Destructor(object capsule):
    cdef Conn *dummyconn=<Conn *>pycapsule.PyCapsule_GetPointer(capsule,NULL)
    DeleteConn(dummyconn)
    pass

cdef void dgold_rpc_continuation(int retval, unsigned char *res, Module *Mod, Conn *conn,void *param):
    cdef bytes py_bytes
    cdef PyObject *param_pyobj
    cdef object paramobj

    param_pyobj=<PyObject *>param
    paramobj=<object>param  # actually a list
    py_bytes=res
    paramobj.append(retval)
    paramobj.append(py_bytes)
    pass


# FIXME: Should use AddAtExitFunc to enable cleanups of stuff in /dev/shm
cdef public AtExitFunc *AddAtExitFunc(void (*Func)(AtExitFunc *, void *Param),void *UserData):
    return NULL


def rpc_authenticated(context):
    if hasattr(context,"_pydg_dgold_rpc_dummyconn"):
        dccapsule=context._pydg_dgold_rpc_dummyconn
        dummyconn=<Conn *>pycapsule.PyCapsule_GetPointer(dccapsule,NULL)
        return bool(dummyconn.Auth)
    return False

def rpc_async(context,bytes cmdbytes):
    cdef Conn *dummyconn
    cdef object retlistobj

    try:
        dccapsule=object.__getattribute__(context,"_pydg_dgold_rpc_dummyconn")
        dummyconn=<Conn *>pycapsule.PyCapsule_GetPointer(dccapsule,NULL)
        pass
    except AttributeError:        
        dummyconn=CreateDummyConn()
        dummyconn.InStream=CreateConnBuf(1024)
        
        dccapsule=pycapsule.PyCapsule_New(<void *>dummyconn,NULL,DummyConnCapsule_Destructor)
        object.__setattr__(context,"_pydg_dgold_rpc_dummyconn",dccapsule)
        pass

    retlist=[]
    retlistobj=retlist
    
    rpc_asynchronous_str_persistent(NULL,NULL,1,dummyconn,1,<void *>retlistobj,dgold_rpc_continuation,NULL,cmdbytes)

    retval=retlist[0]
    retbytes=retlist[1]

    return (retval,retbytes)

def cmd(cmdstr):
    # shorthand for rpc_async(CurContext(),cmdstr.encode('utf-8'))
    (retval,retbytes)=rpc_async(CurContext(),cmdstr.encode('utf-8'))
    return (retval,retbytes.decode('utf-8'))

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

    StartLibrary(&Action,"/usr/local/dataguzzler/libraries")

    pass

class DGModule(object,metaclass=pydg_Module):
    Name=None
    
    def __init__(self,Name,SOName,ModParams):
        # NOTE: Does not support ParenParams (only used by subproc.so)
        cdef InitAction Action
        cdef dg_StringBuf *Buf

        self.Name=Name
        
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

        StartModule(&Action,"/usr/local/dataguzzler/modules")
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

        #sys.stderr.write("__getattribute__ failed\n")
        #sys.stderr.flush()

         
        (retcode,retval)=cmd("%s:%s?" % (self.Name,attrname))

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
            (retcode,retval)=cmd("%s:%s %s" % (self.Name,attrname,str(attrvalue)))
        
            if retcode > 299:
                raise DataguzzlerError(retval)
            pass
        
        return retval

    def cmd(self,cmdstr):
        (retcode,retval)=cmd("%s:%s" % (self.Name,cmdstr))
        
        if retcode > 299:
            raise DataguzzlerError(retval)
        return retval
    
    pass
