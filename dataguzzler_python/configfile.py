import sys
import warnings
import os
import os.path
from types import ModuleType
import importlib
import posixpath
from urllib.request import url2pathname
from urllib.parse import quote
import atexit
import ast
import inspect
import copy
import dataguzzler_python
from dataguzzler_python import dgpy
from dataguzzler_python.configfile_utils import scan_source
from dataguzzler_python.configfile_utils import modify_source_overriding_parameters
from dataguzzler_python.configfile_utils import modify_source_into_function_call
#def whofunc(globalkeys,localkeys):
def whofunc(mod,*args):
    if len(args) == 1:
        # Call who method on the argument
        return args[0].who()
    elif len(args) > 1:
        raise ValueError("Too many arguments to who()")
    
    # NOTE: who() code also present in dgpy.py/class Module and OpaqueWrapper.py

    globalkeys = mod.__dict__.keys()
    
    callerframe = inspect.stack(context=0)[2].frame
    localvars = inspect.getargvalues(callerframe).locals

    localkeys = localvars.keys()
    
    totallist = list(globalkeys)+list(localkeys)

    filtered_totallist = [ attr for attr in totallist if not attr.startswith("_") and not attr=="who" and not attr=="help"]
    filtered_totallist.sort()
    
    old_pretty_printing=r""""
    colwidth=16
    termwidth=80
    spacing=1

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
    """
    return filtered_totallist


class DGPyConfigFileLoader(importlib.machinery.SourceFileLoader):
    """Loader for .dgp config files with include() 
    function in __dict__. Note that this also inserts the path
    of the current source file temporarily into sys.path while 
    it is executing"""

    args=None
    paramdict=None
    sourcetext=None
    sourceast=None
    globalparams=None
    assignable_param_types = None
    sourcetext_context=None
    parentmodule=None
    
    def __init__(self,name,path,sourcetext,sourcetext_context,parentmodule):
        super().__init__(name,path)
        self.paramdict={}
        self.sourcetext=sourcetext
        self.sourcetext_context=sourcetext_context
        self.parentmodule=parentmodule

        
        (self.sourceast,self.globalparams,self.assignable_param_types,dpi_args,dpi_kwargs) = scan_source(self.path,self.sourcetext)
        if dpi_args or dpi_kwargs:
            raise ValueError("dpi_args and dpi_kwargs not supported in .dgp files")
        
        pass

    def get_plausible_params(self):
        """Return dictionary by parameter name of Python type"""

        return self.assignable_param_types
    
    def set_actual_params(self,args,paramdict):
        self.args=args
        self.paramdict=paramdict
        pass
    
    
    # Overridden create_module() inserts custom elements (such as include())
    # into __dict__ before module executes
    def create_module(self,spec):
        module = ModuleType(spec.name)
        module.__file__ = self.path
        #module.__dict__ = {}
        module.__dict__["__builtins__"]=__builtins__

        # add "who()" function
        module.__dict__["who"] = lambda *args: whofunc(module,*args) # lambda : whofunc(module.__dict__.keys(),localdict.keys())

        module.__dict__["_contextstack"]=[ os.path.split(self.sourcetext_context)[0] ]
        sys.path.insert(0,module.__dict__["_contextstack"][-1]) # Current context should always be at start of module search path

        ## store the module structure in a central location so that it is accessible (available as sys.modules["dgpy_config"])
        #dataguzzler_python.configfile_module = module
        
        module.__dict__["include"]=dgpy.include
        module.__spec__=spec
        module.__loader__=self
        module.__annotations__={}
        module.__doc__=None
        return module

    def exec_module(self,module,mode="all"):
        """Overridden exec_module() that presets variables according
        to given kwarg dict, erasing their simply assigned values if present.
        
        Mode can be 'all' to indicate executing the entire module, 'main_thread'
        to indicate executing the initial portion prior to dgpython_release_main_thread(), 'sub_thread' to indicate executing the final portion after dgpython_release_main_thread()"""

        # Insert explicitly passed parameters into dict
        module.__dict__["args"]=self.args  # add "args" variable with positional parameters
        module.__dict__.update(self.paramdict)

        # insert parentmodule into dict if present (for subproc support)
        if self.parentmodule is not None:
            module.__dict__["parent"]=self.parentmodule
            pass

        code = modify_source_overriding_parameters(self.path,copy.deepcopy(self.sourceast),self.paramdict.keys(),mode)
        # We don't care about global declarations here because in the main config file everything is global by default

        # Likewise modify_source_into_function_call() is unnecessary
        
        # self.globalparams
        exec_code = compile(code,self.path,'exec')

        
        exec(exec_code,module.__dict__,module.__dict__)
        pass
    
        
    pass
