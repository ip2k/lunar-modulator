// Test-only baseline build of the limiter before equal-peak division reuse,
// settled-glide skipping, and guarded gain division. The production
// translation unit remains the source of truth for both paths.
#define FM1_LIMIT_DISABLE_EQUAL_PEAK_REUSE
#define FM1_LIMIT_DISABLE_SETTLED_GLIDE_SKIP
#define FM1_LIMIT_DISABLE_GUARDED_GAIN_DIVIDE
#define limit limit_reference
#define fm1_engine_limit fm1_engine_limit_reference
#define fm1_limit_gain fm1_limit_gain_reference
#include "../src/fx_limit.cc"
