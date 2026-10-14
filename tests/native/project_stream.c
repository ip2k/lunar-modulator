/* SPDX-License-Identifier: MIT */
#include "fm1_state.h"
#include "project_store.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#define SLOT 102400u
static uint8_t flash[2*SLOT],baseline[2*SLOT],input[FM1_STATE_BIN_MAX];
static char text[3][524288];
static size_t text_n[3];
static uint32_t input_n;
static unsigned ops,fail_at,torn;
typedef struct { uint32_t off,n; } source;
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
 return read_flash(NULL,s->off+off,p,n)?0:n;
}
static uint32_t input_read(void *ctx,uint32_t off,uint8_t *p,uint32_t n) {
 (void)ctx;if(off>input_n||n>input_n-off)return 0;
 memcpy(p,input+off,n);return n;
}
static int discard(void *ctx,const fm1_rec_t *r){(void)ctx;(void)r;return 1;}
static int validate(void *ctx,uint32_t off,uint32_t n) {
 source src={off,n};fm1_state_report_t rep;(void)ctx;fm1_state_report_init(&rep);
 return fm1_state_bin_read(source_read,&src,n,discard,NULL,&rep,0)?0:-1;
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
static int changed_write(void *ctx,const fm1_rec_t *r) {
 fm1_rec_t next=changed(r);return fm1_state_bin_write(ctx,&next);
}
static int changed_print(void *ctx,const fm1_rec_t *r) {
 fm1_rec_t next=changed(r);return fm1_state_print(ctx,&next);
}
static lunar_project_io io={NULL,read_flash,erase_flash,program_flash,validate};
static int save(lunar_project_store *s,void *mem) {
 fm1_state_report_t rep;fm1_state_writer_t *w;uint32_t n;
 if(lunar_project_begin(s,&io,SLOT))return -1;
 fm1_state_report_init(&rep);
 w=fm1_state_bin_stream_writer(mem,0,NULL,lunar_project_write,s,LP_MAX,&rep);assert(w);
 if(!fm1_state_bin_read(input_read,NULL,input_n,changed_write,w,&rep,0))return -1;
 n=lp_word(flash+s->base+LP_HEADER+20);
 return lunar_project_commit(s,n);
}
static void check_reboot(void) {
 lunar_project_store s;int slot;uint32_t gen,n;source src;fm1_state_report_t rep;
 fm1_state_printer_t printer;unsigned idx=2;
 memset(&s,0,sizeof s);s.io=io;s.slot_bytes=SLOT;
 assert(!lunar_project_scan(&s,&slot,&gen,&n));assert(slot==0||slot==1);
 assert(!memcmp(flash,baseline,SLOT));src.off=(uint32_t)slot*SLOT+LP_HEADER;src.n=n;
 text_n[2]=0;fm1_state_printer_init(&printer,print_put,&idx);fm1_state_report_init(&rep);
 assert(fm1_state_bin_read(source_read,&src,n,fm1_state_print,&printer,&rep,0));
 assert(text_n[slot]==text_n[2]&&!memcmp(text[slot],text[2],text_n[slot]));
}
int main(int argc,char **argv) {
 FILE *f;void *mem;lunar_project_store s;unsigned case_id,count,cut,mode,runs=0,idx=0;
 fm1_state_printer_t printer;fm1_state_report_t rep;
 assert(argc==3);case_id=(unsigned)atoi(argv[2]);
 f=fopen(argv[1],"rb");assert(f);input_n=(uint32_t)fread(input,1,sizeof input,f);assert(!ferror(f));fclose(f);
 mem=malloc(fm1_state_bin_writer_size());assert(mem);
 fm1_state_printer_init(&printer,print_put,&idx);fm1_state_report_init(&rep);
 assert(fm1_state_bin_read(input_read,NULL,input_n,fm1_state_print,&printer,&rep,0));
 idx=1;fm1_state_printer_init(&printer,print_put,&idx);fm1_state_report_init(&rep);
 assert(fm1_state_bin_read(input_read,NULL,input_n,changed_print,&printer,&rep,0));
 if(case_id>=9)assert(text_n[0]!=text_n[1]||memcmp(text[0],text[1],text_n[0]));
 memset(flash,255,sizeof flash);assert(!lunar_project_begin(&s,&io,SLOT));
 assert(!lunar_project_write(&s,0,input,input_n));assert(!lunar_project_commit(&s,input_n));
 memset(flash+SLOT,0,SLOT);
 memcpy(baseline,flash,sizeof flash);ops=0;assert(!save(&s,mem));count=ops;check_reboot();
 if(case_id>=9) {
  for(mode=0;mode<3;mode++)for(cut=case_id-8;cut<=count;cut+=21) {
   memcpy(flash,baseline,sizeof flash);ops=0;fail_at=cut;torn=mode;
   assert(save(&s,mem));assert(ops>=cut);fail_at=0;
   /* End the failed transaction; no further programs are permitted. */
   idx=ops;assert(lunar_project_write(&s,0,input,1));assert(ops==idx);
   check_reboot();runs++;
  }
 }
 printf("operations=%u failed-operations-tested=%u\n",count,runs);free(mem);return 0;
}
