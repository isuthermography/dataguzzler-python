import sys
from Cython.Build import cythonize
#from numpy.distutils.core import setup as numpy_setup, Extension as numpy_Extension
from setuptools import setup, Extension
import numpy as np


#ext_modules=cythonize("dataguzzler_python/*.pyx")

dgold_ext= Extension("dataguzzler_python.dgold",
                         sources=["dataguzzler_python/dgold.pyx","dataguzzler_python/dgold_rpc_c.c"],
                         include_dirs=[ np.get_include() ] + ["/usr/local/dataguzzler-lib/include","/usr/local/dataguzzler/include/dg_internal"],
                         library_dirs=[ "/usr/local/dataguzzler-lib/lib", "/usr/local/dataguzzler/lib/dg_internal"],
                         libraries=[ "dg_internal", "dg_comm", "dataguzzler" ],
                         extra_link_args=["-shared-libgcc","-lrt","-lgcc","-lpthread","-Wl,-rpath,/usr/local/dataguzzler/lib/dg_internal","-Xlinker","--export-dynamic","-Wl,-rpath,/usr/local/dataguzzler-lib/lib"])

ext_modules=[ dgold_ext ]
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
            package_data={ "dataguzzler_python": []},
            entry_points={"console_scripts": console_scripts_entrypoints })
