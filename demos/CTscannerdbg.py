import sys
import os
import numpy as np

from dataguzzler_python import pydg

from dataguzzler_python.dgpy import check_dgpython

check_dgpython()

from dataguzzler_python import dgold
from dataguzzler_python.dgold import cmd as dgcmd



dgold.library("wfmstore.so")
dgold.library("metadata.so")
dgold.library("dio8bit.so")
dgold.library("dglink.so")
dgold.library("fftwlink.so"," nthreads=4\n fftw_estimate\n")


sys.path.append('/usr/local/src/dataguzzler-python/demos')
import kevextube

# Should provide mlockall functionality? 


TIME=dgold.DGModule("TIME","posixtime.so","")
WFM=dgold.DGModule("WFM","wfmio.so","")

AUTH=dgold.DGModule("AUTH","auth.so",r"""
        AuthCode(localhost) = "xyzzy"
	AuthCode(127.0.0.1/32) = "xyzzy"
	AuthCode([::1]/128) = "xyzzy"
""")

ICAPT=dgold.DGModule("ICAPT","edtcapture.so",r""" 
	# device parameters
        devname="pdv" 
        unit=0
        channel=0

        # image size expected from camera (note that only black and white images, 8 or 16 bit, are currently supported. 
	width=6144
        height=1944

        channelname="CAMLINK" # Name of the dataguzzler channel
	numbufs=4 # size of the ring buffer, in frames. 

	calcsync=true # don't allow new acquisitions until previous done processing
	discardtopline=false

        timeout=300 ms

""")
