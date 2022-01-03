import threading
from .context import PushThreadContext,PopThreadContext

class Lock(object):
    """ Like threading.lock but drops module context when acquired.
    Can be used with threading.Condition (at least with current Python versions)"""
    _lock = None

    def __init__(self):
        self._lock=threading.Lock()
        pass

    def _at_fork_reinit(self):
        self._lock.at_fork_reinit()
        pass

    def __enter__(self):
        return self.acquire()

    def __exit__(self,*args,**kwargs):
        return self.release()

    def __repr__(self):
        return "<dataguzzler_python.lock.Lock>"

    def release(self):
        self._lock.release()
        PopThreadContext()
        pass
    
    def acquire(self,blocking=True,timeout=-1):
        PushThreadContext(None)
        success = self._lock.acquire(blocking,timeout)
        if not(success):
            PopThreadContext()
            pass
        return success

    def locked(self):
        return self._lock.locked()
    pass


def Condition(lock=None):

    if lock is None:
        lock = Lock()
        pass
    
    if not isinstance(lock,Lock):
        raise ValueError("dataguzzler-python condition variable must be built on dataguzzler-python lock")
    
    return threading.Condition(lock)
