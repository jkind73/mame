# Fetched control-flow slot prototype — NOT INTEGRATED

Primary ST-097 p.90 describes executing the prefetched instruction on a jump;
p.53 permits program-port writes only while EX=0 and advances the address.
Pinned Ymir6d779960127ced72087a418c1daefc637d0aaa80 Run fetches nextInstr before
executing the previous instruction. Beetle1382b85dcad2e98ef9a67426a775ba548eaf0c68
likewise retains its decoded NextInstr across host program writes. Both preserve
the old fetched word, rather than rereading changed RAM when the slot executes.
References read only; no implementation copied.

The candidate adds a registered32-bit slot word and captures it when a control
instruction establishes a pending slot. Consumption uses that word. The debugger
instruction hook receives the actual slot address rather than the branch target.
Reset initializes the word; accepted LE and program-DMA completion invalidate the
pending flag as before. Ordinary sequential prefetch, first-fetch bubbles, ES,
LPS cycle cost/loop interactions, PC readback and full debugger/DRC synchronization
are NOT claimed fixed. This selected control-flow latch is not a full pipeline.
Adding a saved field changes snapshot registration; qualify same-build replay,
not cross-build snapshot compatibility.

The existing actual-method pipeline suite passes393216 PC/target/control-flow
cases plus1280 RAM-mutation/registered-word replay cases. Its oracles now distinguish
executed addresses from bus fetches: an early prefetch is not an extra executed
instruction. A poisoned saved opcode verifies registration. Six mutants are
rejected (reread, missing opcode save, wrong debugger hook, zero sentinel, missing
pending save/reset). Existing DMA/parallel/multiplier/LOP suites and full-TU syntax
pass after adding the field to their recording contexts; assertions are retained.

The existing native pipeline fixture expands12→27: five branch forms (JMP,
Z/NZ taken branches, MVI-PC and BTM) at ordinary, slot-FF and slot-00 boundaries.
While legally EP-paused, it writes a replacement through the program port WITHOUT
LE, then resumes. Current c33fe0da passes all12 earlier controls and fails all15
new fetched-word observations; all guards match. Its current PC+1 only selects a
phase, not a hardware-PC timing claim.

The actual pending-slot save fixture is strengthened too: RAM contains replacement
34 but the saved fetched instruction must still write12. Another guest branch
poisons the live cache with77 before file load. Old c33fe0da completes every
save/mutate/load phase and fails both original/restored marker observations (34
instead of12). Every DSP data/program access is made with EX=0. No native candidate
positive yet. Preserve separately while1ee15ef8 finishes qualification. Promotion
must update the existing pipeline parser/consumer12→27; default suite stays69.
