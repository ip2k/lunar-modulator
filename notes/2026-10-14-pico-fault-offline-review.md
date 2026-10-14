# Pico 2 W USB_KEY FAULT: offline source review

## Finding

[verified: source]  is not an ACK/ROM/SOF diagnosis. In ,  sets the mux to  during startup (around line 220), initializes GP14/GP15 as input with internal pulls disabled, then  (around lines 158–165) calls , enables the two external pull-up drivers and samples both line inputs. It returns false unless both read high; the caller selects  directly and never enters . The simulator regression  confirms a low on the dongle-side D+ node produces  with zero packets.

[verified: source] The relevant assignment is in : GP14 is the D+ sense/open-drain line, GP15 D−, GP16 the D+ pull-up control, GP19 the D− pull-up control, GP17 mux select.  makes GP16 and GP19 outputs high; the external resistors are what should raise GP14/GP15.  §3 gives the intended wiring: each 2.2 kΩ resistor has its own control pin, with 100 Ω in series from GP14/GP15 to their respective bus lines. §2 E3 explains why tying both resistor controls together defeats isolation when switched off.

[reported by coordinator; not independently inspected here]  records two five-second CDC captures, each 171 bytes, showing the USB_KEY banner and ; the coordinator confirmed the capture contents from the private bench paths. They establish repeatable self-test failure on the currently wired Pico 2 W, not a failed key exchange. This review did not open the private capture files or access the bench.

## Root checks suggested by the source

1. With the Pico unpowered and disconnected from the FM-1/PC, verify the actual RP2350 header labels against GPIO numbers (GP14, GP15, GP16, GP19; do not substitute physical header-pin numbers). Trace GP14 through its 100 Ω resistor to the D+ node and GP15 through its own 100 Ω resistor to D−.
2. Verify the D+ pull-up is a separate 2.2 kΩ path from the D+ node to GP16, and D− has its own separate 2.2 kΩ path to GP19. Check for swapped controls, a shared GPIO/resistor connection, solder bridge, or either bus node shorted to ground. Confirm common signal ground and that GP17 actually selects the intended PC/default mux position.
3. If continuity/layout is correct, isolate the dongle-side line nodes from target/host and observe the two sense inputs during self-test: both should rise. If one remains low, localize that line’s GP input, resistor, control output and mux connection before investigating key polarity or timing.

The source cannot identify which physical net is wrong from a  string alone. It also does not prove that the board wiring follows the documented circuit. Since startup sets the mux to PC before self-test, interpret the measurement using the actual relay/mux topology: the sense inputs must still be connected to the locally pulled-up dongle-side nodes in that state, or the designed self-test will read the isolated inputs low. This is a particularly important layout check for the actual assembly.

The FAULT result occurs before : changing D+/D− key polarity, USB_KEY timing, SOF behavior, or FM-1 ROM state cannot explain this specific state. A future  would only clear this electrical precondition; it would not prove ACK, ROM enumeration, or flash recovery. Pico 2 W UF2 programming/USB enumeration likewise proves only that the RP2350 accepted/runs a USB-visible image, not that GP wiring is correct or the FM-1 can enter recovery.

## Boundaries

No code or wiring was changed. This was a source/doc review against base  plus the committed programming note. No GPIO voltage, continuity, Pico, FM-1, USB or bench operation was performed. Next step belongs to the Mac coordinator: check the assembled GPIO/mux/resistor routing, then repeat the existing console observation only under the coordinator’s hardware procedure. Keep recovery acceptance separate from passing self-test and from successful UF2 programming.
