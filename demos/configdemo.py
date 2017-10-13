import sys
import os

from dataguzzler_python import pydg



class DemoClass(object,metaclass=pydg.Module):
    def __init__(self,modulename): # modulename MUST be first parameter
        print("Init the hardware")
        assert(pydg.CurContext() is self)
        pass

    def write(self):
        print("Write to the hardware")
        assert(pydg.CurContext() is self)
        pass

    def read(self):
        print("read from the hardware")
        assert(pydg.CurContext() is self)
        pass

    #def __repr__(self):
    #    return "DemoClass repr!"

    pass

Demo=DemoClass("DemoClass module 1")


class Junk(object):
    pass

JunkObj=Junk()
