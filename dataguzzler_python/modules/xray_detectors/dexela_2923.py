import time
import threading
import serial
import numpy as np
import pint


from ...dgpy import Module

from ...dgpy import InitCompatibleThread

from ... import dgpy
# ur = pint.get_application_registry()

class Dexela2923(metaclass=Module):
    """This class controls a Dexela 2923 x-ray imaging detector. It controls the detector over a serial link, but it does not do image acquisition, which is presumed to be handled seperately.
    """
    
    module_name = None 

    _fh = None # file handle for serial port
    debug = None
    ur=None #pint unit registry
    #  _timeout = None #integer timeout in ms
    # _exposure_time= None #integer exposure time in units of 10 us. Note that default units for exposure time are in ms.
    # _high_full_well = None # Boolean if we want to select high full well gain
    # _trig_mode = None #String:"EDGE", "DURATION", "SOFTWARE"
    
    
    # constants
    # ---------
    TRIGMODE_OTHERREGBITS= 0x071F
    TRIGMODE_SOFTWARE= 0
    TRIGMODE_EDGE= 0x0060
    TRIGMODE_DURATION= 0x00A0

    # TRIGMODE_SOFTWARE = 0x061C  #Register 0
    # TRIGMODE_EXTERNAL = 0x067C  #Register 0
    
    
    def __init__(self,module_name,port_name_or_descriptor,trig_mode="SOFTWARE",exposure_time=100,high_full_well=False,debug=False):
        """port_name_or_descriptor is the pyserial device name (Linux
        or MacOS) or COM port (Windows) corresponding to the
        serial port of the detector, OR it can be an opened device that
        acts like a file descriptor (read() and write() methods).
        This usually should come from the camera link interface.

        trig_mode can be "SOFTWARE", "EDGE", or "DURATION"

        exposure_time is in units of ms.

        high_full_well can be True or False.
        
        """

        self.module_name = module_name
        if hasattr(port_name_or_descriptor,"write"):
            #a file descriptor
            self._fh=port_name_or_descriptor
            pass
        else:
            #open pyserial port
            self._fh=dgpy.include(dgpy, "serial_device.dpi", port_name=port_name_or_descriptor,module_name=module_name,description="Dexela xray detector", baudrate=115200)
            pass

        self.debug=debug
        self.ur=pint.get_application_registry()
        self._wakeup_detector()

        self.exposure_time = exposure_time
        self.trig_mode = trig_mode
        self.high_full_well = high_full_well
        
        pass

    def _wakeup_detector(self):
        self._fh.write(b"WC1\r")
        return self._read_response()

    def _readCR(self):
        CR=self._fh.read(1)
        if CR != b"\r":
            raise ValueError(f"{self.module_name:s} Bad response from detector: expected CR character; got 0x{ord(CR):x}.")
        pass
    
    def _read_response(self):
        #Read status byte
        status_byte=self._fh.read(1)
        if status_byte==b"E":
            #Error
            if self.debug:
                print("read_response:got error")
                pass
            self._readCR()
            return ("E",b"")
        elif status_byte==b"X":
            #Success
            self._readCR()
            if self.debug:
                print("read_response:got success (X) ")
                pass            
            return ("X", b"")
        elif status_byte==b"S":
            #Read 5 more characters
            result=self._fh.read(5)
            #!!!*** Somehow we always seem to read zeros!
            self._readCR()
            if self.debug:
                print("read_response:got characters ")
                pass
            return ("S", result)
        else:
            raise ValueError(f"{self.module_name:s} Bad response from detector: expected E, X, or S; got 0x{ord(status_byte):x}.")
        pass
    
    def _write_register(self,sensor_address,register_address,value):
        # Returns "X" for success or raises exception for error
        cmd=f"W{sensor_address:d}{register_address:03d}{value:05d}\r"
        if self.debug:
            print(f"{self.module_name:s}: write register {cmd:s}")
            pass
        self._fh.write(cmd.encode("utf-8"))
        (status,result)=self._read_response()
        if status != "X":
            raise ValueError(f"{self.module_name:s}: write of 0x{value:x} to register 0x{register_address:x} on sensor {sensor_address:d} failed.")
        return status

    def _read_register(self,sensor_address,register_address):
        # Returns register value or raises exception for error
        cmd=f"R{sensor_address:d}{register_address:03d}\r"
        self._fh.write(cmd.encode("utf-8"))
        (status,result)=self._read_response()
        if self.debug:
            print(f"{self.module_name:s}: read register {cmd:s} returns ({status:s},{result.decode('utf-8'):s})")
            pass
        if status != "S":
            raise ValueError(f"{self.module_name:s}: read from register 0x{register_address:x} on sensor {sensor_address:d} failed.")
        return int(result)
        
    
    @property
    def exposure_time(self):
        """ get or set the exposure time. Default units are ms."""
        lsword=self._read_register(1,11)
        msword=self._read_register(1,12)

        exposure_time_10us=(msword << 16) | lsword #integer exposure time in units of 10 us
        exposure_time_quantity=(exposure_time_10us / 100.) * self.ur.millisecond
        return exposure_time_quantity

    @exposure_time.setter
    def exposure_time(self,value):
        value=self.ur.Quantity(value) #get a pint quantity
        if value.unitless:
            value=value*self.ur.millisecond
            pass
        exposure_time_ms=float(value/self.ur.millisecond)
        exposure_time_10us=exposure_time_ms*100.
        exposure_time_raw=int(round(exposure_time_10us))

        if exposure_time_raw < 0:
            raise ValueError(f"{self.module_name:s}: exposure time cannot be negative.")
        if exposure_time_raw >= (1<<32):
            raise ValueError(f"{self.module_name:s}: exposure time too large.")
        lsword=exposure_time_raw & 0xffff
        msword=(exposure_time_raw >>16) & 0xffff
        self._write_register(0,11,lsword)
        self._write_register(0,12,msword)
        pass
    
    @property
    def high_full_well(self):
        """The gain (high_full_well) is bit 3(0x4) of register 3"""
        reg3=self._read_register(1,3)
        return bool(reg3 & 0x4)

    @high_full_well.setter
    def high_full_well(self,value):
        value=bool(value)
        reg3=self._read_register(1,3)
        if value:
            reg3 |= 0x4
            pass
        else:
            reg3 &= ~0x4
            pass
        self._write_register(0,3,reg3)
        pass

    @property
    def trig_mode(self):
        reg0=self._read_register(1,0)
        raw_value=reg0 & ~self.TRIGMODE_OTHERREGBITS
        return {self.TRIGMODE_SOFTWARE:"SOFTWARE",self.TRIGMODE_EDGE:"EDGE",self.TRIGMODE_DURATION:"DURATION"}[raw_value]

    @trig_mode.setter
    def trig_mode(self,value):
        if value== "SOFTWARE":
            raw_value=self.TRIGMODE_SOFTWARE
            pass
        elif value == "EDGE":
            raw_value=self.TRIGMODE_EDGE
            pass
        elif value == "DURATION":
            raw_value = self.TRIGMODE_DURATION
            pass
        else:
            raise ValueError(f"{self.module_name:s}: unknown trigger mode {value:s}.")
        reg0=self._read_register(1,0)
        reg0 &= self.TRIGMODE_OTHERREGBITS
        reg0 |= raw_value
        self._write_register(0,0,reg0)
        pass
    
    
    pass

