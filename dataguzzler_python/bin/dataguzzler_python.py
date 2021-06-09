import sys
import os
from types import ModuleType
import importlib
import posixpath
from urllib.request import url2pathname
import atexit
# Enable readline editing/history/completion, as in 'python -i' interactive mode
import readline
import rlcompleter

from ..mainloop import start_tcp_server
from ..mainloop import PyDGConn,OldDGConn
from ..mainloop import process_line
from ..mainloop import write_response,render_response

from ..dgpy import SimpleContext
from ..dgpy import InitThreadContext
from ..dgpy import PushThreadContext,PopThreadContext
import dataguzzler_python.dgpy as dgpy

dgpy_config=None

def whofunc(globalkeys,localkeys):
    colwidth=16
    termwidth=80
    spacing=1
    totallist = list(globalkeys)+list(localkeys)
    
    outlist=[ "\n" ]

    colpos=0
    pos=0
    while pos < len(totallist):
        entry=totallist[pos]
        if colpos > 0 and len(entry) > termwidth-colpos: 
            # new line
            outlist.append("\n")
            colpos=0
            pass
        outlist.append(entry)
        colpos += len(entry)
        if colpos < (termwidth//colwidth)*colwidth-2:
            numextraspaces=1 + colwidth - ((colpos+1 + (colwidth-1)) % colwidth) -1
            outlist.append(" "*numextraspaces)
            colpos+=numextraspaces
            pass
        else:
            outlist.append("\n")
            colpos=0
            pass
        pos+=1
        pass
    return "".join(outlist)
    


class DGPyConfigFileLoader(importlib.machinery.SourceFileLoader):
    """Loader for .dgp config files with include() 
    function in __dict__"""

    def create_module(self,spec):
        module = ModuleType(spec.name)
        module.__file__ = self.path
        #module.__dict__ = {}
        module.__dict__["__builtins__"]=__builtins__
        module.__dict__["_contextstack"]=os.path.split(self.path)[0]

        def DGPyConfigFile_include(includeurl):
            """Include a sub-config file as if it were 
            inserted in your main config file. 
            
            Provide the relative or absolute path (includeurl)
            in URL notation with forward slashes and percent-encoding of special 
            characters"""
            
            if posixpath.isabs(includeurl):
                includepath = url2pathname(includeurl)
                pass
            else:
                includepath = os.path.join(module.__dict__["_contextstack"][-1],url2pathname(includeurl))
                pass
            
            # Now includepath is the path of my include file
            # push to context stack
            module.__dict__["_contextstack"].append(includepath)
            
            # load
            includefh=open(includepath,"r")
            includestr=includefh.read()
            includefh.close()
            code = compile(includestr,includepath,'exec')
            
            # run
            exec(code,module.__dict__,module.__dict__)
            run_config(href,config_globals)
            
            # pop from context stack        
            module.__dict__["_contextstack"].pop()        
            pass
        

        
        module.__dict__["include"]=DGPyConfigFile_include
        module.__spec__=spec
        module.__loader__=self
        module.__annotations__={}
        module.__doc__=None
        return module
    pass

def main(args=None):
    if args is None:
        args=sys.argv
        pass
    
    global dgpy_config  #  reminder
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
    
    InitThreadContext(ConfigContext,"dgpy_config") # Allow to run stuff from main thread
    PushThreadContext(ConfigContext)
    
    configfile=args[1]

    # Dictionary of local variables
    # (global variables will be in dgpy_config.__dict__) 
    localdict={}
    dgpy.dgpy_running=True

    # define config file... Use custom loader so we can insert "include" function into default dictionary
    spec = importlib.util.spec_from_file_location("dgpy_config", configfile,loader=DGPyConfigFileLoader("dgpy_config",configfile))
    # load config file
    dgpy_config = importlib.util.module_from_spec(spec)
    sys.modules["dgpy_config"]=dgpy_config

    # add "who()" function
    dgpy_config.__dict__["who"] = lambda : whofunc(dgpy_config.__dict__.keys(),localdict.keys())
    
    # run config file 
    spec.loader.exec_module(dgpy_config)

    PopThreadContext()

    
    tcp_thread=start_tcp_server("localhost",1651)
    old_dg_thread=start_tcp_server("localhost",1649,connbuilder=lambda **kwargs: OldDGConn(**kwargs))

    
    MainContext=SimpleContext()
    InitThreadContext(MainContext,"__main__") # Allow to run stuff from main thread
    PushThreadContext(MainContext)

    globaldecls=[]

    readline.set_completer(rlcompleter.Completer(dgpy_config.__dict__).complete)
    
    while(True):
        InStr=input("dgpy> ")
        (rc,ret,bt)=process_line(globaldecls,localdict,InStr)
        write_response(sys.stdout.buffer,rc,render_response(rc,ret,bt))

        pass
    
    
    pass
