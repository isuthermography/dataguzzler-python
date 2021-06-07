import sys
import os

from dataguzzler_python import dgpy
from dataguzzler_python.dgpy import u
from dataguzzler_python.dgpy import check_dgpython

check_dgpython()

from dataguzzler_python import dgold
from dataguzzler_python.dgold import cmd as dgcmd


dgold.library("wfmstore.so")
dgold.library("metadata.so")
dgold.library("dio8bit.so")
dgold.library("dglink.so")
dgold.library("fftwlink.so"," nthreads=4\n fftw_estimate\n")

TIME=dgold.DGModule("TIME","posixtime.so","")
WFM=dgold.DGModule("WFM","wfmio.so","")

AUTH=dgold.DGModule("AUTH","auth.so",r"""
        AuthCode(localhost) = "xyzzy"
	AuthCode(127.0.0.1/32) = "xyzzy"
	AuthCode([::1]/128) = "xyzzy"
""")



class DemoClass(object,metaclass=dgpy.Module):
    def __init__(self,modulename): # modulename MUST be first parameter
        print("Init the hardware")
        assert(dgpy.CurContext() is self)
        pass

    def write(self):
        print("Write to the hardware")
        assert(dgpy.CurContext() is self)
        pass

    def read(self):
        print("read from the hardware")
        assert(dgpy.CurContext() is self)
        pass

    #def __repr__(self):
    #    return "DemoClass repr!"

    pass

Demo=DemoClass("DemoClass module 1")


class Junk(object):
    pass

JunkObj=Junk()
