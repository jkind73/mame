# Pause/resume — NATIVE QUALIFIED

The preserved prototype is now in production, after dacd1f99 passed its complete
native acceptance. The default suite includes4480 actual-method cases plus four
DMA-resume compositions. Existing harnesses expose the new saved fields; the
host-flag oracle retains its full flag assertions and now accounts for EP/PR
command priority. Actual paused state is reflected in debugger flag text.
The complete consumer now requires24 native pause programs/four configurations
and an actual paused/odd-phase DMA file replay. The complete68-script local
batch passes; binary-dependent local checks remain separate from native acceptance.
Checkpoint f944ce85 passes build35376996618/export35377759991 and the complete
expanded native consumer:24 pause programs/four configurations, actual paused
odd-phase DMA file replay, every prior gate and before/after provenance/BIOS
checks. Binary SHA256:1c0d88d5f123bc50bdd19563b8d704cd25242af1327fa9660b99f865dea9fb13.
Evidence: ../f944ce85-live/. ES single-step and exact prefetch/timing
remain open. Two saved fields are added; cross-version saves are not promised.
Earlier prototype notes below are historical; do not reapply the patch.

# DSP-01 / DSP-03: pause/resume prototype (NOT INTEGRATED)

Production ignores EP/PR. The external candidate ../../scudsp-pause.patch adds
an explicit paused latch and independently tracks DMA's execution stall. Pause
and resume commands must not overwrite the execute latch. PPAF reports EX=0
while paused; resuming during DMA must not release DMA's stall, and DMA completion
must not release pause. Both new fields are registered and reset. Existing
host execute/reset policy is retained; no single-step or prefetch rewrite.

Reference basis:
- Sega ST-097 printed51/PDF67: EP pauses and PR resumes an executing program;
  commands have no effect when execution is disabled. ES is a distinct command,
  not what the old source's EP popmessage called it.
- Ymir6d779960127ced72087a418c1daefc637d0aaa80 scu.cpp PPAF read1259/write2121+
  separates programExecuting/programPaused, gives EP/PR priority over EX writes,
  and reports EX only when running and not paused. scu_dsp.cpp Run allows DMA
  to continue while paused (its instantaneous DMA timing is not an oracle).
- Beetle1382b85dcad2e98ef9a67426a775ba548eaf0c68 scu.inc read501+/write718+
  has distinct pause/execute state and the same command priority/EX read behavior.
  GPL reference inspected only; no implementation source copied.

The prototypes follow the primary's EX=0 command restriction; reference behavior
for prohibited/simultaneous start-pause combinations is not declared resolved.
Exact pause edge timing, ES single-step, first-instruction prefetch bubbles,
active LE behavior and whole-host-stop semantics remain open. Pause is composed
with the existing approximate DMA stall; this does not replace bus arbitration.

Evidence:
- Complete external production translation unit/header pass C++20 syntax.
-4480 actual-method pause/DMA/saved-field/reset cases and four resume-during-DMA
  compositions pass under UBSan. Timer/CPU endpoints are recording stubs, not
  native scheduling. Five mutants fail: releasing DMA on resume, releasing
  pause on DMA completion, ignoring the write mask, and losing either saved bit.
- Qualified f1fe8e09 completes six native loop/byte/full-word/DMA cases with16
  control failures (zero passing cases). It fails to freeze loops, executes
  post-DMA instructions while supposedly paused, and does not resume via PR.
  The independent C-bus output/guard controls still match. If an old emulator
  ignores pause, the fixture explicitly stops it before accessing DSP data RAM.
- Actual paused/odd-phase DMA save/mutate/load reaches all notifications but
  fails four pause/resume/stall observations on the old binary. All C-bus image,
  saved external-word, and WA0 probe controls match. No candidate native replay
  has been performed yet.
-14 ordinary/15 save parser controls pass without running an emulator.

Promotion must update extracted harness declarations for the new saved fields
and control-command priority; it must not weaken the protected flag assertions.
This prototype is separate from the currently qualifying S/Z-only production
change. No parent closure or working-driver promotion.
