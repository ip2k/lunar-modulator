/* SPDX-License-Identifier: MIT */
#include "diagnostic_spi_model.h"
#include "diagnostic_display.h"
enum { SELECT=1, CLEAR, ACK_FENCE, LOW, FENCE, LAUNCH, WAIT, DESELECT };
static const uint8_t commands[3] = {0x2a,0x2b,0x2c};
static int fail(lunar_spi_model_t *m, uint32_t reason) {
  if(m && !m->fault) m->fault=reason;
  return -1;
}
int lunar_spi_model_init(lunar_spi_model_t *m,const lunar_spi_model_ops_t *ops,
                          uint32_t ticks,uint32_t steps) {
  if(!m) return -1;
  if(m->initialized || m->fault) return fail(m,LUNAR_SPI_CONFIG);
  m->initialized=1;
  if(!ops || !ops->pins || !ops->clear_done || !ops->done ||
     !ops->barrier || !ops->launch || !ops->ticks || !ticks ||
     ticks>INT32_MAX || !steps) return fail(m,LUNAR_SPI_CONFIG);
  m->ops=*ops; m->timeout_ticks=ticks; m->max_steps=steps;
  return 0;
}
int lunar_spi_model_submit(void *ctx,uint32_t row,uint32_t ticket,
                            const uint8_t *data,size_t bytes) {
  lunar_spi_model_t *m=ctx;
  if(!m || !m->initialized || m->fault) return -1;
  if(m->stepping || m->active || !data || bytes!=LUNAR_DISPLAY_ROW_BYTES || row>=240)
    return fail(m,LUNAR_SPI_LEASE);
  m->row=data; m->ticket=ticket;
  m->params[0]=0; m->params[1]=0; m->params[2]=0; m->params[3]=239;
  m->params[4]=(uint8_t)(row>>8); m->params[5]=(uint8_t)row;
  m->params[6]=(uint8_t)(row>>8); m->params[7]=(uint8_t)row;
  m->transfer=0; m->phase=SELECT; m->steps=0;
  m->active=1; m->stepping=1;
  m->start=m->ops.ticks(m->ops.ctx); m->stepping=0;
  if(m->fault) return -1;
  return 1;
}
static int service(lunar_spi_model_t *m,uint32_t *ticket) {
  int r;
  if(!m || !m->initialized || m->fault) return -1;
  if(!ticket) return fail(m,LUNAR_SPI_CONFIG);
  if(!m->active) return 0;
  uint32_t now=m->ops.ticks(m->ops.ctx);
  if(m->fault) return -1;
  if(m->steps++>=m->max_steps || (uint32_t)(now-m->start)>=m->timeout_ticks)
    return fail(m,LUNAR_SPI_TIMEOUT);
  switch(m->phase) {
  case SELECT:
    if(m->ops.pins(m->ops.ctx,1,(int)(m->transfer&1u))) return fail(m,LUNAR_SPI_IO);
    m->phase=CLEAR; break;
  case CLEAR:
    if(m->ops.clear_done(m->ops.ctx)) return fail(m,LUNAR_SPI_IO);
    m->phase=ACK_FENCE; break;
  case ACK_FENCE:
    if(m->ops.barrier(m->ops.ctx)) return fail(m,LUNAR_SPI_IO);
    m->phase=LOW; break;
  case LOW:
    r=m->ops.done(m->ops.ctx);
    if(r<0 || r>1) return fail(m,LUNAR_SPI_IO);
    if(!r) m->phase=FENCE; /* stale DONE must clear before launch */
    break;
  case FENCE:
    if(m->ops.barrier(m->ops.ctx)) return fail(m,LUNAR_SPI_IO);
    m->phase=LAUNCH; break;
  case LAUNCH: {
    const uint8_t *p;
    size_t n;
    if(!(m->transfer&1u)) { p=commands+m->transfer/2u; n=1; }
    else if(m->transfer==5) { p=m->row; n=LUNAR_DISPLAY_ROW_BYTES; }
    else { p=m->params+(m->transfer==3?4:0); n=4; }
    if(m->ops.launch(m->ops.ctx,p,n)!=1) return fail(m,LUNAR_SPI_IO);
    m->phase=WAIT; break;
  }
  case WAIT:
    r=m->ops.done(m->ops.ctx);
    if(r<0 || r>1) return fail(m,LUNAR_SPI_IO);
    if(r) m->phase=DESELECT;
    break;
  case DESELECT:
    if(m->ops.pins(m->ops.ctx,0,(int)(m->transfer&1u))) return fail(m,LUNAR_SPI_IO);
    if(++m->transfer==6) {
      *ticket=m->ticket; m->active=0; m->row=0; return 1;
    }
    m->phase=SELECT; break;
  default: return fail(m,LUNAR_SPI_CONFIG);
  }
  return 0;
}
int lunar_spi_model_step(lunar_spi_model_t *m,uint32_t *ticket) {
  if(!m || m->fault) return -1;
  if(m->stepping) return fail(m,LUNAR_SPI_LEASE);
  m->stepping=1;
  int r=service(m,ticket);
  m->stepping=0;
  return m->fault ? -1 : r;
}
