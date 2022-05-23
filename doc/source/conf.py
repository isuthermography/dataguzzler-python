# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))


# -- Project information -----------------------------------------------------

project = 'Dataguzzler-Python'
copyright = '2022, Stephen D. Holland'
author = 'Stephen D. Holland'

# The full version, including alpha/beta/rc tags
#release = '0.6'

import setuptools
import subprocess
import re

# Extract GIT version (use subprocess.call(['git','rev-parse']) to check if we are inside a git repo
if setuptools.distutils.spawn.find_executable("git") is not None and subprocess.call(['git','rev-parse'],stderr=subprocess.DEVNULL)==0:
    # Check if tree has been modified
    modified = subprocess.call(["git","diff-index","--quiet","HEAD","--"]) != 0
    
    gitrev = subprocess.check_output(["git","rev-parse","HEAD"]).decode('utf-8').strip()

    version = "git-%s" % (gitrev)

    # See if we can get a more meaningful description from "git describe"
    try:
        versionraw=subprocess.check_output(["git","describe","--tags","--match=v*"],stderr=subprocess.STDOUT).decode('utf-8').strip()
        # versionraw is like v0.1.0-50-g434343
        # for compatibility with PEP 440, change it to
        # something like 0.1.0+50.g434343
        matchobj=re.match(r"""v([^.]+[.][^.]+[.][^-.]+)(-.*)?""",versionraw)
        version=matchobj.group(1)
        if matchobj.group(2) is not None:
            version += '+'+matchobj.group(2)[1:].replace("-",".")
            pass
        pass
    except subprocess.CalledProcessError:
        # Ignore error, falling back to above version string
        pass

    if modified and version.find('+') >= 0:
        version += ".modified"
        pass
    elif modified:
        version += "+modified"
        pass
    pass
else:
    version = "UNKNOWN"
    pass

release = version



# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'alabaster'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']
