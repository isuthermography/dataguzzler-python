import sys
import threading
import numpy as np

from . import get_snde_or_none

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

    snde = get_snde_or_none()
    if snde is not None:
        snde.set_thread_name(None,"dgpy_None")
        pass
    pass


def InitFreeThread():
    """Use this to initialize a thread that may call dgpy modules or contexts,
    but initialized with no context of its own"""
    InitThread()
    ThreadContext.execution.insert(0,None)

    snde = get_snde_or_none()
    if snde is not None:
        snde.set_thread_name(None,"dgpy_None")
        pass

    pass

def InitCompatibleThread(module,namesuffix,no_thread_will_ever_wait_for_this_thread_while_holding_module_context=False):
    """Use this to initialize a thread that may freely access member variables, etc. of the given module, even though it isn't the primary thread context of the module"""
    context=SimpleContext()
    InitThreadContext(context,object.__getattribute__(module,"_dgpy_contextname")+namesuffix,compatible=module,no_thread_will_ever_wait_for_this_thread_while_holding_module_context=no_thread_will_ever_wait_for_this_thread_while_holding_module_context)
    PushThreadContext(context)
    pass


def ContextCompatibleWith(runningcontext,maincontext):
    if runningcontext is maincontext:
        return True
    if object.__getattribute__(runningcontext,"_dgpy_compatible") is maincontext:
        return True
    return False
    

def InitContext(context,name,compatible=None,no_thread_will_ever_wait_for_this_thread_while_holding_module_context=None):
    object.__setattr__(context,"_dgpy_contextlock",threading.Lock())
    object.__setattr__(context,"_dgpy_contextname",str(name))
    object.__setattr__(context,"_dgpy_compatible",compatible)
    if compatible is not None:
        object.__setattr__(context,"_dgpy_no_thread_will_ever_wait_for_this_thread_while_holding_module_context",no_thread_will_ever_wait_for_this_thread_while_holding_module_context)
        pass
    
    pass

def InitThreadContext(context,name,compatible=None,no_thread_will_ever_wait_for_this_thread_while_holding_module_context=None):
    InitThread()
    InitContext(context,name,compatible=compatible,no_thread_will_ever_wait_for_this_thread_while_holding_module_context=no_thread_will_ever_wait_for_this_thread_while_holding_module_context)
    pass



def PushThreadContext(context):  # Always pair with a PopThreadContext in a finally clause
    if not hasattr(ThreadContext,"execution"):
        ThreadContext.execution=[]
        pass
    
    if len(ThreadContext.execution) > 0: 
        TopContext = ThreadContext.execution[0]
        if TopContext is not None:
            if object.__getattribute__(TopContext,"_dgpy_compatible") is not None:
                if context is not None and not(object.__getattribute__(TopContext,"_dgpy_no_thread_will_ever_wait_for_this_thread_while_holding_module_context")):
                    raise RuntimeError("dataguzzler_python.context.PushThreadContext(): Attempt to call an external module from a \"compatible\" thread without the dgpy_no_thread_will_ever_wait_for_this_thread_while_holding_module_context flag set")
                pass
            object.__getattribute__(TopContext,"_dgpy_contextlock").release()
            pass
        pass

    if context is not None:
        object.__getattribute__(context,"_dgpy_contextlock").acquire()
        pass
    ThreadContext.execution.insert(0,context)

    snde = get_snde_or_none()
    if snde is not None:
        if context is not None:
            snde.set_thread_name(None,object.__getattribute__(context,"_dgpy_contextname"))
            pass
        else:
            snde.set_thread_name(None,"dgpy_None")
            pass
        pass

    pass

def PopThreadContext():
    context=ThreadContext.execution.pop(0)
    if context is not None:
        object.__getattribute__(context,"_dgpy_contextlock").release()
        pass
    
    snde = get_snde_or_none()
    if len(ThreadContext.execution) > 0:
        TopContext = ThreadContext.execution[0]
        if TopContext is not None:
            object.__getattribute__(TopContext,"_dgpy_contextlock").acquire()
            pass

        if snde is not None:
            if TopContext is not None:
                snde.set_thread_name(None,object.__getattribute__(TopContext,"_dgpy_contextname"))
                pass
            else:
                snde.set_thread_name(None,"dgpy_None")
                pass
            pass
        pass
    else:
        if snde is not None:
            snde.set_thread_name(None,"dgpy_None")
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

def FormatCurContext():
    (ctx,compatible) = CurContext()

    res="(%d," % (id(ctx))
    if ctx is None:
        res+="None"
        pass
    else:
        res+=object.__getattribute__(ctx,"_dgpy_contextname")
        pass
    if compatible is not None:
        res+=",compatible=%d" % (id(compatible))
        pass
    res+=")"
    return res

def InContext(context):
    (cur_ctx,cur_compatible) = CurContext()
    if context is cur_ctx or context is cur_compatible:
        return True
    return False

def AssertContext(context):
    assert(InContext(context))
    pass

class SimpleContext(object):
    _dgpy_contextlock=None
    _dgpy_contextname=None
    _dgpy_compatible=None
    _dgpy_no_thread_will_ever_wait_for_this_thread_while_holding_module_context=None

    def __enter__(self):
        PushThreadContext(self)
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        PopThreadContext()
        return False
    pass

class UnprotectedContext_Class(object):
    """ Not a real context. Just here to be used with the "with" statement

    Note that variables do not get censored when you enter the unprotected context
    """

    def __enter__(self):
        PushThreadContext(None)
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        PopThreadContext()
        return False
    pass

UnprotectedContext = UnprotectedContext_Class() # create an instance

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
        #sys.stderr.write("No context switch\n")
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
        #sys.stderr.write("routine name:%s in context: %s\n" % (str(routine),FormatCurContext()))
        res=routine(*censoredargs,**censoredkwargs)
        if not hasattr(res,"_dgpy_nowrapping"):
            #sys.stderr.write("Censoring\n")
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
    
