/* Actual output callback with a mock DMA ring/lease provider, not IRQ proof. */
static uint32_t acquired,retired,mockhash,backend_error,mode,wakes;
static int16_t block[256];static lunar_pipeline_result_t result;
static uint32_t tick(void){return 240000u;}
static void makeblock(uint32_t tag) {
 for(unsigned i=0;i<64;++i)for(unsigned c=0;c<2;++c) {
  int16_t x=tag?(int16_t)(((tag*17+i*113+c*9)%32000)-16000):0;
  block[4*i+c]=block[4*i+c+2]=x;uint16_t u=(uint16_t)x;
  mockhash=(mockhash^(u&255))*16777619u;mockhash=(mockhash^(u>>8))*16777619u;
 }
 memset(&result,0,sizeof result);result.tag=tag;result.case_index=(tag/CASE_BLOCKS)%4u;
 result.case_block=tag%CASE_BLOCKS;result.case_total=tag+1;result.hash=mockhash;
 if(result.case_block+1==CASE_BLOCKS)mockhash=2166136261u;
}
int lunar_pipeline_output_acquire(uint32_t tag,const int16_t **pcm,const lunar_pipeline_result_t **r) {
 if(mode==1)return 0;
 assert(tag==acquired && acquired==retired);makeblock(tag);*pcm=block;*r=&result;++acquired;
 if(mode==2)result.case_total++;
 if(mode==3)block[2]++;
 if(mode==4)result.hash++;
 return 1;
}
int lunar_pipeline_output_retire(uint32_t tag){if(mode==5)return -1;assert(tag==retired && acquired==retired+1);++retired;return 1;}
int lunar_pipeline_live_output(uint32_t tag,const int16_t *pcm,const lunar_pipeline_result_t *r){assert(pcm==block&&r==&result&&r->tag==tag);return mode!=6;}
uint32_t lunar_pipeline_error(void){return backend_error;}
unsigned lunar_pipeline_ready_outputs(void){return 8;}
void lunar_pipeline_wake_drain_done(void){++wakes;}
static int16_t ring[768];
static void reset(void){memset(&transport,0,sizeof transport);memset(ring,7,sizeof ring);transport.base=(uintptr_t)ring;transport.hash=2166136261u;transport.ready_min=8;acquired=retired=preroll_zeros=backend_error=mode=wakes=0;preroll_phase=PRE_QUIET;mockhash=2166136261u;clock_now=tick;}
int main(void) {
 for(unsigned quiet=1;quiet<=9;++quiet) {
  reset();unsigned window=0;
  for(unsigned j=0;j<quiet;++j){memset(ring,7,sizeof ring);copy_output((u8 *)(ring+256*window),512);assert(!acquired&&!retired&&!transport.next&&!transport.fault);for(unsigned k=0;k<256;++k)assert(ring[256*window+k]==0);window=(window+1)%3;}
  preroll_phase=PRE_ARM;
  while(window!=0){copy_output((u8 *)(ring+256*window),512);assert(!acquired&&!retired);window=(window+1)%3;}
  for(uint32_t tag=0;tag<TOTAL;++tag) {
   window=tag%3;copy_output((u8 *)(ring+256*window),512);
   assert(preroll_phase==PRE_MUSIC&&!transport.fault&&transport.next==tag+1);
   assert(acquired==tag+1&&retired==tag+1&&!memcmp(ring+256*window,block,512));
  }
  for(unsigned j=0;j<ZERO_DRAIN_BLOCKS;++j)copy_output((u8 *)(ring+256*(j%3)),512);
  assert(transport.drain==ZERO_DRAIN_BLOCKS && acquired==TOTAL && retired==TOTAL && wakes==1);
  transport.idle=1;backend_error=99;
  for(unsigned j=0;j<120;++j)copy_output((u8 *)(ring+256*(j%3)),512);
  assert(transport.idle_callbacks==120&&!transport.fault&&acquired==TOTAL&&retired==TOTAL);
  for(unsigned j=0;j<768;++j)assert(!ring[j]);
 }
 reset();copy_output((u8 *)ring,511);assert(transport.fault==10301&&!acquired&&!retired&&ring[0]==0x0707);
 reset();copy_output((u8 *)ring+1,512);assert(transport.fault==10301&&!acquired&&!retired&&ring[0]==0x0707);
 reset();preroll_phase=99;copy_output((u8 *)ring,512);assert(transport.fault==16101&&!acquired);
 reset();backend_error=2;copy_output((u8 *)ring,512);assert(transport.fault==10302&&!acquired);
 reset();preroll_phase=PRE_MUSIC;copy_output((u8 *)(ring+256),512);assert(transport.fault==10303&&!acquired);
 for(unsigned m=1;m<=6;++m){reset();mode=m;preroll_phase=PRE_MUSIC;copy_output((u8 *)ring,512);assert(transport.fault&&!retired&&!transport.next);for(unsigned k=0;k<256;++k)assert(!ring[k]);}
 unsigned bad=3;assert(preroll_step(&bad,0)==-1);bad=PRE_QUIET;assert(preroll_step(&bad,3)==-1&&bad==PRE_QUIET);
 puts("nine ARM offsets,198468 blocks, exact PCM/order,64-zero drain,idle and fault refusal PASS");
}
