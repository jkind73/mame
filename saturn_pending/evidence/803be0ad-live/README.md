# SCSP slot LFO — native consumer archive (build 803be0ad)

Source commit `803be0ad86db8a9342bd97b953251964aee6758b` (SCSP LFO phase-step
scale fix), CI "Saturn integration artifact" build `35411489296`, export
`35411944006`. Binary SHA256
`26eef1e732ab77460c3cf4b5c05f7c10fad12693a4f6308fc9ffe60a64d01e4d`.

Files:

- `status.txt` — final consumer verdict (PASS) and the exact gate list.
- `artifact.json` / `final-artifact.json` — provenance before/after (equal).
- `bios.sha256` — the three BIOS ZIPs used, with digests.
- `libraries.txt` — loader output for the CI binary (no `not found`).
- `scsp-lfo*.log` — the four new LFO gates (39 cases each: JP/interpreter,
  JP/DRC, PAL/DRC, ST-V/DRC).
- `lfo-runtime.log` — the JP/interpreter LFO transcript: measured Table 4.21
  rate for all 32 LFOF settings (each within 0.1% of the manual), plus the
  hold/noise/depth-0/pitch rows and the `rate=44100.0 loud=0.500000` summary.
- `lfo-*-invocation.json` — per-run binary/BIOS/Lua SHA256 provenance.

This is the first native (mixer-value) qualification of the slot LFO, via the
new per-device Lua sound hook. It supersedes the earlier method-only record.
The pre-fix binary `7a86f4b7` (build `35409599120`) was the differential
control: it reports no modulation for LFOF ≤ 07H, keeps modulating under
LFORE=1, and runs the mid rates 256× slow — see
`saturn_pending/evidence/scsp-lfo/README.md`.

Not a per-game audio claim: game waveforms and the DSP effect chain are still
exercised only by the existing BIOS/background replay gates.
