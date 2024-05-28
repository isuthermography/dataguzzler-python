import pyvisa
import pyvisa.constants

def user_select_device(visa_rm,
                       visa_resources,
                       module_name=None,
                       description=None,
                       access_mode=pyvisa.constants.AccessModes.no_lock,
                       open_timeout=0,
                       resource_pyclass=None):
    formatted_res=[f"Device #{idx:d}: '{visa_resources[idx]:s}'" for idx in range(len(visa_resources))]
    print("\n".join(formatted_res))
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
    res_name = visa_resources[chosen_idx]
    inst = visa_rm.open_resource(res_name,
                                 access_mode=access_mode,
                                 open_timeout=open_timeout,
                                 resource_pyclass=resource_pyclass)
    return inst
