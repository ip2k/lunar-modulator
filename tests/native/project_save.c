/* SPDX-License-Identifier: MIT */
#include "fm1_state.h"
#include "project_save.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#define SLOT 102400u
static uint8_t flash[2*SLOT],baseline[2*SLOT],input[FM1_STATE_BIN_MAX];
static char text[3][524288];
static size_t text_n[3];
static uint32_t input_n;
static unsigned ops,fail_at,torn;
typedef struct { uint32_t off,n; int failed; } source;
static int read_flash(void *ctx,uint32_t off,void *p,uint32_t n) {
 (void)ctx;assert(off<=sizeof flash&&n<=sizeof flash-off);
 if(++ops==fail_at)return -1;
 memcpy(p,flash+off,n);return 0;
}
static int erase_flash(void *ctx,uint32_t off) {
 (void)ctx;assert(!(off%LP_SECTOR)&&off<=sizeof flash-LP_SECTOR);
 if(++ops==fail_at){if(torn)memset(flash+off,255,torn==2?LP_SECTOR:LP_SECTOR/2);return -1;}
 memset(flash+off,255,LP_SECTOR);return 0;
}
static int program_flash(void *ctx,uint32_t off,const void *p,uint32_t n) {
 const uint8_t *b=p;uint32_t i,k=n;int fail;(void)ctx;
 assert(off<=sizeof flash&&n<=sizeof flash-off&&n<=256);
 assert((off&255u)+n<=256);
 fail=++ops==fail_at;if(fail)k=torn==2?n:(torn?n/2:0);
 for(i=0;i<k;i++){assert((flash[off+i]&b[i])==b[i]);flash[off+i]=b[i];}
 return fail?-1:0;
}
static uint32_t source_read(void *ctx,uint32_t off,uint8_t *p,uint32_t n) {
 source *s=ctx;if(off>s->n||n>s->n-off)return 0;
 if(read_flash(NULL,s->off+off,p,n)){s->failed=1;return 0;}
 return n;
}
static uint32_t input_read(void *ctx,uint32_t off,uint8_t *p,uint32_t n) {
 (void)ctx;if(off>input_n||n>input_n-off)return 0;
 memcpy(p,input+off,n);return n;
}
static int discard(void *ctx,const fm1_rec_t *r){(void)ctx;(void)r;return 1;}
static int validate(void *ctx,uint32_t off,uint32_t n) {
 source src={off,n,0};fm1_state_report_t rep;int ok;(void)ctx;fm1_state_report_init(&rep);
 ok=fm1_state_bin_read(source_read,&src,n,discard,NULL,&rep,0);
 return src.failed?-1:(ok?0:1);
}
static void print_put(void *ctx,const char *p,size_t n) {
 unsigned i=*(unsigned *)ctx;assert(n<=sizeof text[i]-text_n[i]);
 memcpy(text[i]+text_n[i],p,n);text_n[i]+=n;
}
static fm1_rec_t changed(const fm1_rec_t *r) {
 fm1_rec_t next=*r;
 if(next.type==FM1_REC_SESSION) next.u.session.transpose++;
 return next;
}
static int changed_print(void *ctx,const fm1_rec_t *r) {
 fm1_rec_t next=changed(r);return fm1_state_print(ctx,&next);
}
static lunar_project_io io={NULL,read_flash,erase_flash,program_flash,validate};
static fm1_tft_t frame;
static unsigned collects, collect_mode;
static int collect(void *ctx,fm1_rec_sink_t sink_fn,void *sink_ctx,fm1_state_report_t *rep) {
 (void)ctx;collects++;
 if(collect_mode==1)return 0;
 if(collect_mode==2)return 1; /* Refuse a false success without END. */
 return fm1_state_bin_read(input_read,NULL,input_n,sink_fn,sink_ctx,rep,0);
}
static int collect_changed(void *ctx,const fm1_rec_t *r) {
 fm1_rec_t next=changed(r);
 if(collect_mode==3&&collects==2&&next.type==FM1_REC_SESSION)next.u.session.transpose++;
 return fm1_state_bin_write(ctx,&next);
}
static int collect_project(void *ctx,fm1_rec_sink_t sink_fn,void *sink_ctx,fm1_state_report_t *rep) {
 (void)sink_fn;
 return collect(ctx,collect_changed,sink_ctx,rep);
}
static int save(void) {
 fm1_state_report_t rep;int rc;
 fm1_tft_begin(&frame,0x1234);collects=0;
 rc=lunar_project_save(&frame,&io,SLOT,collect_project,NULL,1,1,1,1,&rep);
 assert(!fm1_tft_pixels_valid(&frame));
 fm1_tft_begin(&frame,0x4567);assert(fm1_tft_pixels_valid(&frame));
 return rc;
}
static void check_reboot(void) {
 lunar_project_store s;int slot;uint32_t gen,n;source src;fm1_state_report_t rep;
 fm1_state_printer_t printer;unsigned idx=2;
 memset(&s,0,sizeof s);s.io=io;s.slot_bytes=SLOT;
 assert(!lunar_project_scan(&s,&slot,&gen,&n));assert(slot==0||slot==1);
 assert(!memcmp(flash,baseline,SLOT));src.off=(uint32_t)slot*SLOT+LP_HEADER;src.n=n;src.failed=0;
 text_n[2]=0;fm1_state_printer_init(&printer,print_put,&idx);fm1_state_report_init(&rep);
 assert(fm1_state_bin_read(source_read,&src,n,fm1_state_print,&printer,&rep,0));
 assert(text_n[slot]==text_n[2]&&!memcmp(text[slot],text[2],text_n[slot]));
}
int main(int argc,char **argv) {
 FILE *f;lunar_project_store s;unsigned case_id,count,cut,mode,runs=0,idx=0;
 fm1_state_printer_t printer;fm1_state_report_t rep;
 assert(argc==3);case_id=(unsigned)atoi(argv[2]);
 f=fopen(argv[1],"rb");assert(f);input_n=(uint32_t)fread(input,1,sizeof input,f);assert(!ferror(f));fclose(f);
 fm1_state_printer_init(&printer,print_put,&idx);fm1_state_report_init(&rep);
 assert(fm1_state_bin_read(input_read,NULL,input_n,fm1_state_print,&printer,&rep,0));
 idx=1;fm1_state_printer_init(&printer,print_put,&idx);fm1_state_report_init(&rep);
 assert(fm1_state_bin_read(input_read,NULL,input_n,changed_print,&printer,&rep,0));
 if(case_id>=9)assert(text_n[0]!=text_n[1]||memcmp(text[0],text[1],text_n[0]));
 memset(flash,255,sizeof flash);assert(!lunar_project_begin(&s,&io,SLOT));
 assert(!lunar_project_write(&s,0,input,input_n));assert(!lunar_project_commit(&s,input_n));
 memset(flash+SLOT,0,SLOT);
 memcpy(baseline,flash,sizeof flash);
 { fm1_state_report_t report;fm1_tft_begin(&frame,0x1234);ops=0;
   for(unsigned flag=0;flag<4;flag++) {
    int flags[4]={1,1,1,1};flags[flag]=case_id%2?0:2;
    assert(lunar_project_save(&frame,&io,SLOT,collect_project,NULL,
           flags[0],flags[1],flags[2],flags[3],&report));
    assert(!ops&&!memcmp(flash,baseline,sizeof flash)&&fm1_tft_pixels_valid(&frame));
   }
   for(collect_mode=1;collect_mode<=2;collect_mode++) {
    ops=0;assert(save());assert(!ops&&!memcmp(flash,baseline,sizeof flash));
   }
   collect_mode=0;
   { uint32_t sizes[3]={0,LP_SECTOR-1,LP_MAX+2*LP_SECTOR};
     for(unsigned i=0;i<3;i++) {
      fm1_tft_begin(&frame,0x1234);ops=0;
      assert(lunar_project_save(&frame,&io,sizes[i],collect_project,NULL,1,1,1,1,&report));
      assert(!ops&&!memcmp(flash,baseline,sizeof flash)&&fm1_tft_pixels_valid(&frame));
     }
   }
   { lunar_project_save_output out;uint8_t h[32];
     memset(&out,0,sizeof out);memset(h,0,sizeof h);out.capacity=LP_MAX;lp_put(h+20,32);
     assert(!lunar_project_save_write(&out,0,h,sizeof h));
     assert(lunar_project_save_write(&out,32,h,1));assert(out.failed);
     memset(&out,0,sizeof out);out.capacity=LP_MAX;
     assert(lunar_project_save_write(&out,0,h,31));assert(out.failed&&!out.header_seen);
   }
 }
 ops=0;assert(!save());count=ops;check_reboot();
 if(case_id>=9) {
  memcpy(flash,baseline,sizeof flash);collect_mode=3;ops=0;
  assert(save());collect_mode=0;check_reboot();
 }
 if(case_id<9) {
  /* Outer CRCs still agree, but the newest inner file magic is malformed. */
  uint8_t *h=flash+SLOT;uint32_t size=lp_word(h+12);
  h[LP_HEADER]^=1;lp_put(h+16,lp_crc(0,h+LP_HEADER,size));
  lp_put(h+24,lp_crc(0,h,24));check_reboot();
  assert(!lunar_project_begin(&s,&io,SLOT));assert(s.base==SLOT);
  assert(!memcmp(flash,baseline,SLOT));
 }
 if(case_id>=9) {
  for(mode=0;mode<3;mode++)for(cut=case_id-8;cut<=count;cut+=21) {
   memcpy(flash,baseline,sizeof flash);ops=0;fail_at=cut;torn=mode;
   assert(save());assert(ops>=cut);fail_at=0;
   check_reboot();runs++;
  }
 }
 printf("operations=%u failed-operations-tested=%u\n",count,runs);return 0;
}
