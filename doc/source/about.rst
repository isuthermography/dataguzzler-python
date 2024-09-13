About Dataguzzler-Python
========================

**Dataguzzler-Python** is a tool to facilitate data acquisition,
leveraging Python for scripting and interaction.
A Dataguzzler-Python data acquisition system consists of *modules* that
can control and/or capture data from your measurement hardware, and
often additional higher-level *modules* that integrate functionality
provided by the hardware into some sort of virtual instrument.

Traditional acquisition software is coded to implement some
pre-conceived notion of the experimental process and some idea of how
a scientist or technician will interact with that process.
Unfortunately, often the pre-conceived notion is inadequate, leading
to substantial rework and wasted effort. Furthermore, modifying the
process requires substantial re-programming, which discourages
experimentation and process improvement. In addition, there is the
tendency to accumulate multiple versions of the software with slightly
different functionality but largely similar code, leading to a
version control nightmare.

Dataguzzler-Python is designed to address those problems by helping you
build your acquisition software from layered components (modules)
that separate *policy* (the choice of what to do) from *mechanism*
(the means to accomplish the task), and leave the mechanisms accessible
to human interaction and scripting to facilitate experimentation.
A Dataguzzler-Python based acquisition system is specified through
its configuration (``.dgp``) file, which instantiates the needed
modules for the particular application. Usually the configuration
file amounts to a series of include directives that build and configure
the application from Dataguzzler-Python include (``.dgi``) files
provided by installed Python packages. Then you run the configuration
and interact with it via command (interactive Python prompt)
and/or (optionally) graphical interfaces. 

You write your code to control a hardware device knowing the sorts of
tasks that will be needed (mechanisms) but without worrying about
exactly how it will integrate with the software for the other devices.
A ``.dpi`` include file instantiates the modules and a sample
configuration (``.dgp`` file) tests in a standalone mode. A virtual instrument that manipulates a group of lower level devices can be built the same way.

The configuration for a large composite instrument is therefore little
more than a series of include directives. A custom configuration for a
particular experiment contains very little code and little
duplication, and the traditional version control nightmare is
addressed. In addition, because the Dataguzzler-Python configuration
exposes the lower level mechanisms to human control through the
command interface, you can often perform innovative
experiments without any reconfiguration at all!


At the most fundamental level, Dataguzzler-Python is configured and
interacted with through Python code. The software portion of the
data acquisition system is constructed by executing Python code, and
the simplest form of interaction is through Python code entered at
a prompt. An add-on library, **SpatialNDE2** provides functions
for managing and interacting with the acquired data, including
a live viewer GUI. The viewer can also be integrated into a custom
application-specific GUI for controlling your data acquisition
system. 

Dataguzzler-Python is designed for maximum flexibility and the broadest
possible classes of integration problems, including being remotely
controlled by something else. Specifically, Dataguzzler-Python helps with:

  * Providing an interactive Python shell for controlling the data aquisition
    process.
  * Leveraging the Python language for configuring acquisition modules.
  * Combining and integrating multiple aquisition modules into a
    virtual instrument
  * Managing and interacting with the acquired data (with **SpatialNDE2**). 
  * Minimizing version control problems that arise from temporary
    experiment-specific reconfiguration.
  * Multiplexing control inputs, such as simultaneous interactive and
    script-based operation. 
  * Implementing a highly threaded environment where acquisitions and
    control of multiple devices can happen in parallel.
  * Interfaces and protocols for implementing device control and
    access in a highly threaded environment in ways that eliminate both
    potential deadlocks and race conditions.
  * Providing a remote access interface so that the Dataguzzler-Python
    based virtual instrument can be used as a component by external
    scripts, tools, and devices.
  * Managing the Python main thread so that libraries designed for
    single-threaded use, including GUI toolkits like QT and
    interactive plotting libraries like Matplotlib, can work in the
    multi-threaded environment.
  * Isolating problematic modules within a subprocess so as to prevent
    interference with the rest of the acquisition system. 

**Dataguzzler-Python** does not directly attempt to do experiment
logging or manage hybrid manual/automatic workflows. Such
functionality can be manually implemented in scripts or via the **LIMATIX**
package. 

Dataguzzler-Python is written primarily in Python (with a small amount
of optional C and Cython for interfacing to the old **dataguzzler** tool that
most users will neither use nor need).

Prerequisite dependencies
-------------------------

Dataguzzler-Python is built on Python (tested on 3.8 and newer) on the following common and widely-used tools
and libraries:

  * setuptools: Python packaging support
  * setuptools_scm: Python packaging support
  * wheel: Python packaging support
  * numpy: Python numerical toolkit
  * pint: Python units library
  * PySide2, PySide6, PyQt5, or PyQt6 QT bindings (optional): GUI Python integration
  * Matplotlib (optional; strongly recommended): Interactive plotting
  * pySerial (optional): Interface to physical or virtual (USB) serial ports.
  * pyvisa (optional): Interface to laboratory instruments
  * SpatialNDE2 (optional; strongly recommended): Management and viewing of recorded data

On Windows most of these dependencies are usually most easily
installed using the Anaconda package manager.

