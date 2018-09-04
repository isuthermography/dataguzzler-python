
struct SaveWfmNode {
  struct dgl_Node Node;
  char *Name;
  struct dg_wfminfo *loadinfo;
  struct Wfm *Wfm;
};


static inline char *loadwfms_c(char *Filename,char *ModName,struct dgl_List *WfmList) /* WfmList should be empty */
/* call WITHOUT GIL */
{
  struct Channel *Chan;
  unsigned long long revision;
  struct SaveWfmNode *WfmNode;
  struct dgf_file *infile;
  struct dgf_Chunk *SnapshotChunk,*Chunk;
  char *retval=NULL;
  struct dg_wfminfo *info;

  infile=dgf_open(Filename);

  if (!infile) {
    return "Error opening file";
  }
  

  SnapshotChunk=dgf_checknextchunk(infile,"SNAPSHOT");

  Chunk=dgf_checknextchunk(infile,"METADATA"); 
  dgf_chunkdone(infile,Chunk);/* Ignore metadata */

  
  for (Chunk=dgf_checknextchunk(infile,"GUZZNWFM");Chunk;Chunk=dgf_checknextchunk(infile,"GUZZNWFM")) {
    info=dgf_procGUZZNWFM(infile);    
    
    WfmNode=calloc(sizeof(*WfmNode),1);
    WfmNode->Name=strdup(info->Name);
    WfmNode->loadinfo=info;
    dgl_AddTail(WfmList,(struct dgl_Node *)WfmNode);
  }
  
  dgf_chunkdone(infile,SnapshotChunk); /* "SNAPSHOT" */
  
  dgf_close(infile);

  dg_enter_main_context_c();
  StartTransaction();
  for (WfmNode=(struct SaveWfmNode *)WfmList->lh_Head;WfmNode->Node.ln_Succ;WfmNode=(struct SaveWfmNode *)WfmNode->Node.ln_Succ) {
    
    Chan=CreateChannel(WfmNode->Name,ModName,FALSE,NULL,0);
    //#fprintf(stderr,"LoadWfm: Attempting to create channel %s\n",WfmNode->Name);
    if (!Chan) {
      retval = "Channel Exists";
    }

    Chan=ChanIsMine(WfmNode->Name,ModName);
    if (!Chan) {
      retval = "Channel owned by another module";
    }
    
    
    WfmNode->Wfm=CreateWfm(Chan,0,NULL);

    /* allocate memory */
    WfmAlloc(WfmNode->Wfm,WfmNode->loadinfo->n,WfmNode->loadinfo->ndim,WfmNode->loadinfo->dimlen);

    /* copy data */
    memcpy(WfmNode->Wfm->Info.data,WfmNode->loadinfo->data,WfmNode->loadinfo->n*sizeof(*WfmNode->loadinfo->data));

    /* Copy metadata */
    dgm_CopyMetaDataWI(WfmNode->loadinfo,(struct dg_wfminfo *)WfmNode->Wfm);
	   
    /* free loaded copy */
    dg_deletewfm(WfmNode->loadinfo);
    WfmNode->loadinfo=NULL;
    NotifyChannel(Chan,WfmNode->Wfm,1);
    
  }

  EndTransaction();
  dg_leave_main_context_c();

  return retval;

}

static inline char *savewfms_c(char *Filename,struct dgl_List *WfmList) /* WfmList should have name entries filled out */
/* call WITHOUT GIL */
{
  struct Channel *Chan;
  unsigned long long revision;
  struct Wfm *Wfm;
  char *WfmName;
  struct SaveWfmNode *WfmNode;
  struct dgl_List EmptyList;
  struct dgf_file *outfile;
  char *retval;



  assert(!PyGILState_Check()); // should NOT have the GIL as we lock stuff with dg_enter_main_context()

  dg_enter_main_context();
  

  for (WfmNode=(struct SaveWfmNode *)WfmList->lh_Head;WfmNode->Node.ln_Succ;WfmNode=(struct SaveWfmNode *)WfmNode->Node.ln_Succ) {
    Chan=FindChannel(WfmNode->Name);
    if (!Chan || Chan->Deleted) {
      retval="Channel Not Found";
      //retval=strdup(WfmNode->Name);
      goto cleanup;
    }
  
    Wfm=FindLatestReadyRev(Chan);
    if (!Wfm) {
      retval="Waveform Missing";
      goto cleanup;
    }

    //# Reference Wfm so we can access it with main context dropped
    WfmReference(Wfm);

    WfmNode->Wfm=Wfm;
    
  }


  /* Release lock while we are saving... waveforms locked in memory by WfmReference() above */
  dg_leave_main_context();

  dgl_NewList(&EmptyList); /* We don't support writing metadata */

  outfile=dgf_creat(Filename);

  dgf_startchunk(outfile,"SNAPSHOT");

  dgf_writemetadata(outfile,&EmptyList);
  
  for (WfmNode=(struct SaveWfmNode *)WfmList->lh_Head;WfmNode->Node.ln_Succ;WfmNode=(struct SaveWfmNode *)WfmNode->Node.ln_Succ) {
    dgf_writenamedwfm(outfile,(struct dg_wfminfo *)WfmNode->Wfm);
    
  }

  dgf_endchunk(outfile); /* SNAPSHOT */
  dgf_close(outfile);


  dg_enter_main_context();

  retval=NULL;
cleanup:
  for (WfmNode=(struct SaveWfmNode *)WfmList->lh_Head;WfmNode->Node.ln_Succ;WfmNode=(struct SaveWfmNode *)WfmNode->Node.ln_Succ) {
    if (WfmNode->Wfm) {
      WfmUnreference(WfmNode->Wfm);
      WfmNode->Wfm=NULL;
    }
  }
  dg_leave_main_context();

  return retval;
}
