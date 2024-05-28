import sys
import collections

from dataguzzler_python.dgpy import Module

STARTUPTIMEOUT=600 # ms
NORMALTIMEOUT=None # disable timeout

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
    
class axis:
    axis_name=None 
    proglevel=None # acr9000 program level assigned to this axis (integer)
    axis_num=None # axis0, axis1, ... (integer)
    ppu=None # pulses per unit (float)
    unit_factor=None # unit factor. Sign is a flag for linear vs. rotational.
              # if positive, factor relative to mm. If negative,
              # factor relative to deg. (float)
    configured=None # boolean, set once axis is fully configured
    enabled=None # boolean, is drive turned on
    targetpos=None # target position (float)

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
        if quant.is_compatible_with(ur.meter):
            factor = float(quant/ur.meter)
            pass
        elif quant.is_compatible_with(ur.degree):
            factor = -float(quant/ur.degree)
            pass
        else:
            raise ValueError(f'incompatible units: {units:s}')
        return factor 
    pass

class acr9000(metaclass=Module):
    control_socket=None
    spareprog=None # program level not used by any axis
    axisdict=None
    reader_thread=None # dedicated thread needed for reading because there is no interruptible or asynchronous read functionality consistently available.
    read_lock=None # lock for read_complete_cond and read_request_cond
    read_request_cond=None # condition variable for notifying read request
    read_complete_cond=None # condition variable for notifying read complete
    read_request=None # list provided by requester. Filled out with success flag and result string. Locked by read_lock

    
    waiter_cond=None # condition variable for wait list and waiter thread and wait_dict and wait_status
    wait_dict=None # dictionary by BASIC conditonal line number of wait events currently in progress 
    waiter_thread=None # thread that handles waiting for motions to finish
    wait_status=None # either "Cancelled" (between WaitCancel() and
                     # WaitRestart())
                     # or "NothingToWait" (wait restarted but nothing to wait for)
                     # or "Waiting" (BASIC wait program running on ACR)

    
    def __init__(self,module_name,comm1,**axis_units):
        self.control_socket=comm1
        self.spareprog=15
        self.axisdict=collection.OrderedDict()
        self.wait_status="Cancelled"
        _configure_socket(comm1)
        self.control_socket.write("HALT ALL\r") # stop all axes
        response=self.control_socket.read()
        assert(response=="SYS>")

        # search for axes
        for proglevel in range(NUMPROGLEVELS):
            self.control_socket.write(f"PROG{proglevel:d}\r")
            response=self.control_socket.read()
            matchobj=re.match(r""" *PROG\d+ +P(\d+) *""",response)
            if matchobj is not None:
                response_proglevel=int(matchobj.group(1))
                if response_proglevel==proglevel:
                    # successful match
                    # print(f"found program level {proglevel:d}")
                    self.control_socket.write("ATTACH\r")
                    attach_response=self.control_socket.read()
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
                                self.control_socket.write(f'AXIS{axis_num:d} PPU\r')
                                ppu_response=self.control_socket.read()
                                ppu_match = re.match(" *AXIS\\d+ PPU\r\n([-+]?(\\d+(\\.\\d*)?|\\.\\d+)([eE][-+]?\\d+)?)\r\nP\\d+>",ppu_response)
                                if ppu_match is None:
                                    raise ValueError(f'Bad PPU line for axis {axis_name:s}')
                                ppu = float(ppu_match.group(4))
                                Axis = axis(axis_name=axis_name,
                                            proglevel=proglevel,
                                            axis_num=axis_num,
                                            ppu=ppu,
                                            unit_factor=unit_factor,
                                            configured=True,
                                            enabled=False)
                                axisdict[axis_name]=Axis
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
        #Use spareprog to store our monitoring program
        self.control_socket.write(f'PROG{self.spareprog:d}\r')
        self.control_socket.read() #"P00>"
        
        self.control_socket.write('HALT\r')
        self.control_socket.read() #"P00>"
        
        self.control_socket.write('NEW\r') #Clear program memory
        self.control_socket.read() #"P00>"

        self.control_socket.write('SYS\r')
        self.control_socket.read() #"SYS>"

        self.control_socket.write('DIM P (100)\r') #Reserve variables 
        self.control_socket.read() #"SYS>"

        self.control_socket.write('DIM DEF (100)\r') #Reserve variable definitions
        self.control_socket.read() #"SYS>"

        self.control_socket.write(f'DIM PROG {self.spareprog:d} 16384\r') #Reserve 4 integer variables
        self.control_socket.read() #"SYS>"

        self.control_socket.write(f'PROG{self.spareprog:d}\r')
        self.control_socket.read() #"P00>"

        self.control_socket.write(f'#DEFINE EXITFLAG P0\r') #Flag is integer var #0
        self.control_socket.read() #"P00>"

        self.control_socket.write('5 PRINT \"STRT <\"\r') #Program starting printout
        self.control_socket.read() #"P00>"

        self.control_socket.write('10 REM start of main loop\r')
        self.control_socket.read() #"P00>"

        #The various waits will insert additional lines of code here that check the termination conditions and jump to line 1000 when a condition is satisfied 
        self.control_socket.write('999 GOTO 10\r')
        self.control_socket.read() #"P00>"

        self.control_socket.write('1000 PRINT \"EXITFLAG=\";EXITFLAG;\" <\"\r')
        self.control_socket.read() #"P00>"

        self.control_socket.write('1005 REM Just busy-loop until the user presses escape\r') #This is because the program ending itself triggers an ACR9000  firmware bug 
        self.control_socket.read() #"P00>"

        self.control_socket.write('1007 GOTO 1007\r')
        self.control_socket.read() #"P00>"

        #Turn off all axes
        for axis_name in self.axis_dict:
            Axis=axis_dict[axis_name]
            self.control_socket.write(f'PROG{Axis.proglevel:d}\r')
            self.control_socket.read() #"P00>"

            # issue REN command to cancel any preexisting position
            self.control_socket.write(f'REN {Axis.axis_name:s}\r')
            self.control_socket.read() #"P00>"

            self.control_socket.write(f'P{_targetpos[Axis.axis_num]:d}=P{_trajectorypos[Axis.axis_num]:d}\r') # set the target equal to the actual position
            self.control_socket.read() #"P00>"

            self.control_socket.write(f'DRIVE OFF {Axis.axis_name:s}\r')
            self.control_socket.read() #"P00>"

            # enable multiple-move buffering on this program level
            self.control_socket.write(f'DIM MBUF(10)\r')
            self.control_socket.read() #"P00>"

            self.control_socket.write(f'MBUF ON\r')
            self.control_socket.read() #"P00>"
            pass

        self.read_lock=threading.Lock()
        self.read_request_cond=threading.Condition(self.read_lock)
        self.read_complete_cond=threading.Condition(self.read_lock)
        self.reader_thread=threading.Thread(target=self._reader_thread_code)
        self.reader_thread.start()

        self.waiter_cond=threading.Condition()
        self.wait_dict={}
        self.wait_status='Cancelled'
        self.waiter_thread=threading.Thread(target=self._waiter_thread_code)
        self.waiter_thread.start()
        pass

    def _read(self):
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
                    rdbytes=self.control_socket.read()
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

    def _waiter_thread_code(self):
        InitCompatibleThread(self)

        while True:
            with self.waiter_cond:
                if self.wait_status=='Cancelled':
                    self.waiter_cond.wait()
                    pass
                wait_status=self.wait_status
                pass
            if wait_status=='Waiting':
                with self: # grab our module lock context
                    response=self._read()
                    efpos=response.find('EXITFLAG')
                    assert(efpos >= 0)
                    efmatch=re.match(r'EXITFLAG=(\d+)',response[efpos:])
                    assert(efmatch is not None)
                    linenum=efmatch.group(1)
                    
                    with self.waiter_cond:
                        wait_obj=self.wait_dict[linenum]
                        del self.wait_dict[linenum]
                        wait_obj.notify()
                        pass
                
                    pass
                
                
                
            
        

        
    pass
