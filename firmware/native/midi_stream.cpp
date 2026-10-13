/* SPDX-License-Identifier: MIT */
#include "midi_stream.h"
#include <new>
#include "MIDI.h"

namespace {
struct ReceiveByte {
    static const bool thruActivated = false;
    uint8_t byte;
    bool pending;
    void begin() { pending = false; }
    unsigned available() const { return pending ? 1u : 0u; }
    uint8_t read() { pending = false; return byte; }
    bool beginTransmission(midi::MidiType) { return false; }
    void write(uint8_t) {}
    void endTransmission() {}
};
struct Settings : midi::DefaultSettings {
    static const unsigned SysExMaxSize = 16;
    static const bool Use1ByteParsing = true;
};
using Parser = midi::MidiInterface<ReceiveByte, Settings>;
static ReceiveByte transport;
alignas(Parser) static uint8_t storage[sizeof(Parser)];
static Parser *parser;
/* Host tests have wider callback pointers; retain the 32-bit device bound. */
static_assert(sizeof(void *) != 4 || sizeof(Parser) <= 256,
              "MIDI parser exceeded its device RAM budget");
static_assert(sizeof(Parser) <= 384, "MIDI parser exceeded its host RAM budget");
}

extern "C" void lunar_midi_stream_reset(void)
{
    if (parser) parser->~Parser();
    parser = new (storage) Parser(transport);
    parser->begin(MIDI_CHANNEL_OMNI);
    parser->turnThruOff();
}

extern "C" int lunar_midi_stream_feed(uint8_t byte, uint8_t *status,
                                       uint8_t *a, uint8_t *b)
{
    if (!status || !a || !b) return 0;
    if (!parser) lunar_midi_stream_reset();
    /* A new non-realtime status supersedes an interrupted message. The
     * upstream parser can otherwise consume it as the missing data byte. */
    if (byte >= 0x80u && byte < 0xf8u) parser->begin(MIDI_CHANNEL_OMNI);
    transport.byte = byte;
    transport.pending = true;
    if (!parser->read()) return 0;
    uint8_t type = static_cast<uint8_t>(parser->getType());
    if (type < 0x80u || type >= 0xf0u) return 0;
    if (parser->getData1() > 127u || parser->getData2() > 127u) return 0;
    *status = type | (parser->getChannel() - 1u);
    *a = parser->getData1();
    *b = parser->getData2();
    return 1;
}
