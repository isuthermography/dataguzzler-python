Installation
============

Dataguzzler-Python is distributed as a Python source tree. You will
need a Python installation (at least v3.8). Also install the
prerequisite dependencies listed in the about section (above or
in ``about.rst``.

If you are also installing SpatialNDE2 (highly recommended), you
may want to do that first, as on some platforms (Windows)
the recommended procedure involves creating a virtual Python
environment, and you will want to install Dataguzzler-Python
into the same environment. 


On Anaconda you will probably want at least the following packages:
numpy scipy matplotlib cython ipython pip opencv pint lxml setuptools pyreadline pyserial pyside2 pyvisa. If you considering installing SpatialNDE2, you will also want: 
clhpp pyopencl  hdf5 h5py  netcdf4 cmake openscenegraph pyopengl glfw freeglut glew mesa eigen swig.

To create a new Anaconda environment with all these packages, run, for example:

::
   
   conda create -n SNDE -c conda-forge python=3.9 numpy scipy matplotlib cython ipython pip opencv clhpp pyopencl pint hdf5 h5py lxml setuptools netcdf4 cmake openscenegraph pyopengl glfw freeglut glew mesa eigen swig pyreadline pyserial pyside2 hdf5 pyvisa

You can then activate the Anaconda environment with:

::
   
   conda activate SNDE

(To select this environment in a new Anaconda prompt, you will have to rerun the "conda activate SNDE") 

Installation of Dataguzzler-Python is accomplished by running
(possibly as root or Administrator):

::

   python setup.py install

from a suitable terminal, command prompt, or Anaconda prompt corresponding
to the desired installation enviroment.  In
general, the order of installing Dataguzzler-Python compared to
the dependencies (except Python) doesn't matter, but obviously
a dependency needs to be installed in order to use its
functionality.

Most of the dependencies can be installed using a package manager for
your platform such as ``apt-get``, ``DNF`` / ``Yum``, or `Anaconda
<https://anaconda.com>`_. An alternative is to use the ``pip``
installation tool. For Windows, the recommended package manager is
Anaconda. If you are planning on installing SpatialNDE2 (recommended),
the build environment from that will generally work nicely for
Dataguzzler-Python, so you may want to perform the SpatialNDE2 build
first (see SpatialNDE2 documentation). If using virtual Python
environments, make sure Dataguzzler-Python and all of its dependencies
are installed in the same environment. 


Installing Acquisition Libraries
--------------------------------

Acquisition libraries such as for GaGe (Vitrek) cards and the
Azure Kinect camera can be installed before or after
Dataguzzler-Python. However any libraries that use the C/C++
SpatialNDE2 API need to be installed after SpatialNDE2. In addition,
such libraries need to be rebuilt and reinstalled any time SpatialNDE2
is rebuilt.



