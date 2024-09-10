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
import signal

# Enable readline editing/history/completion, as in 'python -i' interactive mode
import readline
import rlcompleter

from ..mainloop import start_tcp_server,readline_input_processor,ipython_input_processor
from ..mainloop import PyDGConn,OldDGConn
from ..conn import process_line
from ..conn import write_response,render_response

from ..context import SimpleContext,InitContext
from ..context import InitThread,InitThreadContext
from ..context import PushThreadContext,PopThreadContext
from ..configfile import DGPyConfigFileLoader
from ..main_thread import main_thread_run,initialization_main_thread_context, initialization_sub_thread_context
from ..help import monkeypatch_visiblename

import dataguzzler_python.dgpy as dgpy


dgpy_config=None


def main(args=None):

    # Because dataguzzler-python is aggressively threaded
    # make sure a single thread won't tend to occupy the
    # GIL for excessive periods. We upper bound the
    # switch interval at 1 ms, compared to the 2022 default
    # of 5 ms.

    if sys.getswitchinterval() > 1e-3:
        sys.setswitchinterval(1e-3)
        pass

    if args is None:
        args=sys.argv
        pass

    global dgpy_config  #  reminder
    if sys.version_info < (3,6,0):
        raise ValueError("Insufficient Python version: Requires Python 3.6 or above")

    if len(args) < 2:
        print("Usage: %s [--profile] [--ipython] <config_file.dgp> [--arg1 string] [--arg2 343] [--arg3 3.1416] [args...]" % (args[0]))
        sys.exit(0)
        pass

    # Simplify help() output by removing all the extraneous stuff
    monkeypatch_visiblename()

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


    profiling=False
    ipython=False

    localvars={}

    #  Separate config context eliminated because
    # for QT things created during config would be incompatible with main loop
    # ... It was a bit superfluous anyway
    #ConfigContext=SimpleContext()

    #InitThreadContext(ConfigContext,"dgpy_config") # Allow to run stuff from main thread
    #PushThreadContext(ConfigContext)
    InitThread() # Allow stuff to run from main thread
    PushThreadContext(initialization_main_thread_context)

    argc=1

    while True:
        if args[argc] in ["--profile","--ipython"]:
            if args[argc] == '--profile':
                profiling = True
            elif args[argc] == '--ipython':
                ipython = True
            argc += 1
            pass
        else:
            break


    spec_loader = None
    got_exception = False
    try:
        configfile=args[argc]
        argc += 1

        remainingargs = args[argc:]


        # define config file... Use custom loader so we can insert "include" function into default dictionary
        sourcetext=""
        try:
            sourcefh = open(configfile)
            sourcetext = sourcefh.read()
            sourcefh.close()
            pass
        except FileNotFoundError:
            localvars["__dgpy_last_exc_info"]=sys.exc_info()
            traceback.print_exc()

            sys.stderr.write("\nRun dgpy.pm() to debug\n")
            pass



        loader = DGPyConfigFileLoader("dgpy_config",configfile,sourcetext,os.path.split(configfile)[0],None)
        plausible_params = loader.get_plausible_params()

        kwargs={}
        argi = 0

        args_out = [ configfile ]


        while argi < len(remainingargs):
            # handle named keyword parameters

            arg = remainingargs[argi]

            # check for variable overrides
            if arg.startswith("--"): # variable override
                variable_name = arg[2:]
                equals_index = variable_name.find("=")
                if equals_index >= 0:
                    variable_value = variable_name[(equals_index+1):]
                    variable_name = variable_name[:equals_index]
                    pass
                else:
                    argi+=1
                    variable_value = remainingargs[argi]
                    pass

                variable_name=variable_name.replace("-","_") # convert minus to underscore in variable name

                if variable_name not in plausible_params:
                    raise ValueError("Variable override parameter --%s is not simply assigned in the dataguzzler-python configuration" % (variable_name))

                target_type = plausible_params[variable_name]

                variable_value = target_type(variable_value) # cast to type evaluated from config file

                kwargs[variable_name]=variable_value
                pass
            else:
                # add to args_out
                args_out.append(arg)
                pass

            argi += 1
            pass

        if profiling:
            try:
                import yappi
                pass
            except ImportError:
                print("Profiling requires the yappi profiler to be installed; profiling disabled")
                profiling = False
                pass
            pass

        if profiling:
            yappi.start()
            print("Profiling enabled")
            print(" ")
            print("Use")
            print("---")
            print("import yappi")
            print("yappi.stop()")
            #print("yappi.get_thread_stats()")
            print("yappi.get_func_stats().print_all()")
            print(" ")
            pass


        ##### (global variables will be in dgpy_config.__dict__)
        dgpy.dgpy_running=True


        # pass evaluated parameters to loader
        loader.set_actual_params(args_out,kwargs)
        spec = importlib.util.spec_from_loader("dgpy_config", #configfile,
                                               loader=loader)

        # load config file
        dgpy_config = importlib.util.module_from_spec(spec)
        spec_loader = spec.loader
        sys.modules["dgpy_config"]=dgpy_config

        # run config file up until any dgpython_release_main_thread() call
        spec.loader.exec_module(dgpy_config,mode="main_thread")
        pass
    except:
        sys.stderr.write("Exception running config file...\n")

        got_exception = True

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
    console_input_thread=Thread(target=dgp_completer_and_console_input_processor,args=(dgpy_config,"console_input",localvars,rlcompleter,spec_loader,got_exception,ipython),daemon=False)
    console_input_thread.start()

    #Remap Ctrl+C/SIGINT to send to registed functions
    signal.signal(signal.SIGINT, lambda a,b:
                  dgpy._CallKeyboardInterruptFunctions())

    # Register Command Reader to Receive KeyboardInterrupt
    dgpy.RegisterKeyboardInterrupt(console_input_thread.ident)

    main_thread_run() # Let main_thread module take over the main thread

    pass


def dgp_completer_and_console_input_processor(dgpy_config,console_contextname,localvars,rlcompleter,spec_loader,got_exception,ipython):
    # run the spec_loader in sub_thread mode unless we got an exception above
    InitThread() # Allow stuff to run from this thread
    PushThreadContext(initialization_sub_thread_context)

    if not got_exception:
        try:
            # run config file after any dgpython_release_main_thread() call
            spec_loader.exec_module(dgpy_config,mode="sub_thread")
            pass
        except:
            sys.stderr.write("Exception running config file (after dgypthon_release_main_thread())...\n")

            got_exception = True

            localvars["__dgpy_last_exc_info"]=sys.exc_info()

            traceback.print_exc()

            sys.stderr.write("\nRun dgpy.pm() to debug\n")

            #import pdb
            #pdb.post_mortem()

            pass
        finally:
            PopThreadContext()
            pass
        pass
    if ipython:
        ipython_input_processor(dgpy_config,console_contextname,localvars)
    else:
        readline_input_processor(dgpy_config,console_contextname,localvars,rlcompleter)

    pass
