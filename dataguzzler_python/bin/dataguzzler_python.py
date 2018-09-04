import sys
import os
import importlib
import atexit
# Enable readline editing/history/completion, as in 'python -i' interactive mode
import readline
import rlcompleter

from ..mainloop import start_tcp_server
from ..mainloop import PyDGConn,OldDGConn
from ..mainloop import process_line
from ..mainloop import write_response

from ..pydg import SimpleContext
from ..pydg import InitThreadContext
from ..pydg import PushThreadContext,PopThreadContext

pydg_config=None

def main(args=None):
    if args is None:
        args=sys.argv
        pass
    
    global pydg_config  #  reminder
    if sys.version_info < (3,6,0):
        raise ValueError("Insufficient Python version: Requires Python 3.6 or above")
    
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


    ConfigContext=SimpleContext()
    
    InitThreadContext(ConfigContext,"pydg_config") # Allow to run stuff from main thread
    PushThreadContext(ConfigContext)
    
    configfile=args[1]

    # define config file
    spec = importlib.util.spec_from_file_location("pydg_config", configfile)
    # load config file
    pydg_config = importlib.util.module_from_spec(spec)
    sys.modules["pydg_config"]=pydg_config
    # run config file 
    spec.loader.exec_module(pydg_config)

    PopThreadContext()

    
    tcp_thread=start_tcp_server("localhost",1651)
    old_dg_thread=start_tcp_server("localhost",1649,connbuilder=lambda **kwargs: OldDGConn(**kwargs))

    
    MainContext=SimpleContext()
    InitThreadContext(MainContext,"__main__") # Allow to run stuff from main thread
    PushThreadContext(MainContext)

    globaldecls=[]
    localdict={}

    readline.set_completer(rlcompleter.Completer(pydg_config.__dict__).complete)
    
    while(True):
        InStr=input("pydg> ")
        (rc,ret,bt)=process_line(globaldecls,localdict,InStr)
        if bt is None:
            write_response(sys.stdout.buffer,rc,repr(ret).encode('utf-8'))
            pass
        else:
            write_response(sys.stdout.buffer,rc,repr((ret,bt)).encode('utf-8'))
            pass

        pass
    
    
    pass
