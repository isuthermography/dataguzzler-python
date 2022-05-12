from collections import OrderedDict
import copy
from .context import SimpleContext,InitThreadContext,PushThreadContext,PopThreadContext
import spatialnde2 as snde

class RecordingDynamicMetadatum(object):
    is_dynamic = None
    static_value = None
    dynamic_callable = None
    dynamic_args = None
    dynamic_kwargs = None
    pass
    
    
class RecordingDynamicMetadata(object):
    metadata = None # Ordered dictionary by mdname of RecordingDynamicMetadatum

    def __init__(self):
        self.metadata = OrderedDict()
        pass
    pass

class DynamicMetadata(object):
    """DynamicMetadata class for assigning dynamic metadata 
    to recordings. Thread safe so long as all updating methods are called from a single thread. """

    _md_dict = None
    name_root = None

    def __init__(self,name_root):
        self._md_dict = OrderedDict()
        self.name_root = name_root # Base name for naming our thread context so it will be human readable
        pass

    def Snapshot(self):
        new_dyn_md = DynamicMetadata(self.name_root)
        new_dyn_md._md_dict = self._md_dict
        return new_dyn_md

    def AddStaticMetaDatum(self,Path,mdname,mdvalue):
        md_dict_copy = copy.deepcopy(self._md_dict)

        if not Path in md_dict_copy:
            md_dict_copy[Path] = RecordingDynamicMetadata()
            pass

        new_md = RecordingDynamicMetadatum()
        new_md.is_dynamic = False
        new_md.static_value = mdvalue
        
        md_dict_copy[Path].metadata[mdname] = new_md

        self._md_dict = md_dict_copy # atomic update
        pass


    def AddDynamicMetaDatum(self,Path,mdname,callable,*args,**kwargs):
        md_dict_copy = copy.deepcopy(self._md_dict)

        if not Path in md_dict_copy:
            md_dict_copy[Path] = RecordingDynamicMetadata()
            pass

        new_md = RecordingDynamicMetadatum()
        new_md.is_dynamic = True
        new_md.dynamic_callable = callable
        new_md.dynamic_args = args
        new_md.dynamic_kwargs = kwargs
        
        md_dict_copy[Path].metadata[mdname] = new_md

        self._md_dict = md_dict_copy # atomic update
        pass

    def Acquire(self,*recordings):
        context = SimpleContext()
        InitThreadContext(context,self.name_root + ".dynamic_metadata.Acquire")
        PushThreadContext(context)

        try: 
            for rec in recordings:
                recname = rec.info.name
                
                rec.pending_dynamic_metadata = snde.constructible_metadata()
                
                if recname in self._md_dict:
                    
                    for mdname in self._md_dict[recname].metadata:
                        mdatum = self._md_dict[recname].metadata[mdname]
                        
                        if mdatum.is_dynamic:
                            rec.pending_dynamic_metadata.AddMetaDatum(snde.metadatum(mdname,mdatum.dynamic_callable(*mdatum.dynamic_args,**mdatum.dynamic_kwargs)))
                            
                            pass
                        else:
                            # static
                            rec.pending_dynamic_metadata.AddMetaDatum(snde.metadatum(mdname,mdatum.static_value))
                            pass
                        
                        pass
                    pass
                
                rec.mark_dynamic_metadata_done() # Save acquired metadata. 
                pass
            pass
        finally:
            PopThreadContext()
            pass
        pass
    
        
    pass
