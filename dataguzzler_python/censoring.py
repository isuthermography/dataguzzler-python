import os
import os.path
import sys
import numbers
import copy
import types
import collections


import numpy as np
#import pint
from .dgpy import get_pint_util_SharedRegistryObject

from .dgpy import Module
from .dgpy import threadsafe
from .dgpy import wrapdescriptor
from .context import CurContext,RunInContext
from .context import PushThreadContext, PopThreadContext
from .remoteproxy import remoteproxy
from .OpaqueWrapper import OpaqueWrapper,attemptunwrap
from .main_thread import main_thread_context

junk=5
method_wrapper_type=junk.__str__.__class__


builtin_function_or_method_type = os.system.__class__ # os.system should consistently be a builtin


method_attr_types=[ types.MethodType, types.FunctionType, method_wrapper_type, builtin_function_or_method_type ]

def censorobj(sourcecontext,destcontext,attrname,obj):
    # Make sure obj is a base class type
    # Can be run from any thread that holds the lock on obj

    # put other kinds of objects in an opaque wrapper
    # that can be unwrapped only by methods of our module

    # May be called from either context... needs to be thread safe

    # Note: QtCensorObj in QtWrapper largely parallels this
    # changes in this should probably also be made in QtCensorObj()

    if sourcecontext is destcontext or (destcontext is not None and sourcecontext is object.__getattribute__(destcontext,"_dgpy_compatible")):
        return obj # nothing to do!

    
    objclass = object.__getattribute__(obj,"__class__")
    
    if objclass is remoteproxy:
        # remoteproxies can be passed around freely
        return obj

    if objclass is OpaqueWrapper:
        # pre-wrapped object
        return attemptunwrap(obj,destcontext)
    
    if objclass.__name__ == "QtWrapper":
        from .QtWrapper import QtWrapper, qtunwrap
        # pre-wrapped qt object
        if destcontext is main_thread_context:
            return qtunwrap(obj)
        else:
            # already wrapped
            return obj
        pass

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

    if isinstance(obj,bytes):
        return bytes(obj)

    if obj is type or obj is None:
        return obj # never need to wrap "type" or None

    if objclass.__module__ == "spatialnde2":
        # Spatialnde2 wrapped objects are (generally)
        # thread safe so we just pass them through ere
        return obj
    
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
    if isinstance(obj,np.ndarray) or isinstance(obj,get_pint_util_SharedRegistryObject()): # pint.util.SharedRegistryObject is a base class of all pint numbers with units
        # Theoretically we should probably check the type of the array

        if hasattr(obj,"flags"):
            if not obj.flags.writeable:
                return obj # don't worry about immutable objects
            pass
        
        
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
            arraycopy.flags.writeable=False # Make immutable
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

    # If a non-method data descriptor (instance descriptors only -- class descriptors are handled elsewhere):
    if hasattr(obj,"__get__") and hasattr(obj,"__set__") and not hasattr(obj,"__call__"):
        # return wrapped copy
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
