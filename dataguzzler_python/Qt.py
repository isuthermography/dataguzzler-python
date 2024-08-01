""" This module provides support for loading Qt and compatiblity with 
both PySide2 and PyQt5, plus easy extensibility to PySide6 and PyQt6 """

import sys
import os
import os.path
import importlib
import threading
import pkgutil

from dataguzzler_python import QtConfig
from dataguzzler_python import context



def Import_SubModule(qtmodname):
    module = importlib.import_module(selected_bindings + "." + qtmodname)
    if not("." in qtmodname) and not qtmodname in globals():
        # Add it as an attribute of our module too
        globals()[qtmodname] = module
        pass
    elif "." in qtmodname and not qtmodname.split(".")[0] in globals():
        # Add base as an attribute of our module too
        globals()[qtmodname.split(".")[0]] = importlib.import_module(selected_bindings + "." + qtmodname.split(".")[0])
        pass
    return module


        


pyside2_loaded = "PySide2" in sys.modules
pyside6_loaded = "PySide6" in sys.modules
pyqt5_loaded = "PyQt5" in sys.modules

selected_bindings = None

if not(pyside2_loaded or pyside6_loaded or pyqt5_loaded) and QtConfig.prefer_pyqt:
    selected_bindings = "PyQt5"
    pass
elif not(pyside2_loaded or pyside6_loaded or pyqt5_loaded):
    selected_bindings = "PySide2"
    # Check if SpatialNDE2 is built for PySide2 versus PySide6
    spatialnde2_loader = pkgutil.get_loader("spatialnde2")

    if spatialnde2_loader is not None:
        spatialnde2_path = spatialnde2_loader.get_filename()
        spatialnde2_dirpath = os.path.dirname(spatialnde2_path)
        compile_definitions_path = os.path.join(spatialnde2_dirpath, "compile_definitions.txt")
        with open(compile_definitions_path, "r") as fh:
            compile_definitions_str = fh.read()
            pass
        spatialnde2_qt6_enabled = "-DSNDE_ENABLE_QT6=1" in compile_definitions_str
        if spatialnde2_qt6_enabled:
            selected_bindings = "PySide6"
            pass
        pass
    pass
else:
    if pyside2_loaded:
        selected_bindings = "PySide2"
        pass
    elif pyside6_loaded:
        selected_bindings = "PySide6"
        pass
    elif pyqt5_loaded:
        selected_bindings = "PyQt5"
        pass
    else:
        selected_bindings = "PySide2"
        pass
    pass

if selected_bindings is None:
    raise ImportError(f"No suitable Qt Python bindings found; suggest installing PySide2 or PySide6 depending on the version of Qt that your SpatialNDE2 uses.")

if threading.current_thread() is not threading.main_thread():
    raise RuntimeError("Qt may only be imported from main thread")

Qt = None

#Disable loading alternative bindings to get clearer error messages about what is needed
#try: 
Qt = importlib.import_module(selected_bindings)
#    pass
#except ImportError as origexcept:
#    # Attempt swap
#    if selected_bindings == "PySide2":
#        alternative_bindings = "PyQt5"
#        pass
#    else:
#        alternative_bindings = "PySide2"
#        pass
#    try:
#        Qt = importlib.import_module(alternative_bindings)
#        selected_bindings = alternative_bindings
#        pass
#    except ImportError:
#        pass
#
#    if selected_bindings != alternative_bindings:
#        # Second import failed; re-raise original exception
#        raise origexcept
#    pass

Import_SubModule("QtCore")
Import_SubModule("QtWidgets")
Import_SubModule("QtGui")

if selected_bindings=="PyQt5":
    QtSlot = QtCore.pyqtSlot
    QtSignal = QtCore.pyqtSignal
    pass
else:
    QtSlot = QtCore.Slot
    QtSignal = QtCore.Signal
    pass

import dataguzzler_python.QtWrapper

def QtEventLoop(qapp):
    #sys.stdout.write("QtEventLoop Context: %s\n" % context.FormatCurContext())
    #sys.stdout.write("qapp.quitOnLastWindowClosed = %s\n" % str(qapp.quitOnLastWindowClosed
    #sys.stdout.flush()
    qapp.exec_()
    pass

