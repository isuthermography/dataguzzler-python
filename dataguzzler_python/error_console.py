import sys
import io
import os
import threading
import time
import traceback
from dataguzzler_python.Qt import QtWidgets, QtCore, QtGui
from qtconsole.rich_jupyter_widget import RichJupyterWidget

_junk = RichJupyterWidget() # Spin up a separate IPython Kernel before messing with stderr

class StderrConsoleWidget(QtWidgets.QTextBrowser):
    def __init__(self, *args, **kwargs):
        super(StderrConsoleWidget, self).__init__(*args, **kwargs)
        error_manager.RegisterStderrBuffer(id(self), self)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
    
    def __del__(self):
        error_manager.UnregisterStderrBuffer(id(self))

    def write(self, text):
        self.insertPlainText(text)
        self.moveCursor(QtGui.QTextCursor.End)
        self.ensureCursorVisible()

    def flush(self):
        pass

class ErrorConsoleGUI(QtWidgets.QMainWindow):

    def __init__(self, QApp, *args, **kwargs):
        super(ErrorConsoleGUI, self).__init__(*args, **kwargs)
        self.QApp = QApp
        self.setWindowTitle("Dataguzzler-Python Error Log")
        self.central_widget = StderrConsoleWidget()
        self.setCentralWidget(self.central_widget)
        self.resize(500,250)

        if self.QApp is not None:
            QApp.processEvents()


class StderrManager:

    registered_buffers = {}
    
    def __init__(self, old_stderr):
        self._quit = False
        self._old_stderr = old_stderr
        self._old_cstderr_fd = self._old_stderr.fileno()
        self.registered_buffers = {}
        self.registered_buffers['stdout'] = sys.stdout
        self._duped_fd = os.dup(self._old_cstderr_fd)
        self._pipe_reader, pipe_writer = os.pipe()
        os.dup2(pipe_writer, self._old_cstderr_fd)
        os.close(pipe_writer)
        self._capture_thread = threading.Thread(target=self._capture_thread)
        self._capture_thread.start()

    def __del__(self):
        self._quit=True
        self._capture_thread.join()
        os.close(self._pipe_reader)
        os.dup2(self._duped_fd, self._old_cstderr_fd)
        os.close(self._duped_fd)
        sys.stderr = self._old_stderr

    def _capture_thread(self):
        while not self._quit:
            try:
                self.write(os.read(self._pipe_reader, 1024).decode())
            except:
                print(traceback.format_exc())

    def write(self, text):
        for buf in self.registered_buffers.values():
            buf.write(text)

    def flush(self):
        for buf in self.registered_buffers.values():
            buf.flush()

    def RegisterStderrBuffer(self, key, buffer):
        if key in self.registered_buffers:
            raise ValueError('Key %s Already Registered' % (key))

        if hasattr(buffer, 'write') and callable(buffer.write) and hasattr(buffer, 'flush') and callable(buffer.flush):
            self.registered_buffers[key, buffer] = buffer
        else:
            raise ValueError('Buffer must have a "write" and "flush" method')
    
    def UnregisterStderrBuffer(self, key):
        if key in self.registered_buffers:
            del self.registered_buffers[key]
        else:
            raise KeyError('Buffer "%s" is not registered' % (key))
        
    def DisableStdoutOutput(self):
        if 'stdout' in self.registered_buffers:
            del self.registered_buffers['stdout']
        else:
            raise KeyError('Stderr output to original terminal already disabled')
        
    def EnableStdoutOutput(self):
        self.registered_buffers['stdout'] = sys.stdout  

if not isinstance(sys.stderr, StderrManager):
    sys.stderr = StderrManager(sys.stderr)
    error_manager = sys.stderr