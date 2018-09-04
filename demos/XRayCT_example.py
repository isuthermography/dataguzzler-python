import sys
import os
import numpy as np

from limatix.dc_value import numericunitsvalue as nuv

from dataguzzler_python import pydg

from dataguzzler_python import dgold
from dataguzzler_python.dgold import cmd as dgcmd
from dataguzzler_python.dgold import DataguzzlerError


uA = nuv("1 microamp")
kV = nuv("1 kilovolt")

dgold.library("wfmstore.so")
dgold.library("metadata.so")
dgold.library("dio8bit.so")
dgold.library("dglink.so")
dgold.library("fftwlink.so"," nthreads=4\n fftw_estimate\n")

from dataguzzler_python import savewfm  # must be AFTER wfmstore.so library is loaded 

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

stdmathinit=open("/usr/local/dataguzzler/conf/m4/stdinit.pymathm4","r").read()
stdmathfunc=open("/usr/local/dataguzzler/conf/m4/stdfunc.pymathm4","r").read()

MATH=dgold.DGModule("MATH","wfmmath.so",r""" 
  numthreads = 4 # -1 would mean use number of CPU's + 1 
  #debugmode=true
 
  pymath {
    # Support Python-based math functions
    %s
    %s 

    # (can add custom math functions here)
  }

""" % (stdmathinit,stdmathfunc))


ICAPT=dgold.DGModule("ICAPT","edtcapture.so",r""" 
	# device parameters
        devname="pdv" 
        unit=0
        channel=0

        # image size expected from camera (note that only black and white images, 8 or 16 bit, are currently supported. 
	width=1024
        height=1024

        channelname="CAMLINK" # Name of the dataguzzler channel
	numbufs=32 # size of the ring buffer, in frames. should generally be at least the # of averages you are using

	calcsync=true # don't allow new acquisitions until previous done processing
	discardtopline=false

        timeout=300 ms

""")




tube=kevextube.kevextube("/dev/ttyUSBXRayTube")
tube.BeamVoltage(130.0*kV)
tube.BeamCurrent(122.0*uA)



class CTScan(object,metaclass=pydg.Module):
    start=None
    step=None
    endplusone=None

    interrupt=None
    running=None
    _numavgs=None

    @property
    def numavgs(self):
        return self._numavgs
    
    @numavgs.setter
    def numavgs(self,numavgs):
        numavgs=int(numavgs)
        MATH.cmd("def calibavg=avgonce(calibimg,%d)" % (numavgs))
        self._numavgs=numavgs
        pass


    def __init__(self,modulename,start=0.0,step=1.0,endplusone=360.0,numavgs=16): # modulename MUST be first parameter
        #print("Init the hardware")
        assert(pydg.CurContext() is self)

        self.start=start
        self.step=step
        self.endplusone=endplusone
        self.numavgs=numavgs

        self.interrupt=False
        self.running=False

        pass
    
    def run(self):
        assert(pydg.CurContext() is self)

        MOT.cmd("RY:STATUS ON")
        # Clear out IRstack
        MOT.cmd("RY 0")
        MOT.cmd("RY:WAIT")
        MATH.cmd("CLEAR CTcube")
        
        ICAPT.cmd("CALCSYNC FALSE")
        ICAPT.cmd("DISABLE")
        MATH.cmd("SETSTATICMETADATUM(calibavg) Units3 \"degrees\"")
        MATH.cmd("SETSTATICMETADATUM(calibavg) Coord3 \"Angle\"")
        

        self.running=True
        angles=np.arange(self.start,self.endplusone,self.step)
        for angleidx in range(angles.shape[0]):
            angle=angles[angleidx]
            
            if self.interrupt: 
                self.interrupt=False
                break

            # Start motion.... 
            MOT.cmd("RY %f deg" % (angle))

            # Now do time-consuming stuff during motion
            if angleidx > 0: # everything but first iteration
                WFM.cmd("COPY calibavg CTangle") # Provide new waveform for CTcube to accumulate
                pass
            MATH.cmd("SETSTATICMETADATUM(calibavg) IniVal3 %.12e" % (angle))
            MATH.cmd("CLEAR calibavg") # Allow averaging to start
            rev=int(WFM.cmd("REVISION? calibavg").split()[2])

            MOT.cmd("RY:WAIT")  
            TIME.cmd("DELAY 0.25s") # Let motion finish moving and let things settle
            
            ICAPT.cmd("ENABLE")
            WFM.cmd("REVISION calibavg %d" % (rev+self._numavgs))
            #MATH.cmd("WAITAVG calibavg") # Allow averaging to start
            ICAPT.cmd("DISABLE")

            if angleidx==angles.shape[0]-1: # last iteration
                WFM.cmd("COPY calibavg CTangle") # Provide new waveform for CTcube to accumulate
                pass
            pass
            
        MATH.cmd("DELMETADATUM(calibavg) Units3")
        MATH.cmd("DELMETADATUM(calibavg) Coord3")
        MATH.cmd("DELMETADATUM(calibavg) IniVal3")

        ICAPT.cmd("ENABLE")
        ICAPT.cmd("CALCSYNC TRUE")
        self.running=False
        tube.status(False) # Automatically shut down X-Ray source at end of scan
        return None

    def abort(self):
        self.interrupt=True
        # wait for the interrupt to actually occur here 
        
        while self.running:
            TIME.cmd("DELAY 1 s")
            pass

        pass

    #def __repr__(self):
    #    return "DemoClass repr!"

    pass

CTScan=CTScan("CTScan module")




def capturedark(wait=True):
    MATH.cmd("def darkimg=avgonce(rawimg,64)")
    MATH.cmd("CLEAR darkimg")
    if wait:
        MATH.cmd("WAITAVG darkimg")
        pass
    pass

def captureflood(wait=True):
    FloodSave.deletewfm("floodimg")
    MATH.cmd("def floodimg=avgonce(diffimg,64)")
    MATH.cmd("CLEAR floodimg")
    if wait:
        MATH.cmd("WAITAVG floodimg")
        pass
    pass

FloodSave=savewfm.savewfm("FloodSave")
floodpath="~/XRay_floodimages"


def saveflood():
    voltage_kv=tube.BeamVoltage().value("kilovolts")
    current_ua=tube.BeamCurrent().value("microamps")
    FloodSave.savewfms(os.path.expanduser(floodpath),"flood_%fkV_%fuA.dgs" % (voltage_kv,current_ua),( "floodimg", ))
    pass

def loadflood():
    voltage_kv=tube.BeamVoltage().value("kilovolts")
    current_ua=tube.BeamCurrent().value("microamps")
    try: 
        MATH.cmd("UNDEF floodimg")
        pass
    except DataguzzlerError:
        pass

    FloodSave.loadwfms(os.path.expanduser(floodpath),"flood_%fkV_%fuA.dgs" % (voltage_kv,current_ua))
    pass


MATH.cmd("def rawimg=dexeladeinterlace2923(CAMLINK,true)")
MATH.cmd("def diffimg=sub(rawimg,darkimg)")
MATH.cmd("def calibimg=div(diffimg,floodimg)")
MATH.cmd("def CTcube=accum(CTangle,360)")

capturedark(wait=False)
