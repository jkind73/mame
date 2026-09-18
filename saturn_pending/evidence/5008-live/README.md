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
