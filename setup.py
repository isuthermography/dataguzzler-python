import sys
from Cython.Build import cythonize
#from numpy.distutils.core import setup as numpy_setup, Extension as numpy_Extension
from setuptools import setup, Extension
import numpy as np


#ext_modules=cythonize("dataguzzler_python/*.pyx")

dgold_ext= Extension("dataguzzler_python.dgold",
                         sources=["dataguzzler_python/dgold.pyx","dataguzzler_python/dgold_rpc_c.c","dataguzzler_python/dgold_module_c.c","dataguzzler_python/dgold_locking_c.c"],
                         include_dirs=[ np.get_include() ] + ["/usr/local/dataguzzler-lib/include","/usr/local/dataguzzler/include/"],
                         library_dirs=[ "/usr/local/dataguzzler-lib/lib", "/usr/local/dataguzzler/lib/dg_internal"],
                     extra_compile_args=["-g","-O0"],
                         libraries=[ "dg_internal", "dg_comm", "dataguzzler", "dg_units" ],
                         extra_link_args=["-g","-shared-libgcc","-lrt","-lgcc","-lpthread","-Wl,-rpath,/usr/local/dataguzzler/lib/dg_internal","-Xlinker","--export-dynamic","-Wl,-rpath,/usr/local/dataguzzler-lib/lib"])
savewfm_ext=Extension("dataguzzler_python.savewfm",
                      sources=["dataguzzler_python/savewfm.pyx" ],
                      include_dirs=[ np.get_include() ] + ["/usr/local/dataguzzler-lib/include","/usr/local/dataguzzler/include/"],
                         library_dirs=[ "/usr/local/dataguzzler-lib/lib", "/usr/local/dataguzzler/lib/dg_internal"],
                         libraries=[ "dg_internal", "dg_comm", "dataguzzler", "dg_units" ],
                     extra_compile_args=["-g","-O0"],
                         extra_link_args=["-g","-shared-libgcc","-lrt","-lgcc","-lpthread","-Wl,-rpath,/usr/local/dataguzzler/lib/dg_internal","-Xlinker","--export-dynamic","-Wl,-rpath,/usr/local/dataguzzler-lib/lib"])

ext_modules=[ dgold_ext,savewfm_ext ]
console_scripts=["dataguzzler_python"]

console_scripts_entrypoints = [ "%s = dataguzzler_python.bin.%s:main" % (script,script) for script in console_scripts ]




if sys.version_info < (3,6,0):
    raise ValueError("Insufficient Python version: Requires Python 3.6 or above")


setup(name="dataguzzler_python",
            description="dataguzzler_python",
            author="Stephen D. Holland",
            url="http://thermal.cnde.iastate.edu",
            ext_modules=ext_modules,
            packages=["dataguzzler_python","dataguzzler_python.bin"],
            package_data={ "dataguzzler_python": [ "__init__.pxd", "wfmstore.pxd","dg_internal.pxd","dgold.pxd","dgold_module_c.h","dgold_locking_c.h" ]},
            entry_points={"console_scripts": console_scripts_entrypoints })
