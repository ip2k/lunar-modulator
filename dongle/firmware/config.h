// USB_KEY dongle parameters. Single source of truth: dongle/sim reads this
// file, and tests/test_dongle_model.py fails if the model and firmware drift.
#pragma once

// --- pins (Raspberry Pi Pico) ---------------------------------------------
#define PIN_DP            14   // target D+ via 100 R, open-drain / input
#define PIN_DM            15   // target D- via 100 R, open-drain / input
#define PIN_PULLUP_DP     16   // top of D+'s 2.2 k pull-up: out-high = on, hi-Z = off
#define PIN_PULLUP_DM     19   // top of D-'s 2.2 k pull-up. One pin each: on a shared pin, "off"
                               // still joins D+ and D- through 4.4 k (docs/10 E3)
#define PIN_MUX_SEL       17   // relay / mux select
#define PIN_BUTTON        18   // to GND, internal pull-up
#define MUX_SEL_DONGLE    1    // level on PIN_MUX_SEL that gives the dongle the bus
#define MUX_SEL_PC        0    // relay de-energised (NC) = target straight to the PC

// --- USB_KEY -----------------------------------------------------------------
#define USB_KEY_WORD              0x16EF   // sent MSB first, data sampled on clock rising edge
#define KEY_PIO_HZ                1000000  // 1 PIO cycle = 1 us
#define KEY_BIT_CYCLES            20       // 50 kHz clock
#define KEY_BITS                  16
#define KEY_PACKET_US             (KEY_BITS * KEY_BIT_CYCLES + 6)   // 16 bits + tail instructions
#define KEY_GAP_US                160      // both lines released between packets
#define ACK_SAMPLE_US             10
#define ACK_MIN_LOW_US            100      // both lines low this long = acknowledge
#define KEY_PACKETS_PER_POLARITY  40       // alternate mode: swap roles every 40 packets
#define KEY_TIMEOUT_MS            0        // 0 = key forever (until button)
#define ACK_RELEASE_TIMEOUT_MS    20       // chip releases the lines 1-2 ms after the ACK starts

// --- SOF phase (SOF_MODE_DONGLE) ---------------------------------------------
#define SOF_PIO_HZ                1000000
#define SOF_PERIOD_CYCLES         1000     // 1.000 ms between falling edges
#define SOF_PULSE_CYCLES          4        // D+ driven low for 4 us
#define SOF_DP_HIGH_TIMEOUT_MS    500      // chip must pull D+ up within this
#define SOF_SAMPLE_US             100
#define SOF_DONE_LOW_MS           3        // D+ low this long = chip finished calibration
#define SOF_PHASE_TIMEOUT_MS      6000

// --- modes (compile-time defaults; the button can override polarity) ---------
#define POLARITY_DP_CLOCK         0        // D+ clock, D- data  (jielie usb-key.md)
#define POLARITY_DM_CLOCK         1        // D- clock, D+ data  (how-to-enter-uboot.md prose only; its diagram and czietz's tool use D+)
#define POLARITY_ALTERNATE        2
#define DEFAULT_POLARITY_MODE     POLARITY_ALTERNATE
#define SOF_MODE_PC               0        // hand the bus to the PC right after the ACK
#define SOF_MODE_DONGLE           1        // generate the 1 ms edges ourselves, then hand over
#define DEFAULT_SOF_MODE          SOF_MODE_DONGLE
