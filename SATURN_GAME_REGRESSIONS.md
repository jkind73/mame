# Game-by-game regression work

2026-10-08, local Saturn rewrite source. First pass covers the ten available
ST-V drivers below; it does not cover every Saturn disc or every ST-V set.
Each emulator runs alone at low priority, with independent configuration and
NVRAM, fixed RTC, no frame skipping, and video/audio output disabled.
Screenshots come from the emulated screen rather than the host video output.

| Game | Reproduced result | Status / next check |
|---|---|---|
| Radiant Silvergun (`rsgun`) | Visible story/attract screen at 60 seconds. | Older blanket blank-screen report does not reproduce. Gameplay, final boss and reverb remain unverified. |
| Elan-Doree (`elandore`) | Black at 30/60 seconds with DRC and interpreter. VDP2 display remains disabled. | OPEN. CPU polling PCs alone do not prove a dead CPU. Master still executes; initial VDP1 clear costs 175168 clocks, within a frame. Trace the startup transition rather than adding a display-enable hack. |
| Virtua Fighter Remix (`vfremix`) | Scripted coin/start/selection reaches fights with Akira, Wolf, Jeffry and Sarah. Selected fighter confirmed visually. | MT4445's three named character failures do not reproduce after existing rewrites. Remove stale NOT_WORKING flag; retain imperfect graphics/sound. Longer play and audio still need testing. |
| Golden Axe: The Duel (`gaxeduel`) | Visible title/attract at 60 seconds. | Attract reached; gameplay and sound regression cases remain open. |
| Die Hard Arcade (`diehard`) | Visible attract fight at 60 seconds. | Attract reached; quick-time-event slowdown and sound require gameplay checks. |
| Virtua Fighter Kids (`vfkids`) | Original code: deterministic DRC fatal error around 42 seconds: `Overran maxinst in drcuml_block_append`. Fresh current and saved pre-register-fix builds reproduce. | OPEN, under investigation. The first invalid interrupt vector is at about 31.406 seconds: main CPU IRQ14/vector65 reads A5A5A5A5 at 06000104. Both interpreter and DRC lose valid execution; the compiler overflow is a later consequence. Increasing the UML buffer did not fix it and was reverted. This also occurs before the recent register fixes. Interpreter taps covering all WRAM-H mirrors identify the first vector overwrite: slave PC 0605B416 writes A5A5A5A5 at 06100104 (31.396616 s), in its linked-list traversal. ROM verification passes. A bounded interpreter trace shows the traversal starts from a bad head (060FFB00), follows 06000348 and then SEGA (53454741). The earlier producer of the bad head is still unidentified. Disabling the cache also stalled the diagnostic and was reverted. |
| Funky Head Boxers (`fhboxers`) | Visible attract animation at 60 seconds. | Attract reached; CN18 multicab serial support remains missing. |
| Batman Forever (`batmanfr`) | Visible attract animation at 60 seconds. | Attract reached; final-boss rotation and full gameplay remain unverified. |
| Cotton 2 (`cotton2`) | Visible title/attract at 60 seconds. | Attract reached; stage-one music/reverb needs sound-enabled testing. |
| Final Fight Revenge (`ffreveng`) | Visible attract fight at 60 seconds. | Attract reached; broader gameplay/audio not assessed. |

## Reproduction

Run `python3 scripts/saturn_game_survey.py --rompath /path/to/roms
--output /new/output/directory game1 game2 ...` from the workspace. The runner
refuses to overwrite an existing game output directory, runs sequentially,
records commands/exit codes/Lua errors in `results.json`, and retains logs and
fixed-frame PNGs. An exit code of zero is **not** a visual correctness verdict.
The timeout is per game; the subprocess is stopped before moving to another.

The VF Remix regressions use `tests/saturn/game_inputs/vfremix-{wolf,jeffry,sarah}.txt`:

```
python3 scripts/saturn_game_survey.py vfremix --rompath /path/to/roms \
  --output /new/vfremix-test --inputs tests/saturn/game_inputs/vfremix-jeffry.txt \
  --frames 2559,2800
```

Input files replay normal input fields (`frame port mask value`, hexadecimal
mask). They do not patch ROM/RAM or force emulated status flags. Fighter
selection timing is specific to this run configuration; verify the selection
capture before interpreting the fight capture. The harness can add capture
frames using `--frames` and extend runs using `--seconds`.

Current raw evidence is under `/private/tmp/saturn-game-survey/`, including
`regression-set/results.json`, Elan-Doree DRC/interpreter captures, and separate
VF Remix selection/fight captures. Source-level fixes must be described here
after their final build and game verification pass. No upstream issue was
changed, and no whole-game or whole-library accuracy claim is made.

Final normal SDL3 build passes after reverting every temporary CPU diagnostic and cache-disable experiment. The final scripted Sarah replay exits successfully, confirms Sarah at frame 2559, and shows Sarah versus Jacky at frame 3600. Python syntax, checklist consistency and whitespace checks pass. The only driver behavior classification changed by this batch is VF Remix; no new CPU/VDP hardware fix is claimed.

## Continuation: SCU acknowledgment

The master does overwrite the slave's list-head buffer with interrupt-stack data before the slave's invalid traversal. Separately, a real-device regression demonstrates duplicate DRC delivery: a single SCU DMA completion is taken 33 times if the ISR's first instruction lowers SR. SCU used ASSERT_LINE and queued CLEAR_LINE inside its vector callback. HOLD_LINE makes MAME clear the CPU request synchronously before the driver callback; the callback now only releases the SCU arbiter and returns the vector.

`scripts/saturn_scu_irq_test.lua` waits for the initial BIOS clock-change reset, parks the CPU in a controlled loop and installs a real ISR. It verifies three DMA completions (including masked retention and subsequent unmasking), payload, counts and stack restoration. The original interpreter passes, while the original DRC fails with count 33. Both corrected cores pass with counts 1, 2, 2 while masked, and 3 after unmasking. This fixture replaces guest execution and is distinct from gameplay validation.

A normal corrected DRC VF Kids run lasts 122 emulated seconds without a host compiler abort, but frames 3600/7200 are black and CPU PCs are invalid; this is **not a completed game fix**. The control-register interrupt-shadow experiment did not resolve the game and was reverted. No temporary CPU diagnostics remain.

The final normal build passes the fixture in both cores. VF Remix's normal input replay still selects Sarah and reaches Sarah versus Jacky at frame 3600. Elan-Doree remains black in a fresh 62-second corrected run; the master waits on byte 060FFC13, and its VBlank handler repeatedly writes 1 then 0. The slave polls the FRT input-capture flag at FFFFFE11 (not SCI SSR). The shared slave-work flag read by the master is at cache-through 260FFCA8.

## Checklist sweep retest, 2026-10-13

Fresh serial runs use the current DRC, fixed RTC and isolated configuration,
EEPROM and backup RAM. Captures were visually inspected, not inferred from
exit status. This is a targeted 15-game retest, not a repeat of all 119 original
survey entries or a gameplay/audio certification.

| Game | Current observed result |
|---|---|
| vfkids | Visible Akira-versus-Akira fight at 60 seconds; valid CPU PCs. The earlier invalid-vector startup failure no longer reproduces in this run. |
| elandore | Still black at 60 seconds. Open. |
| rsgun | Visible story/attract scene at 60 seconds. |
| vfremix | Visible title at 60 seconds. |
| gaxeduel | Black at 60 seconds; an extended 102-second run shows some intro graphics around 40 seconds and long black intervals thereafter. The preserved pre-batch binary has the same 60-second result and CPU PCs. This is not a completed game fix. |
| diehard | Visible attract fight at 60 seconds. |
| fhboxers | Visible animated attract graphics at 60 seconds. |
| batmanfr | Visible attract background at 60 seconds. |
| cotton2 | Visible title at 60 seconds. |
| ffreveng | Visible attract fight at 60 seconds. |
| skychal | Still black at 65 seconds. Open. |
| techbowl | Still black at 65 seconds. Open; required external equipment is not validated by this run. |
| znpwfvt | Visible title at 65 seconds; original blank-screen report does not reproduce. |
| pcpooh2 | Visible Japanese attendant/error-1 screen at 65 seconds; still not a working game. |
| dfeverg | Visible attract graphics at 65 seconds; original blank-screen report does not reproduce. |

Artifacts: `/private/tmp/checklist-stv-retest-20261013`,
`/private/tmp/checklist-stv-survey-20261013`,
`/private/tmp/checklist-stv-blanks-20261013`,
`/private/tmp/checklist-gaxe-before-20261013` and
`/private/tmp/checklist-gaxe-extended-20261013`.
The old 2026-10-09 Golden Axe captures do show attract graphics at 50 seconds,
so the new black intervals must not be dismissed solely because execution
continues. Conversely the matching pre-batch result rules out attributing this
behavior to the SMPC or scan-edge save-state fixes. The exact historical
DMA/master-write trigger remains unverified and its checklist item stays open.

VF Kids with the existing SH-2 bus-timing setting Off reaches a visible attract scene at frame 3600, with valid game PCs. The isolated setup applies CONFIG.user_value=0 and performs exactly one reset; logged CONFIG is 0 before and after reset. Thus the remaining failure is in the timing-enabled path. Timing remains On by default; no per-game timing-disable workaround was committed. The earlier set_value/config-reset-loop attempt was invalid and its outputs are not game evidence.

To run the acknowledgment fixture, start vfkids with isolated cfg/NVRAM, `-autoboot_delay 0 -autoboot_script scripts/saturn_scu_irq_test.lua -seconds_to_run 3 -video none -sound none`; repeat with `-nodrc`. Require the explicit `SATURN_SCU_IRQ_PASS` marker, not merely process exit 0. The fixture's first ISR instruction lowers SR, which is essential to reproduce the original DRC failure.

Die Hard Arcade also reaches its visible attract fight at frame 3600 after the acknowledgment fix. The next VF Kids timing investigation is narrowed further: some master RAM accesses cost about 330 clocks against a 2–7 clock base; the arbitration trace reports zero waits on another requester and about 330 clocks behind its own logged bus frontier. During a sustained slow interval at 24.048 seconds, the preceding transaction is its own DMAC writing SCSP sound RAM (05A0000C onward), booked ahead of the CPU's access time. This observation does not establish that the DMA cost is wrong; cycle-steal ownership, scheduling and interrupt latency need a separate regression before changing the bus model. All temporary bus diagnostics were reverted.

## Full ST-V survey — 2026-10-13

All 119 games registered by `sega/stv.cpp` were attempted on a fixed copy of
commit `061f86e7163`. 106 launched; 13 could not launch because required ROMs
were unavailable: aclub, pclub2bb, pclub2bu, pclub2ev, pclub2lc, pclub2mb,
pclub2sr, pclub2ts, pclubnbc, pclubsc5, pclubsc6, sandr and slotbatt.
Each launched set was extended to 67 emulated seconds with isolated cfg/NVRAM,
fixed RTC, video/audio output disabled and serial low-priority execution.
All four final contact sheets were visually reviewed, not just process exits.
The initial 22-second pass often remained in BIOS startup and was insufficient
for attract conclusions.

Three extended runs crashed: astrass, decathlt and supgoal. Their failures are
being investigated; the survey completion does not claim these games work.
No Lua errors occurred. Persistent black final captures include cottonbm,
elandore, gaxeduel, magzun, skychal, techbowl, tsuribor, twcup98 and twsoc98.
Sfish2/sfish2j remain at BIOS system checking. Service/attendant/error screens
include chalgolf, fanzonem, sackids, stress, yattrmnp and many Print Club sets;
these are not counted as successful gameplay. Visible titles/attract scenes
include Batman Forever, Die Hard, VF Kids, VF Remix, Radiant Silvergun,
Cotton 2, Final Fight Revenge, Final Arch/SM League, My Fair Lady, Wildlife
Safari and Winter Heat. Visual appearance at one frame does not resolve
sound, long-run hangs, all window scenes or peripheral correctness.

Artifacts: `/private/tmp/checklist-stv-complete-20261013`. Its manifest records
the binary commit/hash and complete game list; `first`, `long` and `attract`
contain per-game commands, captures, logs and exit status. `review-results.json`
combines the extended runs, and `contact-attract-0.png` through `-3.png` retain
the final review sheets. The original **re-run survey** item is completed;
separate game-fix and combined regression items remain open.

### Crash follow-up at `2e826823267`

The SH7604 illegal-delay-slot fix passes 80 native exception cases in both
engines. Astra SuperStars and Decathlete now exit normally after 67 emulated
seconds, but their final captures remain black; this is crash removal, not
successful game emulation. Super Goal still crashes, and a separate
interpreter-only control also fails in interruptible sound-CPU memory access.
No game-fix checklist marker was closed for these results.

Artifacts: `/private/tmp/stv-illegal-slot-games-fixed-20261013` and
`/private/tmp/supgoal-interpreter-20261013.log`.

### Sound RAM boundary correction

The ST-V SH-2 sound map still exposed 1MiB after the shared SCSP allocation
was reduced to 512KiB. The native boundary fixture reproduces a heap overflow
at the first expansion word under AddressSanitizer; the corrected map passes
both engines, including ASan. Astrass, Decathlete and Super Goal now finish
67-second serial runs without crashes. All three final pictures remain black,
so these results do not close their game emulation failures.
Artifacts: `/private/tmp/stv-sound-ram-boundary-fixed-20261013`.

### Controller/report and sound-RAM integration pass (2026-10-13)

Serial 110-second runs with internal 48kHz audio complete without crashes
or Lua errors for cotton2, rsgun, vfremixj, ffreveng and daytonaj. Final
captures show title/intro, fighting attract, rankings and racing attract
as appropriate; Daytona Japan boots with the Japanese BIOS. Artifacts:
`/private/tmp/checklist-console-regressions-20261013`. A parser rebuild
occurred during this console batch; it is not a controlled cross-build
comparison.

The ST-V batch uses a fixed binary recorded in its manifest. Die Hard, VF
Kids, Funky Head Boxers and Batman Forever show visible
attract/ranking scenes at 100 seconds; all five runs, including gaxeduel,
complete without host crashes. Gaxeduel remains black, so its failure is
not resolved. Artifacts: `/private/tmp/checklist-stv-regressions-audio-20261013`.
All ten recordings contain 110 seconds at 48kHz. These observations do not
establish audio parity or close the whole original regression item.

Golden Axe's denser 155-second attract capture still shows captions and
project-logo transitions with most backgrounds absent; it is not simply one
poorly timed black screenshot. No host crash occurs. It remains open;
artifacts: `/private/tmp/gaxeduel-attract-sequence-20261013`.

### Golden Axe acknowledgment regression isolation

An isolated rebuild of 92373a1e6e6 restores the full-color intro at 40 seconds.
Its next source change, a06db8543e1, loses that background. Adding the missing
SCU acknowledgment IMS reset to that revision restores the same full-color
scene. The current build still loses backgrounds with this correction, so a
later independent regression remains under investigation. It is not a claim
that current Golden Axe gameplay is repaired. Captures and immutable binaries:
`/private/tmp/gaxeduel-known-baseline-20261013`,
`/private/tmp/gaxeduel-first-irq-change-20261013`,
`/private/tmp/gaxeduel-first-irq-mask-correction-20261013`, and
`/private/tmp/gaxeduel-scu-ack-mask-fixed-20261013`.

With the acknowledgment mask correction, serial Die Hard and VF Kids
110-second runs both finish without host crashes or Lua errors. Inspected
captures show fighting attract scenes at 100 seconds; both internal audio
files contain 110 seconds at 48kHz. Artifacts:
`/private/tmp/scu-ack-mask-stv-retail-20261013`. This does not certify full
gameplay, final stages or audio hardware parity.

### Golden Axe second regression fixed

The later checkpoint 30d92e6700a still loses backgrounds with the verified
SCU mask and sound-RAM bounds corrections. Removing its IRQ redispatch
timer does not fix it and that experiment was discarded. Live on-chip DMA
traces identify DMAOR.NMIF left set after the clock-change standby wake,
inhibiting valid aligned ROM-to-CRAM requests.

With the full-standby wake correction, the latest build restores the full-color
intro and reaches two visible attract fights (including frame9000). Its
155-second serial run finishes without crashes or Lua errors and produces
a complete 48kHz internal audio recording. Artifacts:
`/private/tmp/gaxeduel-standby-nmif-fixed-20261013`. The exact older
SCSP-DMA/master-write race remains a separate verification within the original
combined three-game checklist item; attract success alone does not close it.

The historical worktree has been archived after retaining its committed
backports and immutable test binaries. Test branches are
`codex/gaxeduel-ack-mask-baseline` and `codex/gaxeduel-checkpoint-candidate`.

### Standby DMA regression retests

After 7dac092797b, nine serial 110-second ST-V runs complete without crashes
or Lua errors and produce full 48kHz internal recordings. Inspected final
captures now show visible Decathlete and Super Goal attract scenes, Cotton
Boomerang's title, and Tecmo World Cup/Soccer '98 titles. These were previously
black. Astra SuperStars, Elan-Doree, Sky Challenger and Tsuribori remain
black; none is marked fixed by exit status alone. Artifacts:
`/private/tmp/standby-nmif-black-game-retests-20261013`.

### Shared encrypted-cartridge mapping regression checks

After installing the protected ports in both SH-2 address spaces, serial
110-second Astra SuperStars, Elan-Doree and Radiant Silvergun runs finish
without crashes or Lua errors. Each internal recording contains 110 seconds
at 48kHz. Inspected frame6000 captures show Radiant Silvergun's visible attract
sequence; Astra and Elan remain black as before the mapping change. This
interface correction does not resolve those two game failures. Artifacts:
`/private/tmp/stv-crypt-shared-bus-retail-20261014`.

### Exact upstream baseline (2026-10-14)

The user's upstream checkout is commit
`98e60b54d0718171636f50e39794d861564aac08` (2026-10-13). Its Windows
executable cannot run natively on this Mac. The exact commit was imported and
built in the separate managed `saturn-upstream-regression-baseline` worktree
with the same Saturn/ST-V subtarget and -j4. The source remains unchanged.
The 315-5881 cipher implementation and Astra initialization match upstream;
the rewrite also changes CPU/cache/bus and SCU behavior, so a renderer-only
comparison would miss possible startup regressions.

Three serial upstream 110-second runs used the existing survey runner, fresh
cfg/NVRAM/diff directories, identical ROM paths, no throttle or frameskip,
video/sound none, and internal 48kHz audio recording. All exited normally
without Lua errors. Inspected Astra captures show its animated star/cloud
intro; the rewrite's equivalent run remains black. Upstream reaches PC
0605b9d8 while the rewrite stays at 0600205a. Diagnostic rewrite runs with both
DRC and interpreter reproduce the same interrupt-masked loop (SR=000000f0),
with stack words 5345528f/000000f0. This identifies a common startup failure;
it does not yet identify which change corrupts the execution path.

Upstream Decathlete's frame6000 shows its score/attract screen, with visible
horizontal graphics artifacts; Die Hard's frame6000 shows the helicopter
intro. Decathlete averages 175.36% unthrottled versus 130.13% in the recent
rewrite run. Scene progression differs and these are whole-run averages,
not a matched-scene benchmark or a Windows performance claim. VF2 and Batman
have not yet been compared against this native upstream baseline.

Artifacts: `/private/tmp/saturn-upstream-stv-baseline-20261014`,
`/private/tmp/saturn-upstream-baseline-build-20261014.log`,
`/private/tmp/astra-startup-stack-current-20261014`, and
`/private/tmp/astra-startup-stack-interpreter-20261014`. Survey manifest
checkout_head identifies the runner checkout; the upstream binary's source
commit is the exact hash above. No production behavior or checklist marker
was changed for this comparison.

### Astra startup: missing sound-CPU switch port

Controlled tracing identifies the failing path: the sound firmware reads
68000 address 600000 while servicing the BIOS request at sound RAM 4F0-4F3.
The unmapped port returns zero, which becomes active input bits. The BIOS
stores these in 06000728 and then generates release events before Astra's
SDK initialization finishes. The resulting error calls the still-uninitialized
callback at 060CF888 (the BIOS RAM-test pattern 53454741) and reaches the fatal
0600205A loop. Both DRC and interpreter reproduce it. Disabling SH-2 bus
timing and restoring the MIDI-empty flag in isolated probes do not fix it.

The upstream sound firmware does not execute this port-polling path in the
same startup window, hiding the missing mapping. The rewrite now maps the
ST-V sound switch word at 600000 to 00FF: eight inactive active-low inputs
and a zero upper byte. This agrees with the local MiSTer SCSP.sv STV_SW
readback and Saturn.sv's unconnected STV_SW='1. Writes are acknowledged and
ignored. No physical hardware measurement or connected-switch wiring is
claimed; additional address aliases are not inferred from the RTL.

The native regression checks both byte lanes, ignored writes, Astra's
callback initialization, absence of the fatal loop, and the inactive BIOS
input report on both engines. Both pass; the preserved pre-fix binary fails
the input-port check. Full build passes. The production 110-second Astra
capture reaches visible attract graphics. Elan-Doree remains black.

Five serial production runs (Astra, Elan, Decathlete, Die Hard and Radiant
Silvergun) all finish without crashes or Lua errors, with complete 110-second
48kHz recordings. Inspected captures retain Die Hard's helicopter intro and
Radiant Silvergun's attract sequence. Decathlete remains visibly imperfect
and averages 129.68% versus upstream's 175.36%; Die Hard averages 126.91%
versus upstream's 205.88%. These whole-run averages are not matched-scene
profiles. Neither performance gap is claimed fixed by the switch-port change.

A separate 110-second ordinary-input replay inserts a coin, starts player 1
and selects a character. Frame4800 shows a Jetuge-versus-Maron fight with
the timer at 55; the run completes without crashes or Lua errors. Visible
rendering artifacts remain, so this validates startup and gameplay progression,
not complete graphics parity. Artifacts:
`/private/tmp/stv-sound-switch-astra-play-20261014`; replay inputs are
`/private/tmp/astra-play-inputs-20261014.txt` (PORTC coin/start, PORTA button 1).

Artifacts: `/private/tmp/stv-sound-switch-native-20261014`,
`/private/tmp/stv-sound-switch-parent-20261014`,
`/private/tmp/stv-sound-switch-retail-20261014`,
`/private/tmp/astra-startup-instructions-current2-20261014`,
`/private/tmp/astra-startup-instructions-upstream-20261014`, and
`/private/tmp/astra-sound-all-writes-current-20261014`. The original checklist
and inventory remain unchanged.

## Native upstream comparison: VF2 intro and sprite cost — 2026-10-14

The native upstream baseline is `98e60b54d071`; the rewrite reference is
`b11e8b66737`. Runs use the same `vf2j` disc/BIOS paths, initialized console
NVRAM, fixed RTC, isolated configuration and no frame skipping. No cross-build
save state is loaded.

The differently shaded Lau portraits at frame 2400 are different movie frames.
The rewrite's entire captured 512-by-224 RGB bitmap at frame 2400 is byte-identical
to upstream frames 2313–2319. Across frames 2100–2700, 369 of 601 rewrite bitmaps
match an upstream bitmap in that capture interval. The intro transitions from
wireframe through flat shading to textures; comparing equal screen-frame numbers
misidentified this transition as lost texturing. These matches establish source
bitmap parity for those frames, not whole-game rendering parity. Unmatched
captures and the remaining arcade graphics reports still require investigation.

All 7,657,620 CD FIFO payload bytes consumed by the rewrite through the 46-second
run match the corresponding prefix of upstream's 8,108,180-byte stream. The
bitmap difference persists with the interpreter and the existing bus-timing
switch off. Repeatedly disabling the cache disrupted movie progression and is
not a valid rendering comparison or a proposed workaround. No peripheral or
rasterizer behavior was changed on the basis of those experiments.

The sprite decoder now returns the exact transparent-dot metadata immediately
for a zero framebuffer word. This avoids format, shadow and RGB/palette decoding
for empty sprite pixels. The extracted actual decoder matches the preserved
reference for every 16-bit word, every sprite type and all eight combinations of
RGB selection, sprite-window enable and transparent-shadow selection: 8,388,608
comparisons under ASan/UBSan. The full real-renderer/erase fixtures also pass.

One serial 90-second native VF2 profile pair measured 244.68% before and 247.31%
after; all PNG captures at frames 2400, 3600 and 4800 are byte-identical. This is a
small measured gain (about 1.1%), not evidence that the upstream performance gap
is resolved. Two bus-history search/expiry candidates showed no useful gain and
were removed before the final build.

Reproduction tools: `scripts/saturn_sprite_decode_equivalence_test.py` and
`scripts/saturn_bitmap_sequence_compare.py`. The latter compares every byte in
each captured bitmap record (big-endian frame number plus a fixed-size bitmap),
without assuming equal frame numbers represent equal movie progression.
Evidence: `/private/tmp/saturn-vf2-zero-sprite-profile-20261014`,
`/private/tmp/saturn-bitmap-sequence-compare-20261014/alignment.json`,
`/private/tmp/saturn-cd-full-stream-compare-20261014`, and
`/private/tmp/saturn-zero-sprite-renderer-tests-20261014.log`.
The original checklist and inventory have not been edited.


## Elan-Doree: VDP1 frame-change ordering — 2026-10-14

The rewrite cleared the previous draw-completion flag (CEF) and started a new
VDP1 draw immediately at VBlank-OUT. Elan-Doree's SGL VBlank-OUT handler reads
CEF before advancing its frame state; it repeatedly saw the newly started draw
instead of the completed one, leaving VDP2 display disabled (TVMD 0103).

Frame change now waits for the first HBlank-IN after VBlank-OUT. ST-013 section
4.2 explicitly permits FCM/FCT writes immediately after VBlank-OUT until that
horizontal edge. MiSTer's VTIM_N/HTIM_N frame-change sequence corroborates the
ordering. This preserves the software write window and previous CEF without
adding guessed dot positions. The pending edge is reset and saved. Vblank erase
still stops at the vertical edge, so postponing buffer change does not extend
the erase interval. No cache disabling or game-specific workaround is used.
This implementation has not been verified against real hardware.

The extracted real edge methods pass ASan/UBSan tests for CEF visibility, FBCR
sampling, duplicate signal levels and erase termination; the parent fails the
CEF assertion. The native Elan-Doree startup fixture reaches game video mode
81c3 and its animated intro with both DRC and interpreter; the parent fails with
0103. Full renderer/window/rotation/erase fixtures and SCU interrupt diagnostics
for both engines pass. The Saturn subtarget builds successfully.

Fresh 110-second runs of Elan-Doree, Astra Superstars, Decathlete, Die Hard Arcade
and Japanese VF2 complete without Lua errors, with visible attract sequences.
The four ST-V recordings contain 110 seconds of 48 kHz audio. These checks do
not establish full graphics or audio parity: visible rendering discrepancies
and the performance gap against upstream remain under investigation. Existing
save states from before the additional saved field are not used for validation.

Reproduction: scripts/saturn_vdp1_frame_edge_test.py and
scripts/stv_elandore_startup_test.py. Evidence is in
/private/tmp/elan-frame-edge-native-fixture-20261014,
/private/tmp/elan-frame-edge-parent-fixture-20261014,
/private/tmp/vdp1-frame-edge-retail-20261014,
/private/tmp/vdp1-frame-edge-vf2-20261014 and
/private/tmp/vdp1-frame-edge-irq-final-20261014.
The original checklist and inventory have not been edited.
