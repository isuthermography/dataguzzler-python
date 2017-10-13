import sys
import os
import importlib

from ..mainloop import start_tcp_server
from ..mainloop import PyDGConn,OldDGConn
from ..mainloop import process_line
from ..mainloop import write_response

from ..pydg import SimpleContext
from ..pydg import InitThreadContext
from ..pydg import PushThreadContext,PopThreadContext

pydg_config=None

def main(args=None):
    if args is None:
        args=sys.argv
        pass
    

    global pydg_config  #  reminder
    if sys.version_info < (3,6,0):
        raise ValueError("Insufficient Python version: Requires Python 3.6 or above")
    

    ConfigContext=SimpleContext()
    
    InitThreadContext(ConfigContext,"pydg_config") # Allow to run stuff from main thread
    PushThreadContext(ConfigContext)
    
    configfile=args[1]

    # define config file
    spec = importlib.util.spec_from_file_location("pydg_config", configfile)
    # load config file
    pydg_config = importlib.util.module_from_spec(spec)
    sys.modules["pydg_config"]=pydg_config
    # run config file 
    spec.loader.exec_module(pydg_config)

    PopThreadContext()

    
    tcp_thread=start_tcp_server("localhost",1651)
    old_dg_thread=start_tcp_server("localhost",1649,connbuilder=lambda **kwargs: OldDGConn(**kwargs))

    
    MainContext=SimpleContext()
    InitThreadContext(MainContext,"__main__") # Allow to run stuff from main thread
    PushThreadContext(MainContext)

    globaldecls=[]
    localdict={}
    
    while(True):
        InStr=input("pydg> ")
        (rc,ret)=process_line(globaldecls,localdict,InStr)
        write_response(sys.stdout.buffer,rc,repr(ret).encode('utf-8'))
        pass
    
    
    pass
