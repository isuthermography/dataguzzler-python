import sys
import os
import os.path
from dataguzzler_python.bin.dataguzzler_python import main as dgpy_main 

def main(args=None):
    if args is None:
        args = sys.argv
        pass
    return dgpy_main(args)
