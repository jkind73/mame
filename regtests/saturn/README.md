# Saturn diagnostic scripts

The `scratchpad` directory preserves the original standalone timing, DMA, state-hash and audio-analysis scripts recovered from the 2026-09/10 session on the mounted Windows volume. `manifest.json` records each original path and SHA-256; the scripts are copied byte-for-byte. The external originals remain available.

These are historical diagnostics, not newly qualified assertions for every current implementation. In particular `dmactest2.lua` samples DMA at frame boundaries, uses oversized overlapping/mirrored memory ranges and estimates a clock from screen width; it cannot establish a precise DMA transfer rate. The `scudma*.lua` assertions target the earlier bus model. Memory hashes are partial rolling checksums, not complete save-state comparisons. Lua `BT_OUT`/`HASH_FRAME` variables configure only these test scripts; they are not production Saturn source hooks.

Run a Lua diagnostic from an isolated output directory:

```
/path/to/saturn saturnjp -noreadconfig -rompath /path/to/roms -video none -sound none -nothrottle -autoboot_delay 0 -autoboot_script /path/to/regtests/saturn/scratchpad/bustest4.lua
```

Add `-nodrc` to compare the interpreter. Use separate cfg/nvram/diff/state directories and run one emulator at a time. Scripts may wait 500 frames or more before starting, and modify emulated memory; do not run them in a normal gameplay session.

`scratchpad/sfx.py recording.wav` counts transient onsets in a stereo signed 16-bit PCM WAV. It is a relative sound-effect diagnostic, not an audio correctness oracle.

Current qualified replacements are in `scripts`: `saturn_transfer_rate_test.lua`, `saturn_dma_audit_test.py`, `saturn_dsp_bus_cost_test.py`, `saturn_startup_state_test.py`, `scsp_disc_test.py`, `scsp_dma_sample_test.py` and `sh7604_device_test.py`. The startup comparison uses complete saves, a fixed RTC and disabled host input providers. See the corresponding root audit reports for coverage and limitations.

The older branch's entire regression suite was not copied: its extraction harnesses and fixture layouts target a different source tree. This directory makes the requested scratchpad diagnostics available in the current branch without claiming those old expectations validate today's implementation.
