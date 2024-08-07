import os.path
import importlib
import posixpath
from urllib.request import url2pathname
from urllib.parse import quote
import ast
import inspect
import copy

def scan_source(sourcepath,sourcetext):
    """Reads in the given text and determines abstract syntax tree.
    Identifies global parameters and also assignment targets and their
    type. NoneType is interpreted as a string"""
    
    if sourcepath is None:
        sourcepath="<unknown>"
        pass
    

    assignable_param_types={}
    
    sourceast=ast.parse(sourcetext,filename=sourcepath)

    globalparams=set([])

    dpi_args=False

    dpi_kwargs=False
    
    cnt=0
    while cnt < len(sourceast.body):
        entry=sourceast.body[cnt]

        if entry.__class__.__name__=="Assign" and len(entry.targets)==1 and entry.targets[0].__class__.__name__=="Name":
            if entry.value.__class__.__name__=="Constant" and entry.value.value.__class__.__name__=="float":
                assignable_param_types[entry.targets[0].id] = float
                pass
            if entry.value.__class__.__name__=="Constant" and entry.value.value.__class__.__name__=="int":
                assignable_param_types[entry.targets[0].id] = int
                pass
            if entry.value.__class__.__name__=="Constant" and entry.value.value.__class__.__name__=="str":
                assignable_param_types[entry.targets[0].id] = str
                pass
            if entry.value.__class__.__name__=="Constant" and entry.value.value.__class__.__name__=="NoneType":
                # Treat None as str -- we probably want a filename or similar
                assignable_param_types[entry.targets[0].id] = str
                pass

            if entry.targets[0].id=="dpi_args":
                dpi_args=True
                pass

            if entry.targets[0].id=="dpi_kwargs":
                dpi_kwargs=True
                pass
            pass
        
            # print entry.targets
            
        if entry.__class__.__name__=="Global":
            for paramkey in entry.names:
                # This key declared as a global
                globalparams.add(paramkey)
                pass
            pass
        cnt+=1
        pass
    
    return (sourceast,globalparams,assignable_param_types,dpi_args,dpi_kwargs)

def modify_source_overriding_parameters(sourcepath,sourceast,paramdict_keys,mode):
    """Reads in the given syntax tree. Removes assignments of given
    keys. Returns byte-compiled code ready-to-execute (paramdict
    values must be independently provided). 

    Mode can be 'all' to indicate keeping the entire module, 'main_thread'
        to indicate keeping the initial portion prior to dgpython_release_main_thread(), 'sub_thread' to indicate keeping the final portion after dgpython_release_main_thread()"""

    
    #sourcefile=open(sourcepath,"r")
    #sourceast=ast.parse(sourcefile.read(),filename=sourcepath)
    #sourcefile.close()
    if sourcepath is None:
        sourcepath="<unknown>"
        pass

    # Remove assignments of dpi_args and/or dpi_kwargs
    gotdpiargs=0
    gotdpikwargs=0
    cnt=0
        
    while cnt < len(sourceast.body):
        entry=sourceast.body[cnt]
        if entry.__class__.__name__=="Assign" and len(entry.targets)==1 and entry.targets[0].__class__.__name__=="Name":
            # print entry.targets
            if entry.targets[0].id=="dpi_args":
                del sourceast.body[cnt]
                gotdpiargs+=1
                continue  # bypass cnt increment below
            if entry.targets[0].id=="dpi_kwargs":
                del sourceast.body[cnt]
                gotdpikwargs+=1
                continue  # bypass cnt increment below
            pass
        cnt+=1
        pass
    
    if gotdpiargs > 1:
        raise ValueError("Overridden parameter dpi_args in %s is not simply assigned exactly once at top level" % (sourcepath))
    if gotdpikwargs > 1:
        raise ValueError("Overridden parameter dpi_kwargs in %s is not simply assigned exactly once at top level" % (sourcepath))
        
    # Remove simple assignments of paramdict entries
    for paramkey in paramdict_keys:
        gotassigns=0
        cnt=0
        
        while cnt < len(sourceast.body):
            entry=sourceast.body[cnt]
            if entry.__class__.__name__=="Assign" and len(entry.targets)==1 and entry.targets[0].__class__.__name__=="Name":
                # print entry.targets
                if entry.targets[0].id==paramkey:
                    del sourceast.body[cnt]
                    gotassigns+=1
                    continue  # bypass cnt increment below
                pass
            cnt+=1
            pass

        if gotdpikwargs==0 and gotassigns != 1:
            raise ValueError("Overridden parameter %s in %s is not simply assigned exactly once at top level" % (paramkey,sourcepath))
        if gotdpikwargs==1 and gotassigns > 1:
            raise ValueError("Overridden parameter %s in %s is simply assigned more than once at top level" % (paramkey,sourcepath))
        pass
    
    if mode == "main_thread":
        # Want to keep all code up until dgpython_release_main_thread()
        for cnt in range(len(sourceast.body)):
            if (sourceast.body[cnt].__class__.__name__ == "Expr" and
                sourceast.body[cnt].value.__class__.__name__ == "Call" and
                sourceast.body[cnt].value.func.__class__.__name__ == "Name" and
                sourceast.body[cnt].value.func.id == "dgpython_release_main_thread"):
                # Remove all code from here on.
                while len(sourceast.body) > cnt:
                    del sourceast.body[-1]
                    pass
                break
            pass
        pass
    elif mode == "sub_thread":
        # Want to keep only code after dgpython_release_main_thread()
        origbody = sourceast.body
        sourceast.body = []
        for cnt in range(len(origbody)):
            if (origbody[cnt].__class__.__name__ == "Expr" and
                origbody[cnt].value.__class__.__name__ == "Call" and
                origbody[cnt].value.func.__class__.__name__ == "Name" and
                origbody[cnt].value.func.id == "dgpython_release_main_thread"):
                # Keep all code from here on.
                for cnt2 in range(cnt+1,len(origbody)):
                    sourceast.body.append(origbody[cnt2])
                    pass
                break
            pass
        pass
    else:
        assert(mode=="all")
        pass
    
    
    return sourceast # compile(sourceast,sourcepath,'exec')

def modify_source_into_function_call(sourceast,localkwargs):
    """Take sourceast, and stuff it into the body of a function call
which takes the named arguments given in the keys of localkwargs. Then
generate a call to the function that stores the return in the
local variable __dgpy_config_ret. Then return an abstract syntax
tree representing this process. 

The name of the defined function is __dgpy_config_function.
    """
    
    curbody = sourceast.body
    
    funcarglist = [ ast.arg(arg=kwarg,annotation=None,type_comment=None) for kwarg in localkwargs ]
    

    funcargs = ast.arguments(posonlyargs=[],
                             args=funcarglist,
                             vararg=None,
                             kwonlyargs=[],
                             kw_defaults=[],
                             kwarg=None,
                             defaults=[])
    
    funcdef = ast.FunctionDef(name="__dgpy_config_function",
                              args=funcargs,
                              body=curbody,
                              decorator_list=[],
                              returns = None,
                              type_comment = None)

    funccallkeywords = [ ast.keyword(arg=kwarg,value=ast.Name(id=kwarg,ctx=ast.Load())) for kwarg in localkwargs ] 
    
    funcretassign = ast.Assign(targets=[ast.Name(id="__dgpy_config_ret",ctx=ast.Store())],
                               value=ast.Call(func=ast.Name(id="__dgpy_config_function",ctx=ast.Load()),
                                              args=[],
                                              keywords=funccallkeywords),
                               type_comment = None)
    
    moddef = ast.Module([funcdef,funcretassign],type_ignores=[])

    ast.fix_missing_locations(moddef)
    
    return moddef
