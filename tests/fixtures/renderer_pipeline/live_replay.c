/* Real live adapter with synchronous host transport hooks; no IRQ/race proof. */
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#ifdef LUNAR_DEVKIT_RENDERER_PIPELINE
#include "renderer_pipeline_live.h"
static lunar_pipeline_consume_fn consume;
static lunar_pipeline_retire_fn retire;
static void *works[2];
int lunar_pipeline_bind(void *a,void *b,lunar_pipeline_consume_fn c,lunar_pipeline_retire_fn r) {
    assert(a && b && a!=b && !consume); works[0]=a;works[1]=b;consume=c;retire=r;return 1;
}
uint32_t lunar_pipeline_error(void) {return 0;}
void lunar_pipeline_fail_park(uint32_t code) {fprintf(stderr,"pipeline refusal %u\n",code);exit(72);}
static void complete(unsigned tag,FILE *f) {
    int16_t pcm[256];lunar_pipeline_result_t result;
    memset(&result,0,sizeof result);result.tag=tag;
    assert(consume(works[tag%2u],tag,pcm,&result));
    assert(retire(works[tag%2u]));
    lunar_pipeline_result_t bad=result;bad.case_total++;
    assert(!lunar_pipeline_live_output(tag,pcm,&bad));
    assert(lunar_pipeline_live_output(tag,pcm,&result));
    assert(!lunar_pipeline_live_output(tag,pcm,&result));
    assert(fwrite(pcm,sizeof *pcm,256,f)==256);
}
#endif
int main(int argc,char **argv) {
    assert(argc==3 && lunar_devkit_renderer_init());
    FILE *f=fopen(argv[1],"wb");assert(f);
#ifdef LUNAR_DEVKIT_RENDERER_PIPELINE
    assert(!lunar_pipeline_live_bind(0));assert(!lunar_pipeline_live_bind(58));
    assert(lunar_pipeline_live_bind(2));assert(!lunar_pipeline_live_bind(2));
    if(!strcmp(argv[2],"direct")){int16_t pcm[256];lunar_devkit_renderer_render(pcm);abort();}
    assert(!lunar_pipeline_live_produce(works[0],1));
    assert(!state.blocks && !state.controls);
#endif
    for(unsigned tag=0;tag<44104u;++tag) {
#ifdef LUNAR_DEVKIT_RENDERER_PIPELINE
        assert(lunar_pipeline_live_produce(works[tag%2u],tag));
        unsigned delayed=!strcmp(argv[2],"delayed");
        if(!delayed || tag)complete(tag-delayed,f);
#else
        int16_t pcm[256];lunar_devkit_renderer_render(pcm);
        assert(fwrite(pcm,sizeof *pcm,256,f)==256);
#endif
    }
#ifdef LUNAR_DEVKIT_RENDERER_PIPELINE
    if(!strcmp(argv[2],"delayed"))complete(44103u,f);
    assert(!lunar_pipeline_live_produce(works[0],44104u));
#endif
    assert(!fclose(f));
    printf("%u %u %u %u %u %u %u %u %u %u\n",state.test_case,state.cycles,
      state.blocks,state.controls,state.invalid,state.clipped,state.completed_cases,
      state.completed_case,state.completed_hash,state.arena_bytes);
    return 0;
}
