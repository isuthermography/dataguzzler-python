# !!!*** python3 only!!!***
import sys
import ast
import socket
import traceback
import importlib
from threading import Thread,Lock
import asyncio
from asyncio import StreamReader,StreamReaderProtocol
from asyncio.coroutines import coroutine
import copy

from .pydg import InitThreadContext
from .pydg import PushThreadContext,PopThreadContext

import ctypes

# First import of dgold requires dlopenflags with RTLD_GLOBAL
# or it won't export its symbols to libraries/modules
oldflags=sys.getdlopenflags()
sys.setdlopenflags(oldflags | ctypes.RTLD_GLOBAL)
from .dgold import rpc_async,rpc_authenticated
sys.setdlopenflags(oldflags)

nextconnid=0  # global... only accessible from main server thread
nextconnidlock=Lock()
Conns={} # Dictionary by connid




# Also create an asyncio thread and mainloop per module.
# Module has a wrapper that delegates calls to the asyncio thread
# e.g. with call_soon_threadsafe() and a pair of asyncio.Future()s:
#   One in the module-specific thread, one in the calling thread,
#   the first grabs the result, the second passes it back  
# Then methods can largely consider a single-threaded environment
# but external calls to other modules may bounce back
# through this method, eliminating the risk of deadlocks.
#  (at the price of interruptability at method calls)
#  So behavior is basically similar to traditional dataguzzler
#  except that modules can run concurrently. 

# maybe use python numericalunits package (?) or
# perhaps limatix units package. 

# Maybe rebuild wfmstore around vtkdataset or similar? What about metadata? VTK doesn't really support more than 3 indices well... But could probably be made to work with shared memory. 



def start_response(writer,returncode,length):
    returncode=int(returncode)
    
    assert(returncode >= 0 and returncode <= 999)
    writer.write(("%3.3d %12.12d " % (returncode,length+2)).encode('utf-8')) # length+2 accounts for trailing
    pass
    
def write_response(writer,returncode,retbytes):
    start_response(writer,returncode,len(retbytes))
    writer.write(retbytes)
    writer.write(b"\r\n")
    pass


def process_line(globaldecls,localdict,linestr):
    empty= (linestr=="")
    returncode=200
    
    import pydg_config
    
    try:
        lineast=ast.parse(linestr)

        if len(lineast.body) < 1:
            return (200,None,None)
        
        if len(lineast.body)==1 and lineast.body[0].__class__.__name__=="Global":
            # Defining a variable as global
            globaldecls.append(lineast.body[0])
            pass
        
        # Insert globaldecls at start of lineast.body
        # (this slicing trick is like the insert-at-start
        # equivalent of list.extend)
        lineast.body[0:0]=globaldecls
        
        # extract last element of tree
        result_ast=lineast.body[-1]
        if result_ast.__class__.__name__=="Expr":
            # If we end with an expression, assign the expression
            # replace last element with assignment of __pydg_resulttemp
            lineast.body[-1] = ast.Assign(targets=[ast.Name(id="__pydg_resulttemp",ctx=ast.Store(),lineno=result_ast.lineno,col_offset=0)],value=result_ast.value,lineno=result_ast.lineno,col_offset=0)
            
            pass
        elif result_ast.__class__.__name__=="Assign":
            # If we end with an assignment, add additional assignment
            # to assign value of evaluated assignment to __pydg_resulttemp
            targetval=copy.deepcopy(result_ast.targets[0])
            targetval.ctx=ast.Load() 
            lineast.body.append(ast.Assign(targets=[ast.Name(id="__pydg_resulttemp",ctx=ast.Store(),lineno=result_ast.lineno,col_offset=0)],value=targetval,lineno=result_ast.lineno,col_offset=0))
            pass
        
        localdict["__pydg_resulttemp"]=None

        # !!! Should wrap pydgc_config.__dict__ to do context conversions (pydg.censor) !!!
        #sys.stderr.write("Exec!\n")
        #sys.stderr.flush()
        exec(compile(lineast,"<interactive>","exec"),pydg_config.__dict__,localdict)
        #sys.stderr.write("Exec finished!\n")
        #sys.stderr.flush()

        ret=localdict["__pydg_resulttemp"]
        del localdict["__pydg_resulttemp"]

        localdict["__pydg_result"]=ret # Leave copy for end-user
        bt=None

        pass
    except Exception as e:
        ret=e
        returncode=500
        localdict["__pydg_last_exc_info"]=sys.exc_info()
        # Leave copy for end-user
        bt=traceback.format_exc()
        pass
    return (returncode,ret,bt)

class PyDGConn(object):
    clientsocket=None
    address=None
    connid=None
    loop=None
    thread=None
    _pydg_contextlock=None

    def __init__(self,**kwargs):
        for arg in kwargs:
            if not hasattr(self,arg):
                raise ValueError("Unknown attribute: %s" % (arg))
            setattr(self,arg,kwargs[arg])
            pass
        pass

    def start(self):
        self.thread=Thread(target=self.threadcode,daemon=True)
        self.thread.start()
        pass
    
    @asyncio.coroutine
    def ConnIO(self,reader,writer):
        #sys.stderr.write("ConnIO()\n")
        empty=False

        localdict={} # Store for local variables
        globaldecls=[] # list of AST global decls
        
        while not empty:
            line = yield from reader.readline()

            (returncode,ret,bt)=process_line(globaldecls,localdict,line.decode('utf-8'))
            if bt is None:
                write_response(writer,returncode,repr(ret).encode('utf-8'))
                pass
            else:
                write_response(writer,returncode,repr((ret,bt)).encode('utf-8'))
                pass

            pass
        writer.close()
        self.loop.stop()
        pass

    
    def threadcode(self):
        InitThreadContext(self,"PyDGConn_0x%x" % (id(self)))
        PushThreadContext(self)
        
        self.loop=asyncio.new_event_loop()
        self.loop.set_debug(True)
        

        def ProtocolFactory():
            #sys.stderr.write("ProtocolFactory()\n")
            reader=StreamReader(limit=asyncio.streams._DEFAULT_LIMIT,loop=self.loop)
            protocol=StreamReaderProtocol(reader,self.ConnIO,loop=self.loop)
            return protocol
        # WARNING: _accept_connection2 is Python asyncio internal and non-documented
        extra={"peername": self.address}
        #sys.stderr.write("accept_connection2()\n")
        accept=self.loop._accept_connection2(ProtocolFactory,self.clientsocket,extra,sslcontext=None,server=None)

        #sys.stderr.write("create_task()\n")
        self.loop.create_task(accept)
        
        #sys.stderr.write("run_forever()\n")
        #import pdb
        #pdb.set_trace()
        self.loop.run_forever()
        #sys.stderr.write("close()\n")
        self.loop.close()
        pass
    
    pass
    

class OldDGConn(object):
    clientsocket=None
    address=None
    connid=None
    loop=None
    thread=None
    _pydg_contextlock=None
    _pydg_contextname=None

    def __init__(self,**kwargs):
        for arg in kwargs:
            if not hasattr(self,arg):
                raise ValueError("Unknown attribute: %s" % (arg))
            setattr(self,arg,kwargs[arg])
            pass
        pass

    def start(self):
        self.thread=Thread(target=self.threadcode,daemon=True)
        self.thread.start()
        pass
    
    @asyncio.coroutine
    def ConnIO(self,reader,writer):
        #sys.stderr.write("ConnIO()\n")
        empty=False

        localdict={} # Store for local variables
        globaldecls=[] # list of AST global decls
        
        while not empty:
            line = yield from reader.readline()
            empty= (line==b"")
            returncode=200

            if not rpc_authenticated(self):
                # Limit access to single command to AUTH module
                line=b"AUTH:"+line.split(b';')[0].strip()
                pass
            try:
                (retval,retbytes)=rpc_async(self,line.strip())
                pass
            except Exception as e:
                retbytes=str(e).encode('utf-8')
                returncode=500
                pass

            write_response(writer,returncode,retbytes)
            pass
        writer.close()
        self.loop.stop()
        pass


    
    def threadcode(self):
        InitThreadContext(self,"OldDGConn_0x%x" % (id(self)))
        PushThreadContext(self)
        
        self.loop=asyncio.new_event_loop()
        # self.loop.set_debug(True)
        

        def ProtocolFactory():
            #sys.stderr.write("ProtocolFactory()\n")
            #asyncio.streams._DEFAULT_LIMIT
            # WARNING: Hardwired limit here prevents loading
            # huge waveforms with dg_upload() or similar!
            reader=StreamReader(limit=10e6,loop=self.loop)
            protocol=StreamReaderProtocol(reader,self.ConnIO,loop=self.loop)
            return protocol
        # WARNING: _accept_connection2 is Python asyncio internal and non-documented
        extra={"peername": self.address}
        #sys.stderr.write("accept_connection2()\n")
        accept=self.loop._accept_connection2(ProtocolFactory,self.clientsocket,extra,sslcontext=None,server=None)

        #sys.stderr.write("create_task()\n")
        self.loop.create_task(accept)
        
        #sys.stderr.write("run_forever()\n")
        #import pdb
        #pdb.set_trace()
        self.loop.run_forever()
        #sys.stderr.write("close()\n")
        self.loop.close()
        pass
    
    pass



def tcp_server(hostname,port,connbuilder=lambda **kwargs: PyDGConn(**kwargs)):
    global nextconnid,nextconnidlock,Conns
    serversocket=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    serversocket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)

    serversocket.bind((hostname,port))
    serversocket.listen(5)

    while True:
        (clientsocket,address)=serversocket.accept()
        clientsocket.setblocking(False)

        nextconnidlock.acquire()
        connid=nextconnid
        nextconnid+=1
        nextconnidlock.release()
        
        
        Conn=connbuilder(clientsocket=clientsocket,
                         address=address,
                         connid=connid)
        Conns[connid]=Conn
        
        Conn.start()
        
        pass
    pass


def start_tcp_server(hostname,port,**kwargs):
    # Returns tcp server thread
    thread=Thread(target=tcp_server,args=(hostname,port),kwargs=kwargs,daemon=True)
    thread.start()
    return thread


