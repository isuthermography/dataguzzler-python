import sys
#from numpy.distutils.core import setup as numpy_setup, Extension as numpy_Extension
if "--with-dgold" in sys.argv:
    from Cython.Build import cythonize
    pass

from setuptools import setup, Extension
import numpy as np

from setuptools.command.install import install
from distutils.command.build import build

class InstallCommand(install):
    user_options = install.user_options + [
        ("with-dgold",None,"Enable dgold module")
        ]
    boolean_options=install.boolean_options+["with-dgold"]
    def initialize_options(self):
        super().initialize_options()
        self.with_dgold=False
        pass
    pass

class BuildCommand(build):
    user_options = build.user_options + [
        ("with-dgold",None,"Enable dgold module")
        ]
    boolean_options=build.boolean_options+["with-dgold"]
    def initialize_options(self):
        super().initialize_options()
        self.with_dgold=False
        pass
    pass

ext_modules = []
package_data = {
    "dataguzzler_python": ["*.dpi"]
}

if "--with-dgold" in sys.argv:
    
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
    
    ext_modules.append(dgold_ext)
    ext_modules.append(savewfm_ext)

    package_data["dataguzzler_python"].extend(["__init__.pxd", "wfmstore.pxd","dg_internal.pxd","dgold.pxd","dgold_module_c.h","dgold_locking_c.h"])
    
    pass

console_scripts=["dataguzzler-python"]

console_scripts_entrypoints = [ "%s = dataguzzler_python.bin.%s:main" % (script,script.replace("-",'_')) for script in console_scripts ]




if sys.version_info < (3,6,0):
    raise ValueError("Insufficient Python version: Requires Python 3.6 or above")



setup(name="dataguzzler_python",
      description="dataguzzler_python",
      author="Stephen D. Holland",
      url="http://thermal.cnde.iastate.edu",
      ext_modules=ext_modules,
      zip_safe=False,
      cmdclass={
          "install": InstallCommand,
          "build": BuildCommand
      },
      packages=["dataguzzler_python","dataguzzler_python.bin"],
      package_data=package_data,
      entry_points={"console_scripts": console_scripts_entrypoints })
