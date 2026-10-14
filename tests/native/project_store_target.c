/* SPDX-License-Identifier: MIT */
#include "project_store.h"
int project_store_target(lunar_project_store *s,const lunar_project_io *io,
                         uint32_t slot_bytes,const void *p,uint32_t n) {
 int rc=lunar_project_begin(s,io,slot_bytes);
 if(rc) return rc;
 rc=lunar_project_write(s,0,p,n);
 return rc?rc:lunar_project_commit(s,n);
}
