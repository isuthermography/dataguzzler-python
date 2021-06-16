# This virtual instrument represents
# a shutter controlled by two servos
# (one of which is configured as reversing
# so we can give them the same pulses)

import time
import pint

from dataguzzler_python.dgpy import Module as dgpy_Module
from dataguzzler_python.dgpy import RunUnprotected

ur = pint.get_application_registry()

class servoshutter(metaclass=dgpy_Module):
    """This class controls a shutter made from two servos (one reversing)
    controlled by an obsolete Pololu 8-port RS232 
    servo controller https://www.pololu.com/product/727/resources
    
    How to use: 

    In your config file: 
      include("serial.dpi")
      include("pint.dpi")
      from pololu_rs232servocontroller import pololu_rs232servocontroller
      from servoshutter import servoshutter

      port = find_serial_port("....fixme...")
      servocont = pololu_rs232servocontroller("servocont",port)

      shutter = servoshutter("shutter",servocont.servos[0],servocont.servos[1])

    Then on the dataguzzler-python console: 
      dgpy> shutter.status="OPEN"
    """

    servo1 = None
    servo2 = None
    _servo_speed = None
    servo_open = None
    servo_closed = None
    _lastchanged = None
    desired_state = None
    _enabled = None
    def __init__(self,
                 modulename,
                 servo1,
                 servo2,
                 initial_state = "CLOSED",
                 servo_speed = 500*ur.us/ur.s,
                 servo_open = 843.75*ur.us,
                 servo_closed = 1706.25*ur.us
                 ):
        self.servo1 = servo1
        self.servo2 = servo2
        self.desired_state = initial_state
        self.servo_open = servo_open
        self.servo_closed = servo_closed
        self._servo_speed = servo_speed
        
        self.enabled = False
        self._lastchanged=time.monotonic()


        # Program servo speeds
        self.servo1.speed = servo_speed
        self.servo2.speed = servo_speed

        pass

    @property
    def status(self):
        if not self.enabled:
            return "DISABLED"
        curtime = time.monotonic()

        timedelta = (curtime-self._lastchanged)*ur.s

        if timedelta < (self.servo_closed-self.servo_open)/self._servo_speed:
            return "MOVING"

        if self.servo1.position == self.servo_open and self.servo2.position == self.servo_open:
            return "OPEN"
        
        if self.servo1.position == self.servo_closed and self.servo2.position == self.servo_closed:
            return "CLOSED"
        
        return "UNKNOWN"

    @status.setter
    def status(self,desired_status):
        if desired_status == "OPEN":
            desired_posn = self.servo_open
            pass
        elif desired_status == "CLOSED":
            desired_posn = self.servo_closed
            pass
        else:
            raise ValueError("Invalid shutter status: %s" % (desired_status))
        
        if not self.enabled:
            self.enabled = True
            pass

        self.desired_state = desired_status

        # Move servos
        self.servo1.position = desired_posn
        self.servo2.position = desired_posn

        # Mark time when move started
        self._lastchanged=time.monotonic()
        pass

    def wait(self):
        curtime = time.monotonic()
        timedelta = (curtime-self._lastchanged)*ur.s

        if timedelta >= (self.servo_closed-self.servo_open)/self._servo_speed:
            return # move complete

        waitsecs = ((self.servo_closed-self.servo_open)/self._servo_speed - timedelta).to(ur.s).magnitude

        # Want to do:
        #   time.sleep(waitsecs)

        # Note that because we are sleeping inside the module any other
        # module accesses (such as status queries) will be locked out
        # unless we run the sleep function in an unprotected environment
        RunUnprotected(time.sleep,waitsecs)

        # Running the sleep in an unprotected environment also allows new
        # commands. If we wanted we could check and loop back to see
        # if a new command has been issued that would mean it might
        # still be moving
        pass
    pass
