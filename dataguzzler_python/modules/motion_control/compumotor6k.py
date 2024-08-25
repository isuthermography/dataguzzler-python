import sys
import collections
import numbers
import re 
import threading
import random
import atexit
import numpy as np
import pint
import time
import copy
from dataguzzler_python import dgpy
from dataguzzler_python.dgpy import Module,InitCompatibleThread
from dataguzzler_python.motion_controller import MotionControllerBase,AxisBase, SimpleAxisGroup

STARTUPTIMEOUT=600 # ms
NORMALTIMEOUT=None # disable timeout
MAXAXES = 8



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



class CM6kAxis(AxisBase):
    axis_name=None # Name of this axis within its controller as a python string
    
    _axis_num=None # axis1, axis2, ... (integer)
    _ppu=None # pulses per unit (float)
    unit_name=None # String representing axis default units
    unit_quantity=None # pint quantity corresponding to axis default units
    _unit_factor=None # unit factor. Sign is a flag for linear vs. rotational.
              # if positive, factor relative to mm. If negative,
              # factor relative to deg. (float)
    
    #enabled=None # boolean, is drive turned on (now a property)
  #  _targetpos=None # target position (float)
    parent=None # CM6k object
    
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
        self.parent._control_socket.write(f"!{self._axis_num:d}DRIVE\r".encode("utf-8"))
        # print('waiting for drive response')
        drive_status_line=self.parent._control_socket.read_until(expected =b'>')
        # print('drive_status_line=',drive_status_line)
        matchobj=re.match(rb"""\s*[*]\d+DRIVE([10])""",drive_status_line)
        onoff=matchobj.group(1)
        if onoff==b"1":
            enabled=True
            pass
        elif onoff==b"0":
            enabled=False
            pass
        else:
            assert(0)
            pass

        return enabled

    def zero(self):
        '''Zeroing is only implemented for all axes together on this motion controller'''
        raise NotImplementedError('Zeroing is only implemented for all axes together on this motion controller. Use the .all attribute to zero all axes')
       
    
        
    @property
    def moving(self):
        """Returns True if the axis is moving or False if it is stopped"""
        self.parent._abort_wait()
        try:
            self.parent._control_socket.write(f"!{self._axis_num:d}TAS.1\r".encode("utf-8"))
            response=self.parent._control_socket.read_until(expected=b'>')
            matchobj=re.match(rb"""\s*\d+TAS([10])""",response)
            moving=matchobj.group(1)
            if moving==b"1":
                return True
            elif moving==b"0":
                return False
            else:
                assert(0)
                pass
            pass
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
        num_pulses = int(round(raw_value*self._ppu))
        
        self.parent._abort_wait()
        try:
            if not self._enabled():
                raise ValueError("Axis is not enabled")
            self.parent._control_socket.write(f"{self._axis_num:d}D{num_pulses:d}\r")
            self.parent._control_socket.read_until(expected =b'>')
            # create a command like GO1XXXXXXX with "1" positioned according to the axis number
            go_command = b"!GO" + b"X"*(self._axis_num-1) + b"1" + b"X"*(self.parent._controller_model-self._axis_num) + b"\r"
            self.parent._control_socket.write(go_command)
            self.parent._control_socket.read_until(expected =b'>')
            pass
        finally:
            self.parent._restart_wait()
            pass
        pass

    def cancel(self):
        """Cancel any move in progress on this axis"""
        self.parent._abort_wait()
        try:
            kill_command = b"!K" + b"X"*(self._axis_num-1) + b"1" + b"X"*(self.parent._controller_model-self._axis_num) + b"\r"
            self.parent._control_socket.write(kill_command)
            self.parent._control_socket.read_until(expected=b'>')
            pass
        finally:
            self.parent._restart_wait()
            pass
        pass

    def _pulse_pos(self):
        # wait must be aborted already
        self.parent._control_socket.write(f"!{self._axis_num:d}TPC\r".encode("utf-8"))
        pos_str=self.parent._control_socket.read_until(expected =b'>')
        #print('pos_str=',pos_str)
        matchobj=re.match(rb"""\s*[*]\d+TPC([+-]\d+)""",pos_str)
        pos_steps = int(matchobj.group(1))
        return pos_steps
        
        
    @property
    def pos(self):
        """On read, returns the current axis position;
        on assignment initiates the move to the specified
        position"""
        self.parent._abort_wait()
        try:
            return (self._pulse_pos()/self._ppu)*self.unit_quantity
           
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
            num_pulses = int(round(raw_value*self._ppu)) - self._pulse_pos()
            if not self._enabled():
                raise ValueError("Axis is not enabled")
            self.parent._control_socket.write(f"{self._axis_num:d}D{num_pulses:d}\r".encode('utf-8'))
            self.parent._control_socket.read_until(expected =b'>')
            # create a command like GO1XXXXXXX with "1" positioned according to the axis number
            go_command = b"!GO" + b"X"*(self._axis_num-1) + b"1" + b"X"*(self.parent._controller_model-self._axis_num) + b"\r"
            self.parent._control_socket.write(go_command)
            self.parent._control_socket.read_until(expected =b'>')
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
                # issue !1DRIVE1 command to enable the drive
                self.parent._control_socket.write(f"!{self._axis_num:d}DRIVE1\r".encode("utf-8"))
                self.parent._control_socket.read_until(expected=b'>')
                pass
            else:
                # issue !1DRIVE0 command to disable the drive
                self.parent._control_socket.write(f"!{self._axis_num:d}DRIVE0\r".encode("utf-8"))
                self.parent._control_socket.read_until(expected=b'>')
                pass
            # print('enabled setter restarting wait')
            pass
        
        finally:
            self.parent._restart_wait()
            pass
        pass
    pass
class CM6kAllAxes(SimpleAxisGroup):
    def zero(self):
        '''This method zeros all axes of the CM6k controller'''
        self.parent._abort_wait()
        try:
            self.parent._control_socket.write(b"@PSET0\r")
            self.parent._control_socket.read_until(expected=b'>')
        finally:
            self.parent._restart_wait()
            pass
        pass
    pass


class CM6k(MotionControllerBase,metaclass=Module):
    _control_socket=None
    axis=None # Ordered dictionary of axis objects
    
    _waiter_cond=None # condition variable used to signal waiter thread and lock for wait_dict and wait_status
    _waiter_ack_cond = None # condition variable used by waiter thread to acknowledge. Uses same lock as waiter_cond
    _wait_list=None # list of tuples of (axis wait bitmask, waitevent) where wait events are represented as condition variables that use the same lock as waiter_cond, currently in progress. Wait bitmask is a numpy array of booleans of length _controller_model that is true for axes that we want to wait to stop 
    _waiter_thread=None # thread that handles waiting for motions to finish
    _wait_command=None # either "Cancel" or "Wait". Set by main thread
    _wait_status=None # either "Cancelled" (between WaitCancel() and
                     # WaitRestart()). Set by wait thread
                     # or "Waiting" (BASIC wait program running on ACR)
    _wait_exit=None  # set to True to trigger the wait thread to exit
    all=None # SimpleAxisGroup object representing all axes
    _controller_model=None # integer representing the 6k model number which is equivalent to the max axes, e.g. 4, 6, or 8
    
    def __init__(self,module_name,pyserial_url,controller_model,axis_defs,baud=9600):
        """Provide an axis definition list. This list
        should be a list of dictionaries with:
         * "name" axis name (string)
         * "ppu" pulses per default unit (integer)
         * "units" default unit (string)
         * "number" CM6k axis number, 1..controller_model (integer)
         * "accel" acceleration limit in default units per s^2
         * "vel" velocity limit in default units per s
         * "LH" hard limit enable; 0: disabled, 1: negative direction
            only, 2: positive direction only, 3: both directions on
            (integer)
         * "LS" hard limit enable; 0: disabled, 1: negative direction
            only, 2: positive direction only, 3: both directions on
            (integer)
         * "config" string containing axis configuration commands
            separated by line breaks (optional)
         * "config_debug" boolean to enable configuration debugging
            (optional)
        NOTE: This module is designed to operate with scaling disabled
              (SCALE0). Do not attempt to enable onboard scaling for
              an axis.
        
 To connect over ethernet to a CM6k, you need to connect on
 port 5002. If the controller thinks it is already connected
 then it will refuse connections

 In addition, you probably need to have the ethernet port it is
 connected to hardwired to 10Mbps half duplex and you probably
 need to manually add an arp entry for the device.
 On linux, e.g. sudo arp -s 172.16.1.1 00:90:55:00:df:dc
 On windows, e.g.
       netsh -c "interface ipv4"
       set neighbors "Local Area Connection" "172.16.1.1" "00-90-55-00-48-98"
 test the connection with ping:
       ping 172.16.1.1
 test the connection with telnet:
       telnet
       open 172.16.1.1 5002
        """

        
        
  
        self._controller_model = int(controller_model)
        
        
        ur = pint.get_application_registry()
        
        self._control_socket=dgpy.include(dgpy,'serial_device.dpi',port_name=pyserial_url,baudrate=baud,xonxoff=False)
        self.axis=collections.OrderedDict()
        self._wait_command="Cancel"
        self._wait_status="Starting"
        self._wait_exit=False
        self._wait_list=[]
        #_configure_socket(comm1)
        _set_timeout(self._control_socket,500) #Set timeout to 500ms
        self._control_socket.write(b"\r") # obtain a prompt

        gotbuf="Startup"
        total_gotbuf=b""
        while len(gotbuf) > 0:
            gotbuf=self._control_socket.read_until(expected=b">")
            total_gotbuf += gotbuf
            pass

        _set_timeout(self._control_socket,STARTUPTIMEOUT)
        self._control_socket.write(b"!K\r") # stop all axes
        response_K=self._control_socket.read_until(expected=b'>')
        self._control_socket.write(b"!HALT\r") # stop all programs
        response_HALT=self._control_socket.read_until(expected=b'>')
        
        time.sleep(0.25)
        # issue !DRIVE00000000 command to disable all drives
        self._control_socket.write(b"!DRIVE"+b"0"*self._controller_model+b"\r")
        self._control_socket.read_until(expected=b'>')
        
        self._control_socket.write(f'SCALE0\r'.encode('utf-8')) # disable internal scaling 
        self._control_socket.read_until(expected=b'>')
        # go through axes
        for axis_def in axis_defs:
            _axis_num = int(axis_def["number"])
            if _axis_num < 1 or _axis_num > self._controller_model:
                raise ValueError(f"invalid axis number {_axis_num:d}")
            axis_name=axis_def['name']
            ppu=axis_def["ppu"]
            self.axis[axis_name]=CM6kAxis(axis_name = axis_name,
                                                 _axis_num = _axis_num,
                                                 _ppu = int(axis_def["ppu"]),
                                                 unit_name = axis_def["units"],
                                                 unit_quantity = ur.Quantity(axis_def["units"]),
                                                 _unit_factor = CM6kAxis._units_to_factor(axis_def["units"]),
                                                 parent = self)
            # Configure axis per definitions

            if "config" in axis_def:
                # transmit custom configuration
                # can NOT include any programs
                # configuration block is presumed to contain command strings separated by new lines and/or carriage returns (will be converted into carriage returns)
                config = axis_def.replace("\n","\r") # convert all line feed characters to carriage return

                config_lines = config.split("\r") # break configuration into a list of strings that had been separated by \r

                for config_line in config_lines:
                    self._control_socket.write(config_line.encode('utf-8') + b"\r")
                    if 'config_debug' in axis_def and axis_def['config_debug']:
                        print(f"{module_name:s}:configuring axis {axis_name:s} with {config_line:s}...")
                        pass
                    response = self._control_socket.read_until(expected=b">")
                    if 'config_debug' in axis_def and axis_def['config_debug']:
                        print(f"{module_name:s}:response = \"{response.decode('utf-8'):s}\"")
                        pass
                    pass
                pass

            # determine feedback source for this axis
            self._control_socket.write(f'{_axis_num:d}SFB\r'.encode('utf-8')) # SFB to read servo feedback source
            axis_sfb = self._control_socket.read_until(expected=b'>').decode('utf-8')
            sfb_match = re.match(r''' *[*]\dSFB([012-])''',axis_sfb)
            if sfb_match is None:
                raise ValueError(f"SFB match failed on {axis_sfb:s}")
            if sfb_match.group(1) == '0' or sfb_match.group(1) == '-':
                # feedback disabled; use DRES
                RES = 'DRES'
                pass
            elif sfb_match.group(1) == '1':
                # encoder feedback; use ERES
                RES = 'ERES'
                pass
            elif sfb_match.group(1) == '2':
                # analog input; not implemented
                raise NotImplementedError('CM6k SFB analog feedback')
            else:
                assert(0)
                pass

            # Read resolution
            self._control_socket.write(f'{_axis_num:d}{RES:s}\r'.encode('utf-8')) 
            axis_res = self._control_socket.read_until(expected=b'>').decode('utf-8')
            res_match = re.match(r''' *[*]\d[DE]RES(\d+)''',axis_res)
            if res_match is None:
                raise ValueError(f"RES match failed on {axis_res:s}")
            resolution = float(res_match.group(1))

            # CM6k multiplies our given acceleration by DRES or ERES so we have to divide by it here
            accel=axis_def['accel']
            scaled_accel=abs(accel*ppu/resolution)
            self._control_socket.write(f'{_axis_num:d}A{scaled_accel:f}\r'.encode('utf-8')) # program acceleration
            self._control_socket.read_until(expected=b'>')

             # CM6k multiplies our given velocity by DRES or ERES so we have to divide by it here
            vel=axis_def['vel']
            scaled_vel=abs(vel*ppu/resolution)
            # print('scaled_vel ',scaled_vel)
            self._control_socket.write(f'{_axis_num:d}V{scaled_vel:f}\r'.encode('utf-8')) # program velocity
            self._control_socket.read_until(expected=b'>')

            LH=int(axis_def['LH'])
            self._control_socket.write(f'{_axis_num:d}LH{LH:d}\r'.encode('utf-8')) # program hardware limits enabled
            self._control_socket.read_until(expected=b'>')

            LS=int(axis_def['LS'])
            self._control_socket.write(f'{_axis_num:d}LS{LS:d}\r'.encode('utf-8')) # program software limits enabled
            self._control_socket.read_until(expected=b'>')

                
            if hasattr(self,axis_def['name']):
                raise ValueError(f"{module_name:s} axis {axis_name:s} shadows a method or attribute")
            setattr(self,axis_def['name'],self.axis[axis_def['name']])
            pass

        
        
        
       
        # Create an 'all' object that refers to all axes
        # self.all = self.create_group(list(self.axis.keys()))
        self.all=CM6kAllAxes(self,list(self.axis.keys()))
        
        # program to be written to CM6k
        # use VARB1 as mask and value
        #DEL dgpywt
        #DEF dgpywt
        #WHILE((MOV & VARB1)=VARB1)
        #NWHILE
        #WRITE"DONE"
        #END
        # when waiting, we will assign VARB1 and then run dgpywt

        # issue TDIR to list all programs and if DGPYWT is present
        # then we have to delete our program
        
        self._control_socket.write(b'TDIR\r')
        tdir=self._control_socket.read_until(expected=b'>') #"P00>"
        if b'DGPYWT' in tdir:
            self._control_socket.write(b'DEL dgpywt\r')
            self._control_socket.read_until(expected=b'>') #"P00>"
            pass
        
        self._control_socket.write(b'DEF dgpywt\r')
        self._control_socket.read_until(expected=b'-') # minus prompts betwee lines
        self._control_socket.write(b'VARB2=VARB1\r')
        self._control_socket.read_until(expected=b'-') # minus prompts betwee lines 
        self._control_socket.write(b'WHILE(VARB2=VARB1)\r') #
        self._control_socket.read_until(expected=b'-') # minus prompts betwee lines
        self._control_socket.write(b'VARB2=MOV & VARB1\r') #
        self._control_socket.read_until(expected=b'-') # minus prompts betwee lines
        self._control_socket.write(b'NWHILE\r')
        self._control_socket.read_until(expected=b'-') # minus prompts betwee lines
        self._control_socket.write(b'WRITE"DONE"\r')
        self._control_socket.read_until(expected=b'-') # minus prompts betwee lines
        self._control_socket.write(b'END\r')
        self._control_socket.read_until(expected=b'>') #"P00>"

        _set_timeout(self._control_socket,NORMALTIMEOUT)
        
        #self.read_lock=threading.Lock()
        #self.read_request_cond=threading.Condition(self.read_lock)
        #self.read_complete_cond=threading.Condition(self.read_lock)
        #self.reader_thread=threading.Thread(target=self._reader_thread_code)
        #self.reader_thread.start()

        self._waiter_cond=threading.Condition()
        self._waiter_ack_cond =threading.Condition(self._waiter_cond)
        self._wait_dict={}
        self._wait_status='Starting'
        self._waiter_thread=threading.Thread(target=self._waiter_thread_code)
        with self._waiter_cond:
            self._waiter_thread.start()
            self._waiter_ack_cond.wait_for(lambda: self._wait_status=="Cancelled")
            pass
        atexit.register(self.atexit) # Register an atexit function so that we can cleanly trigger our subthread to end. Otherwise we might well crash on exit.
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



     
    def atexit(self):
        # print("CM6k: Performing atexit()")
        InitCompatibleThread(self,'_atexit_thread')
        with self._waiter_cond:
            self._wait_exit = True;
            #Type !HALT
            self._control_socket.write(b'!HALT\r')
            #Wait for wait thread to exit
            self._waiter_cond.notify()
            pass
    
        self._waiter_thread.join()
        
        pass

    
    
    def _waiter_thread_code(self):
        # !VARB1=b10000000
        # RUN dgpywt
        # !HALT #immediately halts program execution
        
        InitCompatibleThread(self,'_waiter_thread')

        while True:
            with self._waiter_cond:
                if self._wait_command=='Cancel' and not self._wait_exit:
                    self._wait_status="Cancelled"
                    self._waiter_ack_cond.notify()
                    self._waiter_cond.wait_for(lambda: self._wait_command != "Cancel" or self._wait_exit)
                    pass
                elif self._wait_command=='Wait':
                    #self._wait_status="Waiting"
                    pass
                #self._waiter_ack_cond.notify()
                wait_command=self._wait_command
                wait_list=copy.copy(self._wait_list)

                if self._wait_exit: 
                    if self._wait_status == 'Waiting':
                        self._wait_status = 'Cancelled'
                        #terminate our wait program
                        #self._control_socket.write(b'!HALT\r')
                        pass
                    _set_timeout(self._control_socket,STARTUPTIMEOUT)
                    self._control_socket.read_until(expected=b'>')
                    # print('waiter thread exiting')
                    
                    return # waiter thread exit
                pass
            while wait_command=='Wait' and not self._wait_exit:
               
                # initiate the wait by programming VARB1 and then issuing the run command
                # we want to wait for any axis listed in _wait_list to stop moving
                total_bitmask=np.zeros(self._controller_model,dtype=bool)
                for (wait_bitmask,wait_cond) in wait_list:
                    total_bitmask=total_bitmask | wait_bitmask
                    pass
                # construct a line like !VARB1=b01001000\r based on total bitmask
                self._control_socket.write(b'!VARB1=b'+b''.join([b'1' if bitval else b'0' for bitval in total_bitmask]) + b'\r')
                self._control_socket.read_until(expected=b'>')
                # print('waiter thread running dgpywt')
                self._control_socket.write(b'!RUN dgpywt\r')
                with self._waiter_cond:
                    self._wait_status="Waiting"
                    self._waiter_ack_cond.notify()
                    pass
                #response=self._read()
                response=self._control_socket.read_until(expected=b'>') 
                # print(f'waiter thread got response {str(response):s}')
                assert(response is not None)
                
                donepos=response.find(b'DONE')
                if donepos >= 0 and donepos < len(response):
                    # check which axes are moving
                    self._control_socket.write(b'!TAS.1\r')
                    moving = self._control_socket.read_until(expected=b'>')
                    movingmatch=re.match(rb'\s*[*]([01]+)',moving)
                    assert(movingmatch is not None)
                    moving_np=np.array([moving_char==b'1' for moving_char in movingmatch.group(1)],dtype=bool)
                    with self._waiter_cond:
                        new_wait_list=[]
                        for (wait_bitmask,wait_cond) in self._wait_list:
                            if (moving_np & wait_bitmask).any():
                                # if any of the axes of interest are still moving, then we don't interrupt the wait
                                new_wait_list.append(wait_bitmask,wait_cond)
                                pass
                            else:
                                # all of these axes have stopped
                                wait_cond.notify()
                                # implicitly remove from new_wait_list
                                pass
                            pass
                        self._wait_list = new_wait_list
                        pass
                    pass
                with self._waiter_cond:
                    wait_command=self._wait_command
                    wait_list=self._wait_list
                    pass 


                      
                pass
            pass
        pass


    def wait(self,axis_name_list):
        """Waits for each axis named in the given list to stop moving"""
        self._abort_wait()
        try:
            bitmask=np.zeros(self._controller_model,dtype=bool)
            for axis_name in axis_name_list:
                axis_num=self.axis[axis_name]._axis_num
                bitmask[axis_num]=True
                pass
            with self._waiter_cond:
                _wait_cond = threading.Condition(lock=self._waiter_cond)
                self._wait_list.append((bitmask,_wait_cond))
                pass
            pass
        finally:
            self._restart_wait()
            pass
        with dgpy.UnprotectedContext:
            with _wait_cond:
                _wait_cond.wait()
                pass
            pass
        pass

    def _restart_wait(self):
        # trigger the wait thread to restart the wait
        assert(self._wait_status == 'Cancelled')
        # print('restart wait starting')
        with self._waiter_cond:
            assert(self._wait_status=="Cancelled")
            self._wait_command="Wait"
            self._waiter_cond.notify()
            # print('restart wait waiting')
            self._waiter_ack_cond.wait_for(lambda: self._wait_status=="Waiting")
            # print('restart wait complete')
            pass

        
        pass
    def _abort_wait(self):
        # issue the !HALT command so that the wait thread wakes up
        assert(self._wait_status == 'Waiting')
#        import pdb
 #       pdb.set_trace()
        # print('abort_wait')
        with self._waiter_cond:
            self._wait_command = 'Cancel'
            
            #Type !HALT
            self._control_socket.write(b'!HALT\r')
            self._waiter_cond.notify()
            #Wait for wait thread to acknowledge prompt
            # print('abort waiting for acknowledgement')
            self._waiter_ack_cond.wait_for(lambda: self._wait_status=="Cancelled")
            # print('abort complete')
            pass
        pass
    
                
    pass
