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


# Check if SpatialNDE2 is built for Qt5 versus Qt6
spatialnde2_loader = pkgutil.get_loader("spatialnde2")
spatialnde2_qt_version=None
if spatialnde2_loader is not None:
    spatialnde2_path = spatialnde2_loader.get_filename()
    spatialnde2_dirpath = os.path.dirname(spatialnde2_path)
    compile_definitions_path = os.path.join(spatialnde2_dirpath, "compile_definitions.txt")
    with open(compile_definitions_path, "r") as fh:
        compile_definitions_str = fh.read()
        pass
    _spatialnde2_qt6_enabled = "-DSNDE_ENABLE_QT6=1" in compile_definitions_str
    if _spatialnde2_qt6_enabled:
        spatialnde2_qt_version="6"
        pass
    else:
        spatialnde2_qt_version="5"
        pass
    pass




pyside2_loaded = "PySide2" in sys.modules
pyside6_loaded = "PySide6" in sys.modules
pyqt5_loaded = "PyQt5" in sys.modules
pyqt6_loaded = "PyQt6" in sys.modules

selected_bindings = None

if not(pyside2_loaded or pyside6_loaded or pyqt5_loaded or pyqt6_loaded) and QtConfig.prefer_pyqt:
    if spatialnde2_qt_version=="6":
        selected_bindings="PyQt6"
        pass
    else:
        selected_bindings = "PyQt5"
        pass
    pass
elif not(pyside2_loaded or pyside6_loaded or pyqt5_loaded or pyqt6_loaded):
    selected_bindings = "PySide2"
    if spatialnde2_qt_version=="6":
        selected_bindings = "PySide6"
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
    elif pyqt6_loaded:
        selected_bindings = "PyQt6"
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


try:
    Qt = importlib.import_module(selected_bindings)
    pass
except ImportError as origexcept:
    # Attempt swap
    if selected_bindings == "PySide2":
        alternative_bindings = "PyQt5"
        pass
    elif selected_bindings == "PyQt5":
        alternative_bindings = "PySide2"
        pass
    elif selected_bindings == "PySide6":
        alternative_bindings = "PyQt6"
        pass
    elif selected_bindings == "PyQt6":
        alternative_bindings = "PySide6"
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
Import_SubModule("QtGui")
Import_SubModule("QtNetwork")

if selected_bindings=="PyQt5" or selected_bindings == "PyQt6":
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


# From https://stackoverflow.com/questions/4938723/what-is-the-correct-way-to-make-my-pyqt-application-quit-when-killed-from-the-co
# Ensures that Qt will redirect signals to Python, enabling SIGINT to work correctly
import socket
import signal
class SignalWakeupHandler(QtNetwork.QAbstractSocket):

    def __init__(self, parent=None):
        super().__init__(QtNetwork.QAbstractSocket.UdpSocket, parent)
        self.old_fd = None
        # Create a socket pair
        self.wsock, self.rsock = socket.socketpair(type=socket.SOCK_STREAM)
        # Let Qt listen on the one end
        self.setSocketDescriptor(self.rsock.fileno())
        # And let Python write on the other end
        self.wsock.setblocking(False)
        self.old_fd = signal.set_wakeup_fd(self.wsock.fileno())
        # First Python code executed gets any exception from
        # the signal handler, so add a dummy handler first
        self.readyRead.connect(lambda : None)
        # Second handler does the real handling
        self.readyRead.connect(self._readSignal)

    def __del__(self):
        # Restore any old handler on deletion
        if self.old_fd is not None and signal and signal.set_wakeup_fd:
            signal.set_wakeup_fd(self.old_fd)

    def _readSignal(self):
        # Read the written byte.
        # Note: readyRead is blocked from occuring again until readData()
        # was called, so call it, even if you don't need the value.
        data = self.readData(1)
        # Emit a Qt signal for convenience
        self.signalReceived.emit(data[0])

    signalReceived = QtSignal(int)
