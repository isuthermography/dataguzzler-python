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

def scan_source(sourcepath,sourcetext):
    """Reads in the given text and determines abstract syntax tree.
    Identifies global parameters and also assignment targets and their
    type. NoneType is interpreted as a string"""
    
    if sourcepath is None:
        sourcepath="<unknown>"
        pass
    

    assignable_param_types={}
    
    sourceast=ast.parse(sourcetext,filename=sourcepath)

    globalparams=set([])

    cnt=0
    while cnt < len(sourceast.body):
        entry=sourceast.body[cnt]

        if entry.__class__.__name__=="Assign" and len(entry.targets)==1 and entry.targets[0].__class__.__name__=="Name":
            if entry.value.__class__.__name__=="Constant" and entry.value.value.__class__.__name__=="float":
                assignable_param_types[entry.targets[0].id] = float
                pass
            if entry.value.__class__.__name__=="Constant" and entry.value.value.__class__.__name__=="int":
                assignable_param_types[entry.targets[0].id] = int
                pass
            if entry.value.__class__.__name__=="Constant" and entry.value.value.__class__.__name__=="str":
                assignable_param_types[entry.targets[0].id] = str
                pass
            if entry.value.__class__.__name__=="Constant" and entry.value.value.__class__.__name__=="NoneType":
                # Treat None as str -- we probably want a filename or similar
                assignable_param_types[entry.targets[0].id] = str
                pass
            pass
        
            # print entry.targets
            
        if entry.__class__.__name__=="Global":
            for paramkey in entry.names:
                # This key declared as a global
                globalparams.add(paramkey)
                pass
            pass
        cnt+=1
        pass
    
    return (sourceast,globalparams,assignable_param_types)
    

def modify_source_overriding_parameters(sourcepath,sourceast,paramdict_keys):
    """Reads in the given syntax tree. Removes assignments of given
    keys. Returns byte-compiled code ready-to-execute (paramdict
    values must be independently provided). """
    #sourcefile=open(sourcepath,"r")
    #sourceast=ast.parse(sourcefile.read(),filename=sourcepath)
    #sourcefile.close()
    if sourcepath is None:
        sourcepath="<unknown>"
        pass
    
    for paramkey in paramdict_keys:
        gotassigns=0
        cnt=0
        
        while cnt < len(sourceast.body):
            entry=sourceast.body[cnt]
            if entry.__class__.__name__=="Assign" and len(entry.targets)==1 and entry.targets[0].__class__.__name__=="Name":
                # print entry.targets
                if entry.targets[0].id==paramkey:
                    del sourceast.body[cnt]
                    gotassigns+=1
                    continue  # bypass cnt increment below
                pass
            cnt+=1
            pass

        if gotassigns != 1:
            raise ValueError("Overridden parameter %s in %s is not simply assigned exactly once at top level" % (paramkey,sourcepath))
        pass
    return sourceast # compile(sourceast,sourcepath,'exec')

def modify_source_into_function_call(sourceast,localkwargs):
    """Take sourceast, and stuff it into the body of a function call
which takes the named arguments given in the keys of localkwargs. Then
generate a call to the function that stores the return in the
local variable __dgpy_config_ret. Then return an abstract syntax
tree representing this process. 

The name of the defined function is __dgpy_config_function.
    """
    
    curbody = sourceast.body
    
    funcarglist = [ ast.arg(arg=kwarg,annotation=None,type_comment=None) for kwarg in localkwargs ]
    

    funcargs = ast.arguments(posonlyargs=[],
                             args=funcarglist,
                             vararg=None,
                             kwonlyargs=[],
                             kw_defaults=[],
                             kwarg=None,
                             defaults=[])
    
    funcdef = ast.FunctionDef(name="__dgpy_config_function",
                              args=funcargs,
                              body=curbody,
                              decorator_list=[],
                              returns = None,
                              type_comment = None)

    funccallkeywords = [ ast.keyword(arg=kwarg,value=ast.Name(id=kwarg,ctx=ast.Load())) for kwarg in localkwargs ] 
    
    funcretassign = ast.Assign(targets=[ast.Name(id="__dgpy_config_ret",ctx=ast.Store())],
                               value=ast.Call(func=ast.Name(id="__dgpy_config_function",ctx=ast.Load()),
                                              args=[],
                                              keywords=funccallkeywords),
                               type_comment = None)
    
    moddef = ast.Module([funcdef,funcretassign],type_ignores=[])

    ast.fix_missing_locations(moddef)
    
    return moddef

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

        
        (self.sourceast,self.globalparams,self.assignable_param_types) = scan_source(self.path,self.sourcetext)
        
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
        
        def DGPyConfigFile_include(includepackage,includeurl=None,**kwargs):
            """Include a sub-config file as if it were 
            inserted in your main config file. 
            
            Provide an imported package (or None) as includepackage, then
            the relative or absolute path as includeurl, in URL notation 
            with forward slashes (but not percent-encoding of special 
            characters).
            """

            if includeurl is None:
                if isinstance(includepackage,str):
                    warnings.warn("include() should now have a packaage (or None) as its first argument", category=DeprecationWarning)
                    pass
                includeurl = includepackage
                includepackage = None
                pass

            quoted_includeurl=quote(includeurl)
            
            if posixpath.isabs(quoted_includeurl):
                if includepackage is not None:
                    raise ValueError("Set package context to None if using an absolute include URL such as %s" % (includeurl))
                includepath = url2pathname(quoted_includeurl)
                pass
            else:
                if includepackage is None:
                    includepath = os.path.join(module.__dict__["_contextstack"][-1],url2pathname(quoted_includeurl))
                    pass
                else:
                    includepath = os.path.join(os.path.dirname(includepackage.__file__),url2pathname(quoted_includeurl))
                    pass
                pass
            
            # Now includepath is the path of my include file
            # push to context stack
            module.__dict__["_contextstack"].append(includepath)
            sys.path.insert(0,module.__dict__["_contextstack"][-1]) # Current context should always be at start of module search path
            
            # load
            includefh=open(includepath,"r")
            includetext=includefh.read()
            includefh.close()
            #code = compile(includestr,includepath,'exec')

            (includeast,globalparams,assignable_param_types) = scan_source(includepath,includetext)
            code = modify_source_overriding_parameters(includepath,includeast,kwargs)

            localkwargs = { varname: kwargs[varname] for varname in kwargs if varname not in globalparams }
            globalkwargs = { varname: kwargs[varname] for varname in kwargs if varname in globalparams }

            function_code = modify_source_into_function_call(code,localkwargs)


            exec_code = compile(function_code,includepath,'exec')
            # run
            #exec(code,module.__dict__,module.__dict__)
            localvars={}  # NOTE Must declare variables as global in the .dpi for them to be accessible

            
            localvars.update(localkwargs)  # include any explicitly passed local parameters 

            # update global dictionary according to explicitly passed global parameters
            module.__dict__.update(globalkwargs)

            # Run the include file code
            exec(exec_code,module.__dict__,localvars)
            
            # pop from context stack
            # First remove current context from start of module search path
            sys.path.remove(module.__dict__["_contextstack"][-1]) 
            module.__dict__["_contextstack"].pop()

            return localvars["__dgpy_config_ret"]
        

        
        module.__dict__["include"]=DGPyConfigFile_include
        module.__spec__=spec
        module.__loader__=self
        module.__annotations__={}
        module.__doc__=None
        return module

    def exec_module(self,module):
        """Overridden exec_module() that presets variables according
        to given kwarg dict, erasing their simply assigned values if present."""

        # Insert explicitly passed parameters into dict
        module.__dict__["args"]=self.args  # add "args" variable with positional parameters
        module.__dict__.update(self.paramdict)

        # insert parentmodule into dict if present (for subproc support)
        if self.parentmodule is not None:
            module.__dict__["parent"]=self.parentmodule
            pass

        code = modify_source_overriding_parameters(self.path,self.sourceast,self.paramdict.keys())
        # We don't care about global declarations here because in the main config file everything is global by default

        # Likewise modify_source_into_function_call() is unnecessary
        
        # self.globalparams
        exec_code = compile(code,self.path,'exec')

        
        exec(exec_code,module.__dict__,module.__dict__)
        pass
    
        
    pass
