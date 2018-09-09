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

#try:
#    import limatix
#    import limatix.dc_value
#    import limatix.lm_units
#    pass
#except ImportError:
#    sys.stderr.write("dgpy: limatix not available; dc_value units will not be supported\n")
#    pass

import pint # units library

u = pint.UnitRegistry()  # shared registry

junk=5
method_wrapper_type=junk.__str__.__class__

builtin_function_or_method_type = os.system.__class__ # os.system should consistently be a builtin

method_attr_types=[ types.MethodType, method_wrapper_type, builtin_function_or_method_type ]


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




# For any thread, ThreadContext.execution
# is a stack of objects, such as PyDGConn, or a dgpy.Module
# representing the current execution context of the module.
# that has a ._dgpy_contextlock member and a _dgpy_contextname member. The current context is the bottom-most
# element and the ._dgpy_contextlock member of that context should be held by the
# current executing thread. 
ThreadContext=threading.local()


#executor=ThreadPoolExecutor()

def InitThread():
    ThreadContext.execution=[]  # Create new context stack
    pass
    

def InitContext(context,name):
    object.__setattr__(context,"_dgpy_contextlock",threading.Lock())
    object.__setattr__(context,"_dgpy_contextname",str(name))
    pass

def InitThreadContext(context,name):
    InitThread()
    InitContext(context,name)
    pass

def check_dgpython():
    if not dgpy_running:
        raise ImportError("This dataguzzler-python configuration file is meant to be run via the dataguzzler-python script")
    pass


def PushThreadContext(context):  # Always pair with a PopThreadContext in a finally clause
    if len(ThreadContext.execution) > 0:
        object.__getattribute__(ThreadContext.execution[0],"_dgpy_contextlock").release()
        pass

    if context is not None:
        object.__getattribute__(context,"_dgpy_contextlock").acquire()
        pass
    ThreadContext.execution.insert(0,context)
    pass

def PopThreadContext():
    context=ThreadContext.execution.pop(0)
    if context is not None:
        object.__getattribute__(context,"_dgpy_contextlock").release()
        pass
    
    if len(ThreadContext.execution) > 0:
        object.__getattribute__(ThreadContext.execution[0],"_dgpy_contextlock").acquire()
        pass
    
    return context

def CurContext():
    return ThreadContext.execution[0]

def InContext(context):
    if context is ThreadContext.execution[0]:
        return True
    return False

class SimpleContext(object):
    _dgpy_contextlock=None
    _dgpy_contextname=None
    pass


class OpaqueWrapper(object):
    _wrappedobj=None  # do NOT access within wrapper -- use limited to specified context
    context=None

    def __init__(self,obj):
        self._wrappedobj=obj
        self.context=ThreadContext.execution[0]
        #sys.stderr.write("Wrapping object of type %s\n" % (type(obj).__name__))
        #sys.stderr.flush()
        pass

    def attemptunwrap(self,targetcontext=None):
        if targetcontext is None:
            targetcontext=ThreadContext.execution[0]
        if self.context is targetcontext:
            return _wrappedobj
        else:
            return self
        pass
    pass


def RunInContext(context,routine,routinename,args,kwargs):
    #sys.stderr.write("RunInContext(%s,%s,%s,%s)\n" % (object.__getattribute__(context,"_dgpy_contextname"),str(routine),routinename,str(routine.__code__)))
    #sys.stderr.flush()
    #def routine_runner(parentcontext,context,routine,args,kwargs):
    #    PushThreadContext(context)
    #    try:
    #        pass
    #    finally:
    #        PopThreadContext()
    #        pass
    #    
    #    censoredres=censorobj(context,parentcontext,".retval",res)
    #    return censoredres

    parentcontext=CurContext()

    if parentcontext is context:
        # No context switch necessary
        return routine(*args,**kwargs)

    
    # Censor args to those that can cross context boundaries
    censoredargs=censorobj(parentcontext,context,routinename+".param",args)

    censoredkwargs={}
    for kwarg in kwargs:
        censoredkwargs[str(kwarg)]=censorobj(parentcontext,context,"%s.param[%s]" % (routinename,kwarg),kwargs[kwarg])
        pass
    
    # ***!!! Don't really need to use executor. all we need to do is
    # context-switch ourselves. 
    #future=executor.submit(routine_runner,context,routine,censoredargs,censoredkwargs)
    #concurrent.futures.wait([future])
    #
    #exc=future.exception()
    #if exc is not None:
    #    raise exc
    #
    #return future.result()
    PushThreadContext(context)
    try: 
        res=routine(*censoredargs,**censoredkwargs)
        censoredres=censorobj(context,parentcontext,".retval",res)
        pass
    finally:
        PopThreadContext()
        pass
    
    return censoredres
    
    
#def wrapobj(dgpy_mod,obj,objname,args,kwargs):
    # "Proposed Alternative" (now implemented)
    #   * Create a thread pool for this module/connection(or all modules?)
    #   * Define an explicit lock  per module/connection object.
    #   * Acquire this lock on method entry and release it
    #     on method exit (via the wrapper) 
    #   * When we need to call another module we must censor the
    #     arguments, release the lock for the module/connection we
    #     are in, acquire the lock for the module/connection we want
    #     to run, run it, censor the result, release the run lock,
    #     and acquire the calling lock.
    #   * code objects are censored by wrapping them to execute in the
    #     proper context.
    #   * Can use a global threading.local() object to identify whick
    #     module/connection context a particular thread has checked out, if any
    #
    #   *** Alternative is problematic because many modules need to use
    #       thread synchronization primitives, e.g. mutexes, of their
    #       own, and these are thread-specific. If we start calling
    #       things from different threads, they will break (have to
    #       use semaphores instead) BUT THIS SHOULD BE OK so long
    #       as no thread which calls back out to another module ever
    #       holds a lock (shouldn't happen!) ***
    #
    #   *** Another possible alternative: Use C makecontext/setcontext
    #       and win32 equivalent (there is a ucontext.c library floating around)
    #       to context-switch Python within a single OS thread per-module.
    #       so execute to needing to call another module. Then call out
    #       to C, which releases the GIL, saves the context and creates 
    #       a new context, swaps it in also for python PyThreadState_Swap(),
    #       Now we have a different thread as far as Python is concerned
    #       but the same OS thread. Since python module code should not
    #       hold any locks while calling out to a different module we
    #       should be OK, and as far as the OS is concerned we are
    #       in a single thread 
    #       
    #   **** Suggest "Alternative" (above) with a longer term possibility
    #        of switching to "Another possible alternative" as the
    #        best long-term plan. 
    # OLD IMPLEMENTATION WAS BROKEN
    # ... wrapobj() wants to be a coroutine and therefore
    # must be called through a full chain of await statements
    # ... This is not possible because python magic methods
    #  CAN NOT be coroutines. So we really can't use
    #  an asyncio mainloop for this. 
    #
    
    # Call the specified object (which should be some kind of method or wrapped)
    # in the correct thread context for dgy_mod, and wait for it to return.
    #
    # args and kwargs presumed to be already censored
#
#    if InContext(dgpy_mod):
#        # already in correct context... just do it
#        return obj(*args,**kwargs)
#
#    ## get main loop object
#    #callee_loop=object.__getattribute__(dgpy_mod,"_dgpy_mainloop")
#
#    callerfuture=asyncio.Future()  # future for the caller context, operating based on main loop for the caller's thread
    
#    result=[None,None]  # result, exception

#    async def coro(args,kwargs):
#        try:
#            res=obj(*args,**kwargs)
#            censoredres=censorobj(objname,res))
#            result[0]=censoredres
#            pass
#        except:
#            result[1]=sys.exc_info()[:2]
#            pass
#
#        pass
#    
#    def callback(args,kwargs):
#        coro_obj=coro(args,kwargs)
#        asyncio.ensure_future(coro_obj,callee_loop)
#        pass
#    
#    callee_loop.call_soon_threadsafe(callback(args,kwargs))
#    
#    await callerfuture
    
    
r""" 
    # This first implementation attempt is broken. It just uses a 
    # callback functions, not coroutines

    condvar=threading.Condition()
    condval=[False]
    result=[None,None]  # result, exception
    
    def callback(args,kwargs):
        try:
            res=obj(*args,**kwargs)
            censoredres=censorobj(objname,res))
            result[0]=censoredres
            pass
        except:
            result[1]=sys.exc_info()[:2]
            pass

        condvar.acquire()
        condval[0]=True
        condvar.release()
        pass
            
    
    loop.call_soon_threadsafe(callback,args,kwargs)

    condvar.acquire()
    while not condval[0]:
        condvar.wait()
        pass
    condvar.release()

    if result[1] is not None:
        # Got an exception
        raise ModuleException(result[1][0],result[1][1])

    return result[0]
"""

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


def censorobj(sourcecontext,destcontext,attrname,obj):
    # Make sure obj is a base class type
    # Can be run from any thread that holds the lock on obj

    # put other kinds of objects in an opaque wrapper
    # that can be unwrapped only by methods of our module

    # May be called from either context... needs to be thread safe

    if sourcecontext is destcontext:
        return obj # nothing to do!
    
    if isinstance(obj,bool):
        return bool(obj)

    if isinstance(obj,numbers.Number):
        return int(obj)

    #if  isinstance(obj,float):
    #    return float(obj)

    if isinstance(obj,str):
        return str(obj)


    if type(obj) is Module:
        return obj  # Don't need to wrap module metaclass (below)

    if isinstance(obj,Module):
        # Module classes themselves shouldn't need to be censored
        # (so long as non-thread-safe stuff isn't stored in the class definition)
        return obj
    if isinstance(type(obj),Module):
        # Instances of module classes are self-wrapping, so they don't need to be wrapped either
        return obj
    
    if obj is NotImplemented or obj is None:
        return obj
    
    curcontext=CurContext()
    
    # array, or array or number with units
    if isinstance(obj,np.ndarray) or isinstance(obj,pint.util.SharedRegistryObject): # pint.util.SharedRegistryObject is a base class of all pint numbers with units
        # Theoretically we should probably check the type of the array
        
        # Need to copy array in source context
        if curcontext is not sourcecontext:
            PushThreadContext(sourcecontext)
            try:
                arraycopy=copy.deepcopy(obj) # return copy
                pass
            finally:
                PopThreadContext()
                pass
            pass
        else:
            arraycopy=copy.deepcopy(obj) # return copy
            pass

        if isinstance(obj,np.ndarray):
            arraycopy.flags.writable=False # Make immutable
            pass
        return arraycopy
   
 
    # if obj is an instance of our dgpy.threadsafe abstract base class,
    # then it should be OK
    #sys.stderr.write("type(obj)=%s\n" % (str(type(obj))))
    if isinstance(obj,threadsafe):
        return obj

    

        
    # BUG: Wrappers may not be properly identified via method_attr_types, get wrapped as objects (?)
    # BUG: wrapped wrappers aren't getting properly identified, get rewrapped (don't need to be)
    
    # if a method, return a wrapped copy
    if type(obj) in method_attr_types:
        # if it is a method: Return wrapped copy
        #TargetContext=CurContext()
        
        def wrapper(*args,**kwargs):
            return RunInContext(sourcecontext,obj,obj.__name__,args,kwargs)
            #return RunInContext(sourcecontext,obj,"!!!!!",args,kwargs)
        
        return wrapper

    # If a non-method data descriptor:
    if hasattr(obj,"__get__") and hasattr(obj,"__set__") and not hasattr(obj,"__call__"):
        # return wrapped copy
        return wrapdescriptor(obj)
    
    # for a tuple, return a new tuple with the elements censored
    if isinstance(obj,tuple):
        return tuple([ censorobj(sourcecontext,destcontext,"attrname[%d]" % (subobjcnt),obj[subobjcnt]) for subobjcnt in range(len(obj)) ])
    
    # for a list, return a new list with the elements censored
    if isinstance(obj,list):
        return [ censorobj(sourcecontext,destcontext,"attrname[%d]" % (subobjcnt),obj[subobjcnt]) for subobjcnt in range(len(obj)) ]

    if isinstance(obj,collections.OrderedDict):
        replacement=collections.OrderedDict()
        for key in obj.keys():
            replacement[key]=censorobj(sourcecontext,destcontext,"attrname[%s]" % (str(key)),obj[key])
            pass
        return replacement

    if isinstance(obj,dict):
        replacement = { key: censorobj(sourcecontext,destcontext,"attrname[%s]" % (str(key)),obj[key]) for key in obj.keys() }
        return replacement


    # For other objects, this is an error
    #raise AttributeError("Attribute %s is only accessible from its module's thread context because it is not built from base or immutable types" % (attrname))

    if isinstance(obj,OpaqueWrapper):
        # pre-wrapped object
    
        return obj.attemptunwrap(destcontext)
    
    # For other objects, return an opaque wrapper
    wrappedobj = OpaqueWrapper(obj)

    return wrappedobj

def pm():
    """ pdb debugger... like pdb.pm() """
    frame=inspect.currentframe()
    (etype,evalue,last_tb) = frame.f_back.f_locals["__dgpy_last_exc_info"]
    traceback.print_exception(etype,evalue,last_tb)
    pdb.post_mortem(last_tb)
    pass


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
            InitContext(newobj,args[0]) # add _dgpy_contextlock member
            #import pdb
            #pdb.set_trace()
            PushThreadContext(newobj) # Set context... released in__call__ below
            return newobj
        setattr(cls,"__new__",__new__)
        
        
        # Define __getattribute__ method for the dgpy module class
        # Getattribute wraps all attribute accesses (except magic method accesses)
        # to return wrapped objects, including methods that shift context
        orig_getattribute=getattr(cls,"__getattribute__")

        
        def __getattribute__(self,attrname):
            curcontext=CurContext()
            
            if attrname=="__class__":
                return object.__getattribute__(self,attrname)
                
            try:
                #attr=object.__getattribute__(self,attrname)
                #attr=orig_getattribute(self,attrname)
                
                attr=RunInContext(self,orig_getattribute,"__getattribute__",(self,attrname),{})
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