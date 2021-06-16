import threading

from .context import RunInContext,ThreadContext

# set of names of Python magic methods
# magicnames omits __new__, __init__, __getattribute__,  
# otherwise this list is based on http://www.rafekettler.com/magicmethods.html    
magicnames=set(["__del__", "__cmp__", "__eq__","__ne__","__lt__","__gt__","__le__", "__ge__", "__pos__", "__neg__", "__abs__", "__invert__", "__round__", "__floor__", "__ceil__", "__trunc__", "__add__", "__sub__", "__mul__", "__floordiv__", "__div__", "__truediv__", "__mod__", "__divmod__", "__pow__", "__lshift__", "__rshift__", "__and__", "__or__", "__xor__", "__radd__", "__rsub__", "__rmul__", "__rfloordiv__", "__rdiv__", "__rtruediv__", "__rmod__", "__rdivmod__", "__rpow__", "__rlshift__", "__rrshift__", "__rand__", "__ror__", "__rxor__", "__iadd__", "__isub__", "__imul__", "__ifloordiv__", "__idiv__", "__itruediv__", "__imod__", "__ipow__", "__ilshift__", "__irshift__", "__iand__", "__ior__", "__ixor__", "__int__", "__long__", "__float__", "__complex__", "__oct__", "__hex__", "__index__", "__trunc__", "__coerce__", "__str__", "__bytes__", "__repr__", "__format__", "__hash__", "__nonzero__", "__dir__", "__sizeof__","__delattr__","__setattr__","__len__","__getitem__", "__setitem__","__delitem__","__iter__","__next__","__reversed__", "__contains__", "__missing__","__call__", "__getattr__","__enter__","__exit__","__get__","__set__","__delete__","__copy__","__deepcopy__","__getinitargs__","__getnewargs__","__getstate__","__setstate__","__reduce__","__reduce_ex__","__subclasscheck__","__instancecheck__"])

# Not all magic functions are wrappable... for example  explicit __str__; also __del__ doesn't make ansy sense. We don't currently support proxys of descriptors ("__get__","__set__", and "__delete__")
magicnames_proxyable=set(["__cmp__", "__eq__","__ne__","__lt__","__gt__","__le__", "__ge__", "__pos__", "__neg__", "__abs__", "__invert__", "__round__", "__floor__", "__ceil__", "__trunc__", "__add__", "__sub__", "__mul__", "__floordiv__", "__div__", "__truediv__", "__mod__", "__divmod__", "__pow__", "__lshift__", "__rshift__", "__and__", "__or__", "__xor__", "__radd__", "__rsub__", "__rmul__", "__rfloordiv__", "__rdiv__", "__rtruediv__", "__rmod__", "__rdivmod__", "__rpow__", "__rlshift__", "__rrshift__", "__rand__", "__ror__", "__rxor__", "__iadd__", "__isub__", "__imul__", "__ifloordiv__", "__idiv__", "__itruediv__", "__imod__", "__ipow__", "__ilshift__", "__irshift__", "__iand__", "__ior__", "__ixor__", "__int__", "__long__", "__float__", "__complex__", "__oct__", "__hex__", "__index__", "__trunc__", "__repr__","__bytes__", "__format__", "__hash__", "__nonzero__", "__dir__", "__sizeof__","__delattr__","__setattr__","__len__","__getitem__", "__setitem__","__delitem__","__iter__","__next__","__reversed__", "__contains__", "__missing__","__call__", "__getattr__","__enter__","__exit__","__copy__","__deepcopy__","__getinitargs__","__getnewargs__","__getstate__","__setstate__","__subclasscheck__","__instancecheck__"])

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
    
    return RunInContext(originating_context,lambda *args,**kwargs: object.__getattribute__(wrappedobj,methodname)(*args, **kwargs),methodname,args,kwargs)
    
OpaqueWrapper_nonwrapped_attrs=set(["__str__","__reduce_ex__","__reduce__","__del__"])

class OpaqueWrapper(object):
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
        if attrname in OpaqueWrapper_nonwrapped_attrs:
            return object.__getattribute__(self,attrname)
        return OpaqueWrapper_dispatch(self,"__getattribute__",attrname)
    
    def __str__(self):
        return "OpaqueWrapper 0x%lx for %s" % (id(self),OpaqueWrapper_dispatch(self,"__str__"))

    
        
    #def __subclasscheck__(self):
    #    raise ValueError("Can not check subclass status of a proxy object")
    #
    #def __instancecheck__(self):
    #    raise ValueError("Can not check instance status of a proxy object")
    
    pass

# override magic methods if present in original. Magic methods need
# to be explicitly added because they cannot be overridden
# with __getattribute__() 


for magicname in magicnames_proxyable:
    attrfunc=lambda magicname: lambda self, *args, **kwargs: OpaqueWrapper_dispatch(self,magicname,*args,**kwargs)
    # Write this method into the class. 
    setattr(OpaqueWrapper,magicname,attrfunc(magicname))
    pass
