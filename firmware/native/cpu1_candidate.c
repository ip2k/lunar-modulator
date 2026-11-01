/* SPDX-License-Identifier: MPL-2.0.
 * Guarded boot/hold adapted from felucca-bsp d6b8f771, chip/fm1_cpu1{,_stop}.h.
 * Copyright (C) 2026 Kerem Kilic (Ellic Studio), Charles Vestal,
 * Leo Kuroshita (@kurogedelic), Hügelton Instruments; see third_party notice.
 * Lunar additions: injectable bounded operations, cleanup state, actual adapter
 * binding, clock extension. This candidate establishes no silicon guarantees.
 */
#include "cpu1_candidate.h"
static int rd(const cpu1_ops *o,uint32_t a,uint32_t *v){return o->read(o->context,a,v);}
static int wr(const cpu1_ops *o,uint32_t a,uint32_t v){return o->write(o->context,a,v);}
static void sync(const cpu1_ops *o){o->fence(o->context);}
static int access(const cpu1_ops *o,uint32_t desired){
 uint32_t v;
 if(!rd(o,C1_ACCESS,&v))return 0;
 if((v&1u)!=(desired&1u) && !wr(o,C1_ACCESS,0xe7u))return 0;
 return rd(o,C1_ACCESS,&v) && (v&1u)==(desired&1u);
}
/* Registers/local stack only: usable before C storage initialization. */
int cpu1_candidate_early_hold_record(const cpu1_ops *o,uint32_t *prior_debug){
 uint32_t was,en,con,debug;int ok=1,have_en=0;
 if(!o || o->cpu(o->context)!=0)return 0;
 if(!rd(o,C1_DBG_MSG,&debug))return 0;
 if(prior_debug)*prior_debug=debug;
 if(!rd(o,C1_ACCESS,&was))return 0;
 if(!access(o,1)){access(o,was);return 0;}
 if(rd(o,C1_DBG_EN,&en))have_en=1;else ok=0;
 if(have_en){
  if(!wr(o,C1_DBG_EN,en&~0x003f0030u))ok=0;
  sync(o);
  if(rd(o,C1_CON,&con)){
   if(!wr(o,C1_CON,con|2u))ok=0;
   if(rd(o,C1_CON,&con)){if(!wr(o,C1_CON,con&~8u))ok=0;}else ok=0;
  }else ok=0;
  sync(o);
  for(unsigned i=0;i<256u;++i)o->pause(o->context);
  if(!wr(o,C1_DBG_CLR,0x003f0030u))ok=0;
  sync(o);
  if(!wr(o,C1_DBG_EN,en))ok=0;
 }
 if(!access(o,was))ok=0;
 sync(o);return ok;
}
int cpu1_candidate_early_hold(const cpu1_ops *o){return cpu1_candidate_early_hold_record(o,0);}
static int fail(cpu1_candidate *s){s->failed=1;sync(s->ops);return 0;}
static int cpu0(cpu1_candidate *s){return s->ops && s->ops->cpu(s->ops->context)==0;}
int cpu1_candidate_prepare(cpu1_candidate *s,const cpu1_ops *o,const cpu1_layout *l){
 if(!s || !o || !l || !o->read || !o->write || !o->cpu || !o->ticks ||
    !o->fence || !o->pause || !o->irq_get || !o->irq_set || !o->registers)return 0;
 if(o->cpu(o->context)!=0 || s->prepared || s->attempted || s->failed)return 0;
 s->ops=o;
 if(!l->nonce || l->entry<l->executable_lo || l->entry>=l->executable_hi ||
    l->exception<l->executable_lo || l->exception>=l->executable_hi ||
    l->unexpected<l->executable_lo || l->unexpected>=l->executable_hi ||
    ((l->entry|l->exception|l->unexpected)&1u) ||
    l->user_lo<0x01c08000u || l->user_hi<=l->user_lo ||
    l->super_lo<l->user_hi || l->super_hi<=l->super_lo ||
    l->super_hi>0x01c7fd50u ||
    ((l->user_lo|l->user_hi|l->super_lo|l->super_hi)&7u))return fail(s);
 s->layout=*l;
 uint32_t now=o->ticks(o->context);
 for(unsigned i=0;i<2;++i){s->clocks[i].last=now;s->clocks[i].ms=0;s->clocks[i].remainder=0;}
 s->prepared=1;sync(o);return 1;
}
/* Snapshot before mutation, and mark before writing: a reported write failure
 * may be ambiguous. Cleanup must restore every potentially changed register. */
static const uint32_t saved_addresses[8]={C1_ACCESS,C1_TOP,C1_PC_H0,C1_PC_L0,C1_PC_H1,C1_PC_L1,C1_DIV,C1_ENTRY};
static int save(cpu1_candidate *s,unsigned n){
 if(s->saved_mask&(1u<<n))return 1;
 if(!rd(s->ops,saved_addresses[n],&s->saved[n]))return 0;
 s->saved_mask|=1u<<n;return 1;
}
static int cleanup(cpu1_candidate *s){
 int ok=1;const cpu1_ops *o=s->ops;
 if(s->saved_mask&~1u){
  int unlocked=access(o,1),entry_open=0;
  if(!unlocked)ok=0;
  if(unlocked){
   /* An earlier write may have failed before launch unprotected this slot.
    * Never attempt a protected write after an unconfirmed unlock/open. */
   if((s->saved_mask&0x82u)==0x82u){uint32_t top;
    if(!wr(o,C1_TOP,s->saved[1]&~4u))ok=0;
    entry_open=rd(o,C1_TOP,&top) && !(top&4u);
    if(!entry_open)ok=0;
   }
   /* Entry slot is restored only after setup ACK or terminal hold. */
   for(unsigned n=2;n<8;++n)if(s->saved_mask&(1u<<n)){
    if(n==7 && !entry_open){ok=0;continue;}
    if(!wr(o,saved_addresses[n],s->saved[n]))ok=0;
   }
   /* Restore top protection after the entry word, never before it. */
   if((s->saved_mask&2u) && !wr(o,C1_TOP,s->saved[1]))ok=0;
  }
 }
 if((s->saved_mask&1u) && !access(o,s->saved[0]))ok=0;
 sync(o);if(!ok){s->cleanup_failed=1;fail(s);}return ok;
}
int cpu1_candidate_install_vectors(cpu1_candidate *s){
 if(!cpu0(s) || !s->prepared || s->vectors || s->attempted || s->failed)return 0;
 uint32_t gate;int ok=0;
 if(!s->ops->irq_get(s->ops->context,&gate) || (gate&0x100u))return fail(s);
 if(!save(s,0) || !save(s,1) || !access(s->ops,1))goto done;
 if(!wr(s->ops,C1_TOP,s->saved[1]&~4u))goto done;
 for(unsigned i=0;i<128u;++i)
  if(!wr(s->ops,C1_VECTORS+4u*i,i==1?s->layout.exception:s->layout.unexpected))goto done;
 for(unsigned i=0;i<32u;++i)if(!wr(s->ops,C1_IRQ0+4u*i,0))goto done;
 if(!wr(s->ops,C1_PENDING0,255u))goto done;
 /* Only exception source 1, priority 7; ordinary delivery remains disabled. */
 if(!wr(s->ops,C1_IRQ0,0xf0u))goto done;
 sync(s->ops);
 for(unsigned i=0;i<128u;++i){uint32_t v;
  if(!rd(s->ops,C1_VECTORS+4u*i,&v) || v!=(i==1?s->layout.exception:s->layout.unexpected))goto done;
 }
 ok=1;
done:
 if(!cleanup(s))ok=0;
 if(!ok)return fail(s);
 s->saved_mask=0;s->vectors=1;sync(s->ops);return 1;
}
int cpu1_candidate_hold(cpu1_candidate *s){
 if(!cpu0(s))return 0;
 s->failed=1;sync(s->ops);
 if(!s->prior_debug_valid){
  if(!rd(s->ops,C1_DBG_MSG,&s->prior_debug))s->cleanup_failed=1;
  else s->prior_debug_valid=1;
 }
 int ok=cpu1_candidate_early_hold(s->ops);
 if(ok)s->held=1;else s->cleanup_failed=1;
 sync(s->ops);return ok;
}
int cpu1_candidate_launch(cpu1_candidate *s,void (*entry)(void *),void *argument){
 if(!cpu0(s) || !s->prepared || !s->vectors || s->attempted || s->failed || !entry)return 0;
 s->attempted=1;s->entry=entry;s->argument=argument;sync(s->ops);
 uint32_t gate,con;int ok=0;const cpu1_ops *o=s->ops;
 if(!o->irq_get(o->context,&gate) || (gate&0x100u))goto done;
 for(unsigned i=0;i<8u;++i)if(!save(s,i))goto done;
 if(!access(o,1))goto done;
 for(unsigned i=0;i<32u;++i)if(!wr(o,C1_IRQ1+4u*i,0))goto done;
 if(!wr(o,C1_PENDING1,255u))goto done;
 if(!wr(o,C1_IRQ1,0xf0u))goto done;
 if(!wr(o,C1_PC_H0,UINT32_MAX) || !wr(o,C1_PC_L0,0) ||
    !wr(o,C1_PC_H1,UINT32_MAX) || !wr(o,C1_PC_L1,0) ||
    !wr(o,C1_TOP,s->saved[1]&~4u) || !wr(o,C1_ENTRY,s->layout.entry) ||
    !wr(o,C1_DIV,s->saved[6]|8u))goto done;
 sync(o);
 if(!rd(o,C1_CON,&con) || !wr(o,C1_CON,con|8u) ||
    !rd(o,C1_CON,&con) || !wr(o,C1_CON,con&~2u))goto done;
 sync(o);
 uint32_t start=o->ticks(o->context);
 for(unsigned i=0;i<CPU1_CANDIDATE_POLLS;++i){
  sync(o);
  if(s->failed || (uint32_t)(o->ticks(o->context)-start)>=CPU1_CANDIDATE_BOOT_TICKS)break;
  if(s->setup_nonce==s->layout.nonce){ok=1;break;}
  o->pause(o->context);
 }
done:
 if(!ok)cpu1_candidate_hold(s);
 if(!cleanup(s))ok=0;
 if(!ok){cpu1_candidate_hold(s);return fail(s);}
 s->launch_ok=1;sync(o);return 1;
}
int cpu1_candidate_worker_setup(cpu1_candidate *s){
 cpu1_registers r;const cpu1_ops *o=s->ops;
 if(o->cpu(o->context)!=1 || !s->attempted || s->failed || s->setup_nonce ||
    !o->registers(o->context,&r) || (r.icfg&0x100u) ||
    r.sp<s->layout.user_lo || r.sp>s->layout.user_hi ||
    r.usp<s->layout.user_lo || r.usp>s->layout.user_hi ||
    r.ssp<s->layout.super_lo || r.ssp>s->layout.super_hi)return fail(s);
 uint32_t emu;
 if(!rd(o,C1_EMU_CON,&emu) ||
    !wr(o,C1_SSP_H,s->layout.super_hi-1u) || !wr(o,C1_SSP_L,s->layout.user_lo) ||
    !wr(o,C1_USP_H,s->layout.super_hi-1u) || !wr(o,C1_USP_L,s->layout.user_lo) ||
    !wr(o,C1_EMU_CON,(emu&~((1u<<2)|(31u<<16)))|8u))return fail(s);
 sync(o);s->setup_nonce=s->layout.nonce;sync(o);return 1;
}
void cpu1_candidate_secondary(cpu1_candidate *s){
 const cpu1_ops *o=s->ops;
 if(o->cpu(o->context)!=1 || !s->attempted || s->failed || !s->entry){fail(s);return;}
 sync(o);s->entry(s->argument);
 fail(s); /* Caller must park even when the adapter returns on a late entry. */
}
uint32_t cpu1_candidate_ms(cpu1_candidate *s){
 unsigned cpu=s->ops->cpu(s->ops->context);
 if(cpu>1 || !s->prepared){fail(s);return 0;}
 cpu1_clock *c=&s->clocks[cpu];uint32_t now=s->ops->ticks(s->ops->context),delta=now-c->last;
 c->last=now;c->ms+=delta/24000u;
 uint32_t remainder=c->remainder+delta%24000u;
 c->ms+=remainder/24000u;c->remainder=remainder%24000u;
 return c->ms;
}
int cpu1_candidate_delay(cpu1_candidate *s,unsigned ms){
 if(ms>1000u)return fail(s);
 uint32_t start=s->ops->ticks(s->ops->context),span=ms*24000u;
 for(unsigned i=0;i<CPU1_CANDIDATE_POLLS;++i){
  if((uint32_t)(s->ops->ticks(s->ops->context)-start)>=span)return 1;
  s->ops->pause(s->ops->context);
 }
 return fail(s);
}
int cpu1_candidate_irq_save(cpu1_candidate *s,uint32_t *prior){
 if(!prior || !s->ops->irq_get(s->ops->context,prior) ||
    !s->ops->irq_set(s->ops->context,*prior&~0x100u))return fail(s);
 return 1;
}
int cpu1_candidate_irq_restore(cpu1_candidate *s,uint32_t prior){
 if(!s->ops->irq_set(s->ops->context,prior))return fail(s);
 return 1;
}
void cpu1_candidate_fault(cpu1_candidate *s,uint32_t vector,uint32_t reti,uint32_t rete,
                         uint32_t sp,uint32_t emu,uint32_t debug){
 unsigned cpu=s->ops->cpu(s->ops->context);if(cpu>1){fail(s);return;}
 cpu1_fault_record *f=&s->faults[cpu];cpu1_registers r={0};
 if(!f->valid){
  s->ops->registers(s->ops->context,&r);
  f->cpu=cpu;f->vector=vector;f->reti=reti;f->rete=rete;f->sp=sp;
  f->usp=r.usp;f->ssp=r.ssp;f->icfg=r.icfg;f->emu=emu;f->debug=debug;
  sync(s->ops);f->valid=1;
 }
 fail(s);
}
