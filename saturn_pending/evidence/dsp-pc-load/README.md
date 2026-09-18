# Stopped PC-load correction — NATIVE QUALIFIED

Integrated after c33fe0da passed its complete native consumer. The existing
host-control model now executes262144 masked flag/PC/slot/state cases. The
existing pause native fixture now has20 programs (80/four configurations),
retaining all six earlier pause/DMA programs. Parser/consumer counts are updated;
the default suite remains69 scripts. Targeted suites and full-TU syntax pass.
Source1ee15ef8 passes full69-script local/CI, build35381311374/export35382269649 and the complete native consumer:80 expanded programs/four configurations and all prior runtime/save/provenance gates. This full consumer was repeated after workspace recovery with the identical binary SHA256511e756c0f44c08a2c6371d1e75ba05a4b40cb1614e15afe260c5ccf4788e4c9. Evidence: ../1ee15ef8-live/. Historical prototype
notes follow; do not reapply the patch. Full ES/prefetch/timing remains open.

# Stopped PC-load correction prototype — NOT INTEGRATED

ST-097 printed52/PDF68 says LE loads the start address only while EX=0.
Pinned Ymir6d779960127ced72087a418c1daefc637d0aaa80 WritePC rejects active writes
and runs before the PPAF execute/pause strobes. This supports an entry-state
test, permitting a stopped load-and-start write but rejecting an active load.
Beetle1382b85dcad2e98ef9a67426a775ba548eaf0c68 lacks the active-write guard;
that divergence is not concealed. Both references discard the prefetched
instruction on PC load. Source inspected only; no reference code copied.

The candidate masks LE as a strobe, tests stopped/paused state before changing
EX/EP/PR, and clears the existing pending-slot flag on accepted loads. This is
not a full prefetch pipeline, ES implementation or hardware edge/PC-readback
qualification. Other registers and DMA ownership are untouched. LPS/prefetch
interactions still need their broader pipeline work.

The EXISTING host-control model expands to262144 actual-method cases, retaining
all read-only flag assertions and adding byte/halfword/full/zero masks, entry
pause/execute state, pending-slot invalidation and independent DMA HALT ownership.
Candidate PASS; current source fails. Four mutants fail: active load accepted,
checking state after the write, unmasked LE and retaining an old pending slot.

The EXISTING pause native suite expands from6 to20 programs. On qualified
f8022878,10 pass/10 fail: all six earlier pause/DMA controls and four stopped
load/start controls pass; four active-load and six paused pending-slot programs
fail (16 mismatch messages). Wrapped/nonwrapped branches and full/halfword/LE-byte
loads are exercised. Every DSP data read is performed only after EX=0; PPAF's
current core-specific PC+1 is only a phase selector, not a timing oracle.
No candidate native positive exists. The three-file patch is preserved separately
while c33fe0da's logical-flag native qualification runs. Promotion must update the
pause parser/consumer6→20; the default suite remains69 scripts. No parent closure.
