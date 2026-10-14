#include "../../engines/src/fx_hall.cc"
extern "C" unsigned calc_hall() { fm1_host_t h = {}; h.sample_rate = 44118.0f; return fm1::hall::InstanceSize(&h); }
