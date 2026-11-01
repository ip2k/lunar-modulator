/* Divide's input and scheduled output share one sample-frame timeline. MIT. */
#include "fm1_mod.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern const fm1_mod_kind_t fm1_mod_kind_divide;
#define CHECK(c) do { if (!(c)) { fprintf(stderr, "line %d: %s\n", __LINE__, #c); exit(1); } } while (0)
int main(int argc, char **argv) {
  const fm1_mod_kind_t *k = &fm1_mod_kind_divide;
  const fm1_host_t host = { FM1_ENGINE_API_VERSION, 44118.0f, 64 };
  float p[10], out[2]; fm1_mod_gate_t gate[2], gout[2]; fm1_mod_io_t io;
  void *mem = calloc(1, k->instance_size(&host)); unsigned i, n = 0; unsigned rises[16];
  CHECK(argc == 2 && mem && k->create(mem, &host, 1) == mem);
  memset(&io, 0, sizeof(io)); memset(gate, 0, sizeof(gate)); memset(gout, 0, sizeof(gout));
  for (i = 0; i < 10; ++i) p[i] = k->params[i].def;
  io.p = p; io.gate = gate; io.gout = gout; io.out = out; io.tick = 1;
  p[1] = 1; p[4] = 3; p[6] = 0; /* OUT1 Div1, OUT2 silent. */
  gate[0].n = 1; gate[0].ev[0].frame = 2; gate[0].ev[0].high = 1;
  gate[1].n = 1; gate[1].ev[0].frame = 20; gate[1].ev[0].high = 1;
  if (!strcmp(argv[1], "delayed-before-reset")) p[9] = 0.25f; /* floor(11.0295) frames */
  else if (!strcmp(argv[1], "future-reset")) p[9] = 1.0f;
  else if (!strcmp(argv[1], "mult-clock")) {
    p[0] = 1; p[1] = 1; gate[1].n = 0;
    gate[0].n = 2; gate[0].ev[1].frame = 20; gate[0].ev[1].high = 1;
  } else if (!strcmp(argv[1], "same-frame-reset")) { p[1] = 2; gate[1].ev[0].frame = 2; }
  else CHECK(!strcmp(argv[1], "clock-before-reset"));
  k->process(mem, &io);
  for (i = 0; i < gout[0].n; ++i) if (gout[0].ev[i].high) rises[n++] = gout[0].ev[i].frame;
  if (!strcmp(argv[1], "mult-clock")) {
    /* Mult x1 keeps this chronology check within the port's edge budget. */
    CHECK(n == 2 && rises[0] == 2 && rises[1] == 20 && fm1_mod_gate_end(&gout[0]));
    gate[0].n = gate[1].n = 0; io.tick = 2; k->process(mem, &io);
    CHECK(gout[0].n == 1 && !gout[0].ev[0].high && gout[0].ev[0].frame == 20);
  } else if (!strcmp(argv[1], "future-reset")) {
    CHECK(n == 0); gate[0].n = gate[1].n = 0; io.tick = 2; k->process(mem, &io);
    for (i = 0; i < gout[0].n; ++i) CHECK(!gout[0].ev[i].high);
  } else { CHECK(n == 1 && rises[0] == (!strcmp(argv[1], "delayed-before-reset") ? 13u : 2u)); }
  free(mem); return 0;
}
