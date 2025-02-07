import sys
import time
from threading import Thread

from dataguzzler_python.dgpy import Module as dgpy_Module
from dataguzzler_python.dgpy import InitCompatibleThread

import spatialnde2 as snde

import numpy as np


class DummyData(object, metaclass=dgpy_Module):
    recdb = None
    chanptr = None
    thread = None
    _quit = False

    def __init__(self, module_name, recdb, len=None, shape=None):
        self.module_name = module_name
        self.recdb = recdb

        assert(shape is not None or len is not None)

        if (shape is not None and len is not None):
            assert(np.prod(shape) == len)
            self.len = len
            self.shape = shape
        elif shape is not None:
            if isinstance(shape, int):
                shape = (shape,)
            elif not hasattr(shape, '__iter__'):
                raise Exception("Shape must be integer or iterable")
            self.len = np.prod(shape)
            self.shape = shape
        elif len is not None:
            self.len = len
            self.shape = (len,)
        else:
            assert(False)

        with recdb.start_transaction() as trans:
            self.chanptr = recdb.define_channel(trans, "/%s" % (self.module_name), "main")

        self.StartAcquisition()

    def AcquisitionThread(self):
        InitCompatibleThread(self, "_thread")

        while not self._quit:
            with self.recdb.start_transaction() as trans:
                rec = snde.create_ndarray_ref(trans, self.chanptr, snde.SNDE_RTN_FLOAT32)
            rec.rec.metadata = snde.immutable_metadata()
            rec.rec.mark_metadata_done()
            rec.allocate_storage(self.shape, False)
            rec.data[:] = np.sin(np.linspace(0, 10*np.pi, self.len)).reshape(self.shape) + np.random.normal(0,0.01,self.len).reshape(self.shape)
            rec.rec.mark_data_ready()
            trans.globalrev_wait()
            time.sleep(0.01)
            pass

    def StartAcquisition(self):
        if self.thread is not None:
            if self.thread.isAlive():
                sys.stderr.write("Warning: Acquisition Thread Already Running\n")
                sys.stderr.flush()
                return
        
        self._quit = False
        self.thread = Thread(target=self.AcquisitionThread, daemon=True)
        self.thread.start()

    def RestartAcquisition(self):
        if self.thread is not None:
            self._quit = True
            while self.thread.isAlive():
                pass    

        self.StartAcquisition()
        


    pass