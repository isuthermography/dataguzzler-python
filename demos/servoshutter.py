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
    
    WARNING: This immediately centers the servos on startup!

    How to use: 

    In your config file: 
      from dataguzzler_python import dgpy
      include(dgpy,"serial.dpi")
      include(dgpy,"pint.dpi")
      from pololu_rs232servocontroller import pololu_rs232servocontroller
      from servoshutter import servoshutter

      port_name = "....fixme..."  # replace the "....fixme..." with the serial port device serial number 
      servocont = pololu_rs232servocontroller("servocont",port_name)

      shutter = servoshutter("shutter",servocont.servos[0],servocont.servos[1])

    Then on the dataguzzler-python console: 
      dgpy> shutter.status="OPEN"
    """

    servo1 = None
    servo2 = None
    _servo_speed = None
    _servo_open = None
    _servo_closed = None
    _servo_centered = None
    _lastchanged = None
    desired_state = None
    def __init__(self,
                 module_name,
                 servo1,
                 servo2,
                 initial_state = "CLOSED",
                 servo_speed = 500*ur.us/ur.s,
                 servo_open = 843.75*ur.us,
                 servo_closed = 1706.25*ur.us,
                 servo_centered = 1500*ur.us
                 ):
        self.servo1 = servo1
        self.servo2 = servo2
        self.desired_state = initial_state
        self._servo_speed = servo_speed
        self._servo_open = servo_open
        self._servo_closed = servo_closed
        self._servo_centered = servo_centered
        
        self._lastchanged=time.monotonic()


        # Program servo speeds
        self.servo1.speed = servo_speed
        self.servo2.speed = servo_speed

        # The servo controller wants to start centered,
        # so its best just to let it do that
        self.servo1.position=servo_centered
        self.servo2.position=servo_centered
        pass


    @property
    def status(self):
        r"""Command or report status of the shutter: Usually "OPEN" or "CLOSED" """

        curtime = time.monotonic()

        timedelta = (curtime-self._lastchanged)*ur.s

        if timedelta < (self._servo_closed-self._servo_open)/self._servo_speed:
            return "MOVING"

        if self.servo1.position_matches(self._servo_open) and self.servo2.position_matches(self._servo_open):
            return "OPEN"

        if self.servo1.position_matches(self._servo_centered) and self.servo2.position_matches(self._servo_centered):
            return "CENTERED"

        if self.servo1.position_matches(self._servo_closed) and self.servo2.position_matches(self._servo_closed):
            return "CLOSED"
        
        return "UNKNOWN"

    @status.setter
    def status(self,desired_status):
        if desired_status == "OPEN":
            desired_posn = self._servo_open
            pass
        elif desired_status == "CLOSED":
            desired_posn = self._servo_closed
            pass
        else:
            raise ValueError("Invalid shutter status: %s" % (desired_status))
        

        self.desired_state = desired_status

        # Move servos
        self.servo1.position = desired_posn
        self.servo2.position = desired_posn

        # Mark time when move started
        self._lastchanged=time.monotonic()
        pass

    def wait(self):
        """Wait long enough for the last-initiated move to complete"""
        curtime = time.monotonic()
        timedelta = (curtime-self._lastchanged)*ur.s

        if timedelta >= (self._servo_closed-self._servo_open)/self._servo_speed:
            return # move complete

        waitsecs = ((self._servo_closed-self._servo_open)/self._servo_speed - timedelta).to(ur.s).magnitude

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
