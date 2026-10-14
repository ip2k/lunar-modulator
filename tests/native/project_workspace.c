/* SPDX-License-Identifier: MIT */
#include "project_workspace.h"
#include "fm1_state.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint8_t input[FM1_STATE_BIN_MAX], output[FM1_STATE_BIN_MAX];
static uint32_t input_n, output_n;
static unsigned calls, fail_at;
static uint32_t rd(void *ctx,uint32_t off,uint8_t *p,uint32_t n) {
    uint32_t len=ctx==input?input_n:output_n;
    if(off>len || n>len-off)return 0;
    memcpy(p,(uint8_t *)ctx+off,n);return n;
}
static int wr(void *ctx,uint32_t off,const void *p,uint32_t n) {
    (void)ctx; if(++calls==fail_at)return -1;
    assert(off<=sizeof output && n<=sizeof output-off);
    memcpy(output+off,p,n);return 0;
}
static int sink(void *ctx,const fm1_rec_t *r) {(void)ctx;(void)r;return 1;}
int main(int argc,char **argv) {
    assert(argc==3);unsigned mode=(unsigned)atoi(argv[2]);assert(mode<30);
    size_t offset=16u+4u*(mode%4), bytes=fm1_state_bin_writer_size();
    uint8_t *raw=malloc(sizeof(fm1_tft_t)+48), *snap=malloc(sizeof(fm1_tft_t));assert(raw&&snap);
    memset(raw,0xa5,sizeof(fm1_tft_t)+48);
    fm1_tft_t *t=(fm1_tft_t *)(void *)(raw+offset);
    fm1_tft_begin(t,0x1234);memcpy(snap,t,sizeof *t);
    lunar_project_workspace lease={NULL,NULL,0};
    assert(!lunar_project_workspace_begin(NULL,t,bytes,1,1,1));
    assert(!lunar_project_workspace_begin(&lease,NULL,bytes,1,1,1));
    assert(!lunar_project_workspace_begin(&lease,t,0,1,1,1));
    assert(!lunar_project_workspace_begin(&lease,t,SIZE_MAX,1,1,1));
    for(int i=0;i<3;i++) {
        int flags[3]={1,1,1};flags[i]=mode%2?0:2;
        assert(!lunar_project_workspace_begin(&lease,t,bytes,flags[0],flags[1],flags[2]));
        assert(!memcmp(snap,t,sizeof *t));
    }
    void *mem=lunar_project_workspace_begin(&lease,t,bytes,1,1,1);
    assert(mem && !((uintptr_t)mem&15u) && !fm1_tft_pixels_valid(t));
    assert(!lunar_project_workspace_begin(&lease,t,bytes,1,1,1));
    FILE *f=fopen(argv[1],"rb");assert(f);input_n=(uint32_t)fread(input,1,sizeof input,f);assert(!ferror(f));fclose(f);
    memset(output,255,sizeof output); fail_at=mode%3==1?1:mode%3==2?3:0;
    fm1_state_report_t rep;fm1_state_report_init(&rep);
    fm1_state_writer_t *w=fm1_state_bin_stream_writer(mem,0,NULL,wr,NULL,sizeof output,&rep);assert(w);
    int ok=fm1_state_bin_read(rd,input,input_n,fm1_state_bin_write,w,&rep,0);
    if(!fail_at) {
        assert(ok);output_n=(uint32_t)output[20]|(uint32_t)output[21]<<8|(uint32_t)output[22]<<16|(uint32_t)output[23]<<24;
        assert(fm1_state_bin_read(rd,output,output_n,sink,NULL,&rep,0));
    } else { assert(!ok && calls==fail_at);assert(output[0]==255); }
    assert(!memcmp((uint8_t *)t+sizeof t->px,snap+sizeof t->px,offsetof(fm1_tft_t,pixel_overflow)-sizeof t->px));
    size_t after=offsetof(fm1_tft_t,pixel_overflow)+sizeof t->pixel_overflow;
    assert(!memcmp((uint8_t *)t+after,snap+after,sizeof *t-after));
    for(size_t i=0;i<offset;i++)assert(raw[i]==0xa5);
    for(size_t i=offset+sizeof *t;i<sizeof *t+48;i++)assert(raw[i]==0xa5);
    assert(!lunar_project_workspace_end(&lease) && !fm1_tft_pixels_valid(t));
    assert(lunar_project_workspace_end(&lease)==-1);
    fm1_tft_begin(t,0x4567);assert(fm1_tft_pixels_valid(t));
    for(unsigned i=0;i<240u*240u;i++)assert(fm1_tft_pixel(t,i)==0x4567);
    printf("mode=%u workspace=%zu pixel_bytes=%zu calls=%u\n",mode,bytes,sizeof t->px,calls);
    free(snap);free(raw);return 0;
}
