/* Included after the real renderer_live.c fixture: use its configured app. */
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#ifdef FM1_APP_RENDER_PIPELINE
#include "fm1_app_pipeline.h"
uint32_t fm1_app_pipeline_error(void) { return 0; }
void fm1_app_pipeline_fail(uint32_t code) {
    fprintf(stderr,"pipeline refusal %u\n",code); exit(72);
}
#endif
int main(int argc, char **argv) {
    const unsigned total=8u*5513u;
    assert(argc==3 && lunar_devkit_renderer_init());
    FILE *file=fopen(argv[1],"wb");assert(file);
    assert(mod("slot 5 lfo1 > fx1:Mix amt=10"));
    assert(mod("slot 6 env3 > host:amp amt=-10"));
    assert(line("metro 1"));
    for(unsigned block=0;block<total;++block) {
        unsigned c=(block/5513u)%4u,b=block%5513u;
        if(block%37u==0)fm1_app_master(&app,(block&1)?0.65f:0.95f,0);
        if(block%187u==0)assert(line((block&1)?"metro 0":"metro 1"));
        if(!b)for(unsigned n=0;n<voices[c];++n)fm1_app_unit_note_on(&app,0,48+(int)n,90);
        if(b==6u*44100u/64u)for(unsigned n=0;n<voices[c];++n)fm1_app_unit_note_off(&app,0,48+(int)n);
        if(!(b%64u)) {
            fm1_app_unit_set_level(&app,1,(b&64u)?45.f:55.f);
            fm1_app_set_param(&app,fm1_app_insert_unit(0,0),1,(b&64u)?1200.f:2400.f);
        }
#ifdef FM1_APP_RENDER_PIPELINE
        void *slot=fm1_app_pipeline_work(block%2u);
        if(!block && !strcmp(argv[2],"alias"))app.unit[1].self=app.unit[2].self;
        assert(fm1_app_pipeline_produce(&app,slot));
        if(!block) {
            if(!strcmp(argv[2],"duplicate"))fm1_app_pipeline_produce(&app,slot);
            if(!strcmp(argv[2],"retire_early"))fm1_app_pipeline_retire(slot);
            if(!strcmp(argv[2],"reinit"))fm1_app_init(&app,44100.f);
            if(!strcmp(argv[2],"draw"))fm1_app_draw(&app,0);
            if(!strcmp(argv[2],"draw_checked"))fm1_app_draw_checked(&app);
            if(!strcmp(argv[2],"worker_edit"))fm1_app_set_param(&app,fm1_app_sound_unit(1),0,1.f);
        }
        int delayed=strcmp(argv[2],"immediate")!=0;
        if(!delayed || block) {
            void *done=fm1_app_pipeline_work((block-(unsigned)delayed)%2u);
            const float *pcm=fm1_app_pipeline_consume(done);assert(pcm);
            assert(fwrite(pcm,sizeof(float),128,file)==128);
            assert(fm1_app_pipeline_retire(done));
        }
#else
        const float *pcm=fm1_app_render(&app,64);
        assert(fwrite(pcm,sizeof(float),128,file)==128);
#endif
    }
#ifdef FM1_APP_RENDER_PIPELINE
    if(strcmp(argv[2],"immediate")) {
        void *last=fm1_app_pipeline_work((total-1u)%2u);
        const float *pcm=fm1_app_pipeline_consume(last);assert(pcm);
        assert(fwrite(pcm,sizeof(float),128,file)==128);
        assert(fm1_app_pipeline_retire(last));
    }
#endif
    assert(!fclose(file));
    puts("44104 blocks / 22581248 float PCM bytes complete");
    return 0;
}
