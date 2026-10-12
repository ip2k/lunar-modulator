/* Sample-frame sequencer automation acceptance probe. MIT licence.
 * Include the app to inspect its pre-limiter bus and exercise the same
 * private render path as fm1_app_render, with deterministic test engines. */
#include <stdio.h>
#include <stdlib.h>
#include "../src/fm1_app.c"

static fm1_app_t app;
typedef struct { float value[5]; unsigned calls[5], rendered; } probe_t;
static probe_t probes[FM1_APP_UNITS];
static const char *const modes[] = { "A", "B", "C", "D" };
static const fm1_param_t params[] = {
  {"Mix", FM1_PARAM_FLOAT, 0, 1, 1, NULL, 0, 1, FM1_PARAM_MOD, 0, "Mix"},
  {"Mode", FM1_PARAM_ENUM, 0, 3, 0, modes, 0, 2, FM1_PARAM_MOD, 0, "Mode"},
  {"Time", FM1_PARAM_FLOAT, 1, 100, 1, NULL, 0, 3, FM1_PARAM_CONTINUOUS_LOG, 0, "Time"},
  {"Forbidden", FM1_PARAM_FLOAT, 0, 1, 0, NULL, 0, 4, FM1_PARAM_NOLOCK, 0, "No"},
  {"Focus", FM1_PARAM_FLOAT, 0, 1, 0, NULL, 0, 5, FM1_PARAM_PER_FOCUS, 0, "Focus"}
};
static void set(void *self, uint16_t i, float v) {
  probe_t *p = self;
  if (i < 5) { p->value[i] = v; ++p->calls[i]; }
}
static void sound(void *self, float *out, uint32_t n) {
  probe_t *p = self;
  p->rendered += n;
  for (uint32_t i = 0; i < 2*n; ++i) out[i] = 0.125f * p->value[0];
}
static void effect(void *self, float *out, uint32_t n) {
  probe_t *p = self;
  p->rendered += n;
  for (uint32_t i = 0; i < 2*n; ++i) out[i] *= p->value[0];
}
static void note(void *s, uint8_t k, uint8_t v) { (void)s; (void)k; (void)v; }
static void off(void *s, uint8_t k) { (void)s; (void)k; }
static const fm1_engine_t snd = {
 .magic=FM1_ENGINE_MAGIC, .api_version=FM1_ENGINE_API_VERSION,
 .kind=FM1_KIND_SOUND, .id="automation-sound", .name="Probe", .params=params, .n_params=5,
 .note_on=note, .note_off=off, .set_param=set, .render=sound
};
static const fm1_engine_t fx = {
 .magic=FM1_ENGINE_MAGIC, .api_version=FM1_ENGINE_API_VERSION,
 .kind=FM1_KIND_AUDIO_FX, .id="automation-effect", .name="Probe", .params=params, .n_params=5,
 .set_param=set, .render=effect
};
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x); return 1; } } while (0)
#define NEAR(a,b) (fabsf((a)-(b)) < 0.00002f)
static void setup(void) {
  if (app.mod) mod_release(&app);
  fm1_app_init(&app, 384.0f);  /* 48 frames/sixteenth; first step1 lock at47 */
  mod_release(&app);           /* test FX/mix locks with no modulation runtime */
  memset(probes, 0, sizeof probes);
  for (int u=0; u<FM1_APP_UNITS; ++u) {
    app.unit[u].e = unit_sound(u) >= 0 ? &snd : &fx;
    app.unit[u].self = &probes[u];
    app.unit[u].driven = 0;
    for (unsigned i=0; i<5; ++i) app.unit[u].value[i] = probes[u].value[i] = params[i].def;
  }
  fm1_app_export_sound_mask(&app, 1);
  app.seq_host.n = 0;
}
static int line(const char *text) {
  return fm1_app_seq_line(&app, text, strlen(text)) == strlen(text);
}
static void lock(unsigned frame, unsigned track, unsigned lane, unsigned value) {
  fm1_seq_ev_t *e = &app.seq_ev[app.seq_host.n++];
  memset(e, 0, sizeof *e);
  e->kind=FM1_SEQ_EV_LOCK; e->frame=frame; e->track=track; e->a=lane; e->b=value;
}
static void render(unsigned n) {
  app.mod_nwr=0; app.seq_nmix=0;
  render_sounds(&app,n,app.out);
  render_fx(&app,1,app.out,n); render_fx(&app,2,app.out,n);
}
static int timing(void) {
  setup();
  CHECK(line("route 0 1 0;alabel 0 0 in1:Mix;abaseq 0 0 127;alabel 0 1 in2:Mix;abaseq 0 1 127;alabel 0 2 m1:Mix;abaseq 0 2 127;alabel 0 3 m2:Mix;abaseq 0 3 127;alabel 0 4 mix:Level;abaseq 0 4 127"));
  lock(8,0,0,64); lock(16,0,1,64); lock(24,0,2,64); lock(32,0,3,64); lock(40,0,4,64);
  render(64);
  for(unsigned i=0;i<64;++i) {
    float want=.125f;
    for(unsigned j=0;j<5;++j) if(i >= 8*(j+1)) want *= 64.0f/127.0f;
    CHECK(NEAR(app.out[2*i],want)); CHECK(NEAR(app.out[2*i+1],want));
  }
  CHECK(probes[0].calls[0]==0); /* FX Mix must never alias synth Mix. */
  CHECK(app.level[0]==100 && app.unit[6].value[0]==1 && app.unit[1].value[0]==1);
  render(64); CHECK(NEAR(app.out[0],.125f*powf(64.0f/127.0f,5)));
  CHECK(app.seq_auto_dropped==0 && app.seq_auto_writes==5);
  return 0;
}
static int stop_reset(void) {
  setup();
  CHECK(line("route 0 1 0;clen 0 16;alabel 0 0 in1:Mix;abaseq 0 0 127;aset 0 0 1 0 1;alabel 0 1 mix:Level;abaseq 0 1 127;aset 0 1 1 0 1;play"));
  render(64);
  CHECK(app.out[2*46]==.125f && app.out[2*47]==0);
  CHECK(app.seq_target[0][0].active && app.seq_target[0][1].active);
  CHECK(line("stop")); render(64);
  CHECK(NEAR(app.out[0],.125f) && probes[6].value[0]==1 && app.seq_level[0]==100);
  CHECK(!app.seq_target[0][0].active && !app.seq_target[0][1].active);
  CHECK(line("play")); render(64); CHECK(app.out[2*47]==0);
  CHECK(fm1_app_seq_reset(&app,8)==0);
  CHECK(probes[6].value[0]==1 && app.seq_level[0]==100);
  render(64); CHECK(app.out[0]==.125f);
  /* An effect or level knob edit changes the D6 base under a live lock. */
  CHECK(line("route 0 1 0;clen 0 16;alabel 0 0 in1:Mix;abaseq 0 0 127;aset 0 0 1 0 1;alabel 0 1 mix:Level;abaseq 0 1 127;aset 0 1 1 0 1;play"));
  render(64);
  fm1_app_set_param(&app,6,0,64.0f/127.0f);
  fm1_app_unit_set_level(&app,0,100.0f*32.0f/127.0f);
  CHECK(line("stop")); render(64);
  CHECK(NEAR(app.out[0],.125f*64.0f*32.0f/(127.0f*127.0f)));
  CHECK(fm1_app_seq_reset(&app,8)==0);
  CHECK(NEAR(probes[6].value[0],64.0f/127.0f));
  return 0;
}
static int routes_types_mask(void) {
  setup();
  CHECK(line("route 0 1 2;alabel 0 0 in1:Mix;abaseq 0 0 127;alabel 0 1 m1:Mode;alabel 0 2 m2:Time;alabel 0 3 in2:Forbidden;alabel 0 4 in2:Focus;alabel 0 5 mix:Level"));
  lock(0,0,0,0); lock(0,0,1,85); lock(0,0,2,64); lock(0,0,3,127); lock(0,0,4,127); lock(0,0,5,0);
  render(64);
  CHECK(probes[10].value[0]==0 && probes[6].value[0]==1);
  CHECK(probes[1].value[1]==2);
  CHECK(fabsf(probes[2].value[2]-powf(100.0f,64.0f/127.0f))<.001f);
  CHECK(probes[11].calls[3]==0 && probes[11].calls[4]==0 && app.seq_auto_refused==2);
  CHECK(app.out[0]==.125f); /* masked sound2 still renders/automates, contributes zero */
  CHECK(probes[4].rendered==64 && probes[10].rendered==64 && app.level[2]==100);
  CHECK(line("route 0 1 0")); render(64); CHECK(probes[10].value[0]==1);
  CHECK(app.seq_level[2]==0); /* mix base was explicitly zero */
  CHECK(line("route 0 0 9;alabel 0 0 in1:Mix;alabel 0 1 m1:Mix"));
  lock(0,0,0,0); lock(0,0,1,64); render(64);
  CHECK(probes[6].value[0]==1 && NEAR(probes[1].value[0],64.0f/127.0f));
  CHECK(app.seq_auto_refused==3); /* inserts refuse MIDI route; master stays global */
  CHECK(fm1_seq_lane_param(&snd,"in1:Mix")==-1 && fm1_seq_lane_param(&snd,"synth:Mix")==0);
  CHECK(fm1_seq_lane_target("mix:Other",NULL)==-1 && fm1_seq_lane_target("m1:x:Mix",NULL)==-1);
  fm1_app_export_sound_mask(&app,0); render(64); CHECK(app.out[0]==0);
  fm1_app_export_sound_mask(&app,31); CHECK(app.export_sound_mask==15);
  return 0;
}
static int release_and_legacy(void) {
  setup();
  CHECK(!app.mod && app.export_sound_mask==1);
  CHECK(line("route 0 1 0;clen 0 16;alabel 0 0 in1:Mix;abaseq 0 0 127;aset 0 0 1 0 1;alabel 0 1 mix:Level;abaseq 0 1 127;aset 0 1 1 0 1;play"));
  render(64); CHECK(app.out[2*47]==0);
  CHECK(line("aclr 0 0;aclr 0 1")); render(64);
  CHECK(app.out[0]==.125f && probes[6].value[0]==1 && app.seq_level[0]==100);
  CHECK(!app.seq_target[0][0].active && !app.seq_target[0][1].active);
  CHECK(line("stop;alabel 0 0 synth:Mix;alabel 0 1 synth:Focus"));
  lock(0,0,0,32); lock(0,0,1,127); render(64);
  CHECK(NEAR(probes[0].value[0],32.0f/127.0f) && probes[0].value[4]==1);
  CHECK(probes[6].value[0]==1); /* reserved labels did not change legacy focus support */
  return 0;
}
static int modulation(void) {
  char err[256];
  setup(); fm1_app_mod_reset(&app,7);
  CHECK(app.mod && fm1_app_mod_line(&app,"rack default",err,sizeof err));
  CHECK(fm1_app_mod_line(&app,"set 1 shape=square width=1 rate=0",err,sizeof err));
  CHECK(fm1_app_mod_line(&app,"slot 1 lfo1 > snd.fx1:Mix amt=25 pol=uni",err,sizeof err));
  CHECK(line("route 0 1 0;clen 0 16;alabel 0 0 in1:Mix;abaseq 0 0 64;aset 0 0 1 32 1;play"));
  render(64);
  const unsigned code=(unsigned)fm1_app_mod_unit(6);
  CHECK(NEAR(fm1_mod_base(app.mod,code,0),32.0f/127.0f));
  CHECK(probes[6].value[0] > 32.0f/127.0f); /* modulation adds to the lock base */
  CHECK(app.out[2*47] > .125f*32.0f/127.0f);
  CHECK(line("stop")); render(64);
  CHECK(NEAR(fm1_mod_base(app.mod,code,0),64.0f/127.0f));
  CHECK(probes[6].value[0] > 64.0f/127.0f);
  CHECK(fm1_app_seq_reset(&app,8)==0);
  CHECK(fm1_mod_base(app.mod,code,0)==1); /* reset returns to configured knob */
  CHECK(app.seq_auto_dropped==0);
  return 0;
}
static int panel_targets(void) {
  setup();
  CHECK(line("route 0 1 0;clen 0 16;alabel 0 0 in1:Mix;abaseq 0 0 64;aset 0 0 4 32 1"));
  app.mode = FM1_MODE_SEQ;
  app.ui.view = FM1_SEQ_VIEW_STEP;
  app.ui.held_n = 1; app.ui.held[0].step = 4;
  app.ui.step_page = FM1_SEQ_UI_STEP_PAGES + 1; /* probe has one page per engine */
  fm1_app_encoder(&app, FM1_ENC_KNOB1, 1);
  fm1_seq_step_info_t step;
  CHECK(fm1_seq_get_page(app.seq,0,0,4,1,&step));
  CHECK(step.lock[0] == 33 && step.lock_mask == 1);
  CHECK(!strcmp(fm1_seq_lane_label(app.seq,0,0),"in1:Mix"));
  app.ui.shift = 1;
  fm1_app_encoder(&app, FM1_ENC_KNOB1, 1);
  CHECK(fm1_seq_get_page(app.seq,0,0,4,1,&step) && !step.lock_mask);
  app.ui.shift = 0; app.ui.clear_held = 1;
  fm1_app_encoder(&app, FM1_ENC_KNOB1, 1);
  CHECK(!fm1_seq_lane_label(app.seq,0,0)[0]);
  app.ui.clear_held = 0;
  /* Refused effect controls assign nothing; synth PER_FOCUS remains valid. */
  fm1_seq_ui_sound_t context;
  lock_target_context(&app,FM1_SEQ_TARGET_INSERT1,&context);
  CHECK(!fm1_seq_ui_target_lockable(&context,3) && !fm1_seq_ui_target_lockable(&context,4));
  lock_target_context(&app,FM1_SEQ_TARGET_SOUND,&context);
  CHECK(fm1_seq_ui_target_lockable(&context,4));
  fm1_app_encoder(&app,FM1_ENC_KNOB4,1);
  CHECK(!fm1_seq_lane_label(app.seq,0,0)[0]);
  /* Each target independently assigns the correct prefix through app encoders. */
  static const char *const labels[] = {"synth:Mix","in1:Mix","in2:Mix","m1:Mix","m2:Mix","mix:Level"};
  for (unsigned k=0;k<6;++k) {
    app.ui.step_page = FM1_SEQ_UI_STEP_PAGES + k;
    fm1_app_encoder(&app,FM1_ENC_KNOB1,-1);
    CHECK(!strcmp(fm1_seq_lane_label(app.seq,0,k),labels[k]));
    CHECK(fm1_seq_get_page(app.seq,0,0,4,1,&step) && step.lock[k] == 126);
  }
  CHECK(app.ui.lock_pages == 6);
  CHECK(probes[0].calls[0] == 0); /* quiet held FX edits never touch synth */
  /* Several held steps retain the base-knob gesture on each target. */
  app.ui.held_n=2; app.ui.held[1].step=6;
  app.ui.step_page=FM1_SEQ_UI_STEP_PAGES+1;
  fm1_app_encoder(&app,FM1_ENC_KNOB1,-2);
  CHECK(app.unit[6].value[0] < 1 && app.unit[0].value[0] == 1);
  app.ui.step_page=FM1_SEQ_UI_STEP_PAGES+5;
  fm1_app_encoder(&app,FM1_ENC_KNOB1,-5);
  CHECK(app.level[0] == 95);
  fm1_seq_track_info_t track;
  CHECK(fm1_seq_get_track(app.seq,0,&track) && track.base[5] == fm1_seq_value7(&mix_lock_param,95));
  app.ui.held_n=1;
  /* Masters remain assignable on MIDI tracks; relative targets disappear. */
  CHECK(line("route 1 0 2;clen 1 16")); app.ui.track = 1;
  app.ui.step_page = FM1_SEQ_UI_STEP_PAGES;
  fm1_app_encoder(&app,FM1_ENC_KNOB1,-1);
  CHECK(!strcmp(fm1_seq_lane_label(app.seq,1,0),"m1:Mix") && app.ui.lock_pages == 2);
  /* Actual visible FX and Mix knobs record into the focused route. */
  app.ui.track=0; app.ui.held_n=0; app.ui.view=FM1_SEQ_VIEW_TRACK;
  app.ui.playing=app.ui.recording=app.ui.clip_playing=1; app.ui.rec_track=0; app.ui.step=5;
  app.ui.take_param=-1; app.mode=FM1_MODE_FX; app.fx_slot=FX_IN1; app.fx_page=0;
  app.unit[6].value[0]=1; app.level[0]=100;
  fm1_app_encoder(&app,FM1_ENC_KNOB1,-2);
  CHECK(fm1_seq_get_page(app.seq,0,0,5,1,&step) && step.lock[1] == 125);
  app.fx_slot=FX_MIX;
  fm1_app_encoder(&app,FM1_ENC_KNOB1,-3);
  CHECK(fm1_seq_get_page(app.seq,0,0,5,1,&step) && step.lock[5] == 124);
  CHECK(app.level[0] == 100); /* live lock leaves configured level intact */
  const unsigned oldmask = step.lock_mask;
  fm1_app_encoder(&app,FM1_ENC_KNOB2,-4); /* unrelated sound: ordinary mixer knob */
  CHECK(app.level[1] == 96);
  CHECK(fm1_seq_get_page(app.seq,0,0,5,1,&step) && step.lock_mask == oldmask);
  app.fx_slot=FX_IN1; app.ui.take_param=0; app.ui.take_lane=1;
  app.unit[6].e=NULL; /* a live take survives the effect's removal */
  CHECK(fx_take_value(&app,6,0,.75f) == .75f);
  return 0;
}
int main(void) {
  if(timing() || stop_reset() || routes_types_mask() || release_and_legacy() || modulation() || panel_targets()) return 1;
  puts("PASS sample frames, isolation, inserts/master/mix, D6, knob bases, reset, routes, enum/log, NOLOCK/PER_FOCUS, masks and modulation precedence");
  return 0;
}
