/* Actual imported scanner with injected GPIO; no target instructions run.
 * Scanner/HAL derived portions GPL-3.0-only. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "fm1_time.h"
#include "fm1_gpio.h"
#include "fm1_cc.h"
static uint32_t gpio[8][8];
#undef FM1_PR
#define FM1_PR(p,r) gpio[p][(r)/4]
static uint32_t clock_ticks;
static uint32_t fake_ticks(void) { return clock_ticks++; }
#define fm1_ticks fake_ticks
static struct { uint32_t scan,id; int value,encoder; } events[512];
static unsigned count;
static void accepted(uint32_t scan,unsigned id,int value,int encoder) {
  assert(count<512);
  events[count].scan=scan; events[count].id=id;
  events[count].value=value; events[count++].encoder=encoder;
}
#define FM1_INPUT_ACCEPTED_KEY(scan,id,down) accepted(scan,id,down,0)
#define FM1_INPUT_ACCEPTED_ENCODER(scan,id,delta) accepted(scan,id,delta,1)
#include "fm1_input.h"
static uint8_t matrix[11];
static void frame(void) {
  for(unsigned p=0;p<11;++p) {
    assert(fm1__tick_col==p);
    uint32_t v=(uint32_t)~matrix[p];
    gpio[FM1_PA][FM1_IN/4]=(v&1u)|((v&0x1eu)<<4);
    gpio[FM1_PB][FM1_IN/4]=(v&0x20u)<<2;
    fm1_input_tick();
  }
}
static void frames(unsigned n) { while(n--) frame(); }
int main(void) {
  fm1_input_init(); frames(2);
  /* One bounce cannot become a press; accepted multi-key order is the real
   * column then row order, not ascending physical ID or aggregate bit order. */
  matrix[0]=(1u<<1)|(1u<<3); frame(); memset(matrix,0,11); frame(); assert(!count);
  matrix[0]=(1u<<1)|(1u<<3); frames(2);
  assert(count==2 && events[0].id==5 && events[1].id==23);
  memset(matrix,0,11); frames(7); assert(count==2); frame(); assert(count==4);
  assert(events[2].id==5 && events[2].value==0 && events[3].id==23);
  for(unsigned id=0;id<41;++id) {
    unsigned before=count;
    for(unsigned p=0;p<11;++p) for(unsigned r=1;r<5;++r)
      if(FM1_KEYMAP[r][p]==(int)id) matrix[p]|=(uint8_t)(1u<<r);
    frames(2); assert(count==before+1 && events[before].id==id && events[before].value==1);
    memset(matrix,0,11); frames(8);
    assert(count==before+2 && events[before+1].id==id && !events[before+1].value);
  }
  for(unsigned e=0;e<7;++e) {
    unsigned before=count;
    const uint8_t *m=FM1_ENC[e];
    static const unsigned cycle[]={1,3,2,0};
    for(unsigned k=0;k<4;++k) {
      unsigned cur=cycle[k];
      matrix[m[0]]=(uint8_t)((matrix[m[0]]&~(1u<<m[1]))|(((cur>>1)&1u)<<m[1]));
      matrix[m[2]]=(uint8_t)((matrix[m[2]]&~(1u<<m[3]))|((cur&1u)<<m[3]));
      frames(2);
    }
    assert(count==before+1 && events[before].encoder && events[before].id==e && events[before].value==1);
  }
  for(unsigned i=1;i<count;++i) assert(events[i].scan>=events[i-1].scan);
  printf("actual scanner: %u ordered accepted events, 41 keys/7 detents/bounce passed\n",count);
  return 0;
}
