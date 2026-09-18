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
