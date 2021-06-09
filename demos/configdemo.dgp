import sys
import os

from dataguzzler_python import dgpy
from dataguzzler_python.dgpy import u
from dataguzzler_python.dgpy import check_dgpython

check_dgpython()



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
