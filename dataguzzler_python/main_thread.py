import sys
import time
import os
import signal
import queue
import atexit
import traceback
import threading

from .dgpy import SimpleContext,InitContext,PushThreadContext,PopThreadContext


# Initialization runs in the initialization context

initialization_main_thread_context = SimpleContext()
InitContext(initialization_main_thread_context,"dgpy_initialization")


initialization_sub_thread_context = SimpleContext()
InitContext(initialization_sub_thread_context,"dgpy_initialization")

# Then we spin off the main thread in the main_thread_context
# running whatever is sent to us in the main_thread_queue
main_thread_queue = queue.Queue()
main_thread_context = SimpleContext()

InitContext(main_thread_context,"dgpy_main_thread")



def do_systemexit():
    #PopThreadContext()
    #sys.stderr.write("Attempting to exit; tid=%d!\n" % (threading.get_ident()))
    # we need interrupt main thread with hangup signal, because otherwise we get a hang. But for some reason the exitfuncs (writing out readline history) don't get called in that case, so we run them manually

    global exit_flag,exit_function_lock,exit_function
    
    if threading.current_thread() is threading.main_thread(): # or exit_function is None:
        #sys.stderr.write("do_systemexit() from main thread\n")
        atexit._run_exitfuncs()
        if os.name=="nt":
            os.kill(os.getpid(),signal.CTRL_BREAK_EVENT)
            pass
        else:
            os.kill(os.getpid(),signal.SIGHUP)
            pass
        
        sys.exit(0)
        pass
    else:
        #sys.stderr.write("do_systemexit() triggering main loop to exit\n")

        # Trigger main loop to exit
        with exit_function_lock:
            exit_flag = True
            ex_fn = exit_function
            main_thread_queue.put((None,None,None,None,None))
            pass
        if ex_fn is not None:
            ex_fn()
            pass
        
        # Right now all the places we can be called
        # in this condition just do a return
        # from the console thread.
        # So this lets us let the console thread
        # die if we just return
        
        #time.sleep(10)
        #sys.exit(1)
    pass


def queue_to_run_in_main_thread(exit_function,callable, *args,dgpy_compatible_context=None,**kwargs):
    """This primarily exists to support GUI toolkits that must have 
    their mainloop execute in the original thread that called main().
    Typically you will instantiate your GUI and then call its 
    event loop in a function or method that you pass to this 
    function. 

    The callable will be run in the main_thread_context defined in
    main_thread.py unless dgpy_compatible_context is provided, in 
    which case a new context, "dgpy_main_thread_custom" is created
    that is compatible with the given context, and the callable
    is run in that context. 

    (The callable is free to push and pop thread contexts as needed)

    Be aware that if you pass this function an OpaqueWrapper, that will
    trigger a context change to the wrapped context when called, and
    if your function is an infinite loop it will then monopolize the
    context, except when calling out to functions/methods in other 
    contexts. 

    One handy trick may be to intentionally put your main loop in 
    your module context (usually with PushThreadContext(module_instance)), 
    but put the waiting function in a secondary
    context but with some sort of trigger (perhaps functionality for
    this might be built into dgpy.Module in the future?) to terminate 
    the wait whenever an outside method call is performed. That way
    even inside the main loop and all methods (except for the wait), 
    all code will be executed with the module's lock held, and 
    thread safety worries are dramatically reduced. 

    Another related approach would be some future hook in 
    dgpy.Module to delegate method calls to the main loop, such that
    all code executes in that main loop context. The problem with
    this approach is that it is only safe to make direct synchronous
    calls to outside modules if they can't possibly try to call 
    back to your module, which is hard to guarantee (occupation of 
    the main loop counts as a lock, which is not dropped when you 
    make a method call to another module. It must be considered in 
    the locking order. As long as it is first in the order you are 
    OK but obviously if an indirect call gets somehow back to your
    module, it will try to delegate to the main loop, which is then
    occupied. A possible workaround for this would be to detect
    the case of a recursive call in the main loop context, and 
    execute the method directly rather than delegating. 

    If there's a question about what context any given bit of code
    is executing in, the following lines will print that to 
    standard error as a tuple: 
        from dataguzzler_python.context import FormatCurContext
        sys.stderr.write(FormatCurContext()+"\n")
    The second element of the tuple is the module name, dgpy_main_thread,
    or similar. 

    """
    main_thread_queue.put((exit_function,callable,args,dgpy_compatible_context,kwargs))
    pass

exit_function_lock = threading.Lock() # locks exit_flag, exit_function
exit_flag=None
exit_function = None

def main_thread_run():
    global exit_function_lock
    global exit_flag
    global exit_function
    
    PushThreadContext(main_thread_context)
    exit_flag= False
    while not exit_flag:
        
        dgpy_compatible_context=None
        try:
            with exit_function_lock:
                if exit_flag:
                    break
                pass
            (exit_function,callable,args,dgpy_compatible_context,kwargs) = main_thread_queue.get()
            #sys.stderr.write("Main thread got entry in main_thread_queue: %s\n" % (str((exit_function,callable,args,dgpy_compatible_context,kwargs))))
            
            pass
        except KeyboardInterrupt:
            # Exit immediately on Ctrl-C 
            #sys.stderr.write("Immediate exit!\n")

            # we need interrupt main thread with hangup signal, because otherwise we get a hang. But for some reason the exitfuncs (writing out readline history) don't get called in that case, so we run them manually
            do_systemexit()
            pass


        if exit_flag:
            break
        
        if dgpy_compatible_context is not None:
            custom_context = SimpleContext()
            InitContext(custom_context,"dgpy_main_thread_custom",compatible=dgpy_compatible_context)
            
            PushThreadContext(custom_context)
            pass
        try:
            callable(*args,**kwargs)
            pass
        except KeyboardInterrupt:
            # Exit immediately on Ctrl-C
            # interrupt the keyboard reader thread
            
            # we need interrupt main thread with hangup signal, because otherwise we get a hang. But for some reason the exitfuncs (writing out readline history) don't get called in that case, so we run them manually
            do_systemexit()
            pass
        except:
            sys.stderr.write("Exception in main loop thread:\n")
            (etype,evalue,last_tb)=sys.exc_info()
            traceback.print_exception(etype,evalue,last_tb)
            pass
        finally:
            if dgpy_compatible_context is not None:
                PopThreadContext()
                pass
            pass
        #sys.stderr.write("Main thread function exited; exit_flag = %s\n" % str(exit_flag))
        
        pass

    do_systemexit()
    
    pass
