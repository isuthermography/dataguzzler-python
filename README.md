Dataguzzler-Python
==================

Dataguzzler-Python is a tool to facilitate data acquisition,
leveraging Python for scripting and interaction.
A Dataguzzler-Python data acquisition system consists of *modules* that
can control and/or capture data from your measurement hardware, and
often additional higher-level *modules* that integrate functionality
provided by the hardware into some sort of virtual instrument.

For basic information see: doc/source/about.rst
For installation instructions see: doc/source/installation.rst
For a quickstart guide see: doc/source/quickstart.rst

Basic requirements are Python v3.8 or above with the following packages: numpy, setuptools, wheel, build, setuptools_scm

Basic installation is (possibly as root or Administrator):
    pip install --no-deps --no-build-isolation .

More detailed documentation is also available in doc/source/

To render the documentation use a command prompt, change to the
doc/ directory and type "make". On Windows it will create HTML
documentation in the doc/build/html directory. On Linux you get options
such as "make html" and "make latexpdf" to get different forms
of documentation. 
