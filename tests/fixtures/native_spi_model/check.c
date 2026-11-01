/* Host-only injected protocol/lease proof. MIT. */
#include "diagnostic_spi_model.h"
#include "diagnostic_display.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {
  uint32_t now, actions, launches, selected, data, live, done, delay;
  int mode;
  unsigned fail_at;
  lunar_spi_model_t *model;
  const uint8_t *borrowed;
  uint8_t snapshot[480];
  size_t bytes;
} mock_t;
static int action(mock_t *s) { return ++s->actions==s->fail_at; }
static int pins(void *ctx,int selected,int data) {
  mock_t *s=ctx; if(action(s)) return -1;
  if(s->mode==1) return -1;
  if(s->mode==11) { uint32_t ticket; assert(lunar_spi_model_step(s->model,&ticket)<0); }
  if(!selected) assert(s->done && s->live);
  s->selected=(unsigned)selected; s->data=(unsigned)data;
  if(!selected) { s->live=0; s->borrowed=0; }
  return 0;
}
static int clear(void *ctx) {
  mock_t *s=ctx; if(action(s)) return -1;
  if(s->mode==2) return -1;
  if(s->mode!=3) s->done=0;
  return 0;
}
static int done(void *ctx) {
  mock_t *s=ctx; if(action(s)) return -1;
  if(s->mode==4) return -1;
  if(s->borrowed) assert(!memcmp(s->borrowed,s->snapshot,s->bytes));
  if(s->live && s->mode!=5 && s->delay--==0) s->done=1;
  return (int)s->done;
}
static int fence(void *ctx) { mock_t *s=ctx; if(action(s)) return -1; return s->mode==6?-1:0; }
static int launch(void *ctx,const uint8_t *p,size_t n) {
  mock_t *s=ctx; if(action(s)) return -1;
  assert(s->selected && !s->done && !s->live);
  if(s->mode==7) return 0;
  unsigned part=s->launches++%6;
  assert(s->data==(part&1u));
  if(!(part&1u)) { static const uint8_t c[]={0x2a,0x2b,0x2c}; assert(n==1 && *p==c[part/2]); }
  else if(part==1) assert(n==4 && !memcmp(p,"\0\0\0\357",4));
  else if(part==3) { unsigned y=(s->launches-1)/6; assert(n==4 && p[0]==0 && p[1]==y && p[2]==0 && p[3]==y); }
  else assert(n==480);
  s->borrowed=p; s->bytes=n; memcpy(s->snapshot,p,n); s->live=1; s->delay=2;
  if(s->mode==8) s->done=1; /* completion before first post-launch read */
  return 1;
}
static uint32_t ticks(void *ctx) { return ((mock_t *)ctx)->now; }
static uint16_t pixels[240*240];
static unsigned draws;
static const uint16_t *draw(void *ctx,uint32_t frames) { (void)ctx; assert(frames==1470); ++draws; return pixels; }
static void run(int mode) {
  lunar_spi_model_t m={0}; lunar_diagnostic_display_t d={0};
  mock_t s={0}; s.mode=mode; s.model=&m; s.done=1; s.now=UINT32_MAX-10;
  lunar_spi_model_ops_t ops={pins,clear,done,fence,launch,ticks,&s};
  assert(!lunar_spi_model_init(&m,&ops,1000,100));
  assert(!lunar_display_init(&d,LUNAR_DISPLAY_HOST_MOCK,lunar_spi_model_submit,&m));
  d.ticket=UINT32_MAX; draws=0;
  assert(lunar_display_frame(&d,draw,0,1470)==1 && draws==1);
  assert(lunar_display_pump(&d)==1 && d.ticket==0);
  uint8_t row[480]; memcpy(row,d.row,sizeof row);
  if(mode==9) { /* submit while borrowed must not overwrite parameters */
    uint8_t params[8]; memcpy(params,m.params,8);
    assert(lunar_spi_model_submit(&m,99,9,row,480)<0);
    assert(!memcmp(params,m.params,8) && m.active); return;
  }
  if(mode==10) s.now+=1000; /* wrap-safe deadline */
  for(unsigned y=0;y<240;++y) {
    unsigned steps=0;
    int r=0;
    uint32_t ticket=999;
    do {
      unsigned before=s.actions;
      r=lunar_spi_model_step(&m,&ticket);
      assert(s.actions-before<=1); ++steps; assert(steps<105);
      assert(lunar_display_frame(&d,draw,0,1470)==0 && draws==1);
      assert(!memcmp(row,d.row,480));
    } while(!r);
    if(mode && mode!=8) {
      assert(r<0 && m.fault && m.active && d.pending && d.active);
      unsigned actions=s.actions;
      s.mode=8; s.done=1;
      for(unsigned i=0;i<5;++i) assert(lunar_spi_model_step(&m,&ticket)<0);
      assert(s.actions==actions && !memcmp(row,d.row,480));
      assert(lunar_spi_model_init(&m,&ops,1000,100)<0);
      return;
    }
    assert(r==1 && ticket==d.ticket);
    assert(lunar_display_complete(&d,ticket,1)==1);
    if(y<239) { assert(lunar_display_pump(&d)==1); memcpy(row,d.row,480); }
  }
  assert(!d.active && !d.pending && !m.active && !m.row && s.launches==1440);
}
int main(void) {
  for(unsigned i=0;i<240*240;++i) pixels[i]=(uint16_t)i;
  for(int mode=0;mode<=11;++mode) run(mode);
  /* Every operation of all six first-row transfers: no post-fault operation,
   * no lease release, including errors only in WAIT or final deselect. */
  for(unsigned at=1;at<=60;++at) {
    lunar_spi_model_t m={0}; mock_t s={0}; uint8_t row[480]={0}; uint32_t ticket;
    lunar_spi_model_ops_t ops={pins,clear,done,fence,launch,ticks,&s};
    s.fail_at=at;
    assert(!lunar_spi_model_init(&m,&ops,1000,100));
    assert(lunar_spi_model_submit(&m,0,0,row,480)==1);
    int r; unsigned steps=0;
    do { r=lunar_spi_model_step(&m,&ticket); assert(++steps<105); } while(!r);
    assert(r<0 && m.fault && m.active && m.row==row);
    unsigned actions=s.actions; s.fail_at=0; s.done=1;
    assert(lunar_spi_model_step(&m,&ticket)<0 && actions==s.actions);
  }
  /* Wrong and duplicate completions cannot release a display/frame lease. */
  lunar_diagnostic_display_t d={0}; lunar_spi_model_t m={0}; mock_t s={0};
  lunar_spi_model_ops_t ops={pins,clear,done,fence,launch,ticks,&s};
  assert(!lunar_spi_model_init(&m,&ops,1000,100));
  assert(!lunar_display_init(&d,LUNAR_DISPLAY_HOST_MOCK,lunar_spi_model_submit,&m));
  assert(lunar_display_frame(&d,draw,0,1470)==1 && lunar_display_pump(&d)==1);
  assert(lunar_display_complete(&d,d.ticket+1,1)<0 && d.pending && d.active);
  assert(lunar_display_complete(&d,d.ticket,1)<0 && d.pending && d.active);
  puts("SPI model: 12 cases + 60 operation faults + wrong/late ticket; 240 rows; immediate/delayed/fault/frozen clock/lease/wrap passed");
  return 0;
}
