#include <stddef.h>

#include <sys/types.h>
#include <sys/poll.h>
#include <pthread.h>
#include <Python.h>

#include "dg_linklist.h"
#include "dg_internal/util.h"
#include "dg_internal/conn.h"
#include "dg_internal/mod.h"
#include "dg_internal/main.h"


#include "dgold_locking_c.h"

pthread_mutex_t dg_main_context_mutex; /* Always locked BEFORE GIL... MUST RELEASE GIL (i.e. Py_BEGIN_ALLOW_THREADS) before acquiring this lock */

pthread_key_t dg_in_main_context_key; /* True while mutex is held */
int one=1;
int zero=0;


void dg_enter_main_context_c(void)
/* Should only be called from Cython in WITH NOGIL code */
{
  assert(!PyGILState_Check());
  pthread_mutex_lock(&dg_main_context_mutex);
  pthread_setspecific(dg_in_main_context_key, &one);
}

void dg_leave_main_context_c(void)
/* Should only be called from Cython in WITH NOGIL code */
{
  pthread_setspecific(dg_in_main_context_key, &zero);
  pthread_mutex_unlock(&dg_main_context_mutex);
}

void dg_leave_main_context(void)
{
  Py_BEGIN_ALLOW_THREADS;
  dg_leave_main_context_c();
  Py_END_ALLOW_THREADS;
}

void dg_enter_main_context(void)
{
  Py_BEGIN_ALLOW_THREADS;
  dg_enter_main_context_c();
  Py_END_ALLOW_THREADS;
}





int dg_in_main_context(void)  // prototype in main.h
{  
  /* return nonzero if we are in the main dataguzzler context
     and if it is therefore OK to manipulate data structures */

  ///* in old dataguzzler_python, this means return nonzero if we hold the GIL,
  //   as the GIL is used to lock all the C functions */
  //return PyGILState_Check();
  return *((int *)pthread_getspecific(dg_in_main_context_key));

  
}

void dg_main_context_init(void)
{
  pthread_mutex_init(&dg_main_context_mutex,NULL);
  pthread_key_create(&dg_in_main_context_key,NULL);

}
