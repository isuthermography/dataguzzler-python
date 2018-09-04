import sys
import serial 
import re

from limatix.dc_value import numericunitsvalue as nuv

from dataguzzler_python import pydg

class kevextube(object,metaclass=pydg.Module):
    ser=None

    def __init__(self,portname):
        # baud rate 38400, 8,n,1
        self.ser=serial.Serial(portname,baudrate=38400,bytesize=serial.EIGHTBITS,parity=serial.PARITY_NONE,stopbits=serial.STOPBITS_ONE,rtscts=True)
        pass

    def _parse(self,line):
        # Parse response from tube
        #sys.stderr.write("kevextube: Parsing response %s; line[0]=%s\n" % (line.decode('utf-8'),repr(line[0])))
        assert(line[0]==b'!'[0])
        assert(line[1]==b' '[0])
        assert(line[-1]==b'\n'[0])
        assert(line[-2]==b'\r'[0])
        
        return line[2:-2]

    def BeamCurrent(self,current=None):
        if current is not None:
            self.ser.write(b"BEAM %d\r\n" % (int(current.value("microamps"))))
            pass
        else: 
            self.ser.write(b"BEAM SETTING\r\n")
            pass

        echo=self.ser.readline()
        resp=self._parse(self.ser.readline())
        #sys.stderr.write("Got BEAM read response %s\n" % (resp))

        assert(resp.startswith(b"Beam setting "))
        assert(resp.endswith(b" uA"))
        uA=int(resp[13:-3])
        return uA*nuv("1 microamp")

    def BeamCurrentMeas(self):
        self.ser.write(b"BEAM\r\n")
        echo=self.ser.readline()
        resp=self._parse(self.ser.readline())
        #sys.stderr.write("Got BEAM read response %s\n" % (resp))
        assert(resp.startswith(b"Beam measured "))
        assert(resp.endswith(b" uA"))
        uA=float(resp[14:-3])
        
        return uA*nuv("1 microamp")

    def BeamVoltage(self,voltage=None):
        if voltage is not None:
            self.ser.write(b"HV %d\r\n" % (float(voltage.value("kilovolts"))))
            pass
        else:
            self.ser.write(b"HV SETTING\r\n")
            pass
        
        echo=self.ser.readline()
        resp=self._parse(self.ser.readline())
        #sys.stderr.write("Got HV write response %s\n" % (resp))
        assert(resp.startswith(b"HV setting "))
        assert(resp.endswith(b" KV"))
        kV = float(resp[11:-3].strip())
        return kV*nuv("1 kilovolt")

    def BeamVoltageMeas(self):
        self.ser.write(b"HV\r\n")
        echo=self.ser.readline()
        resp=self._parse(self.ser.readline())
        #sys.stderr.write("Got HV read response %s\n" % (resp))
        assert(resp.startswith(b"HV Measured "))
        assert(resp.endswith(b" KV"))
        
        kV = float(resp[12:-3].strip())
        
        return kV*nuv("1 kilovolt")
        
    def status(self,bool_onoff=None):
        if bool_onoff is not None:
            if bool_onoff is True:
                statusstr=b"ON"
                pass
            else: 
                statusstr=b"OFF"
                pass
                
            self.ser.write(b"XRAY %s\r\n" % (statusstr))
            echo=self.ser.readline()
            resp=self._parse(self.ser.readline())
            if resp==b"OK":
                return statusstr==b"ON"
            else:
                raise ValueError("Bad XRAY response %s" % (resp))
            
            #sys.stderr.write("Got XRAY write response %s\n" % (resp))

            pass
            
        self.ser.write(b"XRAY\r\n")
        echo=self.ser.readline()
        resp=self._parse(self.ser.readline())
        #sys.stderr.write("Got XRAY read response %s\n" % (resp))
        if resp.strip()=="ON":
            return True
        return False
        

    pass

#if __name__=="__main__":
#    tube=kevextube("/dev/ttyUSBXRayTube")
#    pass
