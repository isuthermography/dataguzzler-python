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
import ctypes
import numbers

import numpy as np

from .remoteproxy import remoteproxy

from .dgpy import InitThreadContext
from .dgpy import PushThreadContext,PopThreadContext
from .conn import PyDGConn,OldDGConn

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


