import serial

from serial.tools.list_ports import comports

serial_devices = list(comports())

def find_serial_device(hwinfo):
    """Given a (portion of a) hardware info field (3rd entry or .hwid attribute) of the
    serial_devices list, find the name of the corresponding serial device"""
    filtered = [ device for device in serial_devices if hwinfo in port.hwid ]
    if len(filtered) < 1:
        raise NameError("Serial device matching \"%s\" not found" % (hwinfo))
    if len(filtered) > 1:
        raise NameError("Multiple serial devices matching \"%s\" found" % (hwinfo))
    return filtered[0].device

def user_select_device(serial_devices,
                     module_name=None,
                     description=None,
                     baudrate=9600,
                     bytesize=serial.EIGHTBITS,
                     parity=serial.PARITY_NONE,
                     stopbits=serial.STOPBITS_ONE,
                     timeout=None,
                     xonxoff=False,
                     rtscts=False,
                     write_timeout=None,
                     dsrdtr=None,
                     inter_byte_timeout=None):
    formatted_devices=[f"Device #{idx:d}: '{serial_devices[idx].device:s}' hwid='{serial_devices[idx].hwid:s}'" for idx in range(len(serial_devices))]
    print("\n".join(formatted_devices))
    print("(q to quit)")
    if module_name is None and description is None:
        prompt = "Select device --> "
        pass
    elif module_name is None and description is not None:
        prompt = f"Select {description:s} device --> "
        pass
    elif module_name is not None and description is None:
        prompt = f"Select device for module \"{module_name:s}\" --> "
        pass
    else:
        assert(module_name is not None and description is not None)
        prompt = f"Select {description:s} device for module \"{module_name:s}\" --> "
        pass
    chosen = input(prompt)
    if chosen == 'q' or chosen == 'Q':
        return None
    chosen_idx = int(chosen)
    res_name = serial_devices[chosen_idx].device
    inst = serial.Serial(res_name,
                         baudrate=baudrate,
                         bytesize=bytesize,
                         parity=parity,
                         stopbits=stopbits,
                         timeout=timeout,
                         xonxoff=xonxoff,
                         rtscts=rtscts,
                         write_timeout=write_timeout,
                         dsrdtr=dsrdtr,
                         inter_byte_timeout=inter_byte_timeout)
    return inst
#!!!*** Consider adding proper buffered read
