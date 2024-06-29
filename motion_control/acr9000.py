import sys
import collections
import numbers
import re
import threading
import numpy as np
import pint
from dataguzzler_python import dgpy
from dataguzzler_python.dgpy import Module

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

class axis_group:
    parent=None # motion controller object
    axis_names=None # List of axis names
    matching_units=None # True if all axes use exactly the same units
    
    def __init__(self, parent, axis_names):
        self.parent = parent
        self.axis_names = axis_names

        self.matching_units = True
        axis0_quantity = getattr(self.parent, axis_names[0]).unit_quantity
        for axis_num in range(1, len(self.axis_names)):
            axis_name = axis_names[axis_num]
            if getattr(self.parent, axis_name).unit_quantity != axis0_quantity:
                self.matching_units = False
                pass
            pass
        pass

    def zero(self):
        for axis_name in self.axis_names:
            axis = getattr(self.parent, axis_name)
            axis.zero()
            pass
        pass

    def wait(self):
        self.parent._wait(self.axis_names)
        pass

    @property
    def moving(self):
        moving = np.zeros(len(self.axis_names), dtype=bool)
        for axis_num in range(len(self.axis_names)):
            axis_name = self.axis_names[axis_num]
            axis = getattr(self.parent, axis_name)
            moving[axis_num] = axis.moving
            pass
        return moving

    @property
    def rel(self):
        return None

    @rel.setter
    def rel(self, value):
        if len(value) != len(self.axis_names):
            raise ValueError("Incorrect number of axis offsets given")
        for axis_num in range(len(self.axis_names)):
            axis_name = self.axis_names[axis_num]
            axis = getattr(self.parent, axis_name)
            axis.rel=value[axis_num]
            pass
        pass

    def cancel(self):
        for axis_name in self.axis_names:
            axis = getattr(self.parent, axis_name)
            axis.cancel()
            pass
        pass

    @property
    def pos(self):
        ur = pint.get_application_registry()
        if self.matching_units:
            # Create a single numpy quantity with the correct units
            pos = ur.Quantity(np.zeros(len(self.axis_names), dtype='d'), getattr(self.parent, self.axis_names[0]).unit_quantity)
            pass
        else:
            # Create a numpy array of objects which are scalar quantities
            pos = np.zeros(len(self.axis_names), dtype=object)
            pass
        for axis_num in range(len(self.axis_names)):
            axis_name = self.axis_names[axis_num]
            axis = getattr(self.parent, axis_name)
            pos[axis_num] = axis.pos
            pass
        return pos

    @pos.setter
    def pos(self, value):
        if len(value) != len(self.axis_names):
            raise ValueError("Incorrect number of axis offsets given")
        for axis_num in range(len(self.axis_names)):
            axis_name = self.axis_names[axis_num]
            axis = getattr(self.parent, axis_name)
            axis.pos = value[axis_num]
            pass
        pass

    @property
    def enabled(self):
        pos = np.zeros(len(self.axis_names), dtype=bool)
        for axis_num in range(len(self.axis_names)):
            axis_name = self.axis_names[axis_num]
            axis = getattr(self.parent, axis_name)
            pos[axis_num] = axis.pos
            pass
        return pos

    @enabled.setter
    def enabled(self, value):
        if isinstance(value, bool):
            for axis_name in self.axis_names:
                axis = getattr(self.parent, axis_name)
                axis.enabled = value
                pass
            return
        if len(value) != len(self.axis_names):
            raise ValueError("Incorrect number of axis offsets given")
        for axis_num in range(len(self.axis_names)):
            axis_name = self.axis_names[axis_num]
            axis = getattr(self.parent, axis_name)
            axis.enabled = value[axis_num]
            pass
        pass
    pass

class axis:
    axis_name=None 
    proglevel=None # acr9000 program level assigned to this axis (integer)
    axis_num=None # axis0, axis1, ... (integer)
    ppu=None # pulses per unit (float)
    unit_name=None
    unit_quantity=None # pint quantity corresponding to axis units
    unit_factor=None # unit factor. Sign is a flag for linear vs. rotational.
              # if positive, factor relative to mm. If negative,
              # factor relative to deg. (float)
    configured=None # boolean, set once axis is fully configured
    #enabled=None # boolean, is drive turned on
    targetpos=None # target position (float)
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

    @staticmethod
    def units_to_factor(units):
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
        self.parent._control_socket.write(f"PROG{self.proglevel:d}\r")
        self.parent._control_socket.read_until(expected ='>')
        self.parent._control_socket.write(f"DRIVE {self.axisname:s}\r")
        drive_status_line=self.parent._control_socket.read_until(expected ='>')
        matchobj=re.match(r""" *DRIVE[^\r\n] +DRIVE ([ONF]+) """,drive_status_line)
        onoff=matchobj.group(1)
        if onoff=="ON":
            enabled=True
            pass
        elif onoff=="OFF":
            enabled=False
            pass
        else:
            assert(0)
            pass

        if enabled:
            # Double-check that the kill-all-motion-request (KAMR) bit is not asserted
            self.parent._control_socket.write(f"?bit{KAMRbit[self.axis]:d}\r")
            KAMR_line=self.parent._control_socket.read_until(expected='>')
            KAMR_match=re.match(r""" *[?]bit\d+ +(\d+) """, KAMR_line)
            bit_status=int(KAMR_match.group(1))
            if bit_status != 0:
                enabled=False
                pass
            pass
        return enabled

    def zero(self):
        self.parent._abort_wait()
        try:
            self.parent._control_socket.write(f"PROG{self.proglevel:d}\r")
            self.parent._control_socket.read_until(expected='>')
            # issue REN command to cancel any preexisting position command
            self.parent._control_socket.write(f"REN {self.axisname:s}\r")
            self.parent._control_socket.read_until(expected='>')

            # set the target equal to the actual position
            self.parent._control_socket.write(f"P{targetpos[self.axis]:d}=P{trajectorypos[self.axis]:d}\r")
            self.parent._control_socket.read_until(expected='>')
            # reset the encoder to define the current position as '0'
            self.parent._control_socket.write(f"RES {self.axisname:s}\r")
            self.parent._control_socket.read_until(expected='>')
            # set the target equal to the actual position
            self.parent._control_socket.write(f"P{targetpos[self.axis]:d}=P{trajectorypos[self.axis]:d}\r")
            self.parent._control_socket.read_until(expected='>')

            if abs(self.parent._GetPReg(actualpos[self.axis])) <= 5.0:
                # allow up to +- 5 encoder pulses of error
                return 0.0

            else:
                raise IOError(f"reset of axis {self.axisname:s} to zero failed")
            pass
        finally:
            self._restart_wait()
            pass
        pass

    def wait(self):
        self.parent._wait([self.axisname])
        pass
    
        
    @property
    def moving(self):
        self.parent._abort_wait()
        try:
            trajpos=self.parent._GetPReg(trajectorypos[self.axis])
            targpos=self.parent._GetPReg(targetpos[self.axis])
            return trajpos!=targpos
        finally:
            self.parent._restart_wait()
            pass
        pass

    @property
    def rel(self):
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
            
            actpos=self.parent._GetPReg(actualpos[self.axis])/self.ppu
            self.targetpos=raw_value + actpos
            
            self.parent._control_socket.write(f"PROG{self.proglevel:d}\r")
            self.parent._control_socket.read_until(expected='>')

            self.parent._control_socket.write(f"{self.axis_name:s}{self.targetpos:.10g}\r")
            self.parent._control_socket.read_until(expected='>')
            pass
        finally:
            self.parent._restart_wait()
            pass
        pass

    def cancel(self):
        self.parent._abort_wait()
        try:
            self.parent._control_socket.write(f"HALT PROG{self.proglevel:d}\r")
            self.parent._control_socket.read_until(expected='>')

            self.parent._control_socket.write(f"P{targetpos[self.axis]:d}=P{trajectorypos[self.axis]:d}\r") # set the target equal to the actual position so that we record the axis as not moving.
            self.parent._control_socket.read_until(expected='>')
            pass
        finally:
            self.parent._restart_wait()
            pass
        pass

    @property
    def pos(self):
        self.parent._abort_wait()
        try:
            return (self.parent._GetPReg(actualpos[self.axis])/self.ppu)*self.unit_quantity
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
            if not self.enabled:
                raise ValueError("Axis is not enabled")
            
            #actpos=self.parent._GetPReg(actualpos[self.axis])/self.ppu
            self.targetpos=raw_value
            
            self.parent._control_socket.write(f"PROG{self.proglevel:d}\r")
            self.parent._control_socket.read_until(expected='>')

            self.parent._control_socket.write(f"{self.axis_name:s}{self.targetpos:.10g}\r")
            self.parent._control_socket.read_until(expected='>')
            pass
        finally:
            self.parent._restart_wait()
            pass
        pass

    @property
    def enabled(self):
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
                self.parent._control_socket.write(f"PROG{self.proglevel:d}\r")
                self.parent._control_socket.read_until(expected='>')
                pass
            self.parent._control_socket.write(f"PROG{self.proglevel:d}\r")
            self.parent._control_socket.read_until(expected='>')
            if enabled:
                # issue REN command to cancel any preexisting position
                self.parent._control_socket.write(f"REN {self.axis_name:s}\r")
                self.parent._control_socket.read_until(expected='>')
                self.parent._control_socket.write(f"P{targetpos[self.axis]:d}=P{trajectorypos[self.axis]:d}\r") # set the target equal to the actual position
                self.parent._control_socket.read_until(expected='>')
                self.parent._control_socket.write(f"DRIVE ON {self.axis_name:s}\r")
                self.parent._control_socket.read_until(expected='>')
                pass
            else:
                self.parent._control_socket.write(f"DRIVE OFF {self.axis_name:s}\r")
                self.parent._control_socket.read_until(expected='>')
                pass
            pass
        
        finally:
            self.parent._restart_wait()
            pass
        pass
    pass

class acr9000(metaclass=Module):
    _control_socket=None
    _spareprog=None # program level not used by any axis
    axisdict=None
#    reader_thread=None # dedicated thread needed for reading because there is no interruptible or asynchronous read functionality consistently available.
    # read_lock=None # lock for read_complete_cond and read_request_cond
    # read_request_cond=None # condition variable for notifying read request
    # read_complete_cond=None # condition variable for notifying read complete
    # read_request=None # list provided by requester. Filled out with success flag and result string. Locked by read_lock

    
    _waiter_cond=None # condition variable used to signal waiter thread and lock for wait_dict and wait_status
    _waiter_ack_cond = None # condition variable used by waiter thread to acknowledge. Uses same lock as waiter_cond
    _wait_dict=None # dictionary by BASIC conditonal line number of wait events(represented as condition variables that use the same lock as waiter_cond) currently in progress 
    _waiter_thread=None # thread that handles waiting for motions to finish
    _wait_status=None # either "Cancelled" (between WaitCancel() and
                     # WaitRestart())
                     # or "Waiting" (BASIC wait program running on ACR)
    all=None # axis_group object representing all axes
    
    def __init__(self,module_name,pyserial_url,**axis_units):
        ur = pint.get_application_registry()
        
        self._control_socket=dgpy.include(dgpy,'serial_device.dpi',port_name=pyserial_url,baudrate=38400,xonxoff=True)
        self._spareprog=15
        self.axisdict=collections.OrderedDict()
        self._wait_status="Cancelled"
        #_configure_socket(comm1)
        _set_timeout(self._control_socket,STARTUPTIMEOUT)
        self._control_socket.write("HALT ALL\r") # stop all axes
        response=self._control_socket.read_until(expected='>')
        assert(response=="SYS>")

        # search for axes
        for proglevel in range(NUMPROGLEVELS):
            self._control_socket.write(f"PROG{proglevel:d}\r")
            response=self._control_socket.read_until(expected='>')
            matchobj=re.match(r""" *PROG\d+ +P(\d+) *""",response)
            if matchobj is not None:
                response_proglevel=int(matchobj.group(1))
                if response_proglevel==proglevel:
                    # successful match
                    # print(f"found program level {proglevel:d}")
                    self._control_socket.write("ATTACH\r")
                    attach_response=self._control_socket.read_until(expected='>')
                    attach_lines=attach_response.split("\n")
                    for attach_line in attach_lines:
                        attach_match=re.match(r""" *ATTACH SLAVE\d+ AXIS(\d+) "([^"]*)".""",attach_line)
                        if attach_match is not None:
                            axis_num = int(attach_match.group(1))
                            axis_name = attach_match.group(2)
                            if axis_num < MAXAXES and len(axis_name) > 0:
                                #Got valid attach line
                                unit_factor = axis.units_to_factor(axis_units[axis_name])
                                #Extract the PPU
                                self._control_socket.write(f'AXIS{axis_num:d} PPU\r')
                                ppu_response=self._control_socket.read_until(expected='>')
                                ppu_match = re.match(" *AXIS\\d+ PPU\r\n([-+]?(\\d+(\\.\\d*)?|\\.\\d+)([eE][-+]?\\d+)?)\r\nP\\d+>",ppu_response)
                                if ppu_match is None:
                                    raise ValueError(f'Bad PPU line for axis {axis_name:s}')
                                ppu = float(ppu_match.group(4))
                                Axis = axis(axis_name=axis_name,
                                            proglevel=proglevel,
                                            axis_num=axis_num,
                                            ppu=ppu,
                                            unit_name=axis_units[axis_name],
                                            unit_quantity=ur.Quantity(axis_units[axis_name]),
                                            unit_factor=unit_factor,
                                            configured=True,
                                            parent=self)
                                self.axisdict[axis_name]=Axis
                                if hasattr(self,axis_name):
                                    raise ValueError(f"{module_name:s} axis {axis_name:s} shadows a method or attribute")
                                setattr(self,axis_name,Axis)
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
        self.all = axis_group(self, list(self.axisdict.keys()))
        
        #Use spareprog to store our monitoring program
        self._control_socket.write(f'PROG{self._spareprog:d}\r')
        self._control_socket.read_until(expected='>') #"P00>"
        
        self._control_socket.write('HALT\r')
        self._control_socket.read_until(expected='>') #"P00>"
        
        self._control_socket.write('NEW\r') #Clear program memory
        self._control_socket.read_until(expected='>') #"P00>"

        self._control_socket.write('SYS\r')
        self._control_socket.read_until(expected='>') #"SYS>"

        self._control_socket.write('DIM P (100)\r') #Reserve variables 
        self._control_socket.read_until(expected='>') #"SYS>"

        self._control_socket.write('DIM DEF (100)\r') #Reserve variable definitions
        self._control_socket.read_until(expected='>') #"SYS>"

        self._control_socket.write(f'DIM PROG {self._spareprog:d} 16384\r') #Reserve 4 integer variables
        self._control_socket.read_until(expected='>') #"SYS>"

        self._control_socket.write(f'PROG{self._spareprog:d}\r')
        self._control_socket.read_until(expected='>') #"P00>"

        self._control_socket.write(f'#DEFINE EXITFLAG P0\r') #Flag is integer var #0
        self._control_socket.read_until(expected='>') #"P00>"

        self._control_socket.write('5 PRINT \"STRT <\"\r') #Program starting printout
        self._control_socket.read_until(expected='>') #"P00>"

        self._control_socket.write('10 REM start of main loop\r')
        self._control_socket.read_until(expected='>') #"P00>"

        #The various waits will insert additional lines of code here that check the termination conditions and jump to line 1000 when a condition is satisfied 
        self._control_socket.write('999 GOTO 10\r')
        self._control_socket.read_until(expected='>') #"P00>"

        self._control_socket.write('1000 PRINT \"EXITFLAG=\";EXITFLAG;\" >\"\r')
        self._control_socket.read_until(expected='>') #" >"
        self._control_socket.read_until(expected='>') #"P00>"

        self._control_socket.write('1005 REM Just busy-loop until the user presses escape\r') #This is because the program ending itself triggers an ACR9000  firmware bug 
        self._control_socket.read_until(expected='>') #"P00>"

        self._control_socket.write('1007 GOTO 1007\r')
        self._control_socket.read_until(expected='>') #"P00>"

        #Turn off all axes
        for axis_name in self.axisdict:
            Axis=self.axisdict[axis_name]
            self._control_socket.write(f'PROG{Axis.proglevel:d}\r')
            self._control_socket.read_until(expected='>') #"P00>"

            # issue REN command to cancel any preexisting position
            self._control_socket.write(f'REN {Axis.axis_name:s}\r')
            self._control_socket.read_until(expected='>') #"P00>"

            self._control_socket.write(f'P{_targetpos[Axis.axis_num]:d}=P{_trajectorypos[Axis.axis_num]:d}\r') # set the target equal to the actual position
            self._control_socket.read_until(expected='>') #"P00>"

            self._control_socket.write(f'DRIVE OFF {Axis.axis_name:s}\r')
            self._control_socket.read_until(expected='>') #"P00>"

            # enable multiple-move buffering on this program level
            self._control_socket.write(f'DIM MBUF(10)\r')
            self._control_socket.read_until(expected='>') #"P00>"

            self._control_socket.write(f'MBUF ON\r')
            self._control_socket.read_until(expected='>') #"P00>"
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
        self._waiter_thread.start()
        pass

    def waitall(self):
        waitlist = list(self._wait_dict.keys())
        self._wait(waitlist)
        pass
    
            
    r"""def _read(self):
        assert(self.read_request is None) # module context locking should prevent multiple simultaneous reads
        our_request=[]
        with self.read_request_cond:
            self.read_request=our_request
            self.read_request_cond.notify()
            pass
        CompatibleContext=CreateCompatibleContext(self)
        with CompatibleContext: # release our context lock
            
            with self.read_complete_cond:
                self.read_complete_cond.wait()
                self.read_request=None
                pass
            pass
        (success,response)=our_request
        if not success:
            return None
        return response

    def _abort_read(self):
        assert(self.read_request is not None)
        with self.read_complete_cond:
            self.read_request.append(False)
            self.read_request.append(None)
            self.read_complete_cond.notify()
            pass
        pass
    """
    r"""
    def _reader_thread_code(self):
        InitCompatibleThread(self)
        rdstring=None
        while True:
            with self.read_request_cond:
                if self.read_request is None:
                    self.read_request_cond.wait()
                    pass
                read_request=self.read_request
                pass

            if read_request is not None:
                if rdstring is None:
                    rdbytes=self._control_socket.read()
                    rdstring=rdbytes.decode('utf-8')
                    pass
                pass
            with self.read_complete_cond:
                if self.read_request is not None:
                    self.read_request.append(True)
                    self.read_request.append(rdstring)
                    rdstring=None
                    self.read_complete_cond.notify()
                    pass
                pass
            pass
        pass
"""
    def _waiter_thread_code(self):
        InitCompatibleThread(self)

        while True:
            with self._waiter_cond:
                if self._wait_status=='Cancelled':
                    self._waiter_ack_cond.notify()
                    self._waiter_cond.wait()
                    pass
                elif wait_status=='Waiting':
                    self._waiter_ack_cond.notify()
                    pass
                wait_status=self._wait_status
                pass
            while wait_status=='Waiting':
                #response=self._read()
                response=self._control_socket.read_until(expected='>') 
                if response is not None:
                    efpos=response.find('EXITFLAG')
                    if efpos >= 0:
                        efmatch=re.match(r'EXITFLAG=(\d+)',response[efpos:])
                        assert(efmatch is not None)
                        linenum=efmatch.group(1)
                        with self: # grab our module lock context
                            with self._waiter_cond:
                                wait_obj=self._wait_dict[linenum]
                                del self._wait_dict[linenum]
                                wait_obj.notify()
                                pass
                            pass
                        continue #Bypass check of wait status until we have something that is not an EXITFLAG. 
                        pass
                    else:
                        #A different string: must be a prompt
                        #OK to check wait status, as we must have pressed escape
                        pass
                    pass
                with self._waiter_cond:
                    wait_status=self._wait_status
                    assert(wait_status=='Cancelled') #If we got a prompt then we must have been cancelled
                    pass
                pass
            pass
        pass

    def _wait(self,axislist):
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
                self._wait_cond = threading.Cond(lock=self._waiter_cond)
                self._wait_dict[linenum] = self._wait_cond
                pass
            
            self._control_socket.write(f'PROG{self._spareprog:d}\r')
            self._control_socket.read_until(expected='>') #"P00>"
            condition = "AND ".join([f"(P{trajectorypos[self.axisdict[axis_name].axis_num]:d}=P{targetpos[self.axisdict[axis_name].axis_num]:d}) " for axis_name in axislist])
            condition_line = f"{linenum:d} IF ( {condition:s}) THEN EXITFLAG={linenum:d}:GOTO 1000 \r"
            self._control_socket.write(condition_line)
            self._control_socket.read_until(expected='>') #"P00>"
            
            pass
        finally:
            self._restart_wait()
            pass
        with wait_cond:
            wait_cond.wait()
            pass 
        pass

    def _restart_wait(self):
        assert(self._wait_status == 'Cancelled')
        # go to our spare program level
        self._control_socket.write(f'PROG{self._spareprog:d}\r')
        self._control_socket.read_until(expected='>') #"P00>"
        # issue the LRUN command to run the program
        self._control_socket.write(f'LRUN\r')
        ## set line terminator to '<' instead of '>'
        #self._control_socket.read_termination=">"
        STRT_response=self._control_socket.read_until(expected='<')#Wait for STRT response. Note the weird terminator
        STRT_idx=STRT_response.find('STRT')
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
            self._control_socket.write(f'\x1b')
            #Wait for prompt
            self._waiter_ack_cond.wait()
            pass
        self._control_socket.write('HALT\r')
        self._control_socket.read_until(expected='>') #Wait for prompt
        pass
    
                
    def _GetPReg(self, regnum):
        # Call between _abort_wait and _restart_wait
        assert(self._wait_status == 'Cancelled')
        self._control_socket.write(f'?P{regnum:d}\r')
        resp = self._control_socket.read_until(expected='>') #Wait for prompt

        matchobj = re.match(r""" *P\d+ +([-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?) """, resp)
        value = float(matchobj.group(4))
        return value
        
    pass
