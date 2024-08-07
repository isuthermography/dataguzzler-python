Writing Dataguzzler-Python Configurations
=========================================

Dataguzzler-Python configurations are written in the form of
Python code stored in a ``.dgp`` file. To illustrate, let us
consider the ``shutter_demo.dgp`` used above in the quickstart
section. ::

   from dataguzzler_python import dgpy
   from dataguzzler_python import password_auth,password_acct

   include(dgpy,"dgpy_startup.dpi") # If you get a NameError here, be sure you are executing this file with dataguzzler-python

   include(dgpy,"serial.dpi")
   include(dgpy,"pint.dpi")

   from pololu_rs232servocontroller import pololu_rs232servocontroller
   from servoshutter import servoshutter

   dgpython_release_main_thread() # From here on, the .dgp executes in a sub thread 
   
   #port = find_serial_port("A700eEMQ")
   port = "loop://"
   servocont = pololu_rs232servocontroller("servocont",port)

   shutter = servoshutter("shutter",servocont.servos[0],servocont.servos[1])


   include(dgpy,"network_access.dpi",
           auth=password_auth(password_acct("dgp","xyzzy")))

   print("dataguzzler-python shutter demo")
   print("-------------------------------")
   ...


Let us examine the configuration file line-by-line::

   from dataguzzler_python import dgpy
   from dataguzzler_python import password_auth,password_acct

   include(dgpy,"dgpy_startup.dpi") # If you get a NameError here, be sure you are executing this file with dataguzzler-python

These first lines are the initialization boilerplate. The ``.dgp`` file is executed by the ``dataguzzler-python`` command as Python code. The first line imports the ``dataguzzler_python.dgpy`` module. The second line pulls in authenticationclasses that are used below. The third (include) line has two functions:
  * To induce an immediate error if you accidentally run the ``.dgp`` file like a regular Python script. The symbol ``include`` will not be defined so you will get an immediate ``NameError``.
  * To load some very common libraries. Specifically it imports the ``sys`` and ``os`` Python standard libraries, as well as importing the ``numpy`` library under the name ``np``.

The ``include`` function is automatically provided by Dataguzzler-Python and the ``.dpi`` file specified by the second parameter (interpreted relative to the package or module given in the first parameter) is executed almost as if present verbatim in the ``.dgp``. The primary difference is that global variable assignments will only affect the ``.dgp`` namespace if the variable is explicitly declared as ``global`` in the ``.dpi`` file.::

   include(dgpy,"serial.dpi")
   include(dgpy,"pint.dpi")

These two lines include support files built into Dataguzzler-Python for interfacing with serial (PySerial) devices, and for working with the Pint units library. The ``serial.dpi`` include file defines a global variable and a global function. The global variable, ``serial_ports``, is a list of tuples of serial port information. The function, ``find_serial_port(hwinfo)`` is used to return a serial port URL with hardware information (such as a serial number or portion) matching the string given as the ``hwinfo`` parameter.

The ``pint.dpi`` include file imports the ``pint`` units library, defines a unit registry in a global variable ``ur``, and defines this unit registry to be the application-wide unit registry.::

   from pololu_rs232servocontroller import pololu_rs232servocontroller
   from servoshutter import servoshutter

These two lines import Dataguzzler-Python module classes from files
located in the same directory as ``shutter_demo.dgp``. The location
of the current ``.dgp`` or ``.dpi`` file is always at the head of
``sys.path`` while it is being processed.::

  dgpython_release_main_thread() # From here on, the .dgp executes in a sub thread 

The dgp file normally executes in the context of the main (primary) thread of the dataguzzler-python process. Certain functions, such as many GUI functions and the GUI event loop, need to run in that main thread. Any graphical elements will appear unresponsive until the GUI event loop starts executing. This pseudo-function ``dgpython_release_main_thread()`` transitions execution of the .dgp file from the main thread context into a sub thread context where the GUI event loop can execute in parallel. In this example, it is included for illustrative purposes, as there is no GUI present. In general, place the call to ``dgpython_release_main_thread()`` after Python imports, after import-like ``include()`` calls, and after the import of ``recdb_gui.dpi``. This way thread-unsafe import operations will happen in sequence, but the GUI will be immediately responsive.::
  
   #port = find_serial_port("A700eEMQ")
   port = "loop://"

These lines illustrate two options for identifying a serial port. The first option (commented out) uses the ``find_serial_port()`` routine provided by ``serial.dpi`` to match the serial number of a USB serial device. You can see potential match strings by viewing the serial port list in the ``serial_ports`` global variable. The second line illustrates that you can explicitly reference any `pySerial URL handler <https://pyserial.readthedocs.io/en/latest/url_handlers.html>`_.::

   servocont = pololu_rs232servocontroller("servocont",port)

   shutter = servoshutter("shutter",servocont.servos[0],servocont.servos[1])

The first line instantiates the ``pololu_rs232servocontroller`` class, defining a module named ``servocont`` using the given port device. The other line instantiates the ``servoshutter`` class, defining a module named ``shutter``  using the first two servos from ``servocont``. ::

   from dataguzzler_python import password_auth,password_acct

   include(dgpy,"network_access.dpi",
           auth=password_auth(password_acct("dgp","xyzzy")))
	   
These lines configure network access (but only local, by default) to
Dataguzzler-Python. They also illustrate how parameters can be passed
to include files. In general, any globally defined variables in a ``.dpi``
file can be overriden by keyword arguments to ``include()``. In this case
there is a global variable ``auth=None`` within ``network_access.dpi``.
Providing the keyword argument replaces the value of ``auth`` with the
provided ``password_auth`` object with a single account with
username ``dgp`` and password ``xyzzy``.

There are other configurable parameters within ``network_access.dpi``:
``bind_address`` defaults to ``"127.0.0.1"`` meaning that connections
by default are only accepted over the IPV4 loopback network. If you want
to be able to accept actual remote network connections, set ``bind_address``
to ``""`` (and make sure your firewall will let those connections through).
Another configurable parameter is ``dgpy_port``, which defaults to ``1651``.
Using this default configuration, you should be able to connect to Dataguzzler-Python with a telnet client configured to connect to host 127.0.0.1 port 1651.
You will have to first authenticate with ``auth("dgp","xyzzy")`` and then
you should be able to issue commands and see responses.

Some Demonstration Configurations
---------------------------------

  * ``simple_qt.dgp`` Illustrates creating a simple QT GUI.
  * ``matplotlibdemo.dgp`` Illustrates the use of matplotlib within Dataguzzler-Python
  * ``recording_db.dgp`` Illustrates loading the SpatialNDE2 recording database and its QT-based interactive viewer. 

Abstracting Functionality Into Include Files
--------------------------------------------

A common development pattern for Dataguzzler-Python is to
first implement a capability directly in a ``.dgp`` file.
Then, once the capability is mature, move the guts into a more abstract
implementation in a ``.dpi`` file that can be included by the
``.dgp``. This way functionality from multiple devices can be
aggregated simply by including all of the relevant ``.dpi`` files.
A hybrid virtual instrument can then be created by adding glue into
the ``.dgp`` that merges the functionality of multiple devices into one,
for example setting parameters in synchrony, including the data from
one device as metadata within data from another device, etc. Then once
the virtual hybrid instrument is mature it can be abstracted into its own
``.dpi`` file and used to build an even higher level device.

Parameters can be passed into included ``.dpi`` files by two methods:
First by a simple assignment of a default value in the ``.dpi`` file
with an override provided by keyword parameters to the ``include()``
call. An alternative is to assign ``dpi_args=None`` and/or ``dpi_kwargs=None`` in the ``.dpi`` file. When the file is included, extra
ordered arguments will be passed in as ``dpi_args`` and extra
keyword arguments will be passed in as a dictionary ``dpi_kwargs``.

Included ``.dpi`` files can also return a value. The file can end
with a ``return`` statement and the value supplied will be the
value of the ``include()`` function call.

Dynamic Metadata
----------------
One of the keys to integrating complicated systems is the use of dynamic metadata where the result of custom queries can be integrated into recording metadata at the end of a SpatialNDE2 transaction. Only certain Dataguzzler-Python modules supprort dynamic metadata. Those that do, such as the module for connecting to the Azure Kinect depth camera, will typically have an attribute ``dynamic_metadata`` that is of class ``dataguzzler_python.dynamic_metadata.DynamicMetadata``.
To add metadata that will be acquired at the end of each acquisition transaction, just call the ``AddStaticMetaDatum()`` or ``AddDynamicMetaDatum()`` methods of the ``DynamicMetadata`` object to acquire fixed or dynamic values respectively. For example, ::
  
   k4a.dynamic_metadata.AddStaticMetaDatum("/k4achan","testmd","testmd_value")
   k4a.dynamic_metadata.AddDynamicMetaDatum("/k4achan","testmd2",lambda: k4a.depth_mode)

The first line writes a fixed string ``"testmd_value`` into a string metadata entry called ``testmd`` in the generated recordings on channel ``/k4achan``.  The second line writes the value returned by the lambda into a metadata entry called ``testmd2`` in the generated recordings on channel ``/k4achan``.  In this way recordings generated by one module can include information on the current state of another module.





