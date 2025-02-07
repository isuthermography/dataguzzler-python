Writing Dataguzzler-Python Modules
==================================

A Dataguzzler-Python module can be the software representation
of a hardware device or a module can be a virtual instrument that controls
multiple lower level modules in synchrony so they act as an
integrated device. The Dataguzzler-Python module is implemented
through a Python class that has ``dgpy.Module`` as its metaclass.
The module is created by instantiating the Python class, usually with
parameters indicating which hardware device(s) or other module(s)
it should be controlling.

Dataguzzler-Python Principles
-----------------------------

The low level mechanics of controlling and acquiring data from
laboratory instrumentation is not generally very difficult, but good
organization and integration of that control and aquisition is
difficult. The trickiest problems in traditional data acquisition are
related to waiting, sequencing, and parallelism. One approach to
addressing those problems is through event driven programming and a
central event loop, but that is **not** the approach taken by
Dataguzzler-Python.

Dataguzzler-Python instead uses a highly threaded approach, because
with multiple threads waiting, sequencing, and parallelism all become
easy. Unfortunately, using multiple threads also creates new problems:
Race conditions and deadlocks. Moreover the Python global interpreter
lock (GIL) limits the performance benefits from multithreading and can
cause additional bottlenecks, as will be discussed below.
Nevertheless deadlocks and significant race conditions can be easily
addressed using the mitigations built in to Dataguzzler-Python. GIL
problems are largely addressed by putting time consuming operations
such as bulk computation and data transfer into C/C++ functions that
are executed with the GIL dropped. As of 2022 it seems plausible that
the GIL may become optional or even be eliminated entirely within a
few years, which would help a lot.

Review of Threading, Locking, and Race Conditions
-------------------------------------------------

When a program has multiple parallel threads of control, multiple
threads can potentially try to write the same areas of memory
(variables, etc.) simultaneously. It is a worthwhile thought
experiment to imagine the same method being executed by two CPU cores
in lock-step on the same object but with different parameters.  In a
previous era, some operations such as memory writes were fundamentally
atomic, so in the case of a object attribute assignment one of the
cores would (arbitrarily) go first and the assignment by the other
core would (arbitrarily) be lost. This is a "race condition".  Modern
multi-core architectures can have separate CPU caches on the different
cores, which can lose coherence making for even more complicated and
bizarre symptoms, but the net effect is that operations can be lost,
missed by the other cores, appear out-of-order, etc. unless properly
synchronized.

Python uses the global interpreter lock (GIL) to ensure that basic
operations on fundamental Python objects are atomic. Object assignment,
list indexing, append operations, dictionary insertion lookups, etc.
are all considered atomic in Python (and will still be atomic even in
a future version without the GIL). However, two threads executing
the same method in parallel with different parameters could still
trip over each other with assignments being lost, etc.

The general approach to addressing race conditions is through locking:
The owner of a lock has the exclusive right to access the data
associated with the lock. Thus operations on the associated data which
are performed while the lock is held appear atomic to other threads
and race conditions on this data can be eliminated. Unfortunately
locking also creates a new problem: If thread A holds lock #1 and is
waiting for lock #2, and at the same time thread B holds lock #2 and
waiting for lock #1, the two threads will wait forever.

There are several approaches to eliminating the possibility of
deadlocks.  The simplest is to never hold more than one lock at a
time. Another approach is to define a *locking order*. So long as
locks are always acquired in a consistent (partial) order, the type of
deadlock illustrated above is no longer possible. It is also helpful
to consider some locks as "last" locks, meaning that they are always
last in the locking order and no other locks may be acquired while
holding them. Writing multi-threaded code with multiple locks
following a locking order is not difficult, but it is tricky and very error
prone. Every method or function call while a lock is held must be
considered as to whether it could, directly or indirectly, wait
on something that could wait for that lock. Locks that are internal
to libraries are particularly problematic because their semantics
may not be well documented. If you call the library (which locks
its internal locks) with one of your
locks held, and in some other thread the library can call one of your
routines while holding its own lock, and that routine acquires a
lock that is the same or earlier in the locking order compared
to the original, then you have a potential deadlock. 

Locking in Dataguzzler-Python: Contexts
---------------------------------------

In Dataguzzler-Python, we introduce the idea of the *context*.
The context can be thought of as the right to access a particular
set of variables. At its core, the context is really just a lock.
Threads -- such as the thread handling input from the console or from
a remote connection -- usually have their own contexts. Modules
have their own context. When a thread performs a method call
into a module, that method call triggers a switch of context,
dropping the existing context from the thread and acquiring the context
of the module. When the method returns, the module context
is dropped and the thread context is reaquired. If the method were
to call a method of another module, then the context from the first
module would be dropped and the context from the second module would
be acquired for the duration of the method call.

The net effect is that only one thread can be executing module methods
at a time. Also each thread only holds one lock at a time. The context
switching is implemented in the ``dgpy.Module`` metaclass used by all
Dataguzzler-Python modules. So by using this metaclass the
module can be written without worrying much about multithreading,
race conditions, locking, or deadlocks, and the code is much
simpler and less error prone than traditional multi-threaded code.

The above is a slight oversimplification: Some care is still needed
because libraries used by the module might have internal locks. Also
the module might need to be internally multithreaded if it is intended
to do continuous acquisition rather than on-command acquisition (more
on that below). In general with respect to locking and other
libraries, a good practice is to consider the Dataguzzler-Python
module context lock to be first in the locking order, meaning that
it shouldn't be acquired with anything else locked. Following this
protocol, libraries can
be freely called with the module context lock held, provided that:

  * Any direct or indirect callbacks to modules are made via
    methods with ``dgpy.Module`` wrappers that perform proper context
    switches.
  * The library doesn't hold any locks while performing such callbacks.

The net result of all this is that single-threaded modules can
generally freely call outside libraries, but that if they acquire
unique blocking access to a fixed resource such as a lock, singleton
object, etc. they should not make calls, directly or indirectly, to
other Dataguzzler-Python modules while holding the fixed resource.
Modules should also be aware that calls to other modules break the
atomicity otherwise guaranteed by the module's context lock, i.e.
other threads may run methods during calls to other modules. 

Because of special support built in to SpatialNDE2, an ``active_transaction``
object (from snde.start_transaction()) does **not** qualify as a fixed
resource per the previous paragraph, and thus it is OK to make external
module calls within a SpatialNDE2 transaction. However it is generally
**not OK** to make such calls from a singleton worker thread because
occupation of the singleton worker thread counts as a lock, and if
any external call back to the module can wait on the singleton worker
thread then you will have a potential deadlock scenario.



Censoring
---------

Because Dataguzzler-Python is strongly threaded, objects returned by a
module or passed from one module to another can easily end accessed
from multiple threads. This motivates a process known as *censoring*
where potentially thread-unsafe Python objects are made safe for
access from other threads and modules. Immutable objects such as
strings, integers, and floats are safe and passed through
directly. Modules, classes, read-only Numpy arrays and read-only Pint
(unit library) quantities are also passed through directly. Writable
Numpy arrays and Pint quantities are copied before being passed.
Lists, dictionaries, and ordered dictionaries are re-created from
censored components before being passed.

Other types of objects, including methods, functions, class instances,
etc. returned by a method or passed as parameters in a method call
from one module to another are considered to be private to the
originating module, and are censored by being wrapped in an
``OpaqueWrapper`` object with the originating context.  Access to an
object contained in an ``OpaqueWrapper`` triggers a switch to that
originating context, and thus in most cases it can be safely and
transparently used from other contexts. For example method access will
return a wrapped method, and calling the wrapped method will execute
it in its original context. One potential pitfall: Since the
Dataguzzler-Python contexts are generally first in the locking order,
you do need to be careful about accessing anything that could be a
wrapped object while holding any lock (at least any lock later in the
locking order).

To summarize, Dataguzzler-Python modules use the ``dgpy.Module``
metaclass that defines a context for method execution and wraps
methods and attributes such that code will execute in its originating
context. Communications between modules should generally be in terms
of basic types such as strings, numbers, read-only numpy arrays or
quantities that are reasonably thread safe. Other classes will be wrapped
and can be called but object parameter and return values will be
censored for safety if outside their originating context.

Anatomy of a Module
-------------------
Using the pololu_rs232servocontroller module as an example,
::

   class pololu_rs232servocontroller(object,metaclass=dgpy_Module):
       """This class controls an obsolete Pololu 8-port RS232 
       servo controller https://www.pololu.com/product/727/resources """
    
    pol = None # Serial port filehandle
    servos = None
    def __init__(self,module_name,port="/dev/ttyUSBpololu"):
        
        self.pol=serial.serial_for_url(port,baudrate=9600)
        self.servos=[]
        
        for servonum in range(8): # 0..7
            self.servos.append(_pololu_rs232servo(self,servonum))
            pass

        pass

    def close(self):
        self.pol.close()
        self.servos = None # remove references to servo objects so they can be cleaned up. 
        pass
    pass
       
The class must be defined with dgpy.Module as its metaclass. The first
parameter of the constructor (after ``self``) is used by the metaclass
and should be called ``module_name``. Additional parameters can be 
used for configuration. In this case, the module creates eight
``_pololu_rs232servo`` objects, one for each port on the servo and
stores them in the ``.servos`` class member list. Any time that list
is accessed from outside the module, it will get censored and its elements
replaced with wrapped references to the servo objects that trigger
a change to the context of this module. Thus the servo objects can be
instances of a regular class but will still run in module context and
be protected from race conditions by the module context lock.

Here is the code for each servo object::
  
   class _pololu_rs232servo(object):
       """Represents single servo"""

       # Define member variables 
       controller = None
       _index = None
       _power = None
       _position = math.nan # position stored as servo counts 0...255
       _speed = None
       _range = 15 # fixed at default
       _neutral = 1500*ur.us

       # Constructor
       def __init__(self,controller,index):
           self.controller=controller
           self._index=index
           self._speed = 25
           self._power = False
           pass

       def _counts_to_position(self,counts):
           """Convert integer number programmed into 
           servo into a "position" in units of microseconds"""
           return (counts-127.5)*self._range*0.5*ur.us + self._neutral

       def _position_to_counts(self,pos):
           return int(round(((pos-self._neutral)/(self._range*0.5*ur.us)).to(ur.dimensionless).magnitude+127.5))        
        
       # Define a propery for the power
       @property
       def power(self):
           """Command or readout whether this servo is energized (True/False)"""
           return self._power # Ideally this would read-back from hardware
    
       @power.setter
       def power(self,status):
           self._power = bool(status)
           if self._power:
               command=b"\x80\x01\x00%c\x4f" % (self._index)
               pass
           else:
               command=b"\x80\x01\x00%c\x0f" % (self._index)
               pass
           self.controller.pol.write(command)
           pass
    
       @property
       def speed(self):
           """Command or read-out the programmed rate of pulse-width change, 
           in microseconds per second."""
           # Each integer in _speed represents 50 us/s pulse width rate
           return self._speed*50*ur.us/ur.s

       @speed.setter
       def speed(self,spd):
           self._speed=int(round(spd/(50*ur.us/ur.s).to(ur.dimensionless).magnitude))
        
           if self._speed < 1:
               self._speed = 1
               pass
           if self._speed > 127:
               self._speed = 127
               pass
        
           command=b"\x80\x01\x01%c%c" % (self._index,self._speed)
           self.controller.pol.write(command)
           pass
    
       @property
       def position(self):
           """Command or read out the pulse width, in microseconds"""
           # Each integer step in _position represents range*.5 us of pulse width
           return self._counts_to_position(self._position)
    
       @position.setter
       def position(self,pos):
           """Note: commanding a position turns on the servo"""
   
           # Be sure we are executing in the proper context (of the controller)
           AssertContext(self.controller)
        
           self._position=self._position_to_counts(pos)
           if self._position < 0:
               self._position = 0
               pass
           if self._position > 255:
               self._position = 255
               pass

           self._power = True # Servo automatically turns on when we command a position.
        
           positionhighbyte=(int(self._position) & 0x80) >> 7
           positionlowbyte=int(self._position) & 0x7f
        
           command=b"\x80\x01\x03%c%c%c" % (self._index,positionhighbyte,positionlowbyte)
           self.controller.pol.write(command)
           pass

       def position_matches(self,pos):
           """Return whether the current commanded servo position 
           matches the specified position. Out of range positions
           will NOT match"""
           compare_position = self._position_to_counts(pos)
           return self._position == compare_position
       pass

The servo class is written without concern for multithreading because
the context lock of the controller that creates it prevents methods
from executing in parallel. The ``.position`` setter even explicitly
tests the context with ``AssertContext()``.  Note also the use of
``@property`` and setter decorators so that the servos' positions can
be read by attribute-style access of ``.position`` or commanded by
assignment to ``.position``. This makes the code that uses it simpler,
less verbose, and more readable. One disadvantage of the use of
properties is that you can't use ``help()`` directly on the property.
Instead you can use ``help()`` on the object containing the property
and it will show the documentation from the ``@property`` getter. 

Dynamic Metadata
----------------

Dynamic metadata is additional metadata that is usually configured
with the module (i.e. arising from the module's configuration file),
rather than intrinsic to the module (i.e. arising directly from the
module's source code). Dynamic metadata is a very powerful integration
tool because it can allow the recordings generated by one module to
contain metadata relating to the state of another module.

A module that supports dynamic metadata will usually have a
``.dynamic_metadata`` property that is an instance of
``dataguzzler_python.dynamic_metadata.DynamicMetadata()``.
Dynamic metadata is added at and after the end of a transaction
to recording(s) that were generated within the transaction.

To support dynamic metadata within a module, call the
``.recording_needs_dynamic_metadata()`` method of each recordiing
that will support dynamic metadata, immediately upon creation. The call to
``.recording_needs_dynamic_metadata()`` must precede the call to
``.mark_metadata.done()``. Then at the end of the transaction, call e.g.::

   transobj = transact.run_in_background_and_end_transaction(self.dynamic_metadata.Snapshot().Acquire,[ list of recordings that can accept dynamic metadata ])

This will cause the dynamic metadata acquisition method to run at the end of the transaction in a thread dedicated to dynamic metadata acquisition.

In case you need to wait for the resulting global revision (including dynamic
metadata) to be complete, for example to support a "Calcsync" mode, you can
use the return value from ``.run_in_background_and_end_transaction()``. The
``transobj`` returned is the former ``recdb.current_transaction``. It has a
method ``get_transaction_globalrev_complete_waiter()`` that returns a
``promise_channel_notify`` that you can use to wait for the globalrev to
become fully complete (all data and metadata from all channels) with
its ``.wait_interruptable()`` method. The wait can be interrupted by calling
the ``.interrupt()`` method from another thread. 

See the section on writing Dataguzzler-Python configuration files for
information and examples of how to assign dynamic metadata. 

Calcsync Mode
-------------

In many cases your module will be written such that it is constantly
waiting for, and then delivering, data from some hardware device.
Such modules are generally multithreaded (see below) and modern devices
can often deliver extremely high throughput rates. Unfortunately,
calculations (SpatialNDE2 math functions) dependent on that data
coming in may not always be able to keep up.

In such circumstances the calculations will keep queuing up as the
computation gets behind. If large amounts of data are coming in very quickly
it is easy to run your computer out of memory. Some approach is needed
to prevent calculations from getting behind, and "Calcsync mode" is
such an approach.

By convention, we make "calcsync" a boolean Python ``@property`` of
the module. When calcsync is ``False`` we acquire data as quickly as
the hardware allows. This avoids, for example, dropping camera frames
from a trigger sequence. When calcsync is ``True`` the acquisition
pauses after data is acquired until the corresponding calculations are
complete.

For modules that do not support dynamic metadata, the process is very
simple: The ``end_transaction()`` returns a ``globalrevision`` object.
Just call the ``wait_complete()`` method of the ``globalrevision`` before
performing the next acquisition.

For modules that do support dynamic metadata, it is somewhat more
complicated because of the possibility that the dynamic metadata function
might end up waiting directly or indirectly for the thread that was
doing the acquisition (perhaps because something it is calling
is waiting for a configuration change that can only happen while acquisition
is paused).

There are several ways to address. One approach would be to mark acquisition
as paused during the wait, so that configuration changes can happen without
involvement of the acquisition thread. Another approach, implemented in the
Azure Kinect module, is to use the ``recdb.current_transaction`` object
returned by ``.run_in_background_and_end_transaction()``. and its
``get_transaction_globalrev_complete_waiter()`` method to get a waitable
object that is interruptable. 



Modules That Use C/C++ APIs and the Python GIL
----------------------------------------------

In may cases the hardware you want to control may only have a C or C++
API. Or you may find that vendor-provided Python modules are
inadequate; for example may not adequately drop the GIL and therefore
slow down other parts of your acquisition system.  In these cases you
will need a module that interfaces to the C/C++ APIs. (Note that using
a subprocess is a possible alternative to rewriting a GIL-intensive
Python interface, but so far only for cases where the module doesn't
need to use the SpatialNDE2 recording database). Some C/C++ libraries
may provide Python wrappers, and some of these (such as SpatialNDE2)
always drop the GIL. Others (such as QT and numpy) sometimes drop the GIL,
and many may not drop the GIL at all. 

Cython is probably the best environment for writing hybrid Python and
C/C++ code. Cython allows you to manipulate C/C++ variables and call C
or C++ functions or objects directly from what otherwise appears to be
Python code but saved in a ``.pyx`` file. You can even create C/C++
classes and functions! Cython also supports explicitly dropping the
Python GIL.

However, Cython has some limitations:

  * Only ``cdef`` classes can store C data types
  * The GIL is held by default and needs to be explicitly dropped with "nogil"
  * Only non-``cdef`` classes can have a metaclass. 

As a result the usual pattern for a Cython Dataguzzler-Python module
that interfaces to a C/C++ library is to define a non-``cdef`` module class
that uses the ``dgpy.Module`` metaclass. This class defines the high-level
interface and instantiates a low level ``cdef`` class that stores the
relevant C/C++ variables for interacting with the library.
An example of this pattern is illustrated in the module for the Azure Kinect camera:
``class K4A`` defines the Dataguzzler-Python module. Its constructor
instantiates a ``cdef class K4ALowLevel`` that contains the C/C++ variables
such as the device pointer and other C data structures.

In general you want your module thread to hold the Python global
interpreter lock (GIL) for as short as possible. In general you don't
want to do **any** bulk data transfers or bulk computation while
holding the GIL, because you can easily cause significant latency
problems for other threads. In addition you have to be very consistent
about dropping the GIL when calling any library
(such as SpatialNDE2) that might have its own
internal locks, and support any kind of callbacks, for fear of creating
a deadlock between the library internal lock and the GIL. 

In Cython, you declare C/C++ API functions
with a ``cdef extern`` in your ``.pyx`` file or in a ``.pxd`` file accessed
via ``cimport``. If the ``cdef extern`` (or particular function definition)
is tagged with ``nogil``, then Cython will allow the function
to be called without the GIL. For example from the Azure Kinect module::

   cdef extern from "k4arecord/playback.h" nogil:
       k4a_result_t k4a_playback_open(const char *path, k4a_playback_t *playback_handle)

In addition to declaring the relevant API functions as ``nogil``, you also
need to explicitly call them from a ``nogil`` block::

   with nogil: 
       waitresult = k4a_device_get_capture(self.dev,&capt,timeout_ms)

You cannot use any pure-python objects or functions (only ``cdef`` objects
and functions) from a ``nogil`` block. That means, for example, that you
cannot call SpatialNDE2 from its Python API. You can, however, obtain
C/C++ pointers from SpatialNDE2 API functions that can be safely called
with ``nogil``. The following illustrates the process for converting
an ``ndarray_recording_ref`` from the SpatialNDE2 Python wrappers first
to an equivalent C++ shared pointer and then to a templated ``ndtyped_recording_ref``. First, the required imports::

   from cython.operator cimport dereference as deref
   from libcpp.memory cimport shared_ptr,dynamic_pointer_cast
   from libc.stdint cimport uintptr_t,uint64_t

   from spatialnde2.geometry_types cimport snde_coord
   from spatialnde2.recstore cimport ndarray_recording_ref,ndtyped_recording_ref

Given variables from the SpatialNDE2 Python wrappers::
   g = recdb.latest_globalrev()
   waveform = g.get_ndarray_ref("waveform")

Cython ``cdef`` C++ shared pointers can be obtained as follows using the produce/consume methods of the SpatialNDE2 Python wrappers::

   cdef shared_ptr[ndarray_recording_ref] *waveform_untyped_ptr=<shared_ptr[ndarray_recording_ref] *><uintptr_t>waveform.produce_raw_shared_ptr()
   cdef shared_ptr[ndarray_recording_ref] waveform_untyped=deref(waveform_untyped_ptr)
   snde.ndarray_recording_ref.consume_raw_shared_ptr(<uintptr_t>waveform_untyped_ptr)

The result is a valid ``cdef`` variable ``waveform_untyped`` that can be safely used in a ``nogil`` block. To be clear, the ``waveform_untyped`` shared pointer is still valid after the ``consume...()`` call, which only invalidates the temporary pointer ``waveform_untyped_ptr``. You can then perform C++ operations such as method calls and casts on this shared pointer, such as::

   cdef shared_ptr[ndtyped_recording_ref[snde_coord]] waveform_typed = dynamic_pointer_cast[ndtyped_recording_ref[snde_coord],ndarray_recording_ref](waveform_untyped)

Note that as of this writing the ``.pxd`` interface files for direct
Cython access to SpatialNDE2 variables are woefully
incomplete. However you can at least pass the shared pointers to C++ functions.


Multithreaded Modules
---------------------

While some hardware is only accessed on-demand, other hardware can operate
continuously in the background. In such a case it usually makes sense
for the Dataguzzler-Python module to be internally multithreaded:
The module to have an acquisition thread that pulls data from the
device in parallel with access its regular Dataguzzler-Python context.
In this situation the module must perform locking to serialize access
to variables that are shared between the regular Dataguzzler-Python context
and the acquisition thread. 

The recommended procedure for an acquisition thread in a Dataguzzler-Python module
is illustrated in the module for the Azure Kinect camera. The thread is started
typically in the module constructor::

   self.capture_thread = Thread(target=self.capture_thread_code)
   self.capture_thread.start() 

The thread itself performs variable declaration/initialization and then calls
``dataguzzler_python.dgpy.InitCompatibleThread()``::

   def capture_thread_code(self):
       cdef k4a_device_configuration_t config = K4A_DEVICE_CONFIG_INIT_DISABLE_ALL
       # ...
       
       InitCompatibleThread(self,"_k4a_capture_thread")

The call to ``InitCompatibleThread()`` gives the newly created thread a context that is "compatible"
with the context of the given module (``self`` in this case), meaning that it can access the
member variables without censoring. Otherwise the new thread would not be able to access module
attributes. However, defining a thread as "compatible" does not address race conditions or synchronization --
you have to do that explicitly by creating locks and/or condition variables.


In the Azure Kinect module we create a ``threading.Condition()`` condition variable::
   self._capture_running_cond = Condition()

This condition variable and its associated lock protect a set of boolean variables::
   _capture_running = None  # Boolean, written only by sub-thread with capture_running_cond locked
   _capture_start = None  # Boolean, set only by main thread and cleared only by sub-thread with capture_running_cond locked
   _capture_stop = None  # Boolean, set only by main thread and cleared only by sub-thread with capture_running_cond locked
   _capture_failed = None # Boolean, set only by sub thread and cleared only by main thread to indicate a failure condition
   _capture_exit = None # Boolean, set only by main thread; triggers sub thread to exit. 
   _previous_globalrev_complete_waiter = None # Used for _calcsync mode; set only by sub thread with capture_running_cond locked but used by main thread

The module has Python properties (pseudo-attributes managed by
methods) that can be accessed from the "main" thread (actually
whichever thread holds the module context lock) to reconfigure the acquisition process. For example::

   @property
   def depth_mode(self):
       cdef K4ALowLevel LowLevel = self.LowLevel
       with LowLevel.config_lock:
           return LowLevel.config.depth_mode
       pass
   
   @depth_mode.setter
   def depth_mode(self,value):
       cdef K4ALowLevel LowLevel = self.LowLevel
       value=int(value)
       with self._capture_running_cond:
           self._stop_temporarily()
           with LowLevel.config_lock:
               LowLevel.config.depth_mode = value
	       pass
           self._restart_if_appropriate()
           pass        
       pass

The ``cdef K4ALowLevel LowLevel`` creates a temporary pointer to the internal ``cdef`` class
for use within the function. ``LowLevel.config_lock`` is a ``threading.Lock()`` that is used
as a custom lock to synchronize access to ``LowLevel.config``. The getter simply reads the
``depth_mode`` C variable while holding the ``config_lock`` and returns it.

In contrast to safely change the depth mode, acquisition must be paused and the depth mode
changed during the pause. The setter uses ``self._capture_running_cond``, which is the aforementioned
``threading.Condition()`` variable that has an internal ``threading.Lock()`` which is held
through the contents of its ``with`` statement. Thus the internal booleans are protected and
``_stop_temporarily()`` chooses abort actions according to the state, interrupting any
running acquisition or internal wait as appropriate. The code within ``_stop_temporarily()``
also waits (via ``self._capture_running_cond.wait_for()``) until the acquisition thread
has acknowledged the state change. The boolean variables can change during ``wait_for()`` because
the condition variable always drops its lock during the wait and reacquires once the
condition is satisifed. Once acquisition is successfully stopped the ``config_lock`` is
acquired (it is after ``self._capture_running_cond`` in the locking order) and the
configuration is changed. Then ``self._restart_if_appropriate()`` triggers the acquisition
thread to restart acquistion if appropriate to the situation.

The code in ``K4A.capture_thread_code()`` implements complimentary logic to wait on ``self._capture_running_cond``
when idle and switch behaviors according to the requested state. Such logic can either be implemented
as this sort of looped conditionals, or more formally in the form of a state machine. 


The Locking Order for Multithreaded Modules
-------------------------------------------

A superficial understanding of the Dataguzzler-Python context locks and
the GIL are sufficient for writing single-threaded Dataguzzler-Python
modules. See the section above on context locks for the proper protocol.
However, in order to write multi-threaded Dataguzzler-Python modules a
deeper understanding is required. 

To prevent deadlocks, the locking order must be very carefully followed
and this constrains what you can call and when. Because of special
support within SpatialNDE2 in the wrapping of ``recdb.start_transaction()``,
transaction locks precede
contexts in the locking order. This is achieved by having the Python
wrapper ``recdb.start_transaction()`` drop the Dataguzzler-Python context
prior to starting the transaction and then reacquiring the context once
the transaction is started. This allows calls to other
Dataguzzler-Python modules within transactions (but not from singleton worker
threads), but also means it is possible for
module execution to be interrupted at
transaction boundaries. 

The Dataguzzler-Python locking order is:
  #. SpatialNDE2 transaction Lock
  #. Dataguzzler-Python context locks
  #. Other SpatialNDE2, custom, and library locks, appropriately ordered. 
  #. Python GIL. 
     
**Since calling another Dataguzzler-Python module involves dropping and
reacquiring the module's Dataguzzler-Python context lock, per the
locking order it is clearly unsafe to call another Dataguzzler-Python
module while holding any (non-transaction) SpatialNDE2, custom, or
library locks.** Also since all other locks precede the Python GIL
in general you need to drop the Python GIL before calling anything
that might acquire a lock. The builtin Python locking objects such
as ``threading.Lock()`` do this implicitly. The SpatialNDE2 SWIG wrappers
automatically drop the GIL. Be very careful if calling SpatialNDE2
directly (not through the wrappers) to always and
consistently drop the GIL. Otherwise a thread that owns an internal
lock or with a unique capability that acts as a lock and has called back
to code that acquires the GIL can deadlock with another thread that
holds the GIL and is trying to acquire the same lock.
In Cython, that means that all such functions
should be declared as ``nogil`` and called only from ``with nogil:``
blocks. The same logic applies to other libraries that may use internal locks
and support callbacks.
     

**Despite their position in the locking order Dataguzzler-Python custom locks
cannot be safely held while calling other modules.** This is because
there is no specific ordering of different custom locks across modules, nor
is there a good way to enforce such an ordering if one were defined. Instead,
there purpose is to prevent a certain class of deadlocks that could otherwise
exist when a sub-thread within one multithreaded module calls some other
Dataguzzler-Python module.

It is a common design pattern in a multithreaded module to have one or more
fixed-purpose worker threads. Such threads are referred to as "singleton threads"
in this document because the module creates exactly one for a given purpose and
when that thread is occupied it is inaccessible from other threads. Therefore,
such a thread is a fixed resource of the module can be interpreted as a lock,
which in turn needs a position in the locking order.

If such a thread can create a transaction, it is inherently inaccessible
externally when doing so, therefore the thread precedes the transaction
and context locks in the locking order:

  #. Singleton thread 
  #. SpatialNDE2 transaction Lock
  #. Dataguzzler-Python context locks
  #. Other SpatialNDE2, custom, and library locks, appropriately ordered. 
  #. Python GIL. 

However if such a thread also dispatches requests from incoming method
calls with a context lock then we have to consider the singleton
thread being acquired with the context lock held. Then the order of
lock acquisition would have to be:

  #. Dataguzzler-Python context locks
  #. Singleton thread 
  #. Other SpatialNDE2, custom, and library locks, appropriately ordered. 
  #. Python GIL. 

Clearly the above two locking orders are incompatible. The solution is that the thread
is not allowed to acquire Dataguzzler-Python context locks (except perhaps its own private lock)
and that is why singleton worker threads that dispatch method call requests
are not allowed to call other Dataguzzler-Python modules. 

Sleeping and ``KeyboardInterrupt``
----------------------------------
There are scenarios where you may need to include an extended pause in your code, for instance, waiting
on a process for which you know how long it will take but do not have feedback, or, running some
timed process where you run and then wait for a defined period of time before running again. Oftentimes
in these scenarios, we wish to be able to break out of this pause by pressing Ctrl + c, which raises a
``KeyboardInterrupt`` exception. This is accomplished by raising a ``SIGINT`` signal.  However, if you
are running a GUI which occupies the main thread, the SpatialNDE2 recording database viewer for instance,
this will interfere with this process in potentially two ways: 1) replacing or disabling the ``SIGINT``
handler, and 2) preventing a signal from reaching the thread that needs to be interrupted because signals
are only processed in the main thread.

To work around the main issue of concern, Dataguzzler-Python replaces the ``SIGINT`` signal handler with
a function that will use the Python C API to raise a ``KeyboardInterrupt`` exception in the command reader
thread.  This is anticipated to cover the majority of common use cases.  However, operations that release
the GIL, such as ``time.sleep`` will not be interrupted by this exception being raised because this can only
be done if the command was ran from the main thread (where the low-level signal handling code wakes the thread).
Once the GIL is reacquired, the exception is processed.

A more general solution to this problem requires a more considerate design when using functions such as ``time.sleep``
or other long running functions that release the GIL.  For instance, one could use ``threading.Event`` or
``threading.Condition`` to construct a waiting process that can be interrupted. For convenience, one such mechanism
is exposed in the ``dgpy`` module for use.  Simply call ``dgpy.sleep(secs)`` in place of ``time.sleep(secs)``.
There is a corresponding ``dgpy.awake(thread_id)`` function that can be used to programmatically interrupt an
active ``dgpy.sleep`` call.

Threads other than the command reader can also register to receive a KeyboardInterrupt or similar exception when
Ctrl + c is pressed.  Use ``dgpy.RegisterKeyboardInterrupt(thread_id)`` to register the callback. This will also call
``dgpy.awake(thread_id)`` to interrupt an active call to ``dgpy.sleep`` in the registered thread. An optional function
handle can be registered instead to modify the behavior -- however, care should be taken not to block, since this
callback will be running in the main thread.

Closing and Exiting
-------------------

It is a good idea to give sub-threads a way to abort and exit as the program closes or when the module is unloaded.
An alternative can be to mark the sub-thread as a "daemon" thread, but that method can cause crashes as other
resources might be released first on program exit. The Azure Kinect module registers an ``atexit`` function that
terminates acquisition and joins the sub-thread prior to exit. 
