/* SPDX-License-Identifier: MIT */
float lunar_probe_f32(float a, float b) { return (a + b) * (a - b) / b; }
double lunar_probe_f64(double a, double b) { return (a + b) * (a - b) / b; }
int lunar_probe_to_int(float a) { return (int)a; }
float lunar_probe_from_int(int a) { return (float)a; }
long long lunar_probe_div64(long long a, long long b) { return a / b; }
