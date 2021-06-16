import pydoc

def cleaner_visiblename(name, all=None,obj=None):
    # Filter out anything starting with '_' unless it is a named tuple with a _fields attribute:
    
    # obey programmer-provided __all__, if present
    if all is not None:
        return name in all

    if name.startswith('_'):
        if hasattr(obj,"_fields"):
            return True
        return False

    if name=="who" or name=="help":
        return False # filter out who() and help() functions that are everywhere


    return True

def monkeypatch_visiblename():
    """The internal Python help() reports on all sorts of special methods
and attributes that should best be hidden. This makes the help printout
borderline useless because of all the excess stuff. 

We have two alternatives: 
   * Include a nearly verbatim copy of pydoc, modified to strip the excess, or
   * Monkeypatch the built-in pydoc to filter out the excess better

Pydoc defines a function "visiblename" to determine whether a given method 
or attribute should be visible. We just replace this with one more 
restrictive"""


    pydoc.visiblename=cleaner_visiblename
    pass
