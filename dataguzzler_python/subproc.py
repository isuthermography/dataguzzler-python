# Subproc.py: Create a subprocess to run additional modules in a separate Python context
import sys
import os
import os.path
import posixpath
import inspect
import time
import importlib
from urllib.request import url2pathname
import asyncio
import threading
from threading import Thread

import multiprocessing
import dataguzzler_python.dgpy as dgpy
from .dgpy import Module as dgpy_Module
from .dgpy import SimpleContext,InitThreadContext,PushThreadContext,PopThreadContext,InitCompatibleThread
from .dgpy import dgpy_nowrap
from .async_conn import PyDGAsyncConn
from .configfile import DGPyConfigFileLoader
from .main_thread import main_thread_run
from .help import monkeypatch_visiblename

def determine_contextdir():
    """Inspect the caller's caller's stack frame to find the 
    "_contextstack" variable set by DGPyConfigFileLoader representing
    the stack of path contexts, and in particular the latest path
    context representing the context for loading relative to the 
    config file currently being processed. Returns None if 
    the variable cannot be found"""
    callerframe=inspect.stack(context=0)[2].frame
    if "_contextstack" in callerframe.f_globals:
        return callerframe.f_globals["_contextstack"][-1]
    return None


class PseudoReaderEventLoop(object):
    """ A fake asyncio event loop, 
    that assumes that if 
    the user awaits on a read, that data WILL come in """ 
    conn_receiver=None # reader 1/2 of the multiprocessing.Pipe()
    reader=None # Reader object that we expose (like a streamreader, but only supports readexactly for now)
    iofunc=None
    writer=None # writer object to pass to iofunc .. (iofunc is not actually allowed to await on the writer!!!... but it can delegate via call_soon_threadsafe) 
    real_evloop = None
    debug = None
    
    def __init__(self,conn_receiver,iofunc,writer,debug):
        self.conn_receiver=conn_receiver
        self.reader = self
        self.iofunc=iofunc
        self.writer = writer
        self.debug = debug
        pass

    async def readexactly(self,nbytes):
        #sys.stderr.write("readexactly(%s)\n" % (str(nbytes)))
        try:
            #sys.stderr.write("pid %d calling recv_bytes\n" % (os.getpid()))
            gotbytes = self.conn_receiver.recv_bytes(maxlength=nbytes)  # NOTE: This actually waits, so the event loop wll stick on this.
            #sys.stderr.write("pid %d got recv_bytes; desired=%d; len=%d\n" % (os.getpid(),nbytes,len(gotbytes)))

            if self.debug and nbytes==24:
                sys.stderr.write("pid %d tid %d readexactly() returned first 8 %s\n" % (os.getpid(),threading.get_ident(),gotbytes[:8].decode("ASCII")))
                pass
            pass
        except EOFError as e:
            # readexactly() is defined as returning IncompleteReadError on EOF
            #sys.stderr.write("pid %d rec_bytes EOFError\n" % (os.getpid()))
            raise asyncio.IncompleteReadError(partial="",expected=nbytes)
        assert(len(gotbytes)==nbytes)
        #yield  gotbytes
        return gotbytes
    
    def run_forever(self):
        self.real_evloop = asyncio.new_event_loop()
        self.real_evloop.run_until_complete(self.iofunc(self.reader,self.writer))

        # if event loop exits, we are done
        self.real_evloop.close()
        
        pass

    def close(self):
        self.real_evloop.call_soon_threadsafe(self.real_evloop.stop)
        pass
    
    pass
    
class PseudoWriterEventLoop(object):
    """ A fake asyncio event loop, for compatibility with async_conn.PyDGAsyncConn.
    This doesn't really do proper event loop stuff, it assumes that 
    writing is triggered by run_soon_threadsafe() and that then once
    the user awaits on a writer that all we need to do is write""" 
    conn_sender=None # writer 1/2 of the multiprocessing.Pipe()
    writer=None # writer object that we expose (like a streamwriter, but only supports write for now)
    pending_writes=None
    real_evloop=None
    debug = None
    
    def __init__(self,conn_sender,debug):
        self.conn_sender=conn_sender
        self.writer=self
        self.pending_writes=[]
        self.real_evloop=asyncio.new_event_loop()
        self.debug=debug
        pass

    def write(self,bts):
        self.pending_writes.append(bts)
        pass

    async def drain(self):
        for bts in self.pending_writes:
            self.conn_sender.send_bytes(bts)
            pass
        self.pending_writes=[]
        pass
    
    
    def run_forever(self):
        if self.debug:
            sys.stderr.write("PseudoWriterEventLoop running\n")
            pass
        self.real_evloop.run_forever()

        if self.debug:
            sys.stderr.write("PseudoWriterEventLoop exiting\n")
            pass
        # if event loop exits, we are done
        self.real_evloop.close()
        pass

    def call_soon_threadsafe(self,callable,*args):
        if self.debug:
            sys.stderr.write("Writer call_soon_threadsafe()\n")
            pass
        
        self.real_evloop.call_soon_threadsafe(callable,*args)
        pass

    #def run_coroutine_threadsafe(self,callable,*args):
    #    sys.stderr.write("Writer run_coroutinethreadsafe()\n")
    #    self.real_evloop.run_coroutine_threadsafe(callable,*args)
    #    pass

    def close(self):

        # Terminate event loop
        self.real_evloop.call_soon_threadsafe(self.real_evloop.stop)
        
    pass



class parentproc(object,metaclass=dgpy_Module):
    """This class gets automatically instantiated in the subprocess to 
represent the parent process""" 
    child_conn_receiver = None # multiprocessing.Pipe from parent processor
    child_conn_sender = None
    readerloop = None  # pseudo-loop 
    loop = None
    writer = None # so PyDGAsyncConn knows how to write
    DGConn = None
    readerthread = None
    writerthread = None
    module_name = None
    debug = None
    
    def __init__(self,module_name,child_conn_receiver,child_conn_sender,debug):
        self.module_name=module_name
        self.child_conn_receiver = child_conn_receiver
        self.child_conn_sender = child_conn_sender
        self.debug=debug
        pass

    def initializeconn(self):
        self.DGConn=PyDGAsyncConn(authenticated=True,debug=self.debug)
        
        self.loop = PseudoWriterEventLoop(self.child_conn_sender,self.debug)  # self.loop used to trigger writes
        self.readerloop = PseudoReaderEventLoop(self.child_conn_receiver,self.DGConn.ConnIO,self.loop,self.debug)  # reader will execute loop inside of ConnIO(); self.loop is writer
        self.writer = self.loop # used by DGConn
        
        self.DGConn.set_conninfo(self) # DGConn uses conninfo.loop.call_soon_threadsafe() to queue up writes to the parent. 
        pass

    def startupconn(self):

        self.writerthread=Thread(target=self._writerthreadcode,daemon=True)
        self.writerthread.start()

        self.readerthread=Thread(target=self._readerthreadcode,daemon=True)
        self.readerthread.start()
        
        pass

    @dgpy_nowrap
    def _readerthreadcode(self):
        ## Initialize a new context for this thread 
        #InitThreadContext(self,"%s_%d_0x%x" % (self.DGConn.ThreadContextPrefix,self.connid,id(self)))
        #PushThreadContext(self)

        InitCompatibleThread(self,"_parentprocreader")
        if self.debug:
            sys.stderr.write("SubProc pid %d readerthread %d\n" % (os.getpid(),threading.get_ident()))
            pass
        self.readerloop.run_forever()

        # If reader loop terminated, then parent exited, and we should too
        sys.exit(0)
        pass

    @dgpy_nowrap
    def _writerthreadcode(self):

        InitCompatibleThread(self,"_parentprocwriter")
        self.loop.run_forever()
        
        pass

    
    def __getattr__(self,attrname):

        return getattr(self.DGConn.proxy_of_remote_root,attrname)
    

    
    pass

def subprocess_code(contextdir,dgpfilename,dgpcontent,child_conn_receiver, child_conn_sender,debug):
    
    if debug:
        sys.stderr.write("Subprocess pid=%d\n" % (os.getpid()))
        pass

    # Simplify help() output by removing all the extraneous stuff
    monkeypatch_visiblename() 

    # dgpy initialization
    ConfigContext=SimpleContext()
    
    InitThreadContext(ConfigContext,"dgpy_config") # Allow to run stuff from main thread
    PushThreadContext(ConfigContext)

    dgpy.dgpy_running=True

    parentmodule = parentproc("parent",child_conn_receiver,child_conn_sender,debug)
    

    spec = importlib.util.spec_from_loader("dgpy_config", #configfile,
                                           loader=DGPyConfigFileLoader("dgpy_config",dgpfilename,dgpcontent,contextdir,parentmodule),
                                           is_package=False)
    
    # load config file
    dgpy_config = importlib.util.module_from_spec(spec)
    sys.modules["dgpy_config"]=dgpy_config

    #object.__getattribute__(parentproc,"startupconn")(parentmodule)
    parentmodule.initializeconn()
    
    # run config file 
    spec.loader.exec_module(dgpy_config)
    # We wait until the config is executed before
    # starting the connection so that all the modules
    # are loaded, thus eliminating race conditions
    # (This does mean that modules can't communicate with "parent"
    # during the initialization phase -- but that's probably a
    # good thing, because the parent process will still be
    # under construction. If back-and-forth is needed, it can
    # be triggered by the parent process after creation of the
    # sub-process. 
    parentmodule.startupconn()

    PopThreadContext()


    #sys.stderr.write("subproc dgpy_config dir(): %s\n" % (dir(dgpy_config)))
    #sys.stderr.write("subproc dgpy_config keys(): %s\n" % (list(dgpy_config.__dict__.keys())))
    #sys.stderr.write("subproc dgpy_config ID: %d\n" % (id(dgpy_config)))
    # Main thread of subprocess has nothing left to do except
    # be available in case somebody wants to run an event loop here
    main_thread_run() 
    
    pass


class subproc(object,metaclass=dgpy_Module):
    """This class is instantiated the parent process, thereby 
    spawning a subprocess. Its instance represents the subprocess 
    in the parent process context and it provides a linkage
    to access and call methods of the subprocess by an RPC mechanism"""
    
    dgpfilename = None
    dgpcontent = None
    contextdir = None
    process = None  # The subprocess (multiprocessing.Process object)
    readerthread = None # Our reader subthread that communicates with the process
    writerthread = None # Our writer subthread that communicates with the process
    readerloop = None
    loop = None # Writer loop ; just called loop so it can be referenced via call_soon_threadsafe
    writer = None # so PyDGAsyncConn knows how to write
    parent_conn_receiver = None
    parent_conn_sender = None

    DGConn = None
    module_name = None
    debug = False
    
    def __init__(self,module_name,dgpfilename,dgpcontent,contextdir,debug):
        """Use from_XXXX classmethods to construct"""
        self.module_name=module_name

        if debug:
            sys.stderr.write("Mainprocess pid=%d\n" % (os.getpid()))
            pass
        self.dgpfilename = dgpfilename
        self.dgpcontent = dgpcontent
        self.contextdir = contextdir
        self.debug = debug

        (self.parent_conn_receiver, child_conn_sender) = multiprocessing.Pipe(False)
        (child_conn_receiver, self.parent_conn_sender) = multiprocessing.Pipe(False)
        
        self.process = multiprocessing.Process(target=subprocess_code,
                                               args=(contextdir,dgpfilename,dgpcontent,child_conn_receiver,child_conn_sender,debug),
                                               daemon=True)
        self.process.start()


        self.DGConn=PyDGAsyncConn(authenticated=True,debug=debug)

        self.loop = PseudoWriterEventLoop(self.parent_conn_sender,debug) # self.loop used to trigger writes
        self.readerloop = PseudoReaderEventLoop(self.parent_conn_receiver,self.DGConn.ConnIO,self.loop,debug)
        self.writer = self.loop # so PyDGAsyncConn knows how to write

        
        self.DGConn.set_conninfo(self)


        self.readerthread=Thread(target=self._readerthreadcode,daemon=True)
        self.readerthread.start()
        
        self.writerthread=Thread(target=self._writerthreadcode,daemon=True)
        self.writerthread.start()

        pass

    @dgpy_nowrap
    def _readerthreadcode(self):
        ## Initialize a new context for this thread 
        #InitThreadContext(self,"%s_%d_0x%x" % (self.DGConn.ThreadContextPrefix,self.connid,id(self)))
        #PushThreadContext(self)

        InitCompatibleThread(self,"_subprocreader")
        self.readerloop.run_forever()
        
        sys.stderr.write("dataguzzler-python %s: Warning: Subprocess exited\n" % (self.module_name))
        self.process.join()

        # Note: we don't currently have a way to trigger our own join() method
        # in some external thread and thus cleanup our threads. Not that this really matters...
        
        pass

    @dgpy_nowrap
    def _writerthreadcode(self):
        InitCompatibleThread(self,"_subprocwriter")
        self.loop.run_forever()
        
        pass

    def __getattr__(self,attrname):
        return getattr(self.DGConn.proxy_of_remote_root,attrname)
    
    def join(self):
        # Note: Should have triggered process somehow to exit
        self.process.join()
        # thread should exit once process closes file descriptors
        self.readerthread.join()
        self.writerthread.join()
        pass
    
    @classmethod
    def from_dgpfile(cls,module_name,dgpfile,contextdir=None,debug=False):
        """
        Create a subprocess with configuration loaded from a file
        dgpfile is a relative or absolute URL of the file to load. 

        Load the specified .dgp file and run it in a subprocess. 
        contextdir is the path to which dgpfile might be relative. 
        If not specified it will be determined from inspecting the 
        stack for the _contextstack generated by the DGPyConfigFileLoader.
        The actual context for the running process will be the location
        of dgpfile."""
        
        if posixpath.isabs(dgpfile):
            dgppath = url2pathname(dgpfile)
        else:
            if contextdir is None:
                contextdir=determine_contextdir()
                pass
            if contextdir is None:
                raise ValueError("Could not figure out context directory")
            dgppath = os.path.join(contextdir,url2pathname(dgpfile))
            pass

        dgpcontent = open(dgppath).read()
        
        return cls(module_name,dgppath,dgpcontent,os.path.split(dgppath)[0],debug)

    @classmethod
    def from_immediate(cls,module_name,dgpcontent,contextdir=None,debug=False):
        """
        Create a subprocess with configuration loaded from a given
        string (usually a multi-line raw string) given as dgpcontent.

        contextdir is the path for relative includes within the 
        dgpcontent. 

        If not specified contextdir will be determined from inspecting the 
        stack for the _contextstack generated by the DGPyConfigFileLoader.
        The actual context for the running process will be the location
        of dgpfile."""

        if contextdir is None:
            contextdir=determine_contextdir()
            pass
        if contextdir is None:
            raise ValueError("Could not figure out context directory")
        
        return cls(module_name,"None",dgpcontent,contextdir,debug)

    
