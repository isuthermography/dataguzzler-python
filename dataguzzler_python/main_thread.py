import sys
import os
import signal
import queue
import atexit

from .dgpy import SimpleContext,InitContext,PushThreadContext,PopThreadContext
from .mainloop import do_systemexit

main_thread_queue = queue.Queue()
main_thread_context = SimpleContext()

InitContext(main_thread_context,"dgpy_main_thread")

def queue_to_run_in_main_thread(callable, *args,dgpy_compatible_context=None,**kwargs):
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
    """
    main_thread_queue.put((callable,args,dgpy_compatible_context,kwargs))
    pass


def main_thread_run():
    
    PushThreadContext(main_thread_context)
    while True:
        exitflag= False
        dgpy_compatible_context=None
        try:
            (callable,args,dgpy_compatible_context,kwargs) = main_thread_queue.get()
            pass
        except KeyboardInterrupt:
            # Exit immediately on Ctrl-C 
            #sys.stderr.write("Immediate exit!\n")

            # we need interrupt main thread with hangup signal, because otherwise we get a hang. But for some reason the exitfuncs (writing out readline history) don't get called in that case, so we run them manually
            do_systemexit()
            pass


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
        
        pass
    
    pass
