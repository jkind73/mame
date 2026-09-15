# After Burner II boot stall — investigation

## Instrumented capture 629e6569: later sound-startup wait

User upload: [629e6569](https://github.com/jkind73/mame/commit/629e6569a5223bca7ec353603acffc83da2954d7),
`afterburner2-boot.log`, 4,066,753 bytes / 22,786 lines, SHA-256
`dd7ba1de850aafc1348413482074c2b282bb549946619d76d8c272aea2d86402`.
The console identifies `saturnjp` / `saturn:aburner2`, 155 seconds at 100% speed.
The uploaded commit is preserved on this branch.

This run **does progress past the initial file read**. The earlier capture's
stopping point must not be mistaken for this run's final wait:

- 7.053333333 s: Read File completion asserts EFLS (`HIRQ=07d5`), 18 sectors stored.
- 8.968–8.976 s: host obtains file information and transfers 36,696 bytes from those
  sectors, then aborts file processing. Partial last-sector transfers are normal.
- 10.836–17.487 s: many further commands and transfers execute at main PC 06006ec2.
  The trace contains **2,351 command-dispatch events**, not just a stuck first read.
- 15.195725609 s: last VDP1 END completes. Later field callbacks show `busy=0`,
  `PTMR=0`; no more draw lists are submitted. This differs from the earlier capture.
- 17.486927808 s: last CD command is End Data Transfer, reporting 52 transferred
  bytes from the final sector. No more command-register reads after its response.
- Between field records 17.554618411 and 17.571350668 s: SMPC logs **SNDON**.
- 18.006666666–155.006666666 s: 138 periodic samples show main PC **06010276**
  (106 samples) or **06010278** (32). Slave remains at 00000200. CR1–4 read counts
  remain 2,137,016 each; HIRQ reads increase roughly once per field. HIRQ is 07d5,
  mask 0000, no pending command, CD PAUSE, no remaining sectors or active transfer.

The 99 retained buffer blocks are accounted for by earlier Put Sector Data
commands allocating 70 blocks to buffer 1 and 29 to buffer 2; that count alone is
not evidence of a leak. Nor is mask=0 proof of a broken interrupt: host polling is
visible. The log localizes the persistent stall to a CPU-side wait after sound
startup, but contains neither its instruction words/register operands nor sound
CPU state. It does not prove which handshake the game is waiting on.

### Source-backed sound IRQ/reset correction

`saturn_state::scsp_irq` discarded both assertions and clears whenever `m_en_68k`
was false. `scsp_device::CheckPendingIRQ` suppresses callbacks for an unchanged
level. Thus an assertion during SNDOFF could be lost after SNDON; a clear or level
change during SNDOFF could also leave an old 68000 input asserted. The CPU reset
input already prevents execution; dropping changes in the driver is unnecessary
and incorrect. Removed the gate, preserving IRQ delivery during RESET. No CD,
VDP1 or game-specific timing/handshake workaround is applied.

Source checks:

- Sega [ST-169-R1](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-169-R1-072694.pdf),
  printed p.3 Table 1.1: sound CPU OFF means reset asserted, while SCSP is ON;
  pp.25–26: SNDON/SNDOFF control MC68EC000, with sound memory retained.
- Pinned [MiSTer Saturn wiring](https://github.com/MiSTer-devel/Saturn_MiSTer/blob/a95b085038ace57fa621558d60a7adc7a3c53f78/rtl/Saturn/Saturn.sv),
  lines 977/1048 wire SNDRES to CPU reset; 1062–1064 wire SCIPL directly to IPL.
  [SCSP RTL](https://github.com/MiSTer-devel/Saturn_MiSTer/blob/a95b085038ace57fa621558d60a7adc7a3c53f78/rtl/Saturn/SCSP/SCSP.sv)
  line 2130 continuously drives `SCIPL_N = ~ILV`.
- Pinned [Ymir SCSP](https://github.com/StrikerX3/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/scsp/scsp.cpp),
  SetCPUEnabled (409–417) is separate from interrupt-level calculation/delivery
  (ending at 851). This supports independent CPU-enable and IRQ signals, not a
  claim of identical emulator reset scheduling.

### Validation and next acceptance test

`test_sound_boot.py` executes the production SCSP priority resolver and Saturn
reset/IRQ callbacks for all 64 old/new level pairs across reset. Restoring the old
IRQ-drop gate fails the assertion checking delivery during RESET. New ASan/UBSan
checks also cover raw RAM word order, mirrors/boundaries, invalid/MMIO/cache-space
rejection, verbose gating, periodic trace throttling and observational behavior.
All **19 regression scripts and nine production-object compilations pass**. This
is not a linked emulator/game run or a test of the sound driver's instructions.

Added once-per-emulated-second, verbose-only `BOOTCPU` evidence alongside field
tracing: main SR/PR/general registers, sound PC/SR/SP/cycle count and reset/HALT
state, and bounded instruction/operand RAM words. It reads backing RAM only—no
MMIO reads, CPU memory handlers or bus wait-state charges. Invalid addresses are
shown as `----`. These diagnostic counters are not emulated/save-state contents.

**The IRQ/reset defect is reproduced and corrected; its responsibility for this
particular boot stall remains unconfirmed.** Rebuild this branch and rerun After
Burner II. If it still hangs, preserve the new `-verbose -log` capture: BOOTCPU now
provides the instruction/operand and sound-CPU evidence needed to identify the
actual wait, without another instrumentation-only rebuild.

## Earlier capture and initial investigation (superseded where noted)

## User report and supplied capture

The user explicitly reports that Saturn After Burner II gets stuck and never
completes boot. This is separate from OutRun's now user-confirmed flashing fix.
The log at [822d45ac](https://github.com/jkind73/mame/commit/822d45ac1a5ce7509993ace32d9000eb57b138e4)
is therefore relevant boot-stall evidence, not an accidentally substituted OutRun
scaling capture. Its console description identifies `saturnjp`, software
`saturn:aburner2`, and an approximately 91-second run.

File `regtests/saturn/newerror.log`: SHA-256
`2288b3f5c73cd4fb0d00c98b003fcdebece80cbbe27a1531ed51cf14838df374`.
CD lines lack timestamps; times below are from the nearest preceding VDP1 record,
not exact CD-command execution timestamps.

| Approximate time | Observation |
|---|---|
| 6.913 s | Read File accepted: first/current FAD 0xAB, 0x12 sectors, filter 0, sector size 2048. |
| 7.047 s | File PLAY status transitions toward PAUSE. |
| 7.047–83.580 s | No subsequent CD commands are logged; VDP1 field activity continues. |
| 83.580 s | Soft reset logged. Whether user- or software-initiated is not established. |
| 90.507 s | Same Read File request accepted again. |
| 90.641 s | Same PLAY-to-PAUSE transition. |
| 92.097 s | Capture ends with VDP1 still completing its command list. |

## What this establishes — and what it does not

The renderer is not permanently stuck in an unfinished primitive. The drive model
progresses through a small file read and returns to PAUSE. This does not prove that
the file data is correct, the expected completion flag reaches the host, or the CPU
advances past its wait. Existing logs omit HIRQ polling, command-register reads,
CPU PCs and periodic buffer/transfer state; some command logging is also disabled.
Therefore absence of command lines is not proof of absence of host CD accesses.
No CD/IRQ/timing workaround or game-specific fix is justified yet.

## Focused diagnostic addition

With `-verbose -log`, `CDBOOT` now records:

- Once per emulated second: main/slave CPU PCs, CD status/next status, HIRQ/mask,
  command-pending bits, CR1–CR4, current FAD/remaining sectors, free/full buffer
  state, sector-present indication, play type and transfer progress.
- Raw command state at command dispatch and state immediately after file EFLS is
  raised. This removes the ambiguity of the older command-log mask.
- Cumulative host read counts and last returned values for HIRQ and CR1–CR4.
  Debugger reads are excluded. Counters/rate limiting are host-only diagnostics,
  not saved emulated state.

The trace does not change emulated register values or completion behavior.
ASan/UBSan tests exercise opt-in gating, debugger reads, CR4's existing handshake,
forced events, once-per-second limiting, missing CPU handles and observational
state preservation. The existing 336 CD transfer cases pass; the 18-script suite
and nine production object builds passed with the production instrumentation.

## Next runtime capture

Rebuild this branch and run only the failing game:

```bat
mame saturnjp aburner2 -verbose -log
```

Leave it stuck for about ten seconds, exit MAME completely, then preserve the log
before starting another game:

```bat
copy error.log afterburner2-boot.log
```

This requests the newly added status/PC evidence, not another copy of the already
analyzed capture. A boot fix has **not** been claimed or visually validated.
