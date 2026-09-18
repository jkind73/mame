# Live integrated transport acceptance — 234c7abc

CI run 35291979814, executable SHA-256
`7508e813a6b93bd4f9650dd5f4a0cfcf73b84d128008a89bc3a8c678365c5062`.
Original ZIP transferred via a checksum-verified GitHub API blob; source input
trees matched before and after execution. Draft release is storage only.

The complete runtime consumer passed: native configuration validation, CD
HIRQ/tray, DRAM/BRAM, internal backup-RAM persistence and save/load, 24 SCSP
timer/divisor measurements, six two-multitap transport cases, scheduled
partial-report save/mutate/load (including restored emulated time), and four
BIOS/background save-replay configurations (184 background cases). ST-V BIOS
means the expected no-cartridge error screen, not game boot.

`SMPC_MULTITAP` and `SMPC_SAVE` logs are genuine linked positive results, not
extracted models. `smpc-timeout-before.log` is a separate genuine negative test:
all four waiting/in-flight VBlank-expiry scenarios reveal late flags/reports in
this pre-timeout binary. The timeout/edge-history fix is not part of this binary.

Text evidence only; no ROMs, NVRAM or save states are committed. Full software,
wire timing, extended IDs and full hardware completion are not inferred.

`sync-save-before.log` is another linked negative control. It saves during
active display, advances naturally into HBlank+VBlank, restores the file, then
samples the first restored HBlank. Actual SCU IST bits are **2**, not the
expected **4**: a spurious VBlank-OUT replaces the HBlank edge. Both missing
edge-history save items are also observed. All save/mutate/load notifications
complete without Lua errors or time-restore failures. The fixture only reads
save items and uses mapped registers for its interrupt oracle; it never
manually overwrites the missing fields. This supports the 2781 source fix but
is not that fix's positive native acceptance.
