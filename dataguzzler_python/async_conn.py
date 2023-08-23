# !!!*** python3 only!!!***
import sys
import os
import os.path
import ast
import socket
import pickle
import traceback
import importlib
import queue
import threading
from threading import Thread,Lock,local,current_thread
import asyncio
from asyncio import StreamReader,StreamReaderProtocol
from asyncio import IncompleteReadError
import copy
import struct
#import ctypes
import numbers

import numpy as np

from .dgpy import get_pint_util_SharedRegistryObject

from .remoteproxy import remoteproxy
from . import dgpy
from .context import InitContext,InitCompatibleThread,InitFreeThread,InitThread,SimpleContext
from .context import PushThreadContext,PopThreadContext,FormatCurContext
from .conn import DGConn
from .remoteproxy import set_active_remote_link_this_thread
from .remoteproxy import remoteproxy

PicklableExceptions = set(["Exception","ArithmeticError","OverflowError","ZeroDivisionError","FloatingPointError","BufferError","LookupError","IndexError","KeyError","AssertionError","AttributeError","EOFError","FloatingPointError","GeneratorExit","ImportError","ModuleNotFoundError","KeyboardInterrupt","MemoryError","NameError","NotImplementedError","OSError","OverflowError","RecursionError","ReferenceError","RuntimeError","StopIteration","StopAsyncIteration","SyntaxError","IndentationError","TabError","SystemError","TypeError","UnboundLocalError","UnicodeError","UnicodeEncodeError","UnicodeDecodeError","UnicodeTranslateError","ValueError","BlockingISError","ChildProcessError","ConnectionError","BrokenPipeError","ConnectionAbortedError","ConnectionRefusedError","ConnectionResetError","FileExistsError","FileNotFoundError","InterruptedError","IsADirectoryError","NotADirectoryError","PermissionError","ProcessLookupError","TimeoutError"])

class AsyncFailureError(RuntimeError):
    def __init__(self,exc_str,tb_str):
        self.exc_str=exc_str
        self.tb_str=tb_str
        pass
    
    def __str__(self):
        return "Exception in asynchronous connection method call: %s\n\nTraceback of asynchronous portion follows:\n%s\n" % (self.exc_str,self.tb_str)

    #def __repr__(self):
    #    return "AsyncFailureError(%s,\n afe2h r\"\"\"%s\"\"\"\n end_afe2h" % (self.exc_str,self.tb_str)
async def write_immediate(writer,*args):
    #sys.stderr.write("pid: %d tid %d write_immediate: %s\n" % (os.getpid(),threading.get_ident(),args[0][:8].decode('iso8859-1')))
    for arg in args:
        writer.write(arg)
        pass
    await writer.drain()
    pass

class ProxyObj(object):
    """ This is our local representation of remote proxies for 
    our objects. It pickles to a remoteproxy object that can be
    instantiated in the remote thread (under 
    remoteproxy.set_active_remote_link_this_thread() identifying the link to us)
    """
    idval=None
    object_to_wrap=None
    remote_refcnt=None # Count of number of times this has been pickled-off to a remote proxy
    
    def __init__(self,object_to_wrap,debug):
        self.idval=id(object_to_wrap)
        self.object_to_wrap=object_to_wrap
        self.remote_refcnt=0
        if debug:
            #sys.stderr.write("object_to_wrap class: %s\n" % (str(object_to_wrap.__class__)))
            sys.stderr.write("pid %d tid %d creating proxy object %d for %s of type %s\n" % (os.getpid(),threading.get_ident(),self.idval,str(object_to_wrap),object_to_wrap.__class__.__name__))
            pass
        
        pass

    def deref(self):
        self.remote_refcnt -= 1
        pass
    
    def __reduce__(self):  # Pickles to a remoteproxy.remoteproxy
        self.remote_refcnt += 1
        return (remoteproxy,(self.idval,True))  # True indicates that remoteproxy object should get remotelink saved when unpickled at other end
    pass

class ImplicitRootProxyObj(ProxyObj):
    def __init__(self):
        self.idval=0
        self.remote_refcnt=1
        self.object_to_wrap = sys.modules["dgpy_config"]
        #sys.stderr.write("pid %d IRPO object_to_wrap id %d\n" % (os.getpid(),id(self.object_to_wrap))) 
        pass
    def deref(self):
        # refcnt of the implicit root proxy object is always 1
        pass
    def __reduce__(self):
        raise RuntimeError("Should never be called")
    
# !!!! Need to update protocol to be symmetric !!!***
class PyDGAsyncConn(DGConn):
    """Binary Asynchronous (RPC) dataguzzler connection"""
    ThreadContextPrefix = "ASyncConn"
    conninfo = None
    
    auth=None
    authenticated=None
    proxydb=None # dictionary by id of proxied objects's we have returned to the other side of the connection
    proxydb_lock=None # threading.Lock used to serialize modifications to proxydb
    
    proxy_of_remote_root = None # object representing the root of the other side of the link

    tls=None # thread-local-store with thread_has_remote_subconn attribute

    waiting_threads = None # dictionary by id(thread) of queue.Queue being waited on by that thread for a response.
    debug = None
    
    def __init__(self,**kwargs):
        self.authenticated=False
        self.proxydb = {}
        self.proxydb_lock = Lock()
        self.tls = local()
        self.waiting_threads = {}
        self.debug = False
        
        for arg in kwargs:
            if not hasattr(self,arg):
                raise ValueError("Unknown attribute: %s" % (arg))
            setattr(self,arg,kwargs[arg])
            pass

        if not self.authenticated and self.auth is None:
            raise ValueError("PyDGAsyncConn: Some authentication method is required")
        # Create implicit proxy of our root (id==0)
        self.proxydb[0] = ImplicitRootProxyObj()
        
        # Create implicit proxy of remote root (id==0)
        set_active_remote_link_this_thread(self)
        self.proxy_of_remote_root = remoteproxy(0,True)
        set_active_remote_link_this_thread(None)
        pass

    def set_conninfo(self,conninfo):
        self.conninfo=conninfo
        pass

    def get_proxy(self,ret):
        self.proxydb_lock.acquire()
        try:
            if id(ret) in self.proxydb:
                # Use pre-existing proxy if we have one
                retproxy = self.proxydb[id(ret)]
                pass
            else:
                # Create a new proxy if necessary
                retproxy = ProxyObj(ret,self.debug)
                self.proxydb[id(ret)]=retproxy
                pass
            pass
        finally:
            self.proxydb_lock.release()
        return retproxy

    def get_proxy_if_needed(self,ret):
        # ... Proxies __are__ actually needed for OpaqueWrappers
        #if object.__getattribute__(ret,"__class__").__name__ == "OpaqueWrapper":
        #    return self.get_proxy(ret)

        if object.__getattribute__(ret,"__class__") is remoteproxy:
            # existing proxies don't get reproxied
            return ret
        if self.debug:
            sys.stderr.write("get_proxy_if_needed on %s\n" % (object.__getattribute__(ret,"__class__").__name__))
            pass
        
        if ret is None or ret is type or isinstance(ret,numbers.Number) or isinstance(ret,str) or isinstance(ret,bytes) or isinstance(ret,np.ndarray) or isinstance(ret,get_pint_util_SharedRegistryObject()) or isinstance(ret,bool) :
            # Simple numbers/strings/other base types/numpy arrays/unit quantities: Do not proxy, just let them pickle
            return ret

        if type(ret) is tuple or type(ret) is list:
            # Simple sequence: Proxy its contents
            outseq=[]
            for el in ret:
                outseq.append(self.get_proxy_if_needed(el))
                pass
            if type(ret) is tuple:
                return tuple(outseq)
            return outseq
        
        if type(ret) is dict:
            # Note: We will crash if a dict has keys that don't pass the simple proxy test. This is intentional as we want to support dicts with simple keys and dicts with non-simple keys are pretty unlikely in our use case. We really don't want whether something is proxied or not to change based on deep content. 

            outdict={}
            for key in ret:
                if not(isinstance(ret,numbers.Number) or isinstance(ret,str) or isinstance(ret,bytes) or isinstance(ret,bool)):  # omit ndarray because it's not hashable
                    raise KeyError("Cannot transfer dictionary with non-simple keys over RPC connection")
                outdict[key] = get_proxy_if_needed(ret[key])
                pass
            
            return outdict
        if type(ret).__name__ in PicklableExceptions:
            return ret
        
        # Otherwise, find or create a proxy 

        return self.get_proxy(ret)

    def deproxy(self,obj):
        """Search for remoteproxy objects in freshly received and unpickled
        objects and unproxy them"""
        if type(obj) is remoteproxy:
            objid = object.__getattribute__(obj,"_remoteproxy_remoteid")
            remote_link = object.__getattribute__(obj,"_remoteproxy_remote_link")
            if self.debug:
                sys.stderr.write("pid %d tid %d deproxying remoteid %d remotelink %d none %d\n" % (os.getpid(),threading.get_ident(),objid,id(remote_link),id(None)))
                pass
            
            if remote_link is not None:
                # This remoteproxy originates from the other side
                # and shouldn't be deproxied
                return obj
            else: 
                if objid not in self.proxydb:
                    raise ValueError("Deproxying unknown object id %d" % (objid))
                if self.debug:
                    sys.stderr.write("Deproxied to %d\n" % (id(self.proxydb[objid].object_to_wrap)))
                    pass
                
                return self.proxydb[objid].object_to_wrap
            pass
        if type(obj) is tuple or type(obj) is list:
            # Simple sequence: de-proxy its contents
            outseq=[]
            for el in obj:
                outseq.append(self.deproxy(el))
                pass
            if type(obj) is tuple:
                return tuple(outseq)
            return outseq
        
        return obj
    
        
    def call_remote_method(self,obj,methodname,args,kwargs):
        """Call the given remote method. obj should be a local proxy of 
        a remote object, such as self.proxy_of_remote_root or a proxy
        returned by a prior method call.
        
        The call is synchronous and releases the current thread
        context while waiting
        """

        if self.debug:
            sys.stderr.write("call_remote_method(%d,%s,...)\n" % (id(obj),methodname))
            if methodname.find("getattr") >= 0:
                sys.stderr.write("args=%s\n" % (str(args)))
                pass
            pass
        
        conninfo_writer = self.conninfo.writer
        #from .dgpy import OpaqueWrapper # avoid import loop
        if object.__getattribute__(conninfo_writer,"__class__").__name__=="OpaqueWrapper": #  is OpaqueWrapper:
            # Sometimes self.conninfo is actually a module in which
            # case we theoretically don't have direct access to its
            # contents from the execution threads. In this case it is
            # OK so we bypass
            conninfo_writer=object.__getattribute__(conninfo_writer,"_wrappedobj")
            pass

        conninfo_loop = self.conninfo.loop
        #from .dgpy import OpaqueWrapper # avoid import loop
        if object.__getattribute__(conninfo_loop,"__class__").__name__=="OpaqueWrapper": #  is OpaqueWrapper:
            # Sometimes self.conninfo is actually a module in which
            # case we theoretically don't have direct access to its
            # contents from the execution threads. In this case it is
            # OK so we bypass
            conninfo_loop=object.__getattribute__(conninfo_loop,"_wrappedobj")
            pass


        #if methodname=="__getattribute__" and args[0]=="__class__":
        #    raise ValueError("Debug!")
        
        crtconn_future = None
        if not hasattr(self.tls,"thread_has_remote_subconn") or not self.tls.thread_has_remote_subconn:
            # Need to initiate remote subconn
            if self.debug:
                sys.stderr.write("Thread initiating CRTCONNB\n");
                pass
            
            cmd=b"CRTCONNB" + struct.pack("!Q",id(current_thread())) + struct.pack("!Q",0)
            #self.conninfo.loop.run_coroutine_threadsafe(write_immediate,self.conninfo.writer,cmd)
            crtconn_future = asyncio.run_coroutine_threadsafe(write_immediate(conninfo_writer,cmd),conninfo_loop.real_evloop)
            self.tls.thread_has_remote_subconn=True
            pass

        ret = None
        

        args_maybeproxy = self.get_proxy_if_needed(args)
        kwargs_maybeproxy = self.get_proxy_if_needed(kwargs)

        #from .remoteproxy import active_remote_link
        #sys.stderr.write("Pre-Start: pid %d tid %d: active_remote_link: %d; None=%d\n" % (os.getpid(),threading.get_ident(),id(active_remote_link.remote_link),id(None)))
        #if active_remote_link.remote_link is not None:
        #    raise ValueError("Recursive call (???)")
            

        set_active_remote_link_this_thread(self)
        try:
            cmd_payload = pickle.dumps((obj,methodname,args_maybeproxy,kwargs_maybeproxy))
            pass
        finally:
            set_active_remote_link_this_thread(None)
            pass
        
        #sys.stderr.write("Start: pid %d tid %d: active_remote_link: %d; None=%d\n" % (os.getpid(),threading.get_ident(),id(active_remote_link.remote_link),id(None)))

        wait_queue = queue.Queue()
        self.waiting_threads[id(current_thread())] = wait_queue

        
        cmd_hdr=b"MTHCALLB" + struct.pack("!Q",id(current_thread())) + struct.pack("!Q",len(cmd_payload))
        #self.conninfo.loop.run_coroutine_threadsafe(write_immediate,self.conninfo.writer,cmd_hdr,cmd_payload)
        #if b"__class__" in cmd_payload:
        #    import pdb
        #    pdb.set_trace()
        #    pass

        
        mthcall_future = asyncio.run_coroutine_threadsafe(write_immediate(conninfo_writer,cmd_hdr,cmd_payload),conninfo_loop.real_evloop)
        
        dgpy.PushThreadContext(None) # release module lock
        
        try:
            
            # wait for futures
            if crtconn_future is not None:
                crtconn_future.result()
                pass

            mthcall_future.result()
            
            # Wait for response
            (ret_exc_tbstr) = wait_queue.get()
            
            wait_queue.task_done()
            # Remove queue, as we no longer need it. 
            del self.waiting_threads[id(current_thread())]

            
            #sys.stderr.write("End: pid: %d tid: %d active_remote_link: %d; None=%d\n" % (os.getpid(),threading.get_ident(),id(active_remote_link.remote_link),id(None)))
            (ret,exc,tb_str) = self.deproxy(ret_exc_tbstr)
            
            pass
        finally:
            dgpy.PopThreadContext() # re-acquire module lock
            pass
        
        if exc is not None:
            #sys.stderr.write("Exception in asynchronous connection method call: %s\n\nTraceback follows:\n%s\n\n" % (str(exc),tb_str))

            # Handle some special cases...
            # __getattribute__ raising AttributeError means that the callback should fallback to __getatttr__
            if (methodname=="__getattribute__" or methodname=="__getattr__") and isinstance(exc,AttributeError):
                raise AttributeError("Remote attribute error %s" % (str(exc)))
            elif methodname=="__next__" and isinstance(exc,StopIteration):
                # Interator protocol
                raise StopIteration
            raise AsyncFailureError(str(exc),tb_str)
            
        #set_active_remote_link_this_thread(None)
        return ret
    


    def releaseproxy(self,idval):
        """Notify the other end that it is OK to release the proxy identfied by idval
        """

        conninfo_writer = self.conninfo.writer
        #from .dgpy import OpaqueWrapper # avoid import loop
        if object.__getattribute__(conninfo_writer,"__class__").__name__=="OpaqueWrapper": #  is OpaqueWrapper:
            # Sometimes self.conninfo is actually a module in which
            # case we theoretically don't have direct access to its
            # contents from the execution threads. In this case it is
            # OK so we bypass
            conninfo_writer=object.__getattribute__(conninfo_writer,"_wrappedobj")
            pass

        conninfo_loop = self.conninfo.loop
        #from .dgpy import OpaqueWrapper # avoid import loop
        if object.__getattribute__(conninfo_loop,"__class__").__name__=="OpaqueWrapper": #  is OpaqueWrapper:
            # Sometimes self.conninfo is actually a module in which
            # case we theoretically don't have direct access to its
            # contents from the execution threads. In this case it is
            # OK so we bypass
            conninfo_loop=object.__getattribute__(conninfo_loop,"_wrappedobj")
            pass
        
        # Need to initiate remote subconn
        #sys.stderr.write("Thread initiating CRTCONNB\n");
        cmd=b"RELPRXYB" + struct.pack("!Q",idval) + struct.pack("!Q",0)
        relprxy_future = asyncio.run_coroutine_threadsafe(write_immediate(conninfo_writer,cmd),conninfo_loop.real_evloop)

        ## Wait for it to be sent (this causes deadlocks)
        #relprxy_future.result()
        pass
    




    
    async def ConnIO(self,reader,writer):
        # ***!!!! Need to implement authentication/security ***!!!
        #sys.stderr.write("ConnIO()\n")
        empty=False

        connectiondict={} # Dictionary of (thread, eventloop) tuples corresponding to connections (threads on the remote side)
        
        localdict={} # Store for local variables
        globaldecls=[] # list of AST global decls
        
        while True:
            # Protocol:
            # 8 character command: (Note that T vs B on connection create/drop is irrelevant)
            ## CRTCONNT -- create persistent connection text
            ## DRPCONNT -- drop persistent connection text
            # CRTCONNB -- create persistent connection binary (pickle) 
            # DRPCONNB -- drop persistent connection binary (pickle)
            ## MTHCALLT -- method call text
            # MTHCALLB -- method call binary
            ## MTHREPLT -- method call reply text
            # MTHREPLB -- method call reply binary
            # RELPRXYB -- proxy release (the connection ID here is instead the proxy ID)
            ## RELPRXYT -- proxy release
            # AUTHCALB -- authentication: followed by connection ID, followed by 8 byte integer number of strings, followed by specified number of (string length, string data) groups. .. NOT YET IMPLEMENTED 
            # AUTHRSPB -- authentication response 

            # Protocol details:
            #  * Sender transmits 8 character command ID followed by
            #    8 byte subconnection ID followed by 8 byte payload length
            # as single call to write() method.
            #  * Sender transmits payload as single call to write() method
            #  * Sender awaits on drain() method 
            #  * Receiver recives 24 header bytes from single call to
            #    await readexactly() method
            #  * Receiver parses contents and retrieves payload (if payload
            #    length is > 0) from
            #    single call to await readexactly() method. 
            # For binary protocol version payload is a pickle of a Python
            # object. Simple, fundamental data structures are included
            # in the pickle. Other data structures are represented by
            # proxy objects which can be passed back later
            #
            # The recipient of a proxy object when done should
            # issue a RELPRXY[BT] so the sender knows it the
            # object being proxied can be freed. 
            
            
            #
            # If it is a return value it will be evaluated too.
            try:  # Try/except on IncompleteReadError
                cmd_connid_payloadlen = await reader.readexactly(24)
                cmd = cmd_connid_payloadlen[:8]
                if self.debug:
                    sys.stderr.write("cmd=%s\n" % (cmd.decode("ASCII")))
                    pass
                connection_id = struct.unpack("!Q",cmd_connid_payloadlen[8:16])[0]
                payloadlen = struct.unpack("!Q",cmd_connid_payloadlen[16:24])[0]

                
                text = (cmd[7]==ord('T'))
                binary = (cmd[7]==ord('B'))
                if not (text ^ binary):
                    sys.stderr.write("Protocol error on socket: command %s is not text or binary\n" % (cmd.decode("utf-8")))
                    continue
                if cmd[:7]==b"CRTCONN":
                    # Create connection
                    if connection_id in connectiondict:
                        sys.stderr.write("Protocol error on socket: reused connection ID\n")
                        continue
                
                    threadloop = asyncio.new_event_loop()
                    connectiondict[connection_id]=(Thread(target=self.subconncode,args=(threadloop,),daemon=True),threadloop)
                    connectiondict[connection_id][0].start()
                    pass
                
                elif cmd[:7]==b"DRPCONN":
                    # Drop connection
                    if connection_id not in connectiondict:
                        sys.stderr.write("Protocol error on socket: unknown connection ID\n")
                        continue
                    
                    (thr,threadloop)=connectiondict[connection_id]
                    threadloop.stop()  # sub-thread will trigger joining by triggering joinconn() in this thread
                
                    del connectiondict[connection_id]
                    
                    pass
            
                elif cmd[:7]==b"RELPRXY":
                    # release proxy
                    proxyid = connection_id
                    try:
                        self.proxydb_lock.acquire()

                        if not proxyid in self.proxydb:
                            sys.stderr.write("Protocol error on socket: unknown proxy id %d\n" % (proxyid))
                            continue
                        localproxy = self.proxydb[proxyid]
                        localproxy.deref()
                        if localproxy.remote_refcnt==0:
                            del self.proxydb[proxyid]  # forget about proxy by removing it from dictionary
                            pass
                        pass
                    finally:
                        self.proxydb_lock.release()
                        pass
                    pass
                
                
                
                elif cmd[:7]==b"MTHCALL":
                    # Single command
                    # In general, everything is a method call
                    # So parameters are object, parameter tuple, kwarg dict

                    if connection_id not in connectiondict:
                        sys.stderr.write("Protocol error on socket: unknown connection ID\n")
                        continue
                    (thr,threadloop)=connectiondict[connection_id]


                    assert(binary) # Text not yet implemented
                    if binary:
                        # Binary format: 8 byte integer with length of a pickle
                        # The pickle contains a tuple with (function, argtuple, kwargdict)
                        pickle_bytes = await reader.readexactly(payloadlen)
                        set_active_remote_link_this_thread(self)
                        try:
                            obj_methodname_args_kwargs = pickle.loads(pickle_bytes)
                            #sys.stderr.write("pickle output: %s\n" % (str(obj_methodname_args_kwargs)))

                            pass
                        finally:
                            set_active_remote_link_this_thread(None)
                            pass
                        
                        (obj,methodname,args,kwargs) = self.deproxy(obj_methodname_args_kwargs)
                        #sys.stderr.write("deproxy output: %s\n" % (str((obj,methodname,args,kwargs))))

                        # delegate obj.methodname(*args,**kwargs) to threadloop, passing the value back to this thread (thread.loop) by another call_soon_threadsafe to self.write_method_reply()
                        threadloop.call_soon_threadsafe(self.try_method,connection_id,writer,text,binary,obj,methodname,args,kwargs)
                        #threadloop.call_soon_threadsafe(lambda ob,methname,rgs,kwrgs: self.conninfo.loop.call_soon_threadsafe(self.write_method_reply,connection_id,writer,text,binary,getattr(ob,methname)(*rgs,**kargs)),obj,methodname,args,kwargs)
                        pass
                
                    pass
                elif cmd[:7]==b"MTHREPL":
                    assert(binary) # Text not yet implemented
                    # Method call reply
                    pickle_bytes = await reader.readexactly(payloadlen)

                    set_active_remote_link_this_thread(self)
                    try:
                        ret_exc_tbstr = pickle.loads(pickle_bytes)
                        pass
                    finally:
                        set_active_remote_link_this_thread(None)
                        pass
                    
                    self.waiting_threads[connection_id].put(ret_exc_tbstr)
                    pass
                #elif cmd[:3]=="ACD":
                #    # Asynchronous command (no response given)
                #    pass
                else:
                    sys.stderr.write("Protocol error on socket: unknown command %s\n" % (cmd))
                pass
            except IncompleteReadError:
                break  # terminate infinite loop and close this mainloop, etc. 
            pass
        writer.close()
        pass

    def try_method(self,connection_id,writer,text,binary,ob,methname,rgs,kwrgs):
        
        if self.debug:
            sys.stderr.write("try_method methname=%s\n" % (methname))
            pass

        if self.debug:
            sys.stderr.write("try_method pid %d thread %d str(ob)=%s rgs=%s kwrgs = %s\n" % (os.getpid(),threading.get_ident(),str(ob),str(rgs),str(kwrgs)))
            pass

        exc = None

        # Work around problem with looking up types...,
        # hardwiring lookups to object.__getattribute__
        if methname=="__getattribute__" and isinstance(ob,type):
            #sys.stderr.write("Overriding\n")
            callable = object.__getattribute__
            if len(rgs) < 2:
                rgs=(ob,rgs[0])
                pass
            pass
        else:
            #sys.stderr.write("Not Overriding; ob=%s(%d); methname=%s; rgs=%s\n" % (str(ob),id(ob),methname,str(rgs)))
            try:
                callable = getattr(ob,methname)
                pass
            except AttributeError as ex:
                exc = ex
                tb_str = traceback.format_exc()

                #sys.stderr.write("getattr AttributeError: %s\n" % (tb_str))
                pass
            pass
        
        ret = None
        tb_str = None
        if exc is None:
            try:
                if self.debug:
                    sys.stderr.write("Calling %s with %s and %s\n" % (callable,rgs,kwrgs))
                    #if callable.__name__=="__hash__" and len(rgs)==0:
                    #    raise ValueError("DEBUG!!!")
                    pass
                
                ret = callable(*rgs,**kwrgs)
                #sys.stderr.write("callable=%s\n" % (str(callable)))
                #sys.stderr.write("CurContext =  %s\n" % (str(FormatCurContext())))
                #sys.stderr.write("Returning %s\n" % (str(ret)))
                pass
            except Exception as ex:
                exc = ex
                tb_str = traceback.format_exc()
                #sys.stderr.write("Execution Error: %s\n" % (tb_str))
                pass
            pass
        
        #self.conninfo.loop.run_coroutine_threadsafe(self.write_method_reply,connection_id,writer,text,binary,ret,exc,tb_str)

        #print("real_evloop ",self.conninfo.loop.real_evloop)

        conninfo_loop = self.conninfo.loop
        if object.__getattribute__(conninfo_loop,"__class__").__name__ == "OpaqueWrapper":
            # Sometimes self.conninfo is actually a module in which
            # case we theoretically don't have direct access to its
            # contents from the execution threads. In this case it is
            # OK so we bypass
            conninfo_loop=object.__getattribute__(conninfo_loop,"_wrappedobj")
            pass
        
        method_reply_future = asyncio.run_coroutine_threadsafe(self._write_method_reply(connection_id,writer,text,binary,ret,exc,tb_str),conninfo_loop.real_evloop)
        # Wait for message to get sent out
        method_reply_future.result()

        pass
    
    async def _write_method_reply(self,connection_id,writer,text,binary,ret,exc,tb_str):
        """This method is called via run_coroutine_threadsafe on self.conninfo.loop 
        when the thread-delegated logic in EXP is all done. It gets 
        passed the result of the function call. It then wraps it with 
        a proxy (if appropriate) and returns a RET block"""
        ret_maybeproxy = self.get_proxy_if_needed(ret)
        try:
            exc_maybeproxy = self.get_proxy_if_needed(exc)
            pass
        except pickle.PicklingError:
            exc_maybeproxy=str(exc)
            pass
        assert(binary) # Text mode not implemented yet


        
        set_active_remote_link_this_thread(self)
        try:
            ret_bytes = pickle.dumps((ret_maybeproxy,exc_maybeproxy,tb_str)) # Increments remote_refcnt in any ProxyObjs.    On the remote side when the proxy is dereferenced, the destructor triggers releaseproxy which will in turn send us an RLP message.
            pass
        #except pickle.PicklingError:
        #    sys.stderr.write("ret_maybeproxy=%s\n" % (str(ret_maybeproxy)))
        #    sys.stderr.write("exc_maybeproxy=%s\n" % (str(exc_maybeproxy)))
        #    raise
        finally:
            set_active_remote_link_this_thread(None)
            pass
            
        writer.write(b"MTHREPLB" + struct.pack("!Q",connection_id) + struct.pack("!Q",len(ret_bytes)))
        writer.write(ret_bytes)
        await writer.drain() # flush the output
    
        pass
    

    def subconncode(self,evloop):
        """Thread for a sub-connection within this asynchronous link"""

        ## self.conninfo may be a dgpy.Module in which case our threads
        ## must be compatible with it so that try_method can pass
        ## stuff back to the event loop
        #if hasattr(self.conninfo,"_dgpy_contextname"):
        #    InitCompatibleThread(self.conninfo,"_parentprocwriter_%d" % (id(threading.current_thread())))
        #    pass

        InitThread()
        
        ThreadContext = SimpleContext()
        InitContext(ThreadContext,"AsyncThread_evloopid(%d)" % (id(evloop)))
        PushThreadContext(ThreadContext)
        try:        
            asyncio.set_event_loop(evloop)
            evloop.run_forever()
            pass
        finally:
            PopThreadContext()
            pass
        
        evloop.close()
        self.conninfo.loop.call_soon_threadsafe(self.joinsubconn,current_thread())
        pass

    def joinsubconn(self,thr):
        """In async event loop, when a connection is closed, this cleans 
        up the thread based on a signal that the thread's event loop has 
        closed"""
        thr.join()
        pass
    
        
    
    
    pass
    
