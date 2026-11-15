/* Direct Compare tick probe; public kind ABI, no runtime/engine bank. MIT. */
#include "fm1_mod.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern const fm1_mod_kind_t fm1_mod_kind_compare;

int main(int argc, char **argv) {
  assert(argc == 6 || argc == 7);
  const fm1_mod_kind_t *kd = &fm1_mod_kind_compare;
  const fm1_host_t host = { FM1_ENGINE_API_VERSION, 44118.0f, 64 };
  float p[6] = { strtof(argv[5], NULL), 0, strtof(argv[3], NULL), strtof(argv[4], NULL),
                 strtof(argv[1], NULL), 0 };
  float out[7] = { 0 };
  fm1_mod_gate_t gates[7];
  fm1_mod_io_t io;
  memset(&io, 0, sizeof io);
  io.p = p; io.out = out; io.gout = gates;
  void *mem = malloc(kd->instance_size(&host));
  assert(mem);
  void *self = kd->create(mem, &host, 1);
  io.tick = 1; kd->process(self, &io);
  p[4] = strtof(argv[2], NULL);
  io.tick = 2; kd->process(self, &io);
  if (argc == 7) { io.tick = 3; kd->process(self, &io); }
  for (unsigned port = 0; port < 7; ++port) {
    printf("%u %u %.0f", port, gates[port].start, (double)out[port]);
    for (unsigned e = 0; e < gates[port].n; ++e) {
      printf(" %u:%u", gates[port].ev[e].frame, gates[port].ev[e].high);
    }
    puts("");
  }
  free(mem);
  return 0;
}
