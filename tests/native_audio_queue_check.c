/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>
#include "audio_queue.h"

int main(int argc, char **argv)
{
    assert(argc == 2);
    unsigned shard = (unsigned)atoi(argv[1]);
    assert(shard < 16);
    struct { uint32_t before; lunar_audio_queue_t q; uint32_t after; } guarded;
    memset(&guarded, 0, sizeof guarded);
    guarded.before = 0x12345678u; guarded.after = 0x87654321u;
    lunar_audio_queue_t *q = &guarded.q;
    /* Every shard crosses the counter rollover, at differing boundaries. */
    q->written = q->read = UINT32_MAX - shard;
    float input[LUNAR_AUDIO_WORDS];
    struct { uint32_t before; int32_t data[LUNAR_AUDIO_WORDS]; uint32_t after; } out;
    int32_t reference[8][LUNAR_AUDIO_WORDS];
    unsigned head = 0, count = 0, misses = 0;
    uint32_t random = 0x31415926u ^ (shard + 1u);
    static const float edges[] = {NAN, INFINITY, -INFINITY, 1, -1, 0, -0.0f, .5f, -.5f, 2, -2};
    static const int32_t expected[] = {0, 32767, -32767, 32767, -32767, 0, 0, 16383, -16383, 32767, -32767};
    for (unsigned i = 0; i < sizeof edges / sizeof edges[0]; i++)
        assert(lunar_audio_q15(edges[i]) == expected[i]);
    for (unsigned iteration = 0; iteration < 32768; iteration++) {
        random = random * 1664525u + 1013904223u;
        /* Bursts deliberately reach both the full and empty states. */
        int push = iteration % 256 < 32 ? 1 : iteration % 256 < 64 ? 0 : (random >> 31);
        if (push) {
            for (unsigned i = 0; i < LUNAR_AUDIO_WORDS; i++) {
                int v = (int)((iteration * 131u + i * 17u + shard) % 65535u) - 32767;
                input[i] = v / 32767.0f;
            }
            uint32_t before = q->written;
            int ok = lunar_audio_push(q, input);
            assert(ok == (count < 8));
            if (ok) {
                for (unsigned i = 0; i < LUNAR_AUDIO_WORDS; i++)
                    reference[(head + count) & 7u][i] = (int32_t)(input[i] * 32767.0f);
                count++;
            } else assert(q->written == before);
        } else {
            out.before = 0xaabbccddu; out.after = 0xddccbbaau;
            memset(out.data, 0x55, sizeof out.data);
            uint32_t before = q->read;
            int ok = lunar_audio_pop(q, out.data);
            assert(ok == (count != 0));
            if (ok) {
                assert(memcmp(out.data, reference[head], sizeof out.data) == 0);
                head = (head + 1) & 7u; count--;
            } else {
                for (unsigned i = 0; i < LUNAR_AUDIO_WORDS; i++) assert(out.data[i] == 0);
                assert(q->read == before); misses++;
            }
            assert(out.before == 0xaabbccddu && out.after == 0xddccbbaau);
        }
        assert(q->written - q->read == count);
        assert(q->underruns == misses);
        assert(guarded.before == 0x12345678u && guarded.after == 0x87654321u);
    }
    return 0;
}
