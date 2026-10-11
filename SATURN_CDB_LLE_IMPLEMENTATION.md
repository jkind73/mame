# Saturn CD block LLE implementation

2026-10-11. **LLE is on hold at the user's request; normal Saturn configuration
uses HLE to avoid the extra SH-1 emulation cost.** The LLE device, bus support,
firmware fixtures and regressions are retained. `tests/saturn/cdb_console_lle.patch`
records the console wiring for re-enabling it later; it is not applied.

The validated LLE configuration executes the real SH7032 firmware through
`saturn_cdb_device` and boots PAL Virtua Fighter 2 into its title and attract
sequence. The former integrated failure (8809 empty FIFO reads in 18
seconds and a return to the BIOS player) is fixed: the final 45-second run has
zero FIFO underflows and overflows at every sampled point.

**No real-hardware verification has been performed.** Drive seek latency,
security-ring carrier timing, and drive-peer response delays remain modeled
assumptions rather than measured hardware timings. Passing firmware and game
regressions does not establish cycle-exact agreement with a physical Saturn.
The optional MPEG cartridge is not supplied by this base-console device.

## Firmware and bus implementation

The locally supplied `cdb106.bin` is 65536 bytes, CRC32 `3681d3b0`, SHA-1
`b3c20fbe57cd2eb595e9edac86817e5948dccae4`. Commands execute this ROM; there is
no replacement host-command interpreter. The device implements the YGR019
command/response latches, IRQ6/7, six-word host FIFO, SH-1 DMA0/1 requests,
synchronous SCI drive link with checksum/ACK, TOC, drive operations,
raw-sector delivery, and security-ring carrier.

Native SH-2 memory instructions check FIFO readiness before changing registers
or completing a bus access. A blocked access yields until the SH-1 can run and
retries the instruction. Both interpreter and DRC honor the wait; DRC temporarily
uses monitored instruction execution while a FIFO transaction is pending/active.
The wait checks include transfer direction, not just FIFO count. This prevents
Put Sector Data from depositing words before firmware resets its old read FIFO.

Both SH-2 internal DMACs use the existing FIFO availability callback and resume
notification. SCU levels 0/1/2 and DSP DMA check the same readiness predicate
before consuming a unit. An eight-byte SCU CD unit is acknowledged as two
four-byte accesses, with its half-transfer state serialized and explicitly tested by saving between the two acknowledgements. A stalled DSP DMA
retains its address/count; unrelated DSP instructions can continue. Existing SCU
bus costs and wait-register timing remain charged on successful accesses.

The CD block's actual external DREQ0/1 connect to the SH-1. Saturn's SH-2 DREQ
pins are not repurposed as invented CD FIFO request lines. Host DMA availability
notifications provide the emulator scheduling handshake.

Untimed debugger/Lua accesses bypass CPU execution and must explicitly poll
DATASTAT. The diagnostic counters make accidental FIFO misuse visible rather
than hiding it from comparisons.

## Audio, framing, tray and saved state

When LLE is enabled, CDDA feeds the SCSP's external stereo inputs. The default HLE configuration retains its existing stereo routes to the SCSP.
Audio seeks and stops clear playback; pause preserves position; resumed audio
unpauses the stream. Playback is bounded to the current audio track. The fixture
captures nonzero stereo samples and checks playback, pause, resumed playback,
stop, tray opening/closing and live audio save/load.

Cooked Mode-2 Form 1 and Form 2 payloads begin at byte 24, with duplicated
subheaders and the correct form bit. Form 1 receives EDC/ECC; Form 2 receives
EDC. Raw images retain their original headers, payload and error-correction
bytes. Tests compare every payload byte against an independent logical image
read and independently calculate the EDC for both forms.

FIFO contents, pointers/count, pending command, direction, SCI bit/byte state,
drive/tray state and timers are saved. Post-load restores IRQ/request and host
wait notifications. A test saves while native FIFO writing and an SCI exchange
are both active, completes the transfer, reloads, and verifies the complete
sector again. CDDA save/load independently verifies its playback cursor.

## Reproducible validation

Build/run the actual firmware fixture:

```
python3 scripts/saturn_cdb_firmware_test.py --build \
  --output /private/tmp/cdb-lle-check --seconds 12 \
  --disc /path/to/PAL-VF2.chd --script scripts/saturn_cdb_sector_test.lua
```

Repeat with `--core drc` and a fresh output directory. Both cores pass firmware
authentication (result 4), a complete independently compared 2048-byte sector,
native reads and writes on both SH-2s, both internal DMACs, all three SCU channels
and DSP DMA. Both SCU CD transfer widths pass. Existing SH-2 UBC, all seven DMA burst-count cases, and DSP concurrency regressions also pass on both cores. Every DMA writer performs a full
sector write/readback comparison. FIFO underflow/overflow counters remain zero.
The runner rejects failed and unfinished sector, Mode-2 and audio tests.

Run `saturn_cdb_mode2_test.lua` with cooked Form 1/2 images and
`saturn_cdb_audio_test.lua` with an audio-track image; both pass on both cores.
The latter accepts `--wav` for captured audio. The DSP DMA blocked-access,
final-beat and host-wait regression passes ASan/UBSan via
`scripts/scudsp_dma_wait_test.py`. The earlier complete SH7032 peripheral suite
also passed both cores under ASan/UBSan, including RAM aliases, disabled DREQ
pulses and idle synchronous SCI clock behavior.

Final integrated evidence: `/private/tmp/saturn-cdb-integrated-final-20261011`
contains the 45-second VF2 log, snapshots and audio. The integrated trace is retained as `scripts/saturn_cdb_console_test.lua`. Additional actual-firmware
results are in `/private/tmp/cdb-all-writers-drc-final` and
`/private/tmp/cdb-cross-core-final-*`. Audio samples were nonzero; this is a
functional regression, not a hardware waveform comparison.

Research: Renesas SH7032 hardware manual sections 8.3.5, 9 and 13;
[firmware reverse engineering](https://github.com/user-none/erings/blob/main/docs/cdblock/saturn_cdblock_firmware.md),
[MiSTer drive protocol](https://github.com/MiSTer-devel/Main_MiSTer/blob/master/support/saturn/saturncdd.cpp)
and YGR019 RTL. Interface facts informed the implementation; implementation code
was not copied. ST-V retains its existing HLE device where used.
