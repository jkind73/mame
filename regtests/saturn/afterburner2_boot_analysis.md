# After Burner II boot stall — investigation

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
