import sys
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

    def __init__(self, module_name, recdb, len=1000):
        self.module_name = module_name
        self.recdb = recdb
        self.len = len

        transact = recdb.start_transaction()
        self.chanptr = recdb.define_channel("/%s" % (self.module_name), "main", self.recdb.raw())
        recdb.end_transaction(transact)

        self.StartAcquisition()

    def AcquisitionThread(self):
        InitCompatibleThread(self, "_thread")

        while not self._quit:
            transact = self.recdb.start_transaction()
            rec = snde.create_ndarray_ref(self.recdb, self.chanptr, self.recdb.raw(), snde.SNDE_RTN_FLOAT32)
            globalrev = self.recdb.end_transaction(transact)
            rec.rec.metadata = snde.immutable_metadata()
            rec.rec.mark_metadata_done()
            rec.allocate_storage([self.len], False)
            rec.data()[:] = np.sin(np.linspace(0, 10*np.pi, self.len)) + np.random.normal(0,0.01,self.len)
            rec.rec.mark_data_ready()
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