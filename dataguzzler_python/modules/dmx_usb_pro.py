import time
import threading
import serial
import numpy as np
import pint


from ..dgpy import Module

from ..dgpy import InitCompatibleThread

from .. import dgpy
ur = pint.get_application_registry()

class enabled_helper(object):
    dmx_instance = None

    def __init__(self,dmx_instance):
        self.dmx_instance = dmx_instance
        pass
    def __getitem__(self,index):
        return self.dmx_instance.get_enabled(index)
    def __setitem__(self,index,value):
        return self.dmx_instance.set_enabled(index,value)
    def __str__(self):
        return str(self.dmx_instance.outputstatus)
    pass

class dmx_usb_pro(metaclass=Module):
    """This class controls a usb interface to the DMX USB Pro 
    light controller. It can be used to turn lights on and off in
    sequence, dim them, etc. 

    Temporal patterns can be loaded from  a spatialnde2 recording
    """
    module_name = None 
    recdb = None #spatialNDE2 recording database. Must be passed on
    #initialization if you want to transmit patterns. 
    fh = None # file handle for serial port
    debug = None
    numchannels = None
    dmxchan = None #channel name to transmit
    dmxchan_dmxoffset = None #the index of the DMX channel on which to
    #transmit the pattern from the spatialNDE2 channel dmxchan
    
   
    dmxthread = None
    dmxmutex = None
    dmxcond = None 


    # Variables locked by dmxmutex
    t0 = None # time of trigger
    # dmxchan_recording_ref = None
    dmxchan_data = None # Copy of data field of dmxchan_recording_ref
    dmxchan_t0 = None
    dmxchan_dt = None
    dmxthread_terminate = None

    outputstatus = None # numpy array of bools indicating which outputs are enabled
    MaxAmpl = None # numpy array of floats giving maximum light level setting for each channel (1.0 = full on)
    CurLevel = None # numpy array of floats giving current level for each channel

    # constants
    # ---------

    # hw_version
    DMX_USB_PRO = 0
    UNKNOWN = 1

    # defines for communication
    SOM_VALUE = 0x7e
    EOM_VALUE = 0xe7
    REPROGRAM_FIRMWARE_LABEL = 1
    REPROGRAM_FLASH_PAGE_LABEL = 1
    RECEIVED_DMX_LABEL = 5
    OUTPUT_ONLY_SEND_DMX_LABEL = 6
    RDM_SEND_DMX_LABEL = 7
    INVALID_LABEL = 0xff


    def __init__(self,module_name,port_name,numchannels,recdb=None,dmxchan=None, dmxchan_dmxoffset=0,debug=False):
        """ port is the device name (Linux or MacOS) or COM port 
        (Windows) corresponding to the virtual serial port of the
        DMX USB Pro Device. You usually find this by 
        include("serial.dpi"); then look at the serial_ports
        variable, find your desired port in the list and pass 
        its third (hwid) field to find_serial_port(), which
        will return the port url you can pass here.
        
        numchannels is the number of devices to control 
        (up to 512)
        
        recdb is a spatialNDE2 recording database and must be provided
        if you want to transmit patterns.

        dmxchan is the spatialNDE2 channel to transmit with a trigger
        It should be a multi_ndarray_recording with a single array
        that is either a 1D function of time or 2D with the first index
        specifying the channel and the second index being time. 

        dmxchan_dmxoffset is the DMX index of the first DMX channel to 
        transmit
        """

        self.module_name = module_name
        self.numchannels = numchannels
        self.debug = debug
        if not self.debug:
            
            self.fh = dgpy.include(dgpy, "serial_device.dpi",port_name=port_name,module_name=module_name,description="DMX USB PRO Device",baudrate=19200)
            pass
        self.outputstatus = np.zeros(numchannels,dtype=np.dtype(np.bool))
        self.CurLevel = np.zeros(numchannels,dtype="d")
        self.MaxAmpl = np.ones(numchannels,dtype="d")
        self.dmxmutex = threading.Lock()
        self.dmxcond = threading.Condition(lock=self.dmxmutex)
        self.enabled = enabled_helper(self)
        self.dmxchan = dmxchan
        self.recdb = recdb
        self.dmxchan_dmxoffset = dmxchan_dmxoffset
        self.dmxthread_terminate = False

        self.dmxthread = threading.Thread(target = self.DMXThreadCode,name = "%s_dmx_thread" % module_name)
        self.dmxthread.start()
        self.SendLightLevels()
        pass

    def __getitem__(self,index):
        with self.dmxmutex:
            return self.CurLevel[index]
        pass
    
    def __setitem__(self,index,value):
        with self.dmxmutex:
            self.CurLevel[index]=value
            pass
        self.SendLightLevels()
        pass

    def __del__(self):
        with self.dmxcond: 
            self.dmxthread_terminate = True
            self.t0 = None
            pass
        self.dmxthread.join()
        pass

    def get_enabled(self,index):
        with self.dmxmutex:
            return self.outputstatus[index]
        pass
    def set_enabled(self,index,value):
        with self.dmxmutex:
            self.outputstatus[index]=value
            pass
        self.SendLightLevels()
        pass

    def trigger(self):
        import spatialnde2 as snde
        with self.dmxcond:
            #extract waveform from spatialNDE2 channel
            g = self.recdb.latest_defined_globalrev()
            r = g.get_recording(self.dmxchan)
            if r.info_state != snde.SNDE_RECS_FULLYREADY:
                raise ValueError("In order to trigger a DMX sequence, the spatialnde2 channel in the latest defined global revision must be fully ready.")
            dmxchan_recording_ref = r.reference_ndarray()
            locktokens = self.recdb.lockmgr.lock_recording_refs([
                (dmxchan_recording_ref, False),
            ],False)
            self.dmxchan_data = dmxchan_recording_ref.data().copy()
            snde.unlock_rwlock_token_set(locktokens)
            
            if len(self.dmxchan_data.shape) == 1:
                timeaxis = 0
                pass
            elif len(self.dmxchan.data.shape) == 2:
                timeaxis = 1
                pass
            else : 
                raise ValueError("error: dmx data channel \"%s\" must be one or two dimensional" % self.dmxchan)
            self.dmxchan_t0 = r.metadata.GetMetaDatumDbl("ande_array-axis%d_offset" % timeaxis, 0.0)
            self.dmxchan_dt = r.metadata.GetMetaDatumDbl("ande_array-axis%d_scale" % timeaxis, 1.0)
            self.t0 = time.monotonic()
            self.dmxcond.notify()
            pass
        pass

            
    def _SendLightLevels_alreadylocked(self):    
        level = np.minimum(self.CurLevel,self.MaxAmpl)*self.outputstatus
        writeval=np.maximum(np.minimum(np.floor((level*256.0)-0.5),255),0).astype(np.uint8)
        if self.debug:
            print("dmx: ","|".join([ str(val) for val in writeval ]))
            pass
        else:
            data_size = 1 + self.numchannels
            to_write = bytes([self.SOM_VALUE,self.OUTPUT_ONLY_SEND_DMX_LABEL,data_size & 0xff,(data_size>>8) & 0xff,0]) + writeval.tobytes() + bytes([self.EOM_VALUE])
            self.fh.write(to_write)
            pass
        pass
    
    def SendLightLevels(self):
        with self.dmxmutex:
            self._SendLightLevels_alreadylocked()
            pass
        pass
    
    def DMXThreadCode(self):
        # print("DMX Thread Code Starting")
        timeout = None
        InitCompatibleThread(self,"dmx_thread")
        while True:
            
            with self.dmxcond:
                # print("DMX Waiting; timeout=%s" % str(timeout))
                self.dmxcond.wait(timeout=timeout)
                # print("DMX Thread Processing")
                if self.t0 is not None:
                    curtime = time.monotonic()
                    data = self.dmxchan_data
                    curindex = int((curtime - self.t0 - self.dmxchan_t0)/self.dmxchan_dt)
                    # print(curindex)
                    if curindex < 0:
                        curindex = 0
                        pass
                    if len(data.shape) == 1:
                        timeaxis = 0
                        pass
                    elif len(data.shape) == 2:
                        timeaxis = 1
                        pass
                    if curindex >= data.shape[timeaxis] - 1:
                        curindex = data.shape[timeaxis] - 1
                        pass
                    
                    if len(data.shape) == 1:
                        sample_data = data[curindex]
                        self.CurLevel[self.dmxchan_dmxoffset] = sample_data
                        pass
                    elif len(data.shape) == 2:
                        sample_data = data[:,curindex]
                        self.CurLevel[(self.dmxchan_dmxoffset):(self.dmxchan_dmxoffset + data.shape[0])] = sample_data
                        pass
                    self._SendLightLevels_alreadylocked()
                    if curindex == data.shape[timeaxis] - 1:
                        timeout = None
                        self.t0 = None
                        self.dmxchan_data = None
                        self.dmxchan_recording_ref = None
                        pass
                    else :
                        nextindex = curindex + 1
                        nexttime = self.dmxchan_t0 + self.dmxchan_dt*nextindex + self.t0
                        timeout = nexttime - curtime
                        pass
                    # print("Timeout",timeout)
                    pass
                elif self.dmxthread_terminate:
                    return
                pass
            pass
        pass
    pass
