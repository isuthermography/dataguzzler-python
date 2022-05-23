Installation
============

Dataguzzler-Python is distributed as a Python source tree. You will
need a Python installation (at least v3.8). Also install the
prerequisite dependencies listed above. Installation is accomplished by running
(possibly as root or Administrator):

::

   python setup.py install

from a suitable terminal, command prompt, or Anaconda prompt.  In
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

Acquisition libraries such as for Gage (DynamicSignals) cards and the
Azure Kinect camera can be installed before or after
Dataguzzler-Python. However any libraries that use the C/C++
SpatialNDE2 API need to be installed after SpatialNDE2. In addition,
such libraries need to be rebuilt and reinstalled any time SpatialNDE2
is rebuilt.



