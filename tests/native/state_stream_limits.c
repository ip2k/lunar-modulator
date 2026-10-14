/* SPDX-License-Identifier: MIT */
/* Streaming SEQS keeps the existing maximum line/chunk/capacity boundaries. */
#include "fm1_state.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned char bytes[FM1_STATE_BIN_MAX], touched[FM1_STATE_BIN_MAX];
static char line[16385];
static unsigned calls, header, lines;
static uint32_t total;
static int wr(void *ctx, uint32_t off, const void *p, uint32_t n) {
  const unsigned char *b=p; (void)ctx; ++calls;
  assert(off<=sizeof bytes && n<=sizeof bytes-off);
  for (uint32_t i=0;i<n;++i) { assert(!touched[off+i]); touched[off+i]=1; bytes[off+i]=b[i]; }
  if (!off) ++header;
  return 0;
}
static uint32_t rd(void *ctx,uint32_t off,uint8_t *p,uint32_t n) {
  (void)ctx; if(off>total || n>total-off)return 0; memcpy(p,bytes+off,n);return n;
}
static int sink(void *ctx,const fm1_rec_t *r) {
  (void)ctx; if(r->type==FM1_REC_LINE && (r->piece&FM1_REC_LAST))++lines; return 1;
}
int main(int argc,char **argv) {
  fm1_state_report_t rep; fm1_rec_t r; unsigned before;
  assert(argc==2); int mode=atoi(argv[1]); assert(mode>=0 && mode<6);
  void *mem=malloc(fm1_state_bin_writer_size()); assert(mem);
  memset(bytes,255,sizeof bytes); memset(line,'x',sizeof line);
  uint32_t cap=mode>=4?1316u+49152u-(mode==5):FM1_STATE_BIN_MAX;
  fm1_state_report_init(&rep);
  fm1_state_writer_t *w=fm1_state_bin_stream_writer(mem,0,NULL,wr,NULL,cap,&rep); assert(w);
  memset(&r,0,sizeof r);r.type=FM1_REC_HEAD;r.u.head.kind=FM1_STATE_SET;r.u.head.major=FM1_STATE_MAJOR;
  assert(fm1_state_bin_write(w,&r));
  memset(&r,0,sizeof r);r.type=FM1_REC_LINE;r.piece=FM1_REC_FIRST|FM1_REC_LAST;
  r.u.line.which=FM1_LINES_SET;r.u.line.s="movy1";r.u.line.n=5;
  assert(fm1_state_bin_write(w,&r));
  int ok=1;unsigned count=mode==2 || mode==3?1:3;
  for(unsigned i=0;i<count && ok;++i) {
    memset(&r,0,sizeof r);r.type=FM1_REC_LINE;r.piece=FM1_REC_FIRST|FM1_REC_LAST;
    r.u.line.which=FM1_LINES_SET;r.u.line.s=line;
    r.u.line.n=mode==3?16385u:(i==2?16374u+(mode==1):16384u);
    ok=fm1_state_bin_write(w,&r);
  }
  memset(&r,0,sizeof r);r.type=FM1_REC_END;
  if(ok)ok=fm1_state_bin_write(w,&r);
  before=calls;assert(!fm1_state_bin_write(w,&r));assert(calls==before);
  if(mode==1 || mode==3 || mode==5) {assert(!ok && !header);assert(rep.code==FM1_STATE_TOO_BIG);}
  else {
    assert(ok && header==1);
    total=(uint32_t)bytes[20]|((uint32_t)bytes[21]<<8)|((uint32_t)bytes[22]<<16)|((uint32_t)bytes[23]<<24);
    assert(total==1316u+(count==1?16388u:49152u));
    fm1_state_report_init(&rep);assert(fm1_state_bin_read(rd,NULL,total,sink,NULL,&rep,0));assert(lines==count+1);
  }
  printf("mode=%d workspace=%zu calls=%u total=%u\n",mode,fm1_state_bin_writer_size(),calls,total);
  free(mem);return 0;
}
