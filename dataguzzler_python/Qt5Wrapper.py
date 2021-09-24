import sys
import os
import threading
import uuid
import types
import numbers
import pint
import copy
import collections
import numpy as np
from .dgpy import threadsafe
from .dgpy import Module
from .context import CurContext, ThreadContext
from matplotlib.backends.qt_compat import QtCore, QtWidgets
from .OpaqueWrapper import OpaqueWrapper, attemptunwrap
from .remoteproxy import remoteproxy

# set of names of Python magic methods
# magicnames omits __new__, __init__, __getattribute__,  
# otherwise this list is based on http://www.rafekettler.com/magicmethods.html    
magicnames=set(["__del__", "__cmp__", "__eq__","__ne__","__lt__","__gt__","__le__", "__ge__", "__pos__", "__neg__", "__abs__", "__invert__", "__round__", "__floor__", "__ceil__", "__trunc__", "__add__", "__sub__", "__mul__", "__floordiv__", "__div__", "__truediv__", "__mod__", "__divmod__", "__pow__", "__lshift__", "__rshift__", "__and__", "__or__", "__xor__", "__radd__", "__rsub__", "__rmul__", "__rfloordiv__", "__rdiv__", "__rtruediv__", "__rmod__", "__rdivmod__", "__rpow__", "__rlshift__", "__rrshift__", "__rand__", "__ror__", "__rxor__", "__iadd__", "__isub__", "__imul__", "__ifloordiv__", "__idiv__", "__itruediv__", "__imod__", "__ipow__", "__ilshift__", "__irshift__", "__iand__", "__ior__", "__ixor__", "__int__", "__long__", "__float__", "__complex__", "__oct__", "__hex__", "__index__", "__trunc__", "__coerce__", "__str__", "__bytes__", "__repr__", "__format__", "__hash__", "__nonzero__", "__dir__", "__sizeof__","__delattr__","__setattr__","__len__","__getitem__", "__setitem__","__delitem__","__iter__","__next__","__reversed__", "__contains__", "__missing__","__call__", "__getattr__","__enter__","__exit__","__get__","__set__","__delete__","__copy__","__deepcopy__","__getinitargs__","__getnewargs__","__getstate__","__setstate__","__reduce__","__reduce_ex__","__subclasscheck__","__instancecheck__"])

# Not all magic functions are wrappable... for example  explicit __str__; also __del__ doesn't make ansy sense. We don't currently support proxys of descriptors ("__get__","__set__", and "__delete__")
magicnames_proxyable=set(["__cmp__", "__eq__","__ne__","__lt__","__gt__","__le__", "__ge__", "__pos__", "__neg__", "__abs__", "__invert__", "__round__", "__floor__", "__ceil__", "__trunc__", "__add__", "__sub__", "__mul__", "__floordiv__", "__div__", "__truediv__", "__mod__", "__divmod__", "__pow__", "__lshift__", "__rshift__", "__and__", "__or__", "__xor__", "__radd__", "__rsub__", "__rmul__", "__rfloordiv__", "__rdiv__", "__rtruediv__", "__rmod__", "__rdivmod__", "__rpow__", "__rlshift__", "__rrshift__", "__rand__", "__ror__", "__rxor__", "__iadd__", "__isub__", "__imul__", "__ifloordiv__", "__idiv__", "__itruediv__", "__imod__", "__ipow__", "__ilshift__", "__irshift__", "__iand__", "__ior__", "__ixor__", "__int__", "__long__", "__float__", "__complex__", "__oct__", "__hex__", "__index__", "__trunc__", "__repr__","__bytes__", "__format__", "__hash__", "__nonzero__", "__dir__", "__sizeof__","__delattr__","__setattr__","__len__","__getitem__", "__setitem__","__delitem__","__iter__","__next__","__reversed__", "__contains__", "__missing__","__call__", "__getattr__","__enter__","__exit__","__copy__","__deepcopy__","__getinitargs__","__getnewargs__","__getstate__","__setstate__"]) #  ,"__subclasscheck__","__instancecheck__"])  NOTE: subclasscheck and/or instancecheck seem to cause exceptions: _abc_subclasscheck(cls, subclass)  TypeError: issubclass() arg 1 must be a class


junk=5
method_wrapper_type=junk.__str__.__class__
builtin_function_or_method_type = os.system.__class__ # os.system should consistently be a builtin
method_attr_types=[ types.MethodType, method_wrapper_type, builtin_function_or_method_type ]

def Qt5WrapDescriptor(towrap):
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
            return dispatcher.DispatchToQtEventLoop(obj,oldget,oldget.__name__,(obj,),{"type": type})
        def __set__(self,obj,value):
            return dispatcher.DispatchToQtEventLoop(obj,oldset,oldset.__name__,(obj,value),{})
        pass
    return descriptor_wrapper(doc)

def Qt5CensorObj(sourcecontext,destcontext,attrname,obj):
    # Make sure obj is a base class type
    # Can be run from any thread that holds the lock on obj

    # put other kinds of objects in an opaque wrapper
    # that can be unwrapped only by methods of our module

    # May be called from either context... needs to be thread safe

    if sourcecontext is destcontext or (destcontext is not None and sourcecontext is object.__getattribute__(destcontext,"_dgpy_compatible")):
        return obj # nothing to do!

    
    objclass = object.__getattribute__(obj,"__class__")
    
    if objclass is remoteproxy:
        # remoteproxies can be passed around freely
        return obj

    if objclass is OpaqueWrapper:
        # pre-wrapped object
        return attemptunwrap(obj,destcontext)

    if isinstance(obj,type):
        # class objects can be passed around freely
        return obj


    if isinstance(obj,bool):
        return bool(obj)

    
    if isinstance(obj,numbers.Number):
        # Presumed to be OK
        return obj

    #if  isinstance(obj,float):
    #    return float(obj)

    if isinstance(obj,str):
        return str(obj)

    if obj is type or obj is None:
        return obj # never need to wrap "type" or None

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
    
    (curcontext, cc_compatible)=CurContext()
    
    # array, or array or number with units
    if isinstance(obj,np.ndarray) or isinstance(obj,pint.util.SharedRegistryObject): # pint.util.SharedRegistryObject is a base class of all pint numbers with units
        # Theoretically we should probably check the type of the array
        
        # Need to copy array in source context
        if curcontext is not sourcecontext and cc_compatible is not sourcecontext:
            arraycopy = ArrayCopyInQtMainThread(obj)
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
            (originating_context,compatible) = CurContext()
            return dispatcher.DispatchToQtEventLoop(originating_context,obj,obj.__name__,args,kwargs)
        
        return wrapper

    # If a non-method data descriptor:
    if hasattr(obj,"__get__") and hasattr(obj,"__set__") and not hasattr(obj,"__call__"):
        # return wrapped copy
        return Qt5WrapDescriptor(obj)
    
    # for a tuple, return a new tuple with the elements censored
    if isinstance(obj,tuple):
        return tuple([ Qt5CensorObj(sourcecontext,destcontext,"attrname[%d]" % (subobjcnt),obj[subobjcnt]) for subobjcnt in range(len(obj)) ])
    
    # for a list, return a new list with the elements censored
    if isinstance(obj,list):
        return [ Qt5CensorObj(sourcecontext,destcontext,"attrname[%d]" % (subobjcnt),obj[subobjcnt]) for subobjcnt in range(len(obj)) ]

    if isinstance(obj,collections.OrderedDict):
        replacement=collections.OrderedDict()
        for key in obj.keys():
            replacement[key]=Qt5CensorObj(sourcecontext,destcontext,"attrname[%s]" % (str(key)),obj[key])
            pass
        return replacement

    if isinstance(obj,dict):
        replacement = { key: Qt5CensorObj(sourcecontext,destcontext,"attrname[%s]" % (str(key)),obj[key]) for key in obj.keys() }
        return replacement


    # For other objects, this is an error
    #raise AttributeError("Attribute %s is only accessible from its module's thread context because it is not built from base or immutable types" % (attrname))

    
    # For other objects, return an opaque wrapper
    wrappedobj = Qt5Wrapper(obj)

    return wrappedobj


class QtDispatch(QtCore.QObject):
    signal = QtCore.pyqtSignal()
    invals = None
    outvals = None
    context = None

    def __init__(self):
        super().__init__()
        self.invals = {}
        self.outvals = {}
        (ctx,pc_compatible)=CurContext()
        self.context = ctx
        self.signal.connect(self._target)

    def _target(self):
        queue = [item for item in self.invals if item not in self.outvals]
        for item in queue:
            try:
                res = self.invals[item]['routine'](*self.invals[item]['args'], **self.invals[item]['kwargs'])
                if not hasattr(res,"_dgpy_nowrapping"):
                    #### TODO:  Check here to see what's blocking at the end
                    censoredres=Qt5CensorObj(self.context,self.invals[item]['context'],".retval",res)
                    pass
                else:
                    censoredres=res
                    pass
                self.outvals[item] = censoredres
            except Exception as err:
                import traceback
                exc_info = sys.exc_info()
                traceback.print_exception(*exc_info)
                self.outvals[item] = None

    def DispatchToQtEventLoop(self, context, routine, routinename, args, kwargs):
        if context is self.context or hasattr(routine,"_dgpy_nowrapping"):
            # No context switch necessary
            return routine(*args,**kwargs)

        guid = uuid.uuid4()
        self.invals[guid] = {}
        self.invals[guid]['context'] = context
        self.invals[guid]['routine'] = routine
        self.invals[guid]['routinename'] = routinename
        
        # Censor args to those that can cross context boundaries
        censoredargs=Qt5CensorObj(context,self.context,routinename+".param",args)
        self.invals[guid]['args'] = censoredargs

        censoredkwargs={}
        for kwarg in kwargs:
            censoredkwargs[str(kwarg)]=Qt5CensorObj(context,self.context,"%s.param[%s]" % (routinename,kwarg),kwargs[kwarg])
            pass

        self.invals[guid]['kwargs'] = censoredkwargs

        self.signal.emit()
        while True:
            if guid in self.outvals:
                return self.outvals[guid]

dispatcher = QtDispatch()

def Qt5Wrapper_dispatch(wrapperobj,methodname, *args, **kwargs):
    wrappedobj = object.__getattribute__(wrapperobj,"_wrappedobj")
    (originating_context,compatible) = CurContext()
    return dispatcher.DispatchToQtEventLoop(originating_context,lambda *args,**kwargs: getattr(wrappedobj,methodname)(*args, **kwargs),methodname,args,kwargs)
    
Qt5Wrapper_nonwrapped_attrs=set(["__getattribute__","__str__","__del__","who","help"])

class Qt5Wrapper(object):
    _wrappedobj = None
    def __init__(self,wrappedobj):
        # if save_remote_link is True, this is being created by
        # unpickling a pickled async_conn.ProxyObj, and we should set _remoteproxy_remote_link to the active remote link 
        # if save_remote_link is False, this was created by
        # unpickling a pickled remoteproxy and we should set )remoteproxy_remote_link to None
        object.__setattr__(self,"_wrappedobj",wrappedobj)
        pass
    
        
    def __getattribute__(self,attrname):
        #sys.stderr.write("Qt5Wrapper: getattribute %s\n" % (attrname))
        if attrname in Qt5Wrapper_nonwrapped_attrs:
            return object.__getattribute__(self,attrname)
        return Qt5Wrapper_dispatch(self,"__getattribute__",attrname)
    
    def __str__(self):
        return "Qt5Wrapper 0x%lx for %s" % (id(self),Qt5Wrapper_dispatch(self,"__str__"))

    def help(self):
        """Convenience method for getting help. OK to override this method"""
        # NOTE: help() code also present in dgpy.py/class Module
        wrappedobj = object.__getattribute__(self,"_wrappedobj")
        orig_help_method = None
        try:
            orig_help_method = getattr(wrappedobj,"help")
            pass
        except AttributeError:
            pass

        if orig_help_method is not None:
            return Qt5Wrapper_dispatch(self,"help")
        return help(self)
        

    def who(self):
        """ .who() method; kind of like dir() but removes special methods, methods with underscores, etc. OK to override this in your classes, in which case your method will be called instead"""

        # NOTE: who() code also present in configfile.py and dgpy.py/class Module

        wrappedobj = object.__getattribute__(self,"_wrappedobj")
        orig_who_method = None
        try:
            orig_who_method = getattr(wrappedobj,"who")
            pass
        except AttributeError:
            pass

        if orig_who_method is not None:
            return Qt5Wrapper_dispatch(self,"who")

        dir_output = dir(wrappedobj)

        filtered_dir_output = [ attr for attr in dir_output if not attr.startswith("_") and not attr=="who" and not attr=="help"]
        filtered_dir_output.sort()

        return filtered_dir_output
    
    #def __subclasscheck__(self):
    #    raise ValueError("Can not check subclass status of a proxy object")
    #
    #def __instancecheck__(self):
    #    raise ValueError("Can not check instance status of a proxy object")
    
    pass


def _Qt5ArrayCopyFunction(array):
    return copy.deepcopy(array)

ArrayCopyInQtMainThread = Qt5Wrapper(_Qt5ArrayCopyFunction)

# override magic methods if present in original. Magic methods need
# to be explicitly added because they cannot be overridden
# with __getattribute__() 


for magicname in magicnames_proxyable:
    attrfunc=lambda magicname: lambda self, *args, **kwargs: Qt5Wrapper_dispatch(self,magicname,*args,**kwargs)
    # Write this method into the class. 
    setattr(Qt5Wrapper,magicname,attrfunc(magicname))
    pass
