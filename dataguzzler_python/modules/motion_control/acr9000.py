import sys
import collections
import numbers
import re 
import threading
import random
import atexit
import numpy as np
import pint
from dataguzzler_python import dgpy
from dataguzzler_python.dgpy import Module,InitCompatibleThread
from dataguzzler_python.motion_controller import MotionControllerBase,AxisBase, SimpleAxisGroup

STARTUPTIMEOUT=600 # ms
NORMALTIMEOUT=None # disable timeout
NUMPROGLEVELS = 16
MAXAXES = 16
# list of position register addresses  -- eg. "?p%d\n",axispos[axis] to query raw position of axisnum (before ppu)
# See Axis Parameters, in ACR users's guide part 2, pages, 73 and 80
trajectorypos=[ 
  12288,
  12544,
  12800,
  13056,
  13312,
  13568,
  13824,
  14080,
  14336,
  14592,
  14848,
  15104,
  15360,
  15616,
  15872,
  16128,
]

targetpos=[
  12289,
  12545,
  12801,
  13057, 
  13313, 
  13569, 
  13825,
  14081,
  14337, 
  14593, 
  14849,
  15105,
  15361,
  15617, 
  15873, 
  16129,

]

actualpos=[
  12290,
  12546,
  12802, 
  13058,
  13314,
  13570,
  13826, 
  14082,
  14338,
  14594,
  14850,
  15106, 
  15362,
  15618, 
  15874,
  16130,
]


KAMRbit=[
  8467,
  8499,
  8531,
  8563,
  8595,
  8627,
  8659,
  8691,
  8723,
  8755,
  8787,
  8819,
  8851,
  8883,
  8915,
  8947,
]

r"""
#These would be for pyvisa
def _set_timeout(socket,timeout_ms_or_None):
    if timeout_ms_or_None is not None:
        socket.timeout=timeout_ms_or_None/1000.0
        pass
    else:
        if hasattr(socket,"timeout"):
            del socket.timeout
            pass
        pass
    pass

def _configure_socket(socket):
    _set_timeout(socket,STARTUPTIMEOUT)
    socket.read_termination=">"
    socket.write_termination=""
    socket.write("\x1bSYS\r") # escape cancels out of any running program
    # read lines as long as we are getting anything
    got_response=True
    while got_response:
        response=socket.read()
        if len(response)=0:
            got_response=False
            pass
        pass
    _set_timeout(socket,NORMALTIMEOUT)
    # go to system command mode
    socket.write("SYS\r")
    response=socket.read()
    pass
"""
def _set_timeout(socket,timeout_ms_or_None):
    if timeout_ms_or_None is not None:
        socket.timeout=timeout_ms_or_None/1000.0
        pass
    else:
        socket.timeout=None
        pass
    pass



class ACR9000Axis(AxisBase):
    axis_name=None # Name of this axis within its controller as a python string
    _proglevel=None # acr9000 program level assigned to this axis (integer)
    _axis_num=None # axis0, axis1, ... (integer)
    _ppu=None # pulses per unit (float)
    unit_name=None # String representing axis default units
    unit_quantity=None # pint quantity corresponding to axis default units
    _unit_factor=None # unit factor. Sign is a flag for linear vs. rotational.
              # if positive, factor relative to mm. If negative,
              # factor relative to deg. (float)
    
    #enabled=None # boolean, is drive turned on (now a property)
    _targetpos=None # target position (float)
    parent=None # acr9000 object
    
    def __init__(self,**kwargs):
        for arg in kwargs:
            if hasattr(self,arg):
                setattr(self,arg,kwargs[arg])
                pass
            else:
                raise ValueError(f"unknown attribute {arg:s}")
            pass
        pass
    
    # .wait() method implemented by AxisBase base class
    #def wait(self):
    #    """Wait for this axis to stop moving."""
    #    self.parent.wait([self.axis_name])
    #    pass

    #.waitrel property implemented by AxisBase base class
    #@property
    #def waitrel(self):
    #    """On read, returns None; on assignment, initiates a move
    #    relative to the current position and waits for the move to
    #    complete. Position can be a number, which is assumed to be in
    #    the axis default units, or a Pint quantity."""
    #    return None

    #@waitrel.setter
    #def waitrel(self, value):
    #    # Value may be given as just a number, in which case
    #    # default units are assumed, or as a pint quantity.
    #    self.rel = value
    #    self.wait()
    #    pass

    #.waitpos property implemented by AxisBase base class
    #@property
    #def waitpos(self):
    #    """On read, returns the current axis position; on assignment
    #    initiates the move to the specified position and waits for the
    #    move to complete. Position can be a number, which is assumed
    #    to be in the axis default units, or a Pint quantity."""
    #    return self.pos

    #@waitpos.setter
    #def waitpos(self, value):
    #    # Value may be given as just a number, in which case
    #    # default units are assumed, or as a pint quantity.
    #    self.pos = value
    #    self.wait()
    #    pass
    
    @staticmethod
    def _units_to_factor(units):
        ur = pint.get_application_registry()
        quant = ur.Quantity(1.0,units)
        if quant.is_compatible_with(ur.millimeter):
            factor = float(quant/ur.millimeter)
            pass
        elif quant.is_compatible_with(ur.degree):
            factor = -float(quant/ur.degree)
            pass
        else:
            raise ValueError(f'incompatible units: {units:s}')
        return factor

    
    def _enabled(self):
        assert(self.parent._wait_status == 'Cancelled')
        # Must be called between _abort_wait and _restart_wait
        self.parent._control_socket.write(f"PROG{self._proglevel:d}\r".encode("utf-8"))
        self.parent._control_socket.read_until(expected =b'>')
        self.parent._control_socket.write(f"DRIVE {self.axis_name:s}\r".encode("utf-8"))
        drive_status_line=self.parent._control_socket.read_until(expected =b'>')
        matchobj=re.match(rb"""\s*DRIVE[^\r\n]+\s+DRIVE\s+([ONF]+)\s""",drive_status_line)
        onoff=matchobj.group(1)
        if onoff==b"ON":
            enabled=True
            pass
        elif onoff==b"OFF":
            enabled=False
            pass
        else:
            assert(0)
            pass

        if enabled:
            # Double-check that the kill-all-motion-request (KAMR) bit is not asserted
            self.parent._control_socket.write(f"?bit{KAMRbit[self._axis_num]:d}\r".encode("utf-8"))
            KAMR_line=self.parent._control_socket.read_until(expected=b'>')
            KAMR_match=re.match(rb"""\s*[?]bit\d+\s+(\d+)\s""", KAMR_line)
            bit_status=int(KAMR_match.group(1))
            if bit_status != 0:
                enabled=False
                pass
            pass
        return enabled

    def zero(self):
        """This method zeros the axis, defining the current position to be 0.0"""
        self.parent._abort_wait()
        try:
            self.parent._control_socket.write(f"PROG{self._proglevel:d}\r".encode("utf-8"))
            self.parent._control_socket.read_until(expected=b'>')
            # issue REN command to cancel any preexisting position command
            self.parent._control_socket.write(f"REN {self.axis_name:s}\r".encode("utf-8"))
            self.parent._control_socket.read_until(expected=b'>')

            # set the target equal to the actual position
            self.parent._control_socket.write(f"P{targetpos[self._axis_num]:d}=P{trajectorypos[self._axis_num]:d}\r".encode("utf-8"))
            self.parent._control_socket.read_until(expected=b'>')
            # reset the encoder to define the current position as '0'
            self.parent._control_socket.write(f"RES {self.axis_name:s}\r".encode("utf-8"))
            self.parent._control_socket.read_until(expected=b'>')
            # set the target equal to the actual position
            self.parent._control_socket.write(f"P{targetpos[self._axis_num]:d}=P{trajectorypos[self._axis_num]:d}\r".encode("utf-8"))
            self.parent._control_socket.read_until(expected=b'>')

            if abs(self.parent._GetPReg(actualpos[self._axis_num])) <= 5.0:
                # allow up to +- 5 encoder pulses of error
                return 0.0

            else:
                raise IOError(f"reset of axis {self.axis_name:s} to zero failed")
            pass
        finally:
            self.parent._restart_wait()
            pass
        pass

    
        
    @property
    def moving(self):
        """Returns True if the axis is moving or False if it is stopped"""
        self.parent._abort_wait()
        try:
            trajpos=self.parent._GetPReg(trajectorypos[self._axis_num])
            targpos=self.parent._GetPReg(targetpos[self._axis_num])
            return trajpos!=targpos
        finally:
            self.parent._restart_wait()
            pass
        pass

    @property
    def rel(self):
        """On read, returns None; on assignment, initiates
        a move relative to the current position."""
        return None

    @rel.setter
    def rel(self, value):
        ur = pint.get_application_registry()
        #if isinstance(value, str):
        value = ur.Quantity(value)
        #    pass
        #elif isinstance(value, numbers.Number):
         #   value = ur.Quantity(value)
          #  pass
        
        if value.unitless:
            value = ur.Quantity(float(value), self.unit_name)
            pass

        raw_value = float(value/self.unit_quantity)
        
        self.parent._abort_wait()
        try:
            if not self._enabled():
                raise ValueError("Axis is not enabled")
            
            actpos=self.parent._GetPReg(actualpos[self._axis_num])/self._ppu
            self._targetpos=raw_value + actpos
            
            self.parent._control_socket.write(f"PROG{self._proglevel:d}\r".encode("utf-8"))
            self.parent._control_socket.read_until(expected=b'>')

            self.parent._control_socket.write(f"{self.axis_name:s}{self._targetpos:.10g}\r".encode("utf-8"))
            self.parent._control_socket.read_until(expected=b'>')
            pass
        finally:
            self.parent._restart_wait()
            pass
        pass

    def cancel(self):
        """Cancel any move in progress on this axis"""
        self.parent._abort_wait()
        try:
            self.parent._control_socket.write(f"HALT PROG{self._proglevel:d}\r".encode("utf-8"))
            self.parent._control_socket.read_until(expected=b'>')

            self.parent._control_socket.write(f"P{targetpos[self._axis_num]:d}=P{trajectorypos[self._axis_num]:d}\r".encode("utf-8")) # set the target equal to the actual position so that we record the axis as not moving.
            self.parent._control_socket.read_until(expected=b'>')
            pass
        finally:
            self.parent._restart_wait()
            pass
        pass

    @property
    def pos(self):
        """On read, returns the current axis position;
        on assignment initiates the move to the specified
        position"""
        self.parent._abort_wait()
        try:
            return (self.parent._GetPReg(actualpos[self._axis_num])/self._ppu)*self.unit_quantity
        finally:
            self.parent._restart_wait()
            pass
        return None

    @pos.setter
    def pos(self, value):
        ur = pint.get_application_registry()
        #if isinstance(value, str):
        value = ur.Quantity(value)
        #    pass
        #elif isinstance(value, numbers.Number):
         #   value = ur.Quantity(value)
          #  pass
        
        if value.unitless:
            value = ur.Quantity(float(value), self.unit_name)
            pass

        raw_value = float(value/self.unit_quantity)
        
        self.parent._abort_wait()
        try:
            if not self._enabled():
                raise ValueError("Axis is not enabled")
            
            #actpos=self.parent._GetPReg(actualpos[self._axis_num])/self._ppu
            self._targetpos=raw_value
            
            self.parent._control_socket.write(f"PROG{self._proglevel:d}\r".encode("utf-8"))
            self.parent._control_socket.read_until(expected=b'>')

            self.parent._control_socket.write(f"{self.axis_name:s}{self._targetpos:.10g}\r".encode("utf-8"))
            self.parent._control_socket.read_until(expected=b'>')
            pass
        finally:
            self.parent._restart_wait()
            pass
        pass

    @property
    def enabled(self):
        """On read, returns True if the current axis is enabled, False
        otherwise. On assignment, attempts to turn the axis on or off
        according to the truth value provided (True or False)."""
        self.parent._abort_wait()
        try:
            return self._enabled()
        finally:
            self.parent._restart_wait()
            pass
        pass

    @enabled.setter
    def enabled(self, value):
        enabled = value == True
        self.parent._abort_wait()
        try:
            if enabled:
                # issue ctrl-y to clear all kill-all-motion-request (KAMR) flags
                self.parent._control_socket.write(b"\x19\r")
                self.parent._control_socket.read_until(expected=b'>')
                pass
            self.parent._control_socket.write(f"PROG{self._proglevel:d}\r".encode("utf-8"))
            self.parent._control_socket.read_until(expected=b'>')
            if enabled:
                # issue REN command to cancel any preexisting position
                self.parent._control_socket.write(f"REN {self.axis_name:s}\r".encode("utf-8"))
                self.parent._control_socket.read_until(expected=b'>')
                self.parent._control_socket.write(f"P{targetpos[self._axis_num]:d}=P{trajectorypos[self._axis_num]:d}\r".encode("utf-8")) # set the target equal to the actual position
                self.parent._control_socket.read_until(expected=b'>')
                self.parent._control_socket.write(f"DRIVE ON {self.axis_name:s}\r".encode("utf-8"))
                self.parent._control_socket.read_until(expected=b'>')
                pass
            else:
                self.parent._control_socket.write(f"DRIVE OFF {self.axis_name:s}\r".encode("utf-8"))
                self.parent._control_socket.read_until(expected=b'>')
                pass
            pass
        
        finally:
            self.parent._restart_wait()
            pass
        pass
    pass

class ACR9000(MotionControllerBase,metaclass=Module):
    _control_socket=None
    _spareprog=None # program level not used by any axis
    axis=None # Ordered dictionary of axis objects
    
    _waiter_cond=None # condition variable used to signal waiter thread and lock for wait_dict and wait_status
    _waiter_ack_cond = None # condition variable used by waiter thread to acknowledge. Uses same lock as waiter_cond
    _wait_dict=None # dictionary by BASIC conditonal line number of wait events(represented as condition variables that use the same lock as waiter_cond) currently in progress 
    _waiter_thread=None # thread that handles waiting for motions to finish
    _wait_status=None # either "Cancelled" (between WaitCancel() and
                     # WaitRestart())
                     # or "Waiting" (BASIC wait program running on ACR)
    _wait_exit=None  # set to True to trigger the wait thread to exit
    all=None # SimpleAxisGroup object representing all axes
    
    def __init__(self,module_name,pyserial_url,**axis_units):
        ur = pint.get_application_registry()
        
        self._control_socket=dgpy.include(dgpy,'serial_device.dpi',port_name=pyserial_url,baudrate=38400,xonxoff=True)
        self._spareprog=15
        self.axis=collections.OrderedDict()
        self._wait_status="Cancelled"
        self._wait_exit=False
        #_configure_socket(comm1)
        _set_timeout(self._control_socket,500) #Set timeout to 500ms
        self._control_socket.write(b"SYS\r") # Change to system mode
        gotbuf="Startup"
        total_gotbuf=b""
        while len(gotbuf) > 0:
            gotbuf=self._control_socket.read_until(expected=b">")
            total_gotbuf += gotbuf
            pass

        if b"SYS" not in total_gotbuf:
            # Not responding... send escape key
            self._control_socket.write(b"\x1b\r") # Change to system mode
            self._control_socket.write(b"SYS\r") # Change to system mode
            gotbuf="Startup"
            total_gotbuf=b""
            while len(gotbuf) > 0:
                gotbuf=self._control_socket.read_until(expected=b">")
                total_gotbuf += gotbuf
                pass
            pass
        _set_timeout(self._control_socket,STARTUPTIMEOUT)
        self._control_socket.write(b"SYS\r") # Change to system mode
        response=self._control_socket.read_until(expected=b'>')
        #import pdb
        #pdb.set_trace()
        assert(response.endswith(b"SYS>"))

        self._control_socket.write(b"HALT ALL\r") # stop all axes
        response=self._control_socket.read_until(expected=b'>')
        
        # search for axes
        for proglevel in range(NUMPROGLEVELS):
            self._control_socket.write(f"PROG{proglevel:d}\r".encode("utf-8"))
            response=self._control_socket.read_until(expected=b'>')
            matchobj=re.match(rb"""\s*PROG\d+\s+P(\d+)\s*""",response)
            if matchobj is not None:
                response_proglevel=int(matchobj.group(1))
                if response_proglevel==proglevel:
                    # successful match
                    # print(f"found program level {proglevel:d}")
                    self._control_socket.write(b"ATTACH\r")
                    attach_response=self._control_socket.read_until(expected=b'>')
                    attach_lines=attach_response.split(b"\n")
                    for attach_line in attach_lines:
                        attach_match=re.match(rb"""\s*ATTACH SLAVE\d+ AXIS(\d+)\s"([^"]*)".""",attach_line)
                        if attach_match is not None:
                            axis_num = int(attach_match.group(1))
                            axis_name = attach_match.group(2).decode("utf-8")
                            if axis_num < MAXAXES and len(axis_name) > 0:
                                #Got valid attach line
                                unit_factor = ACR9000Axis._units_to_factor(axis_units[axis_name])
                                #Extract the PPU
                                self._control_socket.write(f'AXIS{axis_num:d} PPU\r'.encode("utf-8"))
                                ppu_response=self._control_socket.read_until(expected=b'>')
                                ppu_match = re.match(b"\\s*AXIS\\d+ PPU\r\n([-+]?(\\d+(\\.\\d*)?|\\.\\d+)([eE][-+]?\\d+)?)\r\nP\\d+>",ppu_response)
                                if ppu_match is None:
                                    raise ValueError(f'Bad PPU line for axis {axis_name:s}')
                                ppu = float(ppu_match.group(1))
                                axis = ACR9000Axis(axis_name=axis_name,
                                            _proglevel=proglevel,
                                            _axis_num=axis_num,
                                            _ppu=ppu,
                                            unit_name=axis_units[axis_name],
                                            unit_quantity=ur.Quantity(axis_units[axis_name]),
                                            _unit_factor=unit_factor,
                                            parent=self)
                                self.axis[axis_name]=axis
                                if hasattr(self,axis_name):
                                    raise ValueError(f"{module_name:s} axis {axis_name:s} shadows a method or attribute")
                                setattr(self,axis_name,axis)
                                pass
                            pass
                        pass
                    pass
                else:
                    break #Out of valid program levels
                pass
            else:
                break #Out of valid program levels
            pass

        # Create an 'all' object that refers to all axes
        self.all = self.create_group(list(self.axis.keys()))
        
        #Use spareprog to store our monitoring program
        self._control_socket.write(f'PROG{self._spareprog:d}\r'.encode("utf-8"))
        self._control_socket.read_until(expected=b'>') #"P00>"
        
        self._control_socket.write(b'HALT\r')
        self._control_socket.read_until(expected=b'>') #"P00>"
        
        self._control_socket.write(b'NEW\r') #Clear program memory
        self._control_socket.read_until(expected=b'>') #"P00>"

        self._control_socket.write(b'SYS\r')
        self._control_socket.read_until(expected=b'>') #"SYS>"

        self._control_socket.write(b'DIM P (100)\r') #Reserve variables 
        self._control_socket.read_until(expected=b'>') #"SYS>"

        self._control_socket.write(b'DIM DEF (100)\r') #Reserve variable definitions
        self._control_socket.read_until(expected=b'>') #"SYS>"

        self._control_socket.write(f'DIM PROG {self._spareprog:d} 16384\r'.encode("utf-8")) #Reserve 4 integer variables
        self._control_socket.read_until(expected=b'>') #"SYS>"

        self._control_socket.write(f'PROG{self._spareprog:d}\r'.encode("utf-8"))
        self._control_socket.read_until(expected=b'>') #"P00>"

        self._control_socket.write(f'#DEFINE EXITFLAG P0\r'.encode("utf-8")) #Flag is integer var #0
        self._control_socket.read_until(expected=b'>') #"P00>"

        self._control_socket.write(b'5 PRINT \"STRT <\"\r') #Program starting printout
        self._control_socket.read_until(expected=b'>') #"P00>"

        self._control_socket.write(b'10 REM start of main loop\r')
        self._control_socket.read_until(expected=b'>') #"P00>"

        #The various waits will insert additional lines of code here that check the termination conditions and jump to line 1000 when a condition is satisfied 
        self._control_socket.write(b'999 GOTO 10\r')
        self._control_socket.read_until(expected=b'>') #"P00>"

        self._control_socket.write(b'1000 PRINT \"EXITFLAG=\";EXITFLAG;\" >\"\r')
        self._control_socket.read_until(expected=b'>') #" >"
        self._control_socket.read_until(expected=b'>') #"P00>"

        self._control_socket.write(b'1005 REM Just busy-loop until the user presses escape\r') #This is because the program ending itself triggers an ACR9000  firmware bug 
        self._control_socket.read_until(expected=b'>') #"P00>"

        self._control_socket.write(b'1007 GOTO 1007\r')
        self._control_socket.read_until(expected=b'>') #"P00>"

        #Turn off all axes
        for axis_name in self.axis:
            axis=self.axis[axis_name]
            self._control_socket.write(f'PROG{axis._proglevel:d}\r'.encode("utf-8"))
            self._control_socket.read_until(expected=b'>') #"P00>"

            # issue REN command to cancel any preexisting position
            self._control_socket.write(f'REN {axis.axis_name:s}\r'.encode("utf-8"))
            self._control_socket.read_until(expected=b'>') #"P00>"

            self._control_socket.write(f'P{targetpos[axis._axis_num]:d}=P{trajectorypos[axis._axis_num]:d}\r'.encode("utf-8")) # set the target equal to the actual position
            self._control_socket.read_until(expected=b'>') #"P00>"

            self._control_socket.write(f'DRIVE OFF {axis.axis_name:s}\r'.encode("utf-8"))
            self._control_socket.read_until(expected=b'>') #"P00>"

            # enable multiple-move buffering on this program level
            self._control_socket.write(b'DIM MBUF(10)\r')
            self._control_socket.read_until(expected=b'>') #"P00>"

            self._control_socket.write(b'MBUF ON\r')
            self._control_socket.read_until(expected=b'>') #"P00>"
            pass

        _set_timeout(self._control_socket,NORMALTIMEOUT)
        
        #self.read_lock=threading.Lock()
        #self.read_request_cond=threading.Condition(self.read_lock)
        #self.read_complete_cond=threading.Condition(self.read_lock)
        #self.reader_thread=threading.Thread(target=self._reader_thread_code)
        #self.reader_thread.start()

        self._waiter_cond=threading.Condition()
        self._waiter_ack_cond =threading.Condition(self._waiter_cond)
        self._wait_dict={}
        self._wait_status='Cancelled'
        self._waiter_thread=threading.Thread(target=self._waiter_thread_code)
        with self._waiter_cond:
            self._waiter_thread.start()
            self._waiter_ack_cond.wait()
            pass
        #atexit.register(self.atexit) # Register an atexit function so that we can cleanly trigger our subthread to end. Otherwise we might well crash on exit.
        self._restart_wait()
        pass

    # .axes, .axis_unit_names, and .axis_unit_quantities
    # properties are defined and implemented in the
    # MotionControllerBase base class
    #@property
    #def axes(self):
    #    """Returns a list or array of axis names"""
    #    return list(self.axis.keys())

    #@property
    #def axis_unit_names(self):
    #    """Returns a list or array of axis unit names"""
    #    return [self.axis[axis_name.unit_name] for axis_name in self.axis ]

    #@property
    #def axis_unit_quantities(self):
    #    """Returns a list or array of axis units (pint quantity)"""
    #    return [self.axis[axis_name.unit_quantity] for axis_name in self.axis ]

    # .create_group() method is defined and implemented in the
    # MotionControllerBase base class
    #def create_group(self,axis_name_list):
    #    """Create and return an axis group (instance or subclass of
    #    SimpleAxisGroup) based on the given list of axis names"""
    #    # Override this method if you have a custom group class
    #    # for your motion controller. 
    #    return SimpleAxisGroup(self,axis_name_list)



    ## NOTE: atexit did not turn out to be neccesary 
    #def atexit(self):
    #    #print("acr9000: Performing atexit()")
    #    with self._waiter_cond:
    #        self._waiter_exit = True;
    #        self._waiter_cond.notify()
    #        pass
    #
    #    self._waiter_thread.join()
    #    
    #    pass

    
    
    def _waiter_thread_code(self):
        InitCompatibleThread(self,'_waiter_thread')

        while True:
            with self._waiter_cond:
                if self._wait_status=='Cancelled' and not self._wait_exit:
                    self._waiter_ack_cond.notify()
                    self._waiter_cond.wait()
                    pass
                elif self._wait_status=='Waiting':
                    pass
                self._waiter_ack_cond.notify()
                wait_status=self._wait_status

                if self._wait_exit: # not actually used
                    if self._wait_status == 'Waiting':
                        self._wait_status = 'Cancelled'
                        #Press the escape key
                        self._control_socket.write(b'\x1b')
                        self._control_socket.read_until(expected=b'>')
                        self._control_socket.write(b'HALT\r')
                        self._control_socket.read_until(expected=b'>') #Wait for prompt
                        pass
                    return # waiter thread exit
                pass
            while wait_status=='Waiting':
                #response=self._read()
                response=self._control_socket.read_until(expected=b'>') 
                if response is not None:
                    efpos=response.find(b'EXITFLAG')
                    if efpos >= 0 and efpos < len(response):
                        efmatch=re.match(rb'EXITFLAG=(\d+)',response[efpos:])
                        assert(efmatch is not None)
                        efpos += len(efmatch.group(0))
                        linenum=int(efmatch.group(1))
                        with self._waiter_cond:
                            if linenum in self._wait_dict:
                                wait_obj=self._wait_dict[linenum]
                                del self._wait_dict[linenum]
                                wait_obj.notify()
                                pass
                            pass
                        
                        
                        pass
                    #else:
                    #    #A different string: must be a prompt
                    #    #OK to check wait status, as we must have pressed escape
                    #    pass
                    if efpos >= 0:
                        continue #Bypass check of wait status until we have something that is not an EXITFLAG. 
                    pass
                with self._waiter_cond:
                    wait_status=self._wait_status
                    assert(wait_status=='Cancelled') #If we got a prompt then we must have been cancelled
                    pass
                pass
            pass
        pass


    def wait(self,axis_name_list):
        """Waits for each axis named in the given list to stop moving"""
        self._abort_wait()
        try:
            with self._waiter_cond:
                orig_linenum = random.randrange(30,900,10)
                linenum = orig_linenum 
                while linenum in self._wait_dict:
                    linenum+=1
                    if linenum > 899:
                        linenum = 30
                        pass
                    if linenum == orig_linenum:
                        raise ValueError("too many simultaneous waits")
                    pass
                    
                assert(linenum not in self._wait_dict)
                _wait_cond = threading.Condition(lock=self._waiter_cond)
                self._wait_dict[linenum] = _wait_cond
                pass
            
            self._control_socket.write(f'PROG{self._spareprog:d}\r'.encode("utf-8"))
            self._control_socket.read_until(expected=b'>') #"P00>"
            condition = "AND ".join([f"(P{trajectorypos[self.axis[axis_name]._axis_num]:d}=P{targetpos[self.axis[axis_name]._axis_num]:d}) " for axis_name in axis_name_list])
            condition_line = f"{linenum:d} IF ( {condition:s}) THEN EXITFLAG={linenum:d}:GOTO 1000 \r"
            self._control_socket.write(condition_line.encode("utf-8"))
            self._control_socket.read_until(expected=b'>') #"P00>"
            
            pass
        finally:
            self._restart_wait()
            pass
        with dgpy.UnprotectedContext:
            with _wait_cond:
                _wait_cond.wait()
                pass
            pass
        # Need to erase the line of code (wait thread removed us from wait dict)
        self._abort_wait()
        try:
            self._control_socket.write(f"PROG{self._spareprog:d}\r".encode("utf-8"))
            self._control_socket.read_until(expected=b'>') #"P00>"
            self._control_socket.write(f"{linenum:d}\r".encode("utf-8")) # just the line number alone deletes the line
            self._control_socket.read_until(expected=b'>') #"P00>"
            pass
        finally:
            self._restart_wait()
            pass
        pass
    
    def _restart_wait(self):
        assert(self._wait_status == 'Cancelled')
        # go to our spare program level
        self._control_socket.write(f'PROG{self._spareprog:d}\r'.encode("utf-8"))
        self._control_socket.read_until(expected=b'>') #"P00>"
        # issue the LRUN command to run the program
        self._control_socket.write(b'LRUN\r')
        ## set line terminator to '<' instead of b'>'
        #self._control_socket.read_termination=">"
        STRT_response=self._control_socket.read_until(expected=b'<')#Wait for STRT response. Note the weird terminator
        STRT_idx=STRT_response.find(b'STRT')
        assert(STRT_idx >= 0) #Program started succesfully. Delegate to waiter thread. 
        with self._waiter_cond:
            assert(self._wait_status=="Cancelled")
            self._wait_status="Waiting"
            self._waiter_cond.notify()
            self._waiter_ack_cond.wait()
            pass

        
        pass
    def _abort_wait(self):
        assert(self._wait_status == 'Waiting')
        with self._waiter_cond:
            self._wait_status = 'Cancelled'
            
            #Press the escape key
            self._control_socket.write(b'\x1b')
            #Wait for prompt
            self._waiter_ack_cond.wait()
            pass
        self._control_socket.write(b'HALT\r')
        self._control_socket.read_until(expected=b'>') #Wait for prompt
        pass
    
                
    def _GetPReg(self, regnum):
        # Call between _abort_wait and _restart_wait
        assert(self._wait_status == 'Cancelled')
        self._control_socket.write(f'?P{regnum:d}\r'.encode("utf-8"))
        resp = self._control_socket.read_until(expected=b'>') #Wait for prompt

        matchobj = re.match(rb"""\s*[?]P\d+\s+([-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?)\s""", resp)
        value = float(matchobj.group(1))
        return value
        
    pass
