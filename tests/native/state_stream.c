/* SPDX-License-Identifier: MIT */
#include "fm1_state.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned char input[FM1_STATE_BIN_MAX], output[FM1_STATE_BIN_MAX], touched[FM1_STATE_BIN_MAX];
static char text[2][524288];
static size_t lengths[2];
static unsigned calls, fail_at, last_off, last_n;
static uint32_t total;
static uint32_t rd(void *ctx, uint32_t off, uint8_t *p, uint32_t n) {
  if (off > total || n > total-off) return 0;
  memcpy(p,(unsigned char *)ctx+off,n); return n;
}
static void print_put(void *ctx,const char *p,size_t n) {
  unsigned i=*(unsigned *)ctx; assert(n<=sizeof(text[i])-lengths[i]);
  memcpy(text[i]+lengths[i],p,n); lengths[i]+=n;
}
static int wr(void *ctx,uint32_t off,const void *p,uint32_t n) {
  const unsigned char *b=p; unsigned i; (void)ctx;
  calls++; if(calls==fail_at) return -1;
  assert(off<=sizeof(output) && n<=sizeof(output)-off);
  for(i=0;i<n;i++) { assert(!touched[off+i]); assert((output[off+i]&b[i])==b[i]); touched[off+i]=1; output[off+i]=b[i]; }
  last_off=off; last_n=n; return 0;
}
static uint32_t le32(const unsigned char *p) { return (uint32_t)p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24); }
int main(int argc,char **argv) {
  FILE *f; void *mem; fm1_state_writer_t *w; fm1_state_report_t rep;
  fm1_state_printer_t printer; fm1_rec_t end; unsigned idx=0, before; int ok;
  assert(argc==3 || argc==4); fail_at=(unsigned)strtoul(argv[2],NULL,10);
  f=fopen(argv[1],"rb"); assert(f); total=(uint32_t)fread(input,1,sizeof(input),f); assert(!ferror(f)); fclose(f);
  mem=malloc(fm1_state_bin_writer_size()); assert(mem);
#ifdef FM1_STATE_BIN_COMPACT_WRITER
  assert(fm1_state_bin_writer_size()<40000);
  assert(!fm1_state_bin_writer(mem,0,0,NULL,NULL,NULL,NULL));
#endif
  assert(!fm1_state_bin_stream_writer(NULL,0,NULL,wr,NULL,sizeof(output),NULL));
  assert(!fm1_state_bin_stream_writer(mem,0,NULL,NULL,NULL,sizeof(output),NULL));
  assert(!fm1_state_bin_stream_writer(mem,0,NULL,wr,NULL,1317,NULL));
  assert(!fm1_state_bin_stream_writer(mem,0,NULL,wr,NULL,sizeof(output)+1,NULL));
  memset(output,255,sizeof(output)); fm1_state_report_init(&rep);
  w=fm1_state_bin_stream_writer(mem,0,NULL,wr,NULL,fail_at==9999?1318:sizeof(output),&rep); assert(w);
  ok=fm1_state_bin_read(rd,input,total,fm1_state_bin_write,w,&rep,0);
  memset(&end,0,sizeof(end)); end.type=FM1_REC_END;
  before=calls; assert(!fm1_state_bin_write(w,&end)); assert(calls==before);
  if (fail_at && (fail_at<=calls || fail_at==9999)) { assert(!ok); assert(!touched[0]); }
  else {
    assert(ok); assert(last_off==0 && last_n==32);
    fm1_state_printer_init(&printer,print_put,&idx); fm1_state_report_init(&rep);
    assert(fm1_state_bin_read(rd,input,total,fm1_state_print,&printer,&rep,0));
    total=le32(output+20); idx=1; fm1_state_printer_init(&printer,print_put,&idx); fm1_state_report_init(&rep);
    assert(fm1_state_bin_read(rd,output,total,fm1_state_print,&printer,&rep,0));
    assert(lengths[0]==lengths[1] && !memcmp(text[0],text[1],lengths[0]));
    if (argc==4) {
      f=fopen(argv[3],"wb"); assert(f);
      assert(fwrite(output,1,total,f)==total); assert(!fclose(f));
    }
  }
  printf("workspace=%zu calls=%u total=%u\n",fm1_state_bin_writer_size(),calls,total);
  free(mem); return 0;
}
