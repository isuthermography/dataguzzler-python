import sys
import serial
import pint
import math

ur = pint.get_application_registry()

# This little bit of logic means that we can work
# equally well inside or outside of dataguzzler_python
if "dataguzzler_python" in sys.modules:
    from dataguzzler_python.dgpy import Module as dgpy_Module
    pass
else:
    dgpy_Module = type
    pass


# NOTE: OK not to use dgpy_Module metaclass
# so long as this class is not direcltly instantiated
# from outside the pololu_rs232servocontroller code
class _pololu_rs232servo(object):
    """Represents single servo"""
    controller = None
    _index = None
    _power = None
    _position = math.nan
    _speed = None
    _range = 15 # fixed at default
    def __init__(self,controller,index):
        self.controller=controller
        self._index=index
        self._speed = 25
        self._power = False
        pass

    # Define a propery for the power
    @property
    def power(self):
        return self._power
    
    @power.setter
    def power(self,status):
        self._power = bool(status)
        if self._power:
            command=b"\x80\x01\x00%c\x4f" % (self._index)
            pass
        else:
            command=b"\x80\x01\x00%c\x0f" % (self._index)
            pass
        self.controller.pol.write(command)
        pass
    
    @property
    def speed(self):
        # Each integer in _speed represents 50 us/s pulse width rate
        return self._speed*50*ur.us/ur.s

    @speed.setter
    def speed(self,spd):
        self._speed=int(round(spd/(50*ur.us/ur.s).to(ur.dimensionless).magnitude))
        
        if self._speed < 1:
            self._speed = 1
            pass
        if self._speed > 127:
            self._speed = 127
            pass
        
        command=b"\x80\x01\x01%c%c" % (self._index,self._speed)
        self.controller.pol.write(command)
        pass

    @property
    def position(self):
        # Each integer step in _position represents range*.5 us of pulse width
        return self._position*self._range*0.5*ur.us
    
    @position.setter
    def position(self,pos):
        """Note: commanding a position turns on the servo"""

        self._position=int(round((pos/(self._range*0.5*ur.us)).to(ur.dimensionless).magnitude))        
        
        if self._position < 0:
            self._position = 0
            pass
        if self._position > 255:
            self._position = 255
            pass
        
        positionhighbyte=(int(self._position) & 0x80) >> 7
        positionlowbyte=int(self._position) & 0x7f
        
        command=b"\x80\x01\x03%c%c%c" % (self._index,positionhighbyte,positionlowbyte)
        self.controller.pol.write(command)
        pass
    
    
class pololu_rs232servocontroller(object,metaclass=dgpy_Module):
    """This class controls an obsolete Pololu 8-port RS232 
    servo controller https://www.pololu.com/product/727/resources
    
    How to use: 
    include("serial.dpi")
    include("pint.dpi")
    from pololu_rs232servocontroller import pololu_rs232servocontroller
    
    port = find_serial_port("....fixme...")
    servocont = pololu_rs232servocontroller("servocont",port)

    servocont.servos[0].speed = 250*ur.us/ur.s
    servocont.servos[1].speed = 250*ur.us/ur.s

    # Note: commanding a position turns on the servo
    servocont.servos[0].position = 1500*ur.us
    servocont.servos[1].position = 1500*ur.us
    
    print("Commanded position [0] = %s" % (str(servocont.servos[0].position)))
    """
    
    pol = None # Serial port filehandle
    servos = None
    def __init__(self,modulename,port="/dev/ttyUSBpololu"):
        # port should be the device name (Linux or MacOS) or COM port (Windows)
        # Usually find this by include("serial.dpi"); then identify the
        # desired port in the serial_ports list and pass its 3rd (hwid)
        # field to find_serial_port()
        
        self.pol=serial.Serial(port,baudrate=9600)
        self.servos=[]
        
        for servonum in range(8): # 0..7
            self.servos.append(_pololu_rs232servo(self,servonum))
            pass
        
        pass


    def close(self):
        self.pol.close()
        self.servos = None # remove references to servo objects so they can be cleaned up. 
        pass
    pass
