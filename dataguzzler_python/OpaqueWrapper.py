import sys
import os
import threading
import traceback

from .context import RunInContext,ThreadContext

# set of names of Python magic methods
# magicnames omits __new__, __init__, __getattribute__,  
# otherwise this list is based on http://www.rafekettler.com/magicmethods.html    
magicnames=set(["__del__", "__cmp__", "__eq__","__ne__","__lt__","__gt__","__le__", "__ge__", "__pos__", "__neg__", "__abs__", "__invert__", "__round__", "__floor__", "__ceil__", "__trunc__", "__add__", "__sub__", "__mul__", "__floordiv__", "__div__", "__truediv__", "__mod__", "__divmod__", "__pow__", "__lshift__", "__rshift__", "__and__", "__or__", "__xor__", "__radd__", "__rsub__", "__rmul__", "__rfloordiv__", "__rdiv__", "__rtruediv__", "__rmod__", "__rdivmod__", "__rpow__", "__rlshift__", "__rrshift__", "__rand__", "__ror__", "__rxor__", "__iadd__", "__isub__", "__imul__", "__ifloordiv__", "__idiv__", "__itruediv__", "__imod__", "__ipow__", "__ilshift__", "__irshift__", "__iand__", "__ior__", "__ixor__", "__int__", "__long__", "__float__", "__complex__", "__oct__", "__hex__", "__index__", "__trunc__", "__coerce__", "__str__", "__bytes__", "__repr__", "__format__", "__hash__", "__nonzero__", "__dir__", "__sizeof__","__delattr__","__setattr__","__len__","__getitem__", "__setitem__","__delitem__","__iter__","__next__","__reversed__", "__contains__", "__missing__","__call__", "__getattr__","__enter__","__exit__","__get__","__set__","__delete__","__copy__","__deepcopy__","__getinitargs__","__getnewargs__","__getstate__","__setstate__","__reduce__","__reduce_ex__","__subclasscheck__","__instancecheck__"])

# Not all magic functions are wrappable... for example  explicit __str__; also __del__ doesn't make ansy sense. We don't currently support proxys of descriptors ("__get__","__set__", and "__delete__")
magicnames_proxyable=set(["__cmp__", "__eq__","__ne__","__lt__","__gt__","__le__", "__ge__", "__pos__", "__neg__", "__abs__", "__invert__", "__round__", "__floor__", "__ceil__", "__trunc__", "__add__", "__sub__", "__mul__", "__floordiv__", "__div__", "__truediv__", "__mod__", "__divmod__", "__pow__", "__lshift__", "__rshift__", "__and__", "__or__", "__xor__", "__radd__", "__rsub__", "__rmul__", "__rfloordiv__", "__rdiv__", "__rtruediv__", "__rmod__", "__rdivmod__", "__rpow__", "__rlshift__", "__rrshift__", "__rand__", "__ror__", "__rxor__", "__iadd__", "__isub__", "__imul__", "__ifloordiv__", "__idiv__", "__itruediv__", "__imod__", "__ipow__", "__ilshift__", "__irshift__", "__iand__", "__ior__", "__ixor__", "__int__", "__long__", "__float__", "__complex__", "__oct__", "__hex__", "__index__", "__trunc__", "__repr__","__bytes__", "__format__", "__hash__", "__nonzero__", "__dir__", "__sizeof__","__delattr__","__setattr__","__len__","__getitem__", "__setitem__","__delitem__","__iter__","__next__","__reversed__", "__contains__", "__missing__","__call__", "__getattr__","__enter__","__exit__","__copy__","__deepcopy__","__getinitargs__","__getnewargs__","__getstate__","__setstate__"]) #  ,"__subclasscheck__","__instancecheck__"])  NOTE: subclasscheck and/or instancecheck seem to cause exceptions: _abc_subclasscheck(cls, subclass)  TypeError: issubclass() arg 1 must be a class

magicnames_proxyable_ordered = list(magicnames_proxyable)

def forceunwrap(wrapperobj):
    wrappedobj = object.__getattribute__(wrapperobj,"_wrappedobj")

    return wrappedobj
    
def attemptunwrap(wrapperobj,targetcontext=None):
    targetcontext_compatible = None
    if targetcontext is None:
        targetcontext=ThreadContext.execution[0]
        pass
    if targetcontext is not None:
        targetcontext_compatible = object.__getattribute__(targetcontext,"_dgpy_compatible")
        pass

    wrappercontext = object.__getattribute__(wrapperobj,"_originating_context")

    if wrappercontext is targetcontext or wrappercontext is targetcontext_compatible:  
        return object.__getattribute__(wrapperobj,"_wrappedobj")
    else:
        return wrapperobj
    pass

def OpaqueWrapper_dispatch(wrapperobj,methodname, *args, **kwargs):
    wrappedobj = object.__getattribute__(wrapperobj,"_wrappedobj")
    originating_context = object.__getattribute__(wrapperobj,"_originating_context")
    
    #return RunInContext(originating_context,lambda *args,**kwargs: object.__getattribute__(wrappedobj,methodname)(*args, **kwargs),methodname,args,kwargs)
    #sys.stderr.write("methodname=%s; pid=%d\n" % (methodname,os.getpid()))
    #sys.stderr.write("wrappedobj id = %d\n" % (id(wrappedobj)))
    #sys.stderr.write("wrappedobject.__class__.__name__=%s\n" % (object.__getattribute__(wrappedobj,"__class__").__name__))
    #if object.__getattribute__(wrappedobj,"__class__").__name__=="type":
    #    sys.stderr.write("wrappedobject.__name__=%s\n" % (object.__getattribute__(wrappedobj,"__name__")))
    #    pass
    #junk=getattr(wrappedobj,methodname)
    #sys.stderr.write("getattr complete on %d; len(args)=%d\n" % (id(wrappedobj),len(args)))
    #sys.stderr.write("str(wrappedobj)=%s\n" % (str(wrappedobj)))
    #sys.stderr.write("method=%s\n" % (str(junk)))
    return RunInContext(originating_context,lambda *args,**kwargs: getattr(wrappedobj,methodname)(*args, **kwargs),methodname,args,kwargs)
    #try:
    #    ret=RunInContext(originating_context,lambda *args,**kwargs: getattr(wrappedobj,methodname)(*args, **kwargs),methodname,args,kwargs)
    #    pass
    #except:
    #    sys.stderr.write(f"Exception: {str(sys.exc_info()[:2]):s}\n")
    #    sys.stderr.write(f"{traceback.format_exc():s}\n")
    #    raise
    #sys.stderr.write(f"Returned object of type {type(ret).__name__:s}\n")
    #return ret
 
OpaqueWrapper_nonwrapped_attrs=set(["__getattribute__","__str__","__del__","who","help"])

class OpaqueWrapper_prototype(object):
    _originating_context = None
    _wrappedobj = None
    def __init__(self,originating_context,wrappedobj):
        # if save_remote_link is True, this is being created by
        # unpickling a pickled async_conn.ProxyObj, and we should set _remoteproxy_remote_link to the active remote link 
        # if save_remote_link is False, this was created by
        # unpickling a pickled remoteproxy and we should set )remoteproxy_remote_link to None
        object.__setattr__(self,"_originating_context",originating_context)
        object.__setattr__(self,"_wrappedobj",wrappedobj)
        pass
    
        
    def __getattribute__(self,attrname):
        #sys.stderr.write("OpaqueWrapper: getattribute %s\n" % (attrname))
        if attrname in OpaqueWrapper_nonwrapped_attrs:
            return object.__getattribute__(self,attrname)
        return OpaqueWrapper_dispatch(self,"__getattribute__",attrname)
    
    def __str__(self):
        return "OpaqueWrapper 0x%lx for %s" % (id(self),OpaqueWrapper_dispatch(self,"__str__"))

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
            return OpaqueWrapper_dispatch(self,"help")
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
            return OpaqueWrapper_dispatch(self,"who")

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

# override magic methods if present in original. Magic methods need
# to be explicitly added because they cannot be overridden
# with __getattribute__() 


#for magicname in magicnames_proxyable:
    #attrfunc=lambda magicname: lambda self, *args, **kwargs: OpaqueWrapper_dispatch(self,magicname,*args,**kwargs)
    ## Write this method into the class. 
    #setattr(OpaqueWrapper,magicname,attrfunc(magicname))
    #pass

OpaqueWrapper_dict = {} # Dictionary by boolean maps of copies of the OpaqueWrapper class with corresponding magic methods forwarded

# Note: MagicBooleanMap_cache creates a memory leak where classes will not be destroyed. This is better than conflating two classes that might have the same id
MagicBooleanMap_cache = {} # Dictionary by class id of (class, MagicBooleanMap) 
    
def MagicBooleanMap_generate(cls):
    assert(isinstance(cls, type)) # cls should be a class
    listmap = [ hasattr(cls,magicname) for magicname in magicnames_proxyable_ordered] # returns a list of booleans
    intlist = []
    index = 0
    while index < len(listmap):
        bit_index = 0
        int_value = 0
        while bit_index < 31 and index < len(listmap):
            if listmap[index]:
                int_value = int_value | (1 << bit_index)
                pass
            bit_index += 1
            index += 1
            pass
        intlist.append(int_value)
        pass
    return tuple(intlist) # returns hashable tuple of bit mask integers
    
def MagicBooleanMap(cls):
    if id(cls) in MagicBooleanMap_cache:
        (map_cls, map) = MagicBooleanMap_cache[id(cls)]
        return map
    map = MagicBooleanMap_generate(cls)
    MagicBooleanMap_cache[id(cls)] = (cls, map)
    return map

def OpaqueWrapper(originating_context, wrappedobj):
    cls = type(wrappedobj)
    boolean_map = MagicBooleanMap(cls)
    if boolean_map in OpaqueWrapper_dict:
        return OpaqueWrapper_dict[boolean_map](originating_context, wrappedobj)

    # Create derived class because this is the best way to
    # copy a class definition

    class OpaqueWrapper(OpaqueWrapper_prototype):
        def __init__(self, originating_context, wrappedobj):
            super().__init__(originating_context, wrappedobj)
            pass
        pass

    for magicname in magicnames_proxyable:
        if hasattr(cls, magicname):
            attrfunc=lambda magicname: lambda self, *args, **kwargs: OpaqueWrapper_dispatch(self,magicname,*args,**kwargs)
            # Write this method into the class. 
            setattr(OpaqueWrapper,magicname,attrfunc(magicname))
            pass
        pass

    OpaqueWrapper_dict[boolean_map] = OpaqueWrapper

    return OpaqueWrapper(originating_context, wrappedobj)

