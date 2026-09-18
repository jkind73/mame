# DSP-02 / DSP-03: eight-bit transfer counter implementation (NATIVE WIP)

Previous cd074b71 retains the older 16-bit memory-sourced length and performs
one transfer for zero. The candidate masks the fetched count to eight bits and
normalizes zero to 256, without changing the saved progress-field widths.
No reference implementation source is copied.

Reference basis is explicitly convergent software behavior, not a newly found
primary zero-count measurement. Sega ST-097 pp.81–82,87–89,133–140 describes TN0,
word units, immediate/count-source forms and completion, but the reviewed text
does not explicitly establish memory-count width or zero encoding.

- Ymir commit 6d779960127ced72087a418c1daefc637d0aaa80:
  `libs/ymir-core/include/ymir/hw/scu/scu_dsp.hpp:382` declares uint8 dmaCount;
  `libs/ymir-core/src/ymir/hw/scu/scu_dsp.cpp` loads it from the selected RAM word
  or immediate, then transfers in a do/while with pre-decrement.
- Beetle/Mednafen commit 1382b85dcad2e98ef9a67426a775ba548eaf0c68:
  `mednafen/ss/scu.inc` declares uint8_t count (comment: zero = 256), masks the
  memory operand with FF, then uses do/while decrement. GPL code read only.

Actual ca63041f mapped-program reproduction: **8 pass,16 fail of24** across
zero/immediate/memory/high-bit controls, both directions and hold modes. Tests
observe complete data-RAM images and an external destination plus overrun guard.
Read tests use existing C-bus mode2; writes use B-bus mode1. All device mutations
are through host ports; no private DSP state writes.

Candidate extracted actual-method checks pass **20,480 count/direction/bank/hold
cases with five replay cuts each**, 5,120 program-loader cases (including full
256-word loads from all256 start positions), 2,048 read cases, 768 write-DMA cases
and 393,216 pipeline cases. Two compiled count mutants are rejected. Full-TU
C++20 syntax and shell checks pass. Twelve native-output parser controls pass
separately; none of these are native candidate acceptance.

**Acceptance fixture correction:** the older 60,000-word scheduled save test is
an implementation stress test, not a valid single hardware transfer under these
counter semantics. The candidate replaces it with a zero-encoded 256-word
transfer captured after2us, retaining scheduled save/mutate/load and exact replay.
It also extends program-RAM save replay from192 words to a zero-encoded256-word
wrap. Old ca63041f finishes a zero transfer before the save, copying only one data
word; both negative file replays complete all notifications and fail the required
busy/image checks. The program-save negative also encounters missing program-RAM
support on ca63041f and is not an isolated counter negative.

Integrated after cd074b71 passed its complete expanded native consumer. The
portable patch is retained in Git history; do not reapply. There is no new
count-source native positive yet. Shared grants, exact timing, remaining address rules and
alternate program-DMA serializers remain open; no parent closure.

The candidate also uses MAME's supported PRECOMPILE=0 build option and records
compiler-cache paths/configuration/statistics. Current source-labelled caches
are only about14MB despite repeated full native builds; current builds use PCH.
PCH-related rejection is a suspected bottleneck, not proven by existing logs
(which have no ccache statistics). No sloppy time-macro/PCH settings are enabled.
The first no-PCH build is cold; any claimed speed improvement requires observed
later cache hits and successful native acceptance. This is a build experiment,
not emulation performance evidence, and is now applied as a build experiment.


New isolated cd074b71 negatives repeat8 passes/16 count failures. With program
loading now implemented and qualified, zero-encoded program save copies its first
word correctly but finishes before save; exactly255 words are wrong after both
original completion and replay. This isolates the remaining counter defect from
the older ca63041f program-loader failure.

Integrated5d88f975 full local batch passed all58 scripts (exit0); three optional
missing-default-binary live skips are excluded. Log: `local/regressions.log`.
Native build35347062472 remains in progress; full source/binary-qualified
counter/save positives must still be run after export.

Next concrete decoder audit: op_dma still passes opcode&0xf to the count-source
helper, although ST-097 pp.135–136 select the source using bits0–2. The helper
returns zero for selectors8–15. Pinned Mednafen and Ymir use only the bank and
increment bits. Ignored-bit aliasing and actual MCx counter-fetch side effects
need an isolated mapped test and correction; this is not covered by the current
count-width cases. No new fix or native result for that issue is claimed here.


Superseding build status:35347062472 failed in controller include ordering exposed
by PRECOMPILE=0, not in the DSP source. Repair fc6664a6 puts emu.h before device
headers in five controller units, all passing no-PCH full-TU syntax. Build
35352902888 is running. See `build-repair/` for verified failed-artifact logs;
these do not qualify a binary. The source-selector audit now has an isolated
native negative and an unapplied candidate under `../dsp-count-operand/`.
