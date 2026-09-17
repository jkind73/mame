# Single-agent integration status

## Reviewed cartridge/CD changes — WIP, 2026-09-17

Baseline: `4edfe4bc` (production unchanged from `125e3048`). Adapted from the
user-supplied `01a0ac86-f1f7-74c0-81dd-287e6f103c11 (1).patch`, SHA-256
`351216925207e399591f162b14c0c138e5ce9559e9988a3dbee5714b9a352567`.
The `(2)` patch is identical and was not applied. Original source license and
copyright headers are retained.

Production changes: guard empty cartridge DRAM allocations before modulo/index
access, retain existing allocated DRAM aliasing, replace cartridge boundary UI
popups with logging, check backup-RAM write counts, and preserve CD HIRQ DCHG
until acknowledgement instead of discarding it on read.

Primary CD basis: Sega SDK `0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`,
ST-136-R2-093094, printed p.50 / PDF p.58, section 6: software detects a tray-open
condition through HIRQREQ DCHG bit 5. PDF blob:
`7e6f189f4d34cf1d79cd58e61a190e621042e5ed`. This passage was read during the
preceding review. DRAM aliasing and out-of-range bus values remain modeling
policies, not new hardware measurements.

Fresh checks for this WIP:
- 262,144 extracted HIRQ status-overlay/read/ack cases pass. Restoring the old
  DCHG-clearing read compiles and fails its assertion.
- Existing 336 extracted CD transfer cases and boot-trace tests pass.
- 24 extracted cartridge cases pass; the original empty-allocation handler
  compiles and is rejected by the sanitizer with a division-by-zero/FPE.
- 44 existing and 12 added fake-executable runner protocol cases pass.
- Python syntax and `git diff --check` pass.

The imported live CD/cart runners now reject nonzero exits, FAIL/Lua-error output
and malformed PASS markers, and use the actual `saturn` subtarget with absolute
paths. Their fake-executable tests are NOT live MAME/device acceptance.

**Pending:** full regression batch, native linked build, old/new binary tray
negative control, actual cartridge execution, BIOS/gameplay and save/load replay.
Earlier background builds and external logs did not survive workspace recovery;
no completed baseline boot or new linked result is claimed. This is a pushed
implementation WIP, not a validated release. CART-01 and CD-01 remain open.

IOGA, the incremental video patch, Agent1 CPU/bus changes and working/save-flag
promotion are excluded. A separately reviewed IOGA follow-up must discard local
receive-valid state on reset before that patch can be considered for integration.
