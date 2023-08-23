# !!!*** python3 only!!!***
import sys
import ast
import socket
import traceback
import importlib
from threading import Thread,Lock
import asyncio
from asyncio import StreamReader,StreamReaderProtocol
import copy
import ctypes
import numbers

import numpy as np

from .remoteproxy import remoteproxy

from .dgpy import InitThreadContext
from .dgpy import PushThreadContext,PopThreadContext


Conns={} # Dictionary by connid... includes TCP connections and similar but not sub-connections within asynchronous TCP links

def start_response(writer,returncode,length):
    returncode=int(returncode)
    
    assert(returncode >= 0 and returncode <= 999)
    writer.write(("%3.3d %12.12d " % (returncode,length+2)).encode('utf-8')) # length+2 accounts for trailing
    pass

class StringWithTripleQuoteRepr(str):

    def __repr__(self):
        return "\"\"\""+str(self)+"\"\"\""
    pass
def render_response(rc,ret,bt):
    if bt is None:
        if isinstance(ret,str) and not "\"\"\"" in ret:
            return ("r\"\"\""+ret+"\"\"\"").encode('utf-8')
        return repr(ret).encode('utf-8')
    else:
        #return repr((ret,StringWithTripleQuoteRepr(bt))).encode('utf-8')
        return ("%s(%s)" % (ret.__class__.__name__,repr(StringWithTripleQuoteRepr(bt)))).encode('utf-8')
    pass

def write_response(writer,returncode,retbytes):
    start_response(writer,returncode,len(retbytes))
    writer.write(retbytes)
    writer.write(b"\r\n")
    pass

def process_line_unauthenticated(globaldecls,localdict,linestr,authmod):
    ret="UNKNOWN ERROR"
    bt=None
    
    linestr=linestr.strip()
    
    empty= (linestr=="")
    
    returncode=500 # default rc is 500 because rc of 200 indicates authentication success
    if empty:
        return (returncode,ret,bt)

    
    open_paren_idx=linestr.find("(")
    if open_paren_idx < 0:
        returncode=502
        ret="AUTH PARSE ERROR"
        return (returncode,ret,bt)

    authfcn=linestr[:open_paren_idx].strip()
    if authfcn != "auth":
        returncode=503
        ret="AUTH INVALID FUNCTION"
        return (returncode,ret,bt)
    if linestr[-1] != ")": # should end with close parentheses
        returncode=504
        ret="AUTH PARSE ERROR"
        return (returncode,ret,bt)

    paramstr=linestr[(open_paren_idx+1):-1]
    params=paramstr.split(",")

    try:
        param_literals = [ ast.literal_eval(param.strip()) for param in params ]
        pass
    except ValueError:
        returncode=505
        ret="AUTH INVALID PARAMETER"
        return (returncode,ret,bt)
    except SyntaxError:
        returncode=505
        ret="AUTH INVALID PARAMETER"
        return (returncode,ret,bt)
        
    param_literals_are_strings = [ type(pl) is str for pl in param_literals ]
    if not all(param_literals_are_strings):
        returncode=506
        ret="AUTH INVALID PARAMETER TYPE"
        return (returncode,ret,bt)

    # Everything is sanitized; pass to auth.auth() method
    try:
        (returncode,ret) = authmod.auth(*param_literals)
        pass
    except Exception as e:
        ret=e
        returncode=500
        localdict["__dgpy_last_exc_info"]=sys.exc_info()
        # Leave copy for end-user
        bt=traceback.format_exc()
        pass
    
    return (returncode,ret,bt)

def process_line(globaldecls,localdict,linestr):
    empty= (linestr=="")
    returncode=200
    
    import dgpy_config
    
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
            # replace last element with assignment of __dgpy_resulttemp
            lineast.body[-1] = ast.Assign(targets=[ast.Name(id="__dgpy_resulttemp",ctx=ast.Store(),lineno=result_ast.lineno,col_offset=0)],value=result_ast.value,lineno=result_ast.lineno,col_offset=0)
            
            pass
        elif result_ast.__class__.__name__=="Assign":
            # If we end with an assignment, add additional assignment
            # to assign value of evaluated assignment to __dgpy_resulttemp

            # But this is not really compatible with tuple assignment
            # so we don't do it in that case

            if result_ast.targets[0].__class__.__name__ != 'Tuple':
                targetval=copy.deepcopy(result_ast.targets[0])
                targetval.ctx=ast.Load() 
                lineast.body.append(ast.Assign(targets=[ast.Name(id="__dgpy_resulttemp",ctx=ast.Store(),lineno=result_ast.lineno,col_offset=0)],value=targetval,lineno=result_ast.lineno,col_offset=0))
                pass
            
            pass
        
        localdict["__dgpy_resulttemp"]=None

        # !!! Should wrap dgpyc_config.__dict__ to do context conversions (dgpy.censor) !!!
        #sys.stderr.write("Exec!\n")
        #sys.stderr.flush()
        exec(compile(lineast,"<interactive>","exec"),dgpy_config.__dict__,localdict)
        
        #sys.stderr.write("Exec finished!\n")
        #sys.stderr.flush()

        ret=localdict["__dgpy_resulttemp"]
        del localdict["__dgpy_resulttemp"]

        localdict["__dgpy_result"]=ret # Leave copy for end-user
        bt=None

        pass
    except Exception as e:
        ret=e
        returncode=500
        localdict["__dgpy_last_exc_info"]=sys.exc_info()
        # Leave copy for end-user
        bt=traceback.format_exc()
        pass
    return (returncode,ret,bt)


class DGConn(object):
    """Abstract base class for connection handlers that manage stream links of one form or another"""
    ThreadContextPrefix = None  # ThreadContextPrefix should be a string that will be used as a prefix in the thread context.
    conninfo = None  # conninfo usually points toward the acceptor with information such as the remote address, etc. Also contains a .loop attribute with our asyncio event loop (or similar)
    
    def set_conninfo(self,conninfo):
        """ Set the .conninfo attribute """
        raise NotImplementedError()

    async def ConnIO(self,reader,writer):
        """Loop over the reader, accepting input. Also writing as needed"""
        raise NotImplementedError()


class PyDGConn(DGConn):
    """ Text-based dataguzzler connection """
    ThreadContextPrefix = "PyDGConn" # constant 
    auth=None
    authenticated=None
    conninfo = None  # Usually the acceptor object, assigned shortly after we are created

    def __init__(self,**kwargs):
        self.authenticated=False
        for arg in kwargs:
            if not hasattr(self,arg):
                raise ValueError("Unknown attribute: %s" % (arg))
            setattr(self,arg,kwargs[arg])
            pass

        if not self.authenticated and self.auth is None:
            raise ValueError("PyDGConn: Some authentication method is required")

        pass

    def set_conninfo(self,conninfo):
        self.conninfo=conninfo
        pass
    
    
    async def ConnIO(self,reader,writer):
        #sys.stderr.write("ConnIO()\n")
        empty=False

        localdict={} # Store for local variables
        globaldecls=[] # list of AST global decls
        
        while not empty:
            line = await reader.readline()
            if len(line)==0:
                empty=True
                continue

            if self.authenticated: 
                (returncode,ret,bt)=process_line(globaldecls,localdict,line.decode('utf-8'))
                pass
            else:
                (returncode,ret,bt)=process_line_unauthenticated(globaldecls,localdict,line.decode('utf-8'),self.auth)
                if returncode==200: # authentication success
                    self.authenticated=True
                    pass
                pass
            
            
            write_response(writer,returncode,render_response(returncode,ret,bt))
            await writer.drain()
            
            pass
        writer.close()
        pass

    
    
    pass


class OldDGConn(DGConn):
    ThreadContextPrefix = "PyDGConn" # constant 
    conninfo=None # Usually the acceptor object, assigned shortly after we are created
    auth=None # Not used by us, because auth is delegated to old-dg 

    def __init__(self,**kwargs):
        for arg in kwargs:
            if not hasattr(self,arg):
                raise ValueError("Unknown attribute: %s" % (arg))
            setattr(self,arg,kwargs[arg])
            pass
        pass
    
    def set_conninfo(self,conninfo):
        self.conninfo=conninfo
        pass

    
    async def ConnIO(self,reader,writer):
        #sys.stderr.write("ConnIO()\n")
        empty=False
        
        from .dgold import rpc_async,rpc_authenticated

        
        localdict={} # Store for local variables
        globaldecls=[] # list of AST global decls
        
        while not empty:
            line = await reader.readline()
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
            await writer.drain()
            pass
        writer.close()
        pass
    
    pass



class ConnAcceptor(object):
    # Manages 2nd half of accepting connections: Starting up new thread for handling the connection and creating the new connection object
    clientsocket = None
    address = None
    connid = None
    connobj = None
    loop = None  # asyncio eventloop (or similar) object; must have a call_soon_threadsafe() method

    # Contextlock and contextname are needed because this object is passed to InitThreadContext() and PushThreadContext()
    _dgpy_contextlock=None
    _dgpy_contextname=None

    def __init__(self,clientsocket,address,connid,connbuilder,**kwargs):
        self.clientsocket=clientsocket
        self.address=address
        self.connid=connid

        self.connobj = connbuilder(**kwargs)
        global Conns
        Conns[connid]=self.connobj
        self.connobj.set_conninfo(self)
        pass

    def start(self):
        # !!! Would be nice to start a parallel monitoring thread to see if this conn has died
        # and trigger waits to terminate and/or locked resources to be released.
        # But the socket API doesn't give a way to check for a dropped connection except
        # reading it, which would have to wait for an executing waits to finish on their own.
        # Better alternative: perform background readahead until we run out of data in a parallel thread, rather than synchronous read->process->read->process. That way if the reader thread detects a dropped connection we can set an exit flag. 
        
        self.thread=Thread(target=self.threadcode,daemon=True)
        self.thread.start()
        pass

    async def ConnIO(self,reader,writer):
        """Delegate to self.connobj; terminate loop when done"""
        await self.connobj.ConnIO(reader,writer)
        self.loop.stop()
        pass
    
    def threadcode(self):
        # Initialize a new context for this thread 
        InitThreadContext(self,"%s_%d_0x%x" % (self.connobj.ThreadContextPrefix,self.connid,id(self)))
        PushThreadContext(self)
        
        self.loop=asyncio.new_event_loop()
        self.loop.set_debug(True)
        

        
        
        def ProtocolFactory():
            #sys.stderr.write("ProtocolFactory()\n")
            reader=StreamReader(limit=asyncio.streams._DEFAULT_LIMIT,loop=self.loop)
            protocol=StreamReaderProtocol(reader,self.connobj.ConnIO,loop=self.loop)
            return protocol
        # WARNING: _accept_connection2 is Python asyncio internal and non-documented
        # We use this to separate out the initial connection acceptance from the delegation to a protocol (latter is in this sub-thread)
        extra={"peername": self.address}
        #sys.stderr.write("accept_connection2()\n")
        accept=self.loop._accept_connection2(ProtocolFactory,self.clientsocket,extra,sslcontext=None,server=None)

        #sys.stderr.write("create_task()\n")
        self.loop.create_task(accept)
        
        #sys.stderr.write("run_forever()\n")
        #import pdb
        #pdb.set_trace()

        
        #PopThreadContext()   # Ideally we'd drop the thread context while waiting so other stuff created in this context can run. But how is this compatible with Python asyncio????
        self.loop.run_forever()
        #sys.stderr.write("close()\n")
        self.loop.close()
        self.connobj.set_conninfo(None)  # Remove the reference cycle so we can be more easily garbage collected. 

        del Conns[self.connid] # remove global reference to this object so that it can be expired/garbage collected/etc. 
        pass
    pass
