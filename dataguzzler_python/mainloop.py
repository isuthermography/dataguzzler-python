# !!!*** python3 only!!!***
import sys
import os
import signal
import ast
import socket
import traceback
import threading
import importlib
from threading import Thread,Lock
import asyncio
from asyncio import StreamReader,StreamReaderProtocol
from asyncio.coroutines import coroutine
import copy
import ctypes
import numbers
import readline
import atexit

import numpy as np

from .remoteproxy import remoteproxy

from .dgpy import SimpleContext,InitThreadContext,InitThread,InitContext
from .dgpy import PushThreadContext,PopThreadContext
from .conn import PyDGConn,OldDGConn
from .conn import process_line,render_response,write_response

nextconnid=0  # global... only accessible from main server thread
nextconnidlock=Lock()
Conns={} # Dictionary by connid... includes TCP connections and similar but not sub-connections within asynchronous TCP links




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



def tcp_server(hostname,port,connbuilder=lambda **kwargs: PyDGConn(**kwargs),auth=None):
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
                         connid=connid,
                         auth=auth)
        Conns[connid]=Conn
        
        Conn.start()
        
        pass
    pass


def start_tcp_server(hostname,port,**kwargs):
    # Returns tcp server thread
    thread=Thread(target=tcp_server,args=(hostname,port),kwargs=kwargs,daemon=True)
    thread.start()
    return thread

def do_systemexit():
    #PopThreadContext()
    #sys.stderr.write("Attempting to exit; tid=%d!\n" % (threading.get_ident()))
    # we need interrupt main thread with hangup signal, because otherwise we get a hang. But for some reason the exitfuncs (writing out readline history) don't get called in that case, so we run them manually
    atexit._run_exitfuncs()
    if os.name=="nt":
        os.kill(os.getpid(),signal.CTRL_BREAK_EVENT)
        pass
    else:
        os.kill(os.getpid(),signal.SIGHUP)
        pass
    
    sys.exit(0)
    pass

def console_input_processor(dgpy_config,contextname,localvars,rlcompleter):
    """This is meant to be run from a new thread. """
    globaldecls=[]

    # Dictionary of local variables
    localdict={}
    localdict.update(localvars)

    readline.set_completer(rlcompleter.Completer(dgpy_config.__dict__).complete)
    
    InitThread() # This is a new thread
    InputContext=SimpleContext()
    InitContext(InputContext,contextname) # Allow to run stuff from main thread
    PushThreadContext(InputContext)
    try:
        while(True):
            try:
                InStr=input("dgpy> ")
                pass
            except EOFError:
                # main terminal disconnected: exit
                do_systemexit()
                pass
            
            try:
                # Note: process_line() modifies globaldecls and localdict
                
                (rc,ret,bt)=process_line(globaldecls,localdict,InStr)
                write_response(sys.stdout.buffer,rc,render_response(rc,ret,bt))
                pass
            except SystemExit:
                do_systemexit()
                pass
            except Exception as e:
                sys.stderr.write("Internal error in line processing\n")
                print(e)
                traceback.print_exc()
                pass
            pass
        pass
    finally:
        PopThreadContext()
        pass
    pass


