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
import warnings
import importlib
import posixpath
import ast
import ctypes

from urllib.request import url2pathname
from urllib.parse import quote
from .remoteproxy import remoteproxy
from .context import InitThread,InitFreeThread,InitCompatibleThread
from .context import InitContext,InitThreadContext
from .context import PushThreadContext,PopThreadContext
from .context import CurContext,InContext,SimpleContext
from .context import RunUnprotected,RunInContext, UnprotectedContext
from .OpaqueWrapper import OpaqueWrapper,forceunwrap
from dataguzzler_python.configfile_utils import scan_source
from dataguzzler_python.configfile_utils import modify_source_overriding_parameters
from dataguzzler_python.configfile_utils import modify_source_into_function_call

#try:
#    import limatix
#    import limatix.dc_value
#    import limatix.lm_units
#    pass
#except ImportError:
#    sys.stderr.write("dgpy: limatix not available; dc_value units will not be supported\n")
#    pass

_waithandles = {} #threading.Condition()
_keyboardinterruptthreads = {}

def sleep(secs):
    """
    General purpose wakeable sleep method

    When called from the command reader, Ctrl+c will interrupt the wait
    Other threads can use this as well, but they must register to receive
    KeyboardInterrupt exceptions with dgpy.RegisterKeyboardInterrupt.

    Arguments:
        secs: float number of seconds

    Usage:
        dgpy.sleep(1.0) # Sleeps for 1 second
    """
    tid = threading.current_thread().ident
    if tid in _waithandles:
        _waithandle = _waithandles[tid]
    else:
        _waithandles[tid] = threading.Condition()
        _waithandle = _waithandles[tid]
    with _waithandle:
        _waithandle.wait(secs)

def awake(tid):
    """
    Wake a thread sleeping with dgpy.sleep

    Arguments:
        tid: Thread ID from Thread().ident
    """
    _waithandle = _waithandles[tid]
    with _waithandle:
        _waithandle.notify_all()

def RegisterKeyboardInterrupt(tid, fcn=None):
    """
    Registers to receive a KeyboardInterrupt when Ctrl + c is pressed

    Calls dgpy._ctype_async_raise to send exception to registered thread
    This can be modified with optional fcn keyword parameter, but the callback
    should not block since this will be called from the main thread.

    Arguments:
        tid: Thread ID to Be Registered
        fcn=None: Optional function handle to call instead
    """
    assert(tid not in _keyboardinterruptthreads), "Thread already registered"
    if fcn is None:
        fcn = lambda: _ctype_async_raise(tid, KeyboardInterrupt)
    _keyboardinterruptthreads[tid] = fcn

def UnregisterKeyboardInterrupt(tid):
    """
    Disable KeyboardInterrupt Callback

    See RegisterKeyboardInterrupt for more details

    Arguments:
        tid: Thread ID to be Unregistered
    """
    assert(tid in _keyboardinterruptthreads), "Thread not registered"
    del _keyboardinterruptthreads[tid]

def _CallKeyboardInterruptFunctions():
    for tid in _keyboardinterruptthreads:
        _keyboardinterruptthreads[tid]()

# Modified from https://stackoverflow.com/questions/36484151/throw-an-exception-into-another-thread
# Warning -- we cannot interrupt time.sleep using this method.  The only thing
# that can interrupt time.sleep is a signal, which can only processed in the
# main thread (which is why time.sleep can be interrupted with a Ctrl+C at a
# Python Interpreter but not here). There are some platform specific quirks to
# this as well.  We may want to implement a replacement for
# time.sleep at some point that uses some kind of event to instead interrupt
# the wait process. threading.Event could be a good option for this and this
# code below would need to trigger that event.
def _ctype_async_raise(target_tid, exception):
    ret = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(target_tid), ctypes.py_object(exception))
    # ref: http://docs.python.org/c-api/init.html#PyThreadState_SetAsyncExc
    if ret == 0:
        raise ValueError("Invalid thread ID")
    elif ret > 1:
        # Huh? Why would we notify more than one threads?
        # Because we punch a hole into C level interpreter.
        # So it is better to clean up the mess.
        ctypes.pythonapi.PyThreadState_SetAsyncExc(target_tid, NULL)
        raise SystemError("PyThreadState_SetAsyncExc failed")

    # Let's notify any sleeping threads
    awake(target_tid)




def get_pint_util_SharedRegistryObject():
    if "pint" in sys.modules:
        return sys.modules["pint"].util.SharedRegistryObject
        pass
    else:
        return type(None)
        pass
    pass


dgpy_running=False # Flag set by bin/dataguzzler_python.py that indicates
# we are running under dg_python

# set of names of Python magic methods
# magicnames omits __new__, __init__, __getattribute__,
# also omit __enter__ and __exit__ because we provide those directly for context manager use to switch into module context.
# otherwise this list is based on http://www.rafekettler.com/magicmethods.html
magicnames=set(["__del__", "__cmp__", "__eq__","__ne__","__lt__","__gt__","__le__", "__ge__", "__pos__", "__neg__", "__abs__", "__invert__", "__round__", "__floor__", "__ceil__", "__trunc__", "__add__", "__sub__", "__mul__", "__floordiv__", "__div__", "__truediv__", "__mod__", "__divmod__", "__pow__", "__lshift__", "__rshift__", "__and__", "__or__", "__xor__", "__radd__", "__rsub__", "__rmul__", "__rfloordiv__", "__rdiv__", "__rtruediv__", "__rmod__", "__rdivmod__", "__rpow__", "__rlshift__", "__rrshift__", "__rand__", "__ror__", "__rxor__", "__iadd__", "__isub__", "__imul__", "__ifloordiv__", "__idiv__", "__itruediv__", "__imod__", "__ipow__", "__ilshift__", "__irshift__", "__iand__", "__ior__", "__ixor__", "__int__", "__long__", "__float__", "__complex__", "__oct__", "__hex__", "__index__", "__trunc__", "__coerce__", "__str__", "__repr__", "__unicode__", "__format__", "__hash__", "__nonzero__", "__dir__", "__sizeof__","__delattr__","__setattr__","__len__","__getitem__", "__setitem__","__delitem__","__iter__","__reversed__", "__contains__", "__missing__","__call__", "__getattr__","__get__","__set__","__delete__","__copy__","__deepcopy__","__getinitargs__","__getnewargs__","__getstate__","__setstate__","__reduce__","__reduce_ex__"])

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





## If you're here looking at this code because a "descriptor_wrapper" object is being
## returned by your attempt to access a dynamic instance descriptor, this isn't
## actually supported by Python by default.  You will need to do one of two things:
## 1) Override the default behavior of __getattribute__
##    See https://stackoverflow.com/questions/10232174/can-a-python-descriptor-be-used-to-instantiate-an-attribute-in-the-init-of-a
## 2) Set the __perinstance flag on the class
##    See https://stackoverflow.com/questions/2954331/dynamically-adding-property-in-python
## See https://stackoverflow.com/questions/12599972/descriptors-as-instance-attributes-in-python for general info
## Here's some code that is known to work.  Add it to your class:
##     def __getattribute__(self, name):
##         attr = super(YourClassNameHere, self).__getattribute__(name)
##         if hasattr(attr, "__get__"):
##             return attr.__get__(self, YourClassNameHere)
##         return attr
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

        #sys.stderr.write("class init params: %s\n" % (str(inspect.signature(cls.__init__).parameters)))

        class_init_params = list(inspect.signature(cls.__init__).parameters)
        if class_init_params[0] != "self":
            raise ValueError("First __init__ constructor parameter for dgpy.Module class %s is \"%s\" not \"self\"" % (cls.__name__,class_init_params[0]))

        if class_init_params[1] != "module_name":
            raise ValueError("First __init__ constructor parameter after \"self\" for dgpy.Module class %s is \"%s\" not \"module_name\"" % (cls.__name__,class_init_params[1]))


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

        # Define __enter__ and __exit__ magic methods that switch to our module context
        def __enter__(self):
            PushThreadContext(self)
            pass
        setattr(cls,"__enter__", __enter__)

        def __exit__(self):
            PopThreadContext(self)
            pass
        setattr(cls,"__exit__", __exit__)
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

# include() function for config files and modules

def include(includepackage,includeurl,*args,**kwargs):
    """Include a sub-config file as if it were
        inserted in your main config file.

        Provide an imported package (or None) as includepackage, then
        the relative or absolute path as includeurl, in URL notation
        with forward slashes (but not percent-encoding of special
        characters).
        """

    module = sys.modules["dgpy_config"]
    if includeurl is None:
        if isinstance(includepackage,str):
            warnings.warn("include() should now have a package (or None) as its first argument", category=DeprecationWarning)
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

    (includeast,globalparams,assignable_param_types,dpi_args,dpi_kwargs) = scan_source(includepath,includetext)
    code = modify_source_overriding_parameters(includepath,includeast,kwargs,mode="all")

    localkwargs = { varname: kwargs[varname] for varname in kwargs if varname not in globalparams }
    globalkwargs = { varname: kwargs[varname] for varname in kwargs if varname in globalparams }

    if dpi_args:
        localkwargs["dpi_args"]=args
        pass
    elif len(args) > 0:
        raise ValueError(f"Positional parameters provided to a .dpi file {includepath:s} that does not take dpi_args")

    if dpi_kwargs:
        localkwargs["dpi_kwargs"]=kwargs
        pass

    function_code = modify_source_into_function_call(code,localkwargs)


    exec_code = compile(function_code,includepath,'exec')
    # run
    #exec(code,module.__dict__,module.__dict__)
    localvars={}  # NOTE Must declare variables as global in the .dpi for them to be accessible


    localvars.update(localkwargs)  # include any explicitly passed local parameters

    if dpi_args:
        localvars["dpi_args"]=args
        pass
    elif len(args) > 0:
        raise ValueError(f"Positional parameters provided to a .dpi file {includepath:s} that does not take dpi_args")

    if dpi_kwargs:
        localvars["dpi_kwargs"]=kwargs
        pass

    # update global dictionary according to explicitly passed global parameters
    module.__dict__.update(globalkwargs)



    # Run the include file code
    exec(exec_code,module.__dict__,localvars)

    # pop from context stack
    # First remove current context from start of module search path
    sys.path.remove(module.__dict__["_contextstack"][-1])
    module.__dict__["_contextstack"].pop()

    return localvars["__dgpy_config_ret"]

# Alias for Cython because "include" is a reserved word.
dgpy_include=include
