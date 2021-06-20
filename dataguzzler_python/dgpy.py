import threading
import numbers
import types
import numpy as np
import os
import sys
import abc
import collections
import inspect
import traceback
import copy
import pdb

from .remoteproxy import remoteproxy
from .context import InitThread,InitFreeThread,InitCompatibleThread
from .context import InitContext,InitThreadContext
from .context import PushThreadContext,PopThreadContext
from .context import CurContext,InContext,SimpleContext
from .context import RunUnprotected,RunInContext
from .OpaqueWrapper import OpaqueWrapper,forceunwrap

#try:
#    import limatix
#    import limatix.dc_value
#    import limatix.lm_units
#    pass
#except ImportError:
#    sys.stderr.write("dgpy: limatix not available; dc_value units will not be supported\n")
#    pass

import pint # units library... so we can use isinstance() below. 



dgpy_running=False # Flag set by bin/dataguzzler_python.py that indicates 
# we are running under dg_python

# set of names of Python magic methods
# magicnames omits __new__, __init__, __getattribute__,  
# otherwise this list is based on http://www.rafekettler.com/magicmethods.html    
magicnames=set(["__del__", "__cmp__", "__eq__","__ne__","__lt__","__gt__","__le__", "__ge__", "__pos__", "__neg__", "__abs__", "__invert__", "__round__", "__floor__", "__ceil__", "__trunc__", "__add__", "__sub__", "__mul__", "__floordiv__", "__div__", "__truediv__", "__mod__", "__divmod__", "__pow__", "__lshift__", "__rshift__", "__and__", "__or__", "__xor__", "__radd__", "__rsub__", "__rmul__", "__rfloordiv__", "__rdiv__", "__rtruediv__", "__rmod__", "__rdivmod__", "__rpow__", "__rlshift__", "__rrshift__", "__rand__", "__ror__", "__rxor__", "__iadd__", "__isub__", "__imul__", "__ifloordiv__", "__idiv__", "__itruediv__", "__imod__", "__ipow__", "__ilshift__", "__irshift__", "__iand__", "__ior__", "__ixor__", "__int__", "__long__", "__float__", "__complex__", "__oct__", "__hex__", "__index__", "__trunc__", "__coerce__", "__str__", "__repr__", "__unicode__", "__format__", "__hash__", "__nonzero__", "__dir__", "__sizeof__","__delattr__","__setattr__","__len__","__getitem__", "__setitem__","__delitem__","__iter__","__reversed__", "__contains__", "__missing__","__call__", "__getattr__","__enter__","__exit__","__get__","__set__","__delete__","__copy__","__deepcopy__","__getinitargs__","__getnewargs__","__getstate__","__setstate__","__reduce__","__reduce_ex__"])

#if sys.version_info >= (2,7):
#    magicnames.add("__subclasscheck__")  # cannot assign __subclasscheck__ prior to python 2.6
#    magicnames.add("__instancecheck__") # cannot assign __instancecheck__ prior to python 2.6
#    pass


class ModuleException(Exception):
    ModulesException=None
    ModulesTraceback=None
    def __init__(self,ModulesException,ModulesTraceback):
        super(ModulesException,self).__init__("%s: Traceback=%s" % (str(ModulesException),traceback.format_exc(ModulesTraceback)))
        self.ModulesException=ModulesException
        self.ModulesTraceback=ModulesTraceback
        pass
    pass






def wrapdescriptor(towrap):
    oldget = towrap.__get__
    oldset = towrap.__set__
    doc="Undocumented"
    if hasattr(towrap,"__doc__"):
        doc=towrap.__doc__
        pass
        
    class descriptor_wrapper(object):
        def __init__(self,doc):
            self.__doc__=doc
            pass
        def __get__(self,obj,type=None):
            return RunInContext(obj,oldget,oldget.__name__,(obj,),{"type": type})
        def __set__(self,obj,value):
            return RunInContext(obj,oldset,oldset.__name__,(obj,value),{})
        pass
    return descriptor_wrapper(doc)



def pm():
    """ pdb debugger... like pdb.pm() """
    frame=inspect.currentframe()
    (etype,evalue,last_tb) = frame.f_back.f_locals["__dgpy_last_exc_info"]
    traceback.print_exception(etype,evalue,last_tb)
    pdb.post_mortem(last_tb)
    pass


def dgpy_nowrap(method):
    """Decorator for methods to tell dgpy.Module that the method
    doesn't need any wrapping or censoring. 
    usage:
    @dgpy_nowrap
    def mymethod(self,myarg):
        ...
        pass
    """
    setattr(method,"_dgpy_nowrapping",True)
    return method

    

class Module(type):
    # Metaclass for dgpy modules
    
    def __init__(cls,*args,**kwargs):
        # This is called on definition of the dgpy module class as the class is defined

        ## Define _dgpy_threadcode method for the dgpy module class
        #def _dgpy_threadcode(self):
        #    self._dgpy_mainloop=asyncio.new_event_loop()
        #    self._dgpy_mainloop.set_debug(True)
        #    self._dgpy_mainloop.run_forever()
        #    self._dgpy_mainloop.close()
        #    pass
        #
        #setattr(cls,"_dgpy_threadcode",_dgpy_threadcode)

        # define __new__ method for the dgpy module class
        # ... this creates and initializes the ._dgpy_contextlock member
        # and sets the context of executing the __new__ method
        def __new__(cls,*args,**kwargs):
            newobj=object.__new__(cls)

            module_name = None
            #if "module_name" in kwargs:
            #    module_name=kwargs["module_name"]
            #    pass
            if len(args) > 0:
                module_name=args[0]
                pass

            if module_name is None or type(module_name) is not str:
                raise ValueError("First argument to dgpy.Module constructor should be a string: module_name")
            
        
            InitContext(newobj,module_name) # add _dgpy_contextlock member
            #import pdb
            #pdb.set_trace()
            PushThreadContext(newobj) # Set context... released in__call__ below
            return newobj
        setattr(cls,"__new__",__new__)


        if not hasattr(cls,"who"):
            # provide default who() method for class
            def who(self):
                """ .who() method; kind of like dir() but removes special methods, methods with underscores, etc. OK to override this in your classes, in which case your method will be called instead"""
                # NOTE: who() code also present in configfile.py and OpaqueWrapper.py
                dir_output = dir(self)

                filtered_dir_output = [ attr for attr in dir_output if not attr.startswith("_") and not attr=="who" and not attr=="help"]
                filtered_dir_output.sort()
                
                return filtered_dir_output
            setattr(cls,"who",who)
            pass

        if not hasattr(cls,"help"):
            def _help(self):
                """Convenience method for getting help. OK to override this method"""

                # NOTE: help() code also present OpaqueWrapper.py
                return help(self)
            setattr(cls,"help",_help)
            pass

        # Define __getattribute__ method for the dgpy module class
        # Getattribute wraps all attribute accesses (except magic method accesses)
        # to return wrapped objects, including methods that shift context
        orig_getattribute=getattr(cls,"__getattribute__")

        
        def __getattribute__(self,attrname):
            
            if attrname=="__class__":
                return object.__getattribute__(self,attrname)

            #sys.stderr.write("Calling ModuleInstance.__getattribute__(,%s)\n" % (attrname))
            try:
                #attr=object.__getattribute__(self,attrname)
                #attr=orig_getattribute(self,attrname)

                ### !!!! Should put in a shortcut here so if __getattribute__ isn't overloaded, we just use regular __getattribute__
                attr=RunInContext(self,orig_getattribute,"__getattribute__",(self,attrname),{})
                #sys.stderr.write("Ran in context.\n")
                
                pass
            except AttributeError:
                # attribute doesn't exist... do we have a __getattr__ method?
                getattrflag=True
                try: 
                    __getattr__=object.__getattribute__(self,"__getattr__")
                    #__getattr__=getattr(self,"__getattr__")
                    pass
                except AttributeError:
                    getattrflag=False
                    pass
                if getattrflag: 
                    # call wrapped __getattr__

                    #sys.stderr.write("getattrflag: %s\n" % (attrname))
                    #sys.stderr.flush()

                    # avoid import loop...
                    from .censoring import censorobj

                    
                    (curcontext,cc_compatible)=CurContext()
                    censoredattrname=str(attrname)
                    PushThreadContext(self)
                    try: 
                        getattr_res=__getattr__(censoredattrname)

                        censoredres=censorobj(self,curcontext,censoredattrname,getattr_res)
                        pass
                    finally:
                        PopThreadContext()
                        pass
                    
                    return censoredres
                else:
                    # attribute really doesn't exist
                    raise
                pass
            if attrname=="_dgpy_contextlock":
                # always return the lock unwrapped
                return attr
            
            #return censorobj(self,curcontext,attrname,attr)
            return attr # RunInContext already censored result
        
        setattr(cls,"__getattribute__",__getattribute__)
        # try binding __getattribute__ to the class instead.
        # ref: https://stackoverflow.com/questions/1015307/python-bind-an-unbound-method
        #ga_bound = __getattribute__.__get__(cls,cls.__class__)
        #setattr(cls,"__getattribute__",ga_bound)

        # For each defined magic method, define a wrapper that censors params and
        # switches context
        for magicname in magicnames:
            try:
                #magicmethod=object.__getattribute__(cls,magicname)
                #magicmethod=getattr(cls,magicname)
                magicmethod=type.__getattribute__(cls,magicname)
                pass
            except AttributeError:
                continue
            
            wrapmagicmethod = lambda magicmethod,magicname: lambda *args,**kwargs: RunInContext(args[0],magicmethod,magicname,args,kwargs)
            wrappedmagicmethod=wrapmagicmethod(magicmethod,magicname)
            setattr(cls,magicname,wrappedmagicmethod)
            pass
        pass


    def __call__(cls,*args,**kwargs):
        # called on creation of an object (dgpy module)

        # Create object
        try: 
            newmod = type.__call__(cls,*args,**kwargs)
            pass
        finally:
            PopThreadContext()  # Paired with PushThreadContext in __new__() above
            pass
        
        # define _dgpy_thread and _mainloop attributes; start thread
        #newmod._dgpy_mainloop=None
        #newmod._dgpy_thread=Thread(target=newmod._threadcode)
        #newmod._dgpy_thread.start()

        
        
        return newmod

    pass

        
# Abstract base class for objects which are threadsafe
# and can therefore be freely passed between contexts
class threadsafe(object,metaclass=abc.ABCMeta):
    pass
# Use dgpy.threadsafe.register(my_class)  to register your new class

#threadsafe.register(limatix.dc_value.value)
