/* Generated by Cython 0.28.4 */

#ifndef __PYX_HAVE__dataguzzler_python__dgold
#define __PYX_HAVE__dataguzzler_python__dgold


#ifndef __PYX_HAVE_API__dataguzzler_python__dgold

#ifndef __PYX_EXTERN_C
  #ifdef __cplusplus
    #define __PYX_EXTERN_C extern "C"
  #else
    #define __PYX_EXTERN_C extern
  #endif
#endif

#ifndef DL_IMPORT
  #define DL_IMPORT(_T) _T
#endif

__PYX_EXTERN_C struct AtExitFunc *AddAtExitFunc(void (*)(struct AtExitFunc *, void *), void *);

__PYX_EXTERN_C char *SetQueryPrefix;
__PYX_EXTERN_C char *SetQueryPostfix;
__PYX_EXTERN_C int dg_PosixClock;
__PYX_EXTERN_C struct Module *DefaultModule;
__PYX_EXTERN_C char *commandname;
__PYX_EXTERN_C struct dgl_List InitActionList;
__PYX_EXTERN_C struct dgl_List ConnList;
__PYX_EXTERN_C struct dgl_List ModuleList;

#endif /* !__PYX_HAVE_API__dataguzzler_python__dgold */

/* WARNING: the interface of the module init function changed in CPython 3.5. */
/* It now returns a PyModuleDef instance instead of a PyModule instance. */

#if PY_MAJOR_VERSION < 3
PyMODINIT_FUNC initdgold(void);
#else
PyMODINIT_FUNC PyInit_dgold(void);
#endif

#endif /* !__PYX_HAVE__dataguzzler_python__dgold */
