/* Use these functions from Cython code where you hold the GIL */
void dg_enter_main_context(void);
void dg_leave_main_context(void);

/* Use these functions from C code where you do not hold the GIL, or Cython code within a "with nogil" block */
void dg_enter_main_context_c(void);
void dg_leave_main_context_c(void);
void dg_main_context_init(void);


