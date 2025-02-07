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
import copy
import ctypes
import numbers
import readline
import atexit

import numpy as np

from .remoteproxy import remoteproxy
from .main_thread import do_systemexit

from .dgpy import SimpleContext,InitThreadContext,InitThread,InitContext
from .dgpy import PushThreadContext,PopThreadContext
from .conn import PyDGConn,OldDGConn,ConnAcceptor
from .conn import process_line,render_response,write_response

nextconnid=0  # global... only accessible from main server thread
nextconnidlock=Lock()




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



def tcp_server(hostname,port,connbuilder=lambda **kwargs: PyDGConn(**kwargs),**kwargs):
    global nextconnid,nextconnidlock
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

        Acceptor=ConnAcceptor(clientsocket=clientsocket,
                              address=address,
                              connid=connid,
                              connbuilder=connbuilder,
                              **kwargs)
        # Acceptor constructor adds us to the global Conns dictionary

        Acceptor.start()

        pass
    pass


def start_tcp_server(hostname,port,**kwargs):
    # Returns tcp server thread
    thread=Thread(target=tcp_server,args=(hostname,port),kwargs=kwargs,daemon=True)
    thread.start()
    return thread


def ipython_input_processor(dgpy_config,contextname,localvars):
    """This is meant to be run from a new thread. """

    # Dictionary of local variables
    localdict={}
    localdict.update(localvars)

    InitThread() # This is a new thread
    InputContext=SimpleContext()
    InitContext(InputContext,contextname) # Allow to run stuff from main thread
    PushThreadContext(InputContext)
    try:
        # We need to disable the atexit function because it will be called in the main thread
        # and the SQLite module used by the history functionality is not thread safe and
        # will throw an exception (though it appears to save anyway)
        from IPython.core.interactiveshell import InteractiveShell
        InteractiveShell._atexit_operations = InteractiveShell.atexit_operations
        InteractiveShell.atexit_operations = lambda *args: None

        # We need to wrap enable_gui with a QtWrapper to dispatch it to the
        # main thread -- it creates a Qt object
        from dataguzzler_python import QtWrapper
        from IPython.terminal.interactiveshell import TerminalInteractiveShell
        TerminalInteractiveShell.enable_gui = lambda *args: QtWrapper.QtWrapper(InteractiveShell.enable_gui)

        # Configure Prompt Options
        from IPython.terminal.prompts import Prompts, Token
        from traitlets.config.loader import Config

        class CustomPrompt(Prompts):

            def in_prompt_tokens(self):
                return [
                    (Token.Prompt, 'dgpy> ')
                    ]

            # Plan to update this later with something that more closely mirrors the readline interpreter
            def out_prompt_tokens(self):
                return [
                    (Token.OutPrompt, '200   '),
                ]

        # Set Prompt and Other Configuration Options
        cfg = Config()
        cfg.TerminalInteractiveShell.prompts_class=CustomPrompt
        cfg.TerminalInteractiveShell.term_title=True
        cfg.TerminalInteractiveShell.term_title_format="Dataguzzler-Python"
        cfg.TerminalInteractiveShell.debugger_history_file = os.path.join(os.path.expanduser('~'),'.dataguzzler_python_debugger_history')

        # We are using InteractiveShellEmbed to embed IPython (one of several different approaches)
        from IPython.terminal.embed import InteractiveShellEmbed
        ipshell = InteractiveShellEmbed.instance(config=cfg)

        # Configure History to Store Outside of Normal IPython History
        from IPython.core.history import HistoryManager
        hm = HistoryManager(shell=ipshell, parent=ipshell, hist_file=os.path.join(os.path.expanduser('~'),'.dataguzzler_python_ipython_history.sqlite'))
        ipshell.history_manager = hm
        ipshell.configurables.append(hm)

        ipshell(local_ns=localdict, module=dgpy_config)

        # Run atexit function manually to save history from this thread
        ipshell._atexit_operations()

        # Exit
        do_systemexit()
        pass
    finally:
        PopThreadContext()
        pass

def readline_input_processor(dgpy_config,contextname,localvars,rlcompleter):
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
                PopThreadContext();
                InStr=input("dgpy> ")
                pass
            except EOFError:
                # main terminal disconnected: exit
                do_systemexit()
                return
                pass
            except KeyboardInterrupt:
                # Return as though they typed an empty string -- seems like the
                # most sensible option here -- helps to clear out line
                InStr=""
                pass
            finally:
                PushThreadContext(InputContext)
                pass

            try:
                # Note: process_line() modifies globaldecls and localdict

                (rc,ret,bt)=process_line(globaldecls,localdict,InStr)
                write_response(sys.stdout.buffer,rc,render_response(rc,ret,bt))
                pass
            except SystemExit:
                do_systemexit()
                return
                pass
            except KeyboardInterrupt:
                sys.stderr.write("Internal error in line processing\n")
                traceback.print_exc()
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


