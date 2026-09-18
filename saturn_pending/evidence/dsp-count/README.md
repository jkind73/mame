# DSP-02 / DSP-03: eight-bit transfer counter candidate (NOT APPLIED)

Production cd074b71 retains the older 16-bit memory-sourced length and performs
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

`../../scudsp-count.patch` is portable against cd074b71 and includes the core,
extracted tests, adapted real-save fixtures and expanded consumer gate. Apply
only after the current loader baseline is qualified. There is no candidate
native positive yet. Shared grants, exact timing, remaining address rules and
alternate program-DMA serializers remain open; no parent closure.
