import os
import os.path
import sys
import numbers
import copy
import types
import collections


import numpy as np
import pint

from .dgpy import Module
from .dgpy import threadsafe
from .context import CurContext
from .remoteproxy import remoteproxy
from .OpaqueWrapper import OpaqueWrapper,attemptunwrap

junk=5
method_wrapper_type=junk.__str__.__class__


builtin_function_or_method_type = os.system.__class__ # os.system should consistently be a builtin


method_attr_types=[ types.MethodType, method_wrapper_type, builtin_function_or_method_type ]

def censorobj(sourcecontext,destcontext,attrname,obj):
    # Make sure obj is a base class type
    # Can be run from any thread that holds the lock on obj

    # put other kinds of objects in an opaque wrapper
    # that can be unwrapped only by methods of our module

    # May be called from either context... needs to be thread safe

    if sourcecontext is destcontext or (destcontext is not None and sourcecontext is object.__getattribute__(destcontext,"_dgpy_compatible")):
        return obj # nothing to do!

    if object.__getattribute__(obj,"__class__") is remoteproxy:
        # remoteproxies can be passed around freely
        return obj

    if object.__getattribute__(obj,"__class__") is OpaqueWrapper:
        # pre-wrapped object
        return attemptunwrap(obj,destcontext)
    
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
    
    (curcontext, cc_compatible)=CurContext()
    
    # array, or array or number with units
    if isinstance(obj,np.ndarray) or isinstance(obj,pint.util.SharedRegistryObject): # pint.util.SharedRegistryObject is a base class of all pint numbers with units
        # Theoretically we should probably check the type of the array
        
        # Need to copy array in source context
        if curcontext is not sourcecontext and cc_compatible is not sourcecontext:
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

    
    # For other objects, return an opaque wrapper
    wrappedobj = OpaqueWrapper(sourcecontext,obj)

    return wrappedobj
