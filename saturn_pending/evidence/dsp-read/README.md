# DSP-02: read DMA bus classification

The read path recognized only 06xxxxxx as C-bus, then independently tested a
partial address to force B-bus +4 advancement. Consequently 06Axxxxx..06Fxxxxx
lost fixed-source mode, 07xxxxxx could miss C-bus rules, and cartridge/CS2 reads
could spuriously inherit B-bus advancement. CPU mappings expose the same Work
RAM-H at every 1 MiB mirror of 06000000..07FFFFFF (and cache-through aliases).

The fix decodes physical bits 26:0 once, classifies the full C-bus window, and
uses a mutually exclusive B-bus range. It preserves the already working C-bus
increment selection, the B-bus paired-halfword read rule and existing A-bus
fallback. It does NOT finish all A/C-bus increment/address-update quirks or add
bus waits/illegal-transfer handling.

Evidence basis: actual Saturn/ST-V memory maps and the already-corrected main
SCU classifier, documented in official_specs.md under 'C-Bus mirrors'. Pinned
Ymir 6d779960127ced72087a418c1daefc637d0aaa80, scu_defs.hpp GetBusID, masks to
27 bits and treats the entire >=06000000 window as WRAM; scu_dsp.cpp uses its
read increment independently of the particular WRAM alias. No code copied.
A precise primary-manual mirror-aperture passage is still unestablished, as the
existing ledger states; this is map/reference-backed compatibility, not a new
hardware measurement. Ymir's unmapped B-bus gaps differ from MAME's broad bus
window; this fix retains MAME's existing B-bus aperture policy.

Actual 89764c08 native negative: CPU reads first confirm identical backing RAM,
then 1,024 DSP programs cover all 32 mirrors, eight modes, two count forms and
hold/nonhold. 652 pass, 372 fail. No private DSP fields are edited. The old source
also fails the expanded extracted test.

Candidate/production extracted passes: 2,048 cached/uncached mirror/mode/hold/
count cases, plus A/CS2 fixed-source and B-bus isolation. Existing 768 DMA cases
and 393,216 control-flow cases pass. Three compiled mutants fail assertions:
missing upper C-bus half, low-bit B-bus misclassification, CS2 treated as B-bus.
Full-TU C++20 syntax passes. Twelve parser controls pass, not device evidence.
New-source native positive is pending; the gate requires read-DMA programs on
JP/interpreter, JP/DRC, PAL/DRC and ST-V/DRC, in addition to all earlier gates.

Production ca63041f full local batch: 58 scripts, exit zero. Three optional
missing-default-binary live skips are excluded from native acceptance. Log:
`local/regressions.log`. Native build 35341486010 is still building.
