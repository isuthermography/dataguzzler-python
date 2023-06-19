import time
import threading
import serial
import numpy as np
import pint


from ..dgpy import Module

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
    

class dmx_usb_pro(metaclass=Module):
    """This class controls a usb interface to the DMX USB Pro 
    light controller. It can be used to turn lights on and off in
    sequence, dim them, etc. 

    Temporal patterns can be loaded from  a spatialnde2 recording
    """

    fh = None # file handle for serial port
    debug = None
    numchannels = None
    dmxchan = None

    dmxthread = None
    dmxmutex = None


    # Variables locked by dmxmutex
    t0 = None # time of trigger

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


    def __init__(self,module_name,port,numchannels,debug=False):
        """ port is the device name (Linux or MacOS) or COM port 
        (Windows) corresponding to the virtual serial port of the
        DMX USB Pro Device. You usually find this by 
        include("serial.dpi"); then look at the serial_ports
        variable, find your desired port in the list and pass 
        its third (hwid) field to find_serial_port(), which
        will return the port url you can pass here.
        
        numchannels is the number of devices to control 
        (up to 512)"""

        
        self.numchannels = numchannels
        self.debug = debug
        if not self.debug:
            
            self.fh = serial.serial_for_url(port,baudrate=19200)
            pass
        self.outputstatus = np.zeros(numchannels,dtype=np.dtype(np.bool))
        self.CurLevel = np.zeros(numchannels,dtype="d")
        self.MaxAmpl = np.ones(numchannels,dtype="d")
        self.dmxmutex = threading.Lock()
        self.enabled = enabled_helper(self)
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
    
    def SendLightLevels(self):
        with self.dmxmutex:
            
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
    pass
