
cdef extern from "dgold_module_c.h":
    void ModWakeupLoop() nogil
    pass

cdef extern from "dgold_locking_c.h":
    void dg_enter_main_context_c() nogil
    void dg_leave_main_context_c() nogil
    void dg_enter_main_context() 
    void dg_leave_main_context() 
    void dg_main_context_init() nogil
    pass
