import sys
import os
import time
from .dgpy import Module as dgpy_Module
from .dgpy import CurContext

from threading import Thread,Lock

cimport cpython.pycapsule as pycapsule
from cpython.ref cimport PyObject
from libc.stdlib cimport calloc,free
from libc.string cimport strdup

cdef extern from "sys/poll.h":
     pass

#cdef extern from "dg_units.h":
#     pass
     
from dataguzzler cimport linklist as dgl
cimport dataguzzler as dg
from dataguzzler_python cimport wfmstore
from dataguzzler_python cimport dgold
from dataguzzler cimport dg_file



cdef extern from "savewfm_c.h":
    struct SaveWfmNode:
        char *Name
        wfmstore.Wfm *Wfm
        pass
    char *loadwfms_c(char *Filename,char *ModName,dgl.dgl_List *WfmList) nogil
    char *savewfms_c(char *Filename,dgl.dgl_List *WfmList) nogil
 
    pass


class savewfm(object,metaclass=dgpy_Module):
    Name=None

    def __init__(self,Name):
        self.Name=Name
        pass


    def savewfms(self,path, name, waveforms):
        # waveforms is list of waveform names
        cdef SaveWfmNode *WfmNode;
        cdef dgl.dgl_List WfmList
        cdef char *errmsg
        cdef bytes namebytes
        dgl.dgl_NewList(&WfmList); 
        
        waveformnames = [ waveformname.encode('utf8') for waveformname in waveforms ]
         
        # Assemble list of waveforms
        for waveform in waveformnames:
            WfmNode=<SaveWfmNode *>calloc(sizeof(SaveWfmNode),1)
            namebytes=waveform
            WfmNode.Name=strdup(<char *>namebytes)
            dgl.dgl_AddTail(&WfmList,<dgl.dgl_Node *>WfmNode)
            pass
        Filename=os.path.join(path,name).encode('utf8')
        # Perform save
        errmsg=savewfms_c(Filename,&WfmList)
 
        WfmNode=<SaveWfmNode *>dgl.dgl_RemHead(&WfmList)
        while WfmNode is not NULL:
            free(WfmNode.Name)
            free(WfmNode)
            WfmNode=<SaveWfmNode *>dgl.dgl_RemHead(&WfmList)
            pass
        pass
        if errmsg is not NULL:
            raise IOError(errmsg)
        pass

    def loadwfms(self,path, name):
        # waveforms is list of waveform names
        cdef SaveWfmNode *WfmNode;
        cdef dgl.dgl_List WfmList
        cdef char *errmsg
        cdef char *Filename_ptr
        cdef char *Modname_tr
        cdef bytes Modname_bytes 
        
        dgl.dgl_NewList(&WfmList);

        Filename=os.path.join(path,name).encode('utf8')
        Filename_ptr=<char *>Filename
        Modname_bytes=self.Name.encode('utf-8')
        Modname_ptr=<char *>Modname_bytes
 
        # Perform load
        with nogil: 
            errmsg=loadwfms_c(Filename_ptr,Modname_ptr,&WfmList)
            pass

        WfmNode=<SaveWfmNode *>dgl.dgl_RemHead(&WfmList)
        while WfmNode is not NULL:
            free(WfmNode)
            WfmNode=<SaveWfmNode *>dgl.dgl_RemHead(&WfmList)
            pass
        pass
        if errmsg is not NULL:
            raise IOError(errmsg)
        pass

    def deletewfm(self,channame):
        cdef wfmstore.Channel *Chan
        cdef bytes channame_bytes,modname_bytes
        

        channame_bytes=channame.encode('utf-8')
        modname_bytes=self.Name.encode('utf-8')

        dgold.dg_enter_main_context()
        Chan=wfmstore.ChanIsMine(<char *>channame_bytes,<char *>modname_bytes)
        if Chan != NULL:
            wfmstore.DeleteChannel(Chan,modname_bytes)
            pass
        dgold.dg_leave_main_context()
        
        pass

    pass

