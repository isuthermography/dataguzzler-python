import sys
import threading
import numpy as np

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


def InitFreeThread():
    """Use this to initialize a thread that may call dgpy modules or contexts,
    but initialized with no context of its own"""
    InitThread()
    ThreadContext.execution.insert(0,None)
    pass

def InitCompatibleThread(module,namesuffix):
    """Use this to initialize a thread that may freely access member variables, etc. of the given module, even though it isn't the primary thread context of the module"""
    context=SimpleContext()
    InitThreadContext(context,object.__getattribute__(module,"_dgpy_contextname")+"namesuffix",compatible=module)
    PushThreadContext(context)
    pass


def InitContext(context,name,compatible=None):
    object.__setattr__(context,"_dgpy_contextlock",threading.Lock())
    object.__setattr__(context,"_dgpy_contextname",str(name))
    object.__setattr__(context,"_dgpy_compatible",compatible)
    pass

def InitThreadContext(context,name,compatible=None):
    InitThread()
    InitContext(context,name,compatible=compatible)
    pass



def PushThreadContext(context):  # Always pair with a PopThreadContext in a finally clause
    if len(ThreadContext.execution) > 0:
        TopContext = ThreadContext.execution[0]
        if TopContext is not None:
            object.__getattribute__(TopContext,"_dgpy_contextlock").release()
            pass
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
        TopContext = ThreadContext.execution[0]
        if TopContext is not None:
            object.__getattribute__(TopContext,"_dgpy_contextlock").acquire()
            pass
        pass
    
    return context

def CurContext():
    ctx = ThreadContext.execution[0]
    compatible = None
    if ctx is not None:
        compatible = object.__getattribute__(ctx,"_dgpy_compatible")
        pass
    
    return (ctx,compatible)

def InContext(context):
    (cur_ctx,cur_compatible) = CurContext()
    if context is cur_ctx or context is cur_compatible:
        return True
    return False

class SimpleContext(object):
    _dgpy_contextlock=None
    _dgpy_contextname=None
    _dgpy_compatible=None
    pass



def RunUnprotected(routine,*args,**kwargs):
    PushThreadContext(None)
    try:
        ret = routine(*args,**kwargs)
        pass
    finally:
        PopThreadContext()
        pass
    return ret

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

    (parentcontext,pc_compatible)=CurContext()

    if context is parentcontext or context is pc_compatible or hasattr(routine,"_dgpy_nowrapping"):
        # No context switch necessary
        return routine(*args,**kwargs)


    # avoid import loop
    from .censoring import censorobj
    
    
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
        #sys.stderr.write("routine name:%s \n" % (str(routine)))
        res=routine(*censoredargs,**censoredkwargs)
        if not hasattr(res,"_dgpy_nowrapping"):
            censoredres=censorobj(context,parentcontext,".retval",res)
            pass
        else:
            censoredres=res
            pass
        
        pass
    finally:
        PopThreadContext()
        pass
    
    return censoredres
    
