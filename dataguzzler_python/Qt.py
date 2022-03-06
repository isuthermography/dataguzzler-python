""" This module provides support for loading Qt and compatiblity with 
both PySide2 and PyQt5, plus easy extensibility to PySide6 and PyQt6 """

import sys
import importlib
import threading

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


        


pyside_loaded = "PySide2" in sys.modules
pyqt_loaded = "PyQt5" in sys.modules

selected_bindings = None

if not(pyside_loaded ^ pyqt_loaded) and QtConfig.prefer_pyqt:
    selected_bindings = "PyQt5"
    pass
elif not(pyside_loaded ^ pyqt_loaded):
    selected_bindings = "PySide2"
    pass
else:
    if pyside_loaded:
        selected_bindings = "PySide2"
        pass
    else:
        selected_bindings = "PyQt5"
        pass
    pass

if threading.current_thread() is not threading.main_thread():
    raise RuntimeError("Qt may only be imported from main thread")

Qt = None

try: 
    Qt = importlib.import_module(selected_bindings)
    pass
except ImportError as origexcept:
    # Attempt swap
    if selected_bindings == "PySide2":
        alternative_bindings = "PyQt5"
        pass
    else:
        alternative_bindings = "PySide2"
        pass
    try:
        Qt = importlib.import_module(alternative_bindings)
        selected_bindings = alternative_bindings
        pass
    except ImportError:
        pass

    if selected_bindings != alternative_bindings:
        # Second import failed; re-raise original exception
        raise origexcept
    pass

Import_SubModule("QtCore")
Import_SubModule("QtWidgets")

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

