import sys
import os
from types import ModuleType
import importlib
import posixpath
from urllib.request import url2pathname
import atexit
import ast
import inspect


#def whofunc(globalkeys,localkeys):
def whofunc(mod):

    globalkeys = mod.__dict__.keys()
    
    callerframe = inspect.stack(context=0)[2].frame
    localvars = inspect.getargvalues(callerframe).locals

    localkeys = localvars.keys()
    
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


def load_source_overriding_parameters(sourcepath,sourcetext,paramdict_keys):
    """Reads in the given source file. Removes assignments of given
    keys. Returns byte-compiled code ready-to-execute (paramdict
    values must be independently provided). """
    #sourcefile=open(sourcepath,"r")
    #sourceast=ast.parse(sourcefile.read(),filename=sourcepath)
    #sourcefile.close()
    if sourcepath is None:
        sourcepath="<unknown>"
        pass
    
    sourceast=ast.parse(sourcetext,filename=sourcepath)
    
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
    return compile(sourceast,sourcepath,'exec')


class DGPyConfigFileLoader(importlib.machinery.SourceFileLoader):
    """Loader for .dgp config files with include() 
    function in __dict__. Note that this also inserts the path
    of the current source file temporarily into sys.path while 
    it is executing"""
    paramdict=None
    sourcetext=None
    sourcetext_context=None
    parentmodule=None
    
    def __init__(self,name,path,sourcetext,sourcetext_context,parentmodule,paramdict):
        super().__init__(name,path)
        self.paramdict=paramdict
        self.sourcetext=sourcetext
        self.sourcetext_context=sourcetext_context
        self.parentmodule=parentmodule
        pass
    
    # Overridden create_module() inserts custom elements (such as include())
    # into __dict__ before module executes
    def create_module(self,spec):
        module = ModuleType(spec.name)
        module.__file__ = self.path
        #module.__dict__ = {}
        module.__dict__["__builtins__"]=__builtins__

        # add "who()" function
        module.__dict__["who"] = lambda : whofunc(module) # lambda : whofunc(module.__dict__.keys(),localdict.keys())

        module.__dict__["_contextstack"]=[ os.path.split(self.sourcetext_context)[0] ]
        sys.path.insert(0,module.__dict__["_contextstack"][-1]) # Current context should always be at start of module search path
        
        def DGPyConfigFile_include(includeurl,**kwargs):
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
            sys.path.insert(0,module.__dict__["_contextstack"][-1]) # Current context should always be at start of module search path
            
            # load
            includefh=open(includepath,"r")
            includetext=includefh.read()
            includefh.close()
            #code = compile(includestr,includepath,'exec')
            
            code = load_source_overriding_parameters(includepath,includetext,kwargs)
            
            # run
            #exec(code,module.__dict__,module.__dict__)
            localvars={}  # NOTE Must declare variables as global in the .dpi for them to be accessible

            localvars.update(kwargs)  # include any explicitly passed parameters
            
            exec(code,module.__dict__,localvars)
            
            # pop from context stack
            # First remove current context from start of module search path
            sys.path.remove(module.__dict__["_contextstack"][-1]) 
            module.__dict__["_contextstack"].pop()        
            pass
        

        
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
        module.__dict__.update(self.paramdict)

        # insert parentmodule into dict if present
        if self.parentmodule is not None:
            module.__dict__["parent"]=self.parentmodule
            pass
        exec(load_source_overriding_parameters(self.path,self.sourcetext,self.paramdict.keys()),module.__dict__,module.__dict__)
        pass
    
        
    pass
