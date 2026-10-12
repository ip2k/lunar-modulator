/* Live arps retain a BPM clock while the sequencer is paused. MIT. */
#include "fm1_mfx_host.h"
#include "fm1_arp.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

extern const fm1_midi_fx_t fm1_midi_fx_arp;
static uint64_t seq_mem[32768 / 8], arp_mem[2048 / 8];
static fm1_mfx_t mfx;
static fm1_seq_host_t host;
static fm1_seq_ev_t events[272];
static unsigned note_count;
static uint64_t last_note, interval;

static void block(unsigned frames, uint64_t first, int collect) {
  uint32_t n, k;
  const fm1_midi_ev_t *out;
  fm1_seq_host_advance(&host, frames);
  fm1_mfx_block(&mfx, &host, frames, 1);
  out = fm1_mfx_output(&mfx, 0, &n);
  for (k = 0; collect && k < n; ++k) if (out[k].kind == FM1_MIDI_EV_NOTE_ON) {
    const uint64_t at = first + out[k].frame;
    assert(out[k].a == 72); /* live key survives STOP; clip key does not */
    if (note_count) assert(at - last_note == interval);
    last_note = at;
    ++note_count;
  }
  host.n = 0;
}

static void run_span(unsigned frames, unsigned width, uint64_t first, int collect) {
  unsigned done = 0;
  while (done < frames) {
    const unsigned n = frames - done < width ? frames - done : width;
    block(n, first + done, collect);
    done += n;
  }
}

static void scenario(unsigned fraction, unsigned bpm, unsigned width) {
  fm1_seq_limits_t lim;
  fm1_seq_clock_t before, held, resumed;
  fm1_seq_info_t info_before, info_held;
  fm1_seq_track_info_t track_before, track_held;
  char tempo[32];
  const unsigned resume_frames = (48000u * 6000u + bpm * 96u - 1u) / (bpm * 96u);
  const unsigned lead = 4000 + fraction; /* tick = 250 frames at 120 BPM */
  fm1_seq_limits_default(&lim, 8);
  host.seq = fm1_seq_create(seq_mem, &lim, 48000);
  assert(host.seq && fm1_arp_size() <= sizeof arp_mem);
  fm1_seq_host_init(&host, host.seq, events, 272);
  fm1_mfx_init(&mfx, 48000);
  assert(fm1_mfx_set(&mfx, 0, 0, &fm1_midi_fx_arp,
                    fm1_arp_create(arp_mem, 96), 1, NULL));
  {
    const char *setup = "loop 0 0 64; tog 0 0 60 100; play";
    fm1_seq_host_line(&host, setup, strlen(setup));
  }
  assert(fm1_mfx_live_note(&mfx, 0, 72, 100));
  run_span(lead, width, 0, 0);
  fm1_seq_host_line(&host, "pause", 5);
  fm1_seq_get_clock(host.seq, &before);
  fm1_seq_get_info(host.seq, &info_before);
  fm1_seq_get_track(host.seq, 0, &track_before);
  assert(!before.playing && before.accum == (uint64_t)fraction * 1152000u);
  snprintf(tempo, sizeof tempo, "bpm %u", bpm);
  fm1_seq_host_line(&host, tempo, strlen(tempo));
  interval = UINT64_C(48000) * 6000u / bpm / 4u; /* straight 1/16 */
  note_count = 0;
  run_span(48000, width, lead, 1);
  assert(note_count >= 48000 / interval - 1 && note_count <= 48000 / interval + 1);
  fm1_seq_get_clock(host.seq, &held);
  fm1_seq_get_info(host.seq, &info_held);
  fm1_seq_get_track(host.seq, 0, &track_held);
  assert(!held.inc); /* a frozen sequencer must not advertise moving ticks */
  assert(held.master_tick == before.master_tick && held.accum == before.accum);
  assert(info_held.paused && info_held.playback_frames == info_before.playback_frames);
  assert(track_held.pos_tick == track_before.pos_tick);
  fm1_seq_host_line(&host, "resume", 6);
  fm1_seq_get_clock(host.seq, &resumed);
  assert(resumed.playing && resumed.inc && resumed.accum == before.accum);
  block(resume_frames, lead + 48000, 0);
  fm1_seq_get_clock(host.seq, &resumed);
  assert(resumed.master_tick > before.master_tick);
  fm1_seq_get_info(host.seq, &info_held);
  assert(info_held.playback_frames == info_before.playback_frames + resume_frames);
}

int main(void) {
  static const unsigned fractions[] = { 25, 125, 225, 249 };
  static const unsigned tempos[] = { 12000, 9000 };
  static const unsigned widths[] = { 31, 64, 127 };
  unsigned f, t, w;
  for (f = 0; f < 4; ++f) for (t = 0; t < 2; ++t) for (w = 0; w < 3; ++w)
    scenario(fractions[f], tempos[t], widths[w]);
  puts("live arp pause clock: 24 scenarios passed");
  return 0;
}
