import sys
import os
import os.path
from types import ModuleType
import importlib
import posixpath
import multiprocessing
from urllib.request import url2pathname
import threading
from threading import Thread
import traceback
import atexit
import ast
import inspect

# Enable readline editing/history/completion, as in 'python -i' interactive mode
import readline
import rlcompleter

from ..mainloop import start_tcp_server,console_input_processor
from ..mainloop import PyDGConn,OldDGConn
from ..conn import process_line
from ..conn import write_response,render_response

from ..dgpy import SimpleContext
from ..dgpy import InitThreadContext
from ..dgpy import PushThreadContext,PopThreadContext
from ..configfile import DGPyConfigFileLoader
from ..main_thread import main_thread_run

import dataguzzler_python.dgpy as dgpy

dgpy_config=None


def main(args=None):
    if args is None:
        args=sys.argv
        pass
    
    global dgpy_config  #  reminder
    if sys.version_info < (3,6,0):
        raise ValueError("Insufficient Python version: Requires Python 3.6 or above")

    if len(args) < 2:
        print("Usage: %s <config_file.dgp> [arg1:str=value1] [arg2:int=42] [arg3:float=3.1416]" % (args[0]))
        sys.exit(0)
        pass

    multiprocessing.set_start_method('spawn') # This is here because it's a good idea. Otherwise subprocesses have the potential to be dodgy because of fork() artifacts and because we have the original dgpy_config module and the subprocess dgpy_config which replaces it after-the-fact in the Python module list. Also anything with hardware linkages could be super dogdy after a fork
    
    # register readline history file and completer
    readline_doc = getattr(readline, '__doc__', '')
    if readline_doc is not None and 'libedit' in readline_doc:
        readline.parse_and_bind('bind ^I rl_complete')
    else:
        readline.parse_and_bind('tab: complete')
        pass

    try: 
        readline.read_init_file()
        pass
    except OSError:
        # probably no .inputrc file present
        pass

    if readline.get_current_history_length()==0:
        history = os.path.join(os.path.expanduser('~'),'.dataguzzler_python_history')
        try:
            readline.read_history_file(history)
            pass
        except OSError:
            pass

        # Schedule to write out a history file on exit
        atexit.register(readline.write_history_file,history)
        pass


    localvars={}
    
    ConfigContext=SimpleContext()
    
    InitThreadContext(ConfigContext,"dgpy_config") # Allow to run stuff from main thread
    PushThreadContext(ConfigContext)
    try: 
        configfile=args[1]
        
        kwargs={}
        for arg in args[2:]:
            # handle named keyword parameters
            (param_typestr,valuestr) = arg.split("=",1)
            (param,typestr) = param_typestr.split(":")
            
            if typestr=="float":
                kwargs[param]=float(valuestr)
                pass
            elif typestr=="int":
                kwargs[param]=int(valuestr)
                pass
            elif typestr=="str":
                kwargs[param]=valuestr
                pass
            else:
                raise ValueError("Unknown type string: \"%s\"" % (typestr))
            pass
        
        ##### (global variables will be in dgpy_config.__dict__) 
        dgpy.dgpy_running=True
        
        # define config file... Use custom loader so we can insert "include" function into default dictionary
        sourcefh = open(configfile)
        sourcetext = sourcefh.read()
        sourcefh.close()
        
        spec = importlib.util.spec_from_loader("dgpy_config", #configfile,
                                               loader=DGPyConfigFileLoader("dgpy_config",configfile,sourcetext,os.path.split(configfile)[0],None,kwargs))
        
        # load config file
        dgpy_config = importlib.util.module_from_spec(spec)
        sys.modules["dgpy_config"]=dgpy_config
        
        # run config file 
        spec.loader.exec_module(dgpy_config)
        pass
    except:
        sys.stderr.write("Exception running config file. Dropping into debugger...\n")

        localvars["__dgpy_last_exc_info"]=sys.exc_info()

        traceback.print_exc()

        sys.stderr.write("\nRun dgpy.pm() to debug\n")

        #import pdb
        #pdb.post_mortem()
        pass
    
    finally:
        
        PopThreadContext()
        pass

    # TCP servers must now eb started from the config file
    #tcp_thread=start_tcp_server("localhost",1651)
    #old_dg_thread=start_tcp_server("localhost",1649,connbuilder=lambda **kwargs: OldDGConn(**kwargs))

    
    #MainContext=SimpleContext()
    #InitThreadContext(MainContext,"__main__") # Allow to run stuff from main thread
    #PushThreadContext(MainContext)
    console_input_thread=Thread(target=console_input_processor,args=(dgpy_config,"console_input",localvars,rlcompleter),daemon=False)
    console_input_thread.start()

    main_thread_run() # Let main_thread module take over the main thread
    
    pass

