# Live baseline evidence — source 5008a923

Executable SHA-256: `3b4c476bff089672d5049a05f3fd739f7222608a7f84de467a0cd168d5b01557`.
CI run 35287467065; uploaded ZIP checksum and executable provenance verified.
Text logs only: no ROM images, NVRAM, save states or extracted firmware included.

The gated runtime command exited successfully: configuration, CD HIRQ/tray,
DRAM/BRAM, internal backup-RAM persistence/save-load, 24 SCSP timer/divisor rates,
and four configurations of BIOS/background replay. Backgrounds are 46 synthetic
scenes per configuration (184 total). JP DRC/interpreter, PAL DRC and ST-V DRC
are covered. Visual inspection of the JP capture showed the BIOS date/time
setup screen. ST-V showed the expected “ERROR ON CARTRIDGE / PRESS SERVICE
BUTTON” screen with no game cartridge; this is not ST-V game boot acceptance.

`multitap-before.log` is a deliberate separate negative baseline: the old binary
fails remaining-data flags, byte 32 (overwritten with 10), the second-page tail,
and zero-byte port mode/report selection. This demonstrates the live bug before
integrating the pending transport fix. Positive live acceptance of that fix
requires a new binary and is not included in these baseline results.

Additional baseline validation: the JP DRC **1,042-case composition suite**
completed successfully, including its pixel checks and real save/mutate/load
replay. See `saturnjp-drc-composition.log`. This used the same verified 5008a923
executable, not the new SMPC source. Other composition configurations and real
software/gameplay are not inferred from this result.

The scheduled partial-report save/load fixture was also run against a freshly
recovered, checksum-verified copy of this baseline executable. Its real pre-save
and post-load notifications were observed in order around packet mutation. It
completed without Lua errors and **failed the expected transport assertions**;
see `smpc-save-before.log`. This is a negative control, not positive acceptance
of the new snapshot fields. The old binary predates those fields.
