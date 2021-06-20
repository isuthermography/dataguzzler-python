import sys
import threading

# set of names of Python magic methods
# magicnames omits __new__, __init__, __getattribute__,  
# otherwise this list is based on http://www.rafekettler.com/magicmethods.html    
magicnames=set(["__del__", "__cmp__", "__eq__","__ne__","__lt__","__gt__","__le__", "__ge__", "__pos__", "__neg__", "__abs__", "__invert__", "__round__", "__floor__", "__ceil__", "__trunc__", "__add__", "__sub__", "__mul__", "__floordiv__", "__div__", "__truediv__", "__mod__", "__divmod__", "__pow__", "__lshift__", "__rshift__", "__and__", "__or__", "__xor__", "__radd__", "__rsub__", "__rmul__", "__rfloordiv__", "__rdiv__", "__rtruediv__", "__rmod__", "__rdivmod__", "__rpow__", "__rlshift__", "__rrshift__", "__rand__", "__ror__", "__rxor__", "__iadd__", "__isub__", "__imul__", "__ifloordiv__", "__idiv__", "__itruediv__", "__imod__", "__ipow__", "__ilshift__", "__irshift__", "__iand__", "__ior__", "__ixor__", "__int__", "__long__", "__float__", "__complex__", "__oct__", "__hex__", "__index__", "__trunc__", "__coerce__", "__str__", "__bytes__", "__repr__", "__format__", "__hash__", "__nonzero__", "__dir__", "__sizeof__","__delattr__","__setattr__","__len__","__getitem__", "__setitem__","__delitem__","__iter__","__next__","__reversed__", "__contains__", "__missing__","__call__", "__getattr__","__enter__","__exit__","__get__","__set__","__delete__","__copy__","__deepcopy__","__getinitargs__","__getnewargs__","__getstate__","__setstate__","__reduce__","__reduce_ex__","__subclasscheck__","__instancecheck__"])

# Not all magic functions are proxyable... for example doesn't make sense to proxy __del__, and we provide an explicit __str__. We don't currently support proxys of descriptors ("__get__","__set__", and "__delete__")
magicnames_proxyable=set(["__cmp__", "__eq__","__ne__","__lt__","__gt__","__le__", "__ge__", "__pos__", "__neg__", "__abs__", "__invert__", "__round__", "__floor__", "__ceil__", "__trunc__", "__add__", "__sub__", "__mul__", "__floordiv__", "__div__", "__truediv__", "__mod__", "__divmod__", "__pow__", "__lshift__", "__rshift__", "__and__", "__or__", "__xor__", "__radd__", "__rsub__", "__rmul__", "__rfloordiv__", "__rdiv__", "__rtruediv__", "__rmod__", "__rdivmod__", "__rpow__", "__rlshift__", "__rrshift__", "__rand__", "__ror__", "__rxor__", "__iadd__", "__isub__", "__imul__", "__ifloordiv__", "__idiv__", "__itruediv__", "__imod__", "__ipow__", "__ilshift__", "__irshift__", "__iand__", "__ior__", "__ixor__", "__int__", "__long__", "__float__", "__complex__", "__oct__", "__hex__", "__index__", "__trunc__", "__repr__","__bytes__", "__format__", "__hash__", "__nonzero__", "__dir__", "__sizeof__","__delattr__","__setattr__","__len__","__getitem__", "__setitem__","__delitem__","__iter__","__next__","__reversed__", "__contains__", "__missing__","__call__", "__getattr__","__enter__","__exit__","__copy__","__deepcopy__","__getinitargs__","__getnewargs__","__getstate__","__setstate__"]) # ,"__subclasscheck__","__instancecheck__"]) NOTE: subclasscheck and/or instancecheck seem to cause exceptions: _abc_subclasscheck(cls, subclass)  TypeError: issubclass() arg 1 must be a class

# active_remote_link.remote_link is the link (DGConn) object of any currently executing (client-side) remote link or None
# This is used to pass values to the pickler/unpickler for proxy objects so they
# can identify which remote link they came from so that if you try to call them, they can execute over the link.
active_remote_link=threading.local() 
active_remote_link.remote_link=None


def set_active_remote_link_this_thread(remote_link):
    if hasattr(active_remote_link,"remote_link"):
    
        if remote_link is not None:
            assert(active_remote_link.remote_link is None)
            pass
        else:
            assert(active_remote_link.remote_link is not None)
            pass
        pass
    
    active_remote_link.remote_link=remote_link
    pass


def remoteproxy_dispatch(proxyobj,methodname, *args, **kwargs):
    remote_link = object.__getattribute__(proxyobj,"_remoteproxy_remote_link")
    remoteid = object.__getattribute__(proxyobj,"_remoteproxy_remoteid")

    return remote_link.call_remote_method(proxyobj,methodname, args, kwargs)
    
remoteproxy_nonproxied_attrs=set(["__getattribute__","__str__","__reduce_ex__","__reduce__","__del__"])

class remoteproxy(object):
    #_remoteproxy_classname=None
    _remoteproxy_remoteid=None
    _remoteproxy_remote_link=None # remote link this is a proxy for
    #_proxytype=proxytype
    #_proxyinstance=proxyinstance
    def __init__(self,remoteid,save_remote_link):
        # if save_remote_link is True, this is being created by
        # unpickling a pickled async_conn.ProxyObj, and we should set _remoteproxy_remote_link to the active remote link 
        # if save_remote_link is False, this was created by
        # unpickling a pickled remoteproxy and we should set )remoteproxy_remote_link to None
        object.__setattr__(self,"_remoteproxy_remoteid",remoteid)
        if save_remote_link:
            object.__setattr__(self,"_remoteproxy_remote_link",active_remote_link.remote_link)
            pass
        else:
            object.__setattr__(self,"_remoteproxy_remote_link",None)
            pass
        pass
    
        
    def __getattribute__(self,attrname):
        if attrname in remoteproxy_nonproxied_attrs:
            return object.__getattribute__(self,attrname)
        return remoteproxy_dispatch(self,"__getattribute__",attrname)
    
    def __str__(self):
        return "remoteproxy 0x%lx for remote 0x%lx %s" % (id(self),object.__getattribute__(self,"_remoteproxy_remoteid"),remoteproxy_dispatch(self,"__str__"))

    def __reduce__(self):
        # When proxy is re-pickled transit back to its origin
        # it then gets depickled in an environment where
        # active_remote_link.remote_link is None, so it can be
        # readily identified and replaced by the object it is
        # referring to
        if active_remote_link.remote_link is None:
            raise ValueError("Pickling remoteproxy object without an active remote link")
        if object.__getattribute__(self,"_remoteproxy_remote_link") is not active_remote_link.remote_link:
            raise ValueError("Remote link mismatch while pickling remoteproxy object")
        idval=object.__getattribute__(self,"_remoteproxy_remoteid")
        return (remoteproxy,(idval,False))

    def __del__(self):
        """When this proxy is no longer referenced, we want to
        indicate to the remote process that the proxy is gone so 
        that the proxied object can be dereferenced"""
        idval=object.__getattribute__(self,"_remoteproxy_remoteid")
        remote_link = object.__getattribute__(self,"_remoteproxy_remote_link")
        if remote_link is not None:

            #sys.stderr.write("remote_link class=%s\n" % (object.__getattribute__(remote_link,"__class__").__name__))
            
            conninfo = remote_link.conninfo
            if object.__getattribute__(conninfo,"__class__").__name__=="OpaqueWrapper": #  Sometimes conninfo might be a wrapper.... if so, unwrap it
                conninfo = object.__getattribute__(conninfo,"_wrappedobj")
                pass
        
            #sys.stderr.write("conninfo class=%s\n" % (object.__getattribute__(conninfo,"__class__").__name__))
            
            
            conninfo_loop = object.__getattribute__(conninfo,"loop")
            #from .dgpy import OpaqueWrapper # avoid import loop
            if object.__getattribute__(conninfo_loop,"__class__").__name__=="OpaqueWrapper": #  is OpaqueWrapper:
                # Sometimes self.conninfo is actually a module in which
                # case we theoretically don't have direct access to its
                # contents from the execution threads. In this case it is
                # OK so we bypass
                conninfo_loop=object.__getattribute__(conninfo_loop,"_wrappedobj")
                pass
            
            
            conninfo_loop.call_soon_threadsafe(remote_link.releaseproxy,idval)
            pass
        pass
    
        
    #def __subclasscheck__(self):
    #    raise ValueError("Can not check subclass status of a proxy object")
    #
    #def __instancecheck__(self):
    #    raise ValueError("Can not check instance status of a proxy object")
    
    pass

# override magic methods if present in original. Magic methods need
# to be explicitly added because they cannot be overridden
# with __getattribute__() 


#setattr(wrappedclass,"__str__",lambda self, *args, **kwargs: self._wrap(object.__getattribute__(class_to_wrap,"__str__"),args,kwargs))

for magicname in magicnames_proxyable:
    attrfunc=lambda magicname: lambda self, *args, **kwargs: remoteproxy_dispatch(self,magicname,*args,**kwargs)
    # Write this method into the class. 
    setattr(remoteproxy,magicname,attrfunc(magicname))
    pass
