/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LUNAR_PROJECT_SAVE_H
#define LUNAR_PROJECT_SAVE_H
#include "project_workspace.h"
#include "project_store.h"
#include "fm1_state.h"
#ifndef FM1_STATE_BIN_COMPACT_WRITER
#error "Native project SAVE requires the compact streaming writer build"
#endif
/* Synchronous record source, HEAD through END; 1 complete, 0 refused.
 * Production adapter calls fm1_app_state_collect_project. Application state
 * must stay stable across both passes. This bridge grants no flash ownership.
 * All admission/stop flags must be exactly 1. Caller redraws after any lease. */
typedef int (*lunar_project_collect)(void *,fm1_rec_sink_t,void *,fm1_state_report_t *);
typedef struct {
 lunar_project_store *store;
 uint8_t header[32];
 uint32_t capacity, length, fingerprint;
 int header_seen, failed;
} lunar_project_save_output;
static int lunar_project_save_write(void *ctx,uint32_t off,const void *p,uint32_t n) {
 lunar_project_save_output *o=ctx;uint8_t bounds[8];
 if(o->failed||o->header_seen||(!p&&n)||off>o->capacity||n>o->capacity-off) {
  o->failed=1; return -1;
 }
 if(o->store&&lunar_project_write(o->store,off,p,n)) { o->failed=1; return -1; }
 lp_put(bounds,off);lp_put(bounds+4,n);
 o->fingerprint=lp_crc(o->fingerprint,bounds,sizeof bounds);
 o->fingerprint=lp_crc(o->fingerprint,p,n);
 if(off==0) {
  if(n!=sizeof o->header) { o->failed=1; return -1; }
  memcpy(o->header,p,n);o->length=lp_word(o->header+20);
  if(!o->length||o->length>o->capacity) { o->failed=1; return -1; }
  o->header_seen=1;
 }
 return 0;
}
/* 0 committed; negative refusal/failure. No automatic retries. Source and
 * read-only io validator must not mutate the app. Each failure closes the
 * transaction and releases the workspace, leaving pixels invalid for redraw.
 * The stream CRC detects accidental changes between passes; it is not a
 * cryptographic identity check or a substitute for exclusive app ownership.
 * The two-pass size check does not solve allocation of physical flash banks. */
static int lunar_project_save(fm1_tft_t *frame,const lunar_project_io *io,
        uint32_t slot_bytes,lunar_project_collect collect,void *source,
        int storage_admitted,int audio_stopped,int drawing_stopped,
        int display_reads_stopped,fm1_state_report_t *rep) {
 lunar_project_workspace lease={NULL,NULL,0};
 lunar_project_store store;
 lunar_project_save_output pre, out;
 fm1_state_writer_t *w;
 uint32_t capacity;
 void *mem;int rc=-2;
 if(!frame||!io||!collect||!rep||storage_admitted!=1||audio_stopped!=1||
    drawing_stopped!=1||display_reads_stopped!=1||!io->read||!io->erase||
    !io->program||!io->validate||slot_bytes<LP_SECTOR||slot_bytes%LP_SECTOR||
    slot_bytes>LP_MAX+LP_SECTOR) return -2;
 capacity=slot_bytes-LP_HEADER;if(capacity>LP_MAX)capacity=LP_MAX;
 mem=lunar_project_workspace_begin(&lease,frame,fm1_state_bin_writer_size(),
         audio_stopped,drawing_stopped,display_reads_stopped);
 if(!mem)return -2;
 memset(&store,0,sizeof store);memset(&pre,0,sizeof pre);pre.capacity=capacity;
 fm1_state_report_init(rep);
 w=fm1_state_bin_stream_writer(mem,FM1_STATE_WRITER_FIRMWARE,NULL,
         lunar_project_save_write,&pre,capacity,rep);
 if(!w||!collect(source,fm1_state_bin_write,w,rep)||pre.failed||!pre.header_seen)
  goto done;
 rc=lunar_project_begin(&store,io,slot_bytes);if(rc)goto done;
 memset(&out,0,sizeof out);out.capacity=capacity;out.store=&store;
 fm1_state_report_init(rep);
 w=fm1_state_bin_stream_writer(mem,FM1_STATE_WRITER_FIRMWARE,NULL,
         lunar_project_save_write,&out,capacity,rep);
 rc=-1;
 if(!w||!collect(source,fm1_state_bin_write,w,rep)||out.failed||!out.header_seen||
    pre.fingerprint!=out.fingerprint||memcmp(pre.header,out.header,sizeof pre.header))goto done;
 rc=lunar_project_commit(&store,out.length);
 done:
 store.active=0;if(rc)store.failed=1;
 (void)lunar_project_workspace_end(&lease);
 return rc;
}
#endif
