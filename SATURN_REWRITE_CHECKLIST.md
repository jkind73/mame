# Saturn / ST-V source rewrite: status checklist

Updated 2026-10-07 (after commit `81025778514`). Branch `claude/saturn-vdp2-rewrite-4bb92d`.
`[x]` done and committed (commit in brackets), `[~]` partly done, `[ ]` not done.

## How this file stays true

1. **Every commit that changes a Saturn / ST-V source also changes this file**: tick what the commit finished (with its hash once it exists, in the next commit), add what it found, set the date above. The pre-commit hook refuses a commit that touches the Saturn sources without staging this file. Install it once per clone: `python scripts/saturn_checklist.py install-hook`.
2. **Nothing with a line number is typed by hand.** `SATURN_TODO_INVENTORY.md` (every TODO / FIXME / hack / guess / `getenv` note, with its line) and the table at the end of this file are written by `python scripts/saturn_checklist.py scan` from the source. `python scripts/saturn_checklist.py check` (also run by the hook) fails when either differs from the source, so a note that was added or removed cannot go unnoticed. Section 12 below says what each note means; it refers to the note text, never to a line.
3. **When a session resumes**: run `check`, read "Next up", then the open items of the area you work on. The same pointer is in the memory note `saturn-rewrite-checklist.md`.
4. Resolve a note by fixing the cause and deleting the note in the same commit. Never delete a note to make the count drop.

## Rules that apply to every item
- Source order: Rel.2.5 docs (`segahtml/`) over everything, then Rel.1 / ST-xxx PDFs, then hardware probe measurements, then Mednafen / Ymir / MiSTer. Cite the document section in the commit.
- One detailed commit per item. Never `git add -A`, never a bare `git stash`. Commit messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Ymir is GPL-3 (behaviour only). Mednafen is GPL-2 (measured numbers only, no code).
- Never trade accuracy for speed; speed work must be an exact change (state hashes identical before and after). Frame skipping is not an optimization. Do not defer work that is clearly needed and whose inputs are at hand.
- A correct hardware change is committed even when a game breaks; then the other inaccuracy is found (memory `feedback-hardware-first`).
- At most one game run at a time, low priority, short `-seconds_to_run` (batches crashed the machine on 2026-10-06 and 2026-10-07).

## Next up (in this order; the user decides when to switch)
1. **Speed**: games run between 95% and 64%. Profile (gdb sampling) says the cost is the SH-2 bus arbitration callback, the SH7604 cache read, and the VDP2 line renderer. Plan: bit-exact fast path in `sh2_bus_arbitrate`, then `sh2_device::cache_read`, then VDP2 `render_line` / `draw_nbg_fetched` / `draw_rbg`; prove each step with the state-hash Lua script; repeat the profile with sound enabled (the first one ran without). The user paused this on 2026-10-07 while the VF2 sound was looked at.
2. **VF2 sound versus Ymir** (section 7): BIOS chime louder than Ymir, fight sound effects not yet compared.
3. **Diagnostic hooks** (section 11): `SATURN_LEGACY_DDI`, `SATURN_VDP1_LOG`, `SATURN_BUS_TIMING` remain; remove or turn into proper options.
4. **SCSP DMA timing and 1Fs interrupt** (section 7), **SCU DSP audit remainder** (section 5).
5. Open hardware questions that need the probe disc (sections 2, 4, 6).

## 1. VDP2 renderer
- [x] Per-line renderer: NBG0-3, RBG0/1, sprite dots, windows, priority, colour calc, extended colour calc, shadow, line colour
- [x] Legacy renderer removed (`cf4bd684b9c`)
- [x] RBG rotation: coefficient tables, RPMD modes, rotation table base mask, RDBS bank roles for pattern name / character reads
- [x] Extended colour-calc Table 12.2 fix, exclusive-mode colour-calc limits (`c9d1f6fc36c`)
- [x] Window end Y 1FCH-1FFH disables the window in double density (`fd28609cb96`)
- [x] VRAM CPU/DMA arbitration (`046b7a2ce77`)
- [x] Die Hard Arcade sky / floor / ceiling regression fixed
- [x] VDP2 picture of a frame that frame skipping does not show is not drawn; layers that cannot be seen and colour stages that do nothing are skipped (`c54eac2aca6`, `e334d7a9aca`)
- [x] VBLANK-IN at line 224 in the 224 line mode (`3674a79cc9f`; decided by Batman Forever, a hardware test would still confirm)
- [ ] Table 12.2 mode-0 last row prints "2:1:0", code uses 2:1:1: check against the Rel.2.5 page
- [ ] RPMD mode 2: manual wording about B's per-dot coefficients (currently ignored)
- [ ] Exclusive-monitor window X bit layout, exclusive monitor hblank/dot positions (notes in `saturn_vdp2.cpp`)
- [ ] Erase with X1 >= X3
- [ ] VDP2 V counter roll-back, H counter values at the end of the line (HCT 0x15A to 0x3B0), latch behaviour (section 12.3)
- [ ] Open divergence in the fetch pipeline port: Megamix (memory `vdp2-fetch-pipeline-port`)

## 2. VDP1
- [x] Draw engine, erase/swap, end timing (`a2f6b2f5aa0`, `977baa91af6`)
- [x] CPU VRAM access wait during drawing (10 clocks, ST-013 p19, provisional) (`5ade3a9727b`)
- [x] Vertical blank erase limited by the blanking duration (`2b421b274e9`, `cebad0d9512`); Batman Forever attract band fixed
- [x] No command runs longer than a frame; a line that never reaches its end point does not hang (`e3ba4fdb5a9`)
- [x] Plain pixel store for the common drawing modes, clip type chosen once per line (`72e23aa6cbb`)
- [ ] Recalibrate the timing model on a real Saturn (the MiSTer probe fit is provisional, memory `vdp1-probe-calibration`)
- [ ] VDP1 timing and CEF "isn't accurate at all" (header note of `saturn.cpp`; stays open until the recalibration)

## 3. Clocks
- [x] 320 / 352 dot-mode clocks from the manual (`2048db0fbf0`)
- [x] PAL clocks, PAL machine resets to PAL 320 clocks (`9afa5890e7c`, `75a3cfdc511`)

## 4. SH-2 (SH7604)
- [x] On-chip cache model (`677574eb231`)
- [x] DRC fixes: not-taken branch cycles, MAC double charge (`d180837f9dd`, `1ddcbfe38b4`)
- [x] Bus timing callback and Saturn bus costs (`8175d0a6aa6`, `1a0505cf87a`, `0dad4d4478f`, `657e1097e35`, `15e47432da2`), enabled by default (`0ac0806ff8d`)
- [x] Master/slave shared-bus arbitration; each DMAC shares its CPU's slot (`e744cfdd701`)
- [x] On-chip DMAC unit timing from bus costs (`8b009c597d3`)
- [x] DRC vs interpreter loop-cost parity checked on 12 regions and about 30 instruction bodies
- [x] `BUSY_LOOP_HACKS` removed, interrupt controller rewritten from the manual, spurious-IRQ hack gone (`ad8a36209c6`)
- [x] DIVU 39/6 cycles, bus held, overflow IRQ (`2f333b2c87c`)
- [x] WDT resets the chip, flags follow the manual (`bd3d6979c16`)
- [x] Reset values of the on-chip registers, power-on vs manual reset (`68cd9c75f69`)
- [ ] SCI DMA request/ack, standby entry/exit audit
- [ ] Audit every SH7604 on-chip register against manual Appendix B: addresses, access widths, read-back bits, the SCI state machine
- [ ] DIVU: the extra cycle of a read directly after a write to a division register (manual 10.4.1) needs a hardware test
- [ ] On-chip register access time (waits for the probe)
- [ ] Sporadic `asmjit error 26 InvalidInstruction: mov eax, ebx` in the DRC (VF Kids twice under load, once in another branch's old exe). Hardware instability on this machine is suspected (gcc internal compiler errors, a zeroed git index, crashes under load); investigate the DRC only when it reproduces on a quiet machine
- [ ] Speed: see "Next up" 1; bus timing costs about 4% (16% on vfremix), cache model 22% of DRC time

## 5. SCU and SCU DSP
- [x] Removed DMA forced-stop register and DMA access status bits (`558407c370f`; Rel.2.5 errata)
- [x] DMA takes the time of its bus accesses, owns A-bus / B-bus, C-bus-only SH-2 halt (`d8c152eb9da`)
- [x] SCSP DMA 13 clocks per 16 bit transfer (`7727215064e`); the sound CPU is not halted
- [x] Timer 0 / timer 1 (`edb7930781c`)
- [x] DMA level add/mode registers write-protected while transferring (`832d07a446f`); aligned longword reads through a buffer (`c7420fc2dad`); DMA to the SCU's own registers is illegal (`11663b18de0`)
- [x] DSP: DMA instructions follow the hardware rules, no halt for a whole transfer (`19b5657aef8`); the add field is the raw bits 17-15, RA0/WA0 rules (`fe6a13ff156`); ALU flags, condition decode, pause/step (`df75a088706`)
- [ ] Cross-check the FAQ transfer-rate table (program loop 15.4 clk/4B, CPU-DMA 12.4/7.6, SCU-DMA 2.25/2.2) against the model
- [ ] Re-test the DMA-vs-SH-2 cases of the old tree: gaxeduel (SCSP DMA then master write), Resident Evil (zero descriptors, endless indirect chain), Pulirula (slave restart)
- [ ] Indirect-mode zero descriptors: decide the chain behaviour against the docs
- [ ] SCU DSP DMA cost and DSP DMA bus wait: audit what remains after `19b5657aef8` against the MiSTer SCU.sv
- [ ] Game-side rules from Rel.2.5 not emulated: do not read the DSP program control port while running; do not write the interrupt status register (decide whether to log)
- [ ] The `saturn_scu.cpp` and `scudsp.cpp` notes (section 12.4)

## 6. SMPC
- [x] INTBACK peripheral data collected from the VBLANK-OUT with the manual's optimization (`7ee6344e4ae`); an INTBACK issued while the display is active collects in that frame (`7606c1547f3`); reports per ST-169 3.1 (`d73f91888d8`)
- [ ] INTBACK per-device collection time (700 us is a guess): needs hardware
- [ ] OREG10 bits 5 and 4, SNDRES/SYSRES polarity: needs a hardware test
- [ ] Odd addresses latch the last written value; undocumented commands SEC_GETSEED/SEC_VERIFY, NetLink; reset button NMI in the 3VINT period
- [ ] Rel.2.5 SMPC errata beyond those applied; RTC subdevice

## 7. SCSP
- [x] MIEMP bit no longer set (`f462caf260b`); MIDI flags and FIFO (`fbf128d37ab`)
- [x] Interrupt and timer handling per ST-77 (`002a2f85084`); integer envelope generator, noise, DSP pipeline, FM, LFO, SBCTL, master volume in 3 dB steps (commits of 2026-10-01 `a016626df39` to `70cf327d103`)
- [x] DSP program decoded once when written, rebuilt after a savestate load (`452e1374fc6`); this also closes the DSP savestate item
- [x] DAC18B makes the output four times louder (`118a4b42bb6`); Virtua Fighter 2 sound effects and music now match Ymir in level and number of sounds (demo RMS 2350-2670 vs 2310-3056, 48 against 48 sounds in 10 s)
- [ ] VF2: the BIOS startup chime (3-9 s) is 1.4 to 3.8 times louder than Ymir's, peak 21651 vs 12857, so it is not a gain error: compare the effect processor (DSP) output step by step against Ymir
- [ ] VF2: the first title sound comes about 1.5 s after Ymir's; compare the sound CPU timing
- [ ] VF2: record a scripted fight in both emulators (same inputs) and compare sound onsets
- [ ] DMA wait states, per-sample 1Fs interrupt, the DMA that is not timer driven (notes in `scsp.cpp`)
- [ ] Rel.2.5 SCSP errata beyond those applied
- [ ] The notes in `scsp.cpp` (section 12.8)

## 8. CD block
- [ ] LLE: SH-1 plus real firmware (replaces `saturn_cd_hle.cpp`; `saturn_cdb.cpp` is a disabled stub). The only firmware image known is MiSTer's `cdb105.mif`: ask the user which source is acceptable
- [ ] Audit the remaining commands against ST-162
- [ ] The SH-1 peripheral modules (section 12.9) become blockers once the firmware runs

## 9. ST-V
- [x] The magzun hacks and the legacy `ioga` fallback are gone, all machines use the 315-5649 device (`12dadeadf3d`, `232e40f000c`)
- [ ] magzun microphone / RS-422, 315-5649 "buffers always ready" hack
- [ ] 315-5838 `HACK_MODE_NO_KEY`, mic, coin, EEPROM defaults
- [ ] Re-run the ST-V attract survey after today's changes (blank games list in memory `stv-survey-2026-09-25`); Batman was fixed in `e3ba4fdb5a9`

## 10. The six uploaded files (scspdsp, VDP1 draw, VDP2 compose and render) - DONE
- [x] The user's optimizations were applied with their required fixes in `452e1374fc6` (DSP decode cache, DSP bug and savestate rebuild), `72e23aa6cbb` (VDP1), `e334d7a9aca` (VDP2); the GNU `case ...` range, the `EXPECTED()` macro and the unused `win_test` overload are not in the source
- [ ] Old stash entries are still in the shared stash (`optimizations-pre-rebase-onto-master`, `EXTRA`, `garbage`, `extra garbage`, `latestcheckins`, ...): the user decides when to drop them; nothing is dropped without being asked

## 11. Verification and housekeeping
- [x] `SCSP_LOG` is now MAME-style compile-time logging in `scsp.cpp` (`VERBOSE` masks `LOG_IRQ`, `LOG_REG`, `LOG_KEY`, `LOG_MIX`; default 0 so the code is compiled out, no cost; the CD audio play line is `LOGXFER` in `saturn_cd_hle.cpp`); `SCSP_LEGACY` is removed (the rewritten behaviour is the only one, git history has the old one). Verified: logs appear with the masks on, and the VF2 audio of the first 9 s is bit-identical with them off
- [ ] **Diagnostic hooks still to remove or turn into options**: `SATURN_LEGACY_DDI` (`saturn.cpp`), `SATURN_VDP1_LOG` (`saturn.cpp`, `saturn_vdp1.cpp`), `SATURN_BUS_TIMING` (`saturn_bus.cpp`). The generated inventory lists each one under `getenv`
- [ ] Move the standalone Lua timing tests (`dmactest2.lua`, `scudma.lua`, `bustest*.lua`, state-hash and audio-analysis scripts) from the session scratchpad into the repository; `regtests/saturn` lives in the other branch only
- [ ] Regression pass at the end of each area, one game at a time: cotton2, rsgun, vfremix, ffreveng (Saturn); gaxeduel, diehard, vfkids, fhboxers, batmanfr (ST-V); Daytona USA (Japan) boots with the Japanese BIOS; the BIOS animation sound
- [ ] Update the memory notes after each area (`saturn-rewrite-checklist`, `rewrite-plan-2026-09-29`, `sh2-bus-timing`, `vdp2-line-renderer-progress`, `saturn-vf2-audio`)
- [ ] Update the stale header comments in `saturn.cpp` (the SCU IRQ / VDP2 counter list: VBLANK-OUT, timer 0 and the HBLANK-IN are done) and `saturn_vdp2.cpp` ("stub overlay") when their items are closed

## 12. What the notes in the source mean
The generated list is `SATURN_TODO_INVENTORY.md`; the table at the end gives the count per file. Each group below is one source file; a group is closed when its notes are gone from the inventory.

### 12.1 `sat_console.cpp`
- [ ] Decap the SH-1 for the CD block (section 8)
- [ ] IRQs: some games have problems with timing-accurate IRQs. Plan: list every source (SCU, SH-2 on-chip, SMPC, VDP1/2, SCSP, CD block), verify each edge time against the docs, collect the failing games, fix
- [ ] ST-V Cart-Dev mode hangs even with the `-dev` BIOS; IC13 games on the dev BIOS do not load
- [ ] SCU DSP "fair share of issues" (section 12.4)
- [ ] RS-232C serial interface, needed by fhboxers
- [ ] Video "nowhere near perfection": re-assess VDP1/VDP2 against captures now that both are rewritten
- [ ] Reimplement the idle skip only if cycle counts and IRQ timing stay identical
- [ ] Move the SCU device into its own file (check nothing SCU-related is left in `saturn.cpp` / `stv.cpp`)
- [ ] test1f diagnostic hacks (two patched addresses): find why the check fails
- [ ] mamedev issue 15773; the access that must not return 0 or the SH-2 crashes ("might be a CD block bug"); changing the driver configuration screws the NVRAM; 3D Lemmings TH control mode (needs hardware)

### 12.2 `stv.cpp`, `stvdev.cpp`, `315_5649.cpp`, `315-5881_crypt.*`, `shared/rax.cpp`
- [ ] Per-game list in the header: aclub (Error 11, voice pitches: re-test after the SCU DMA timing commits, VDP1 contours, IOGA serial), colmns97 stuck envelope, critcrsh 7-seg LED, danchih/danchiq mametesters 6270 (verify and close), fanzonem "Door Open", fhboxers CN18, magzun mic, myfairld mametesters 2642 (re-test after the VDP1 rewrite), smleague/finlarch random hangs (re-test after the bus arbitration), stress, tsuribor analog rod, vfremix mametesters 4445, wasafari (RBG0 not drawn: re-test after the VDP2 rewrite), wwshin window glitches (re-test after the window fixes), yattrmnp
- [ ] ROM names (Sega nomenclature, IC positions), upper-nibble output port, BCD decoder chip type, cartridge as A-bus slot option, abus fill (1-filled?), SCSP reset line, SCSP clock (22579200 unknown divider), microphone bindings, RAX output, sense/delta values, BSERVICE/BTEST, coin error in maintenance mode, i486 connection
- [ ] Default 1P EEPROM images (nine machines, see the inventory)
- [ ] `stvdev.cpp`: two other clocks (36 MHz, 14.318 MHz); `rax.cpp`: last stage of Batman Forever
- [ ] `315_5649.cpp`: "recv buffers always full, transmit buffers always empty"; `315-5881_crypt`: standard hookup crashes LA Machine Gun, merge the ST-V and NAOMI interface

### 12.3 `saturn.cpp` and `saturn_vdp2.cpp`
- [x] VBLANK-OUT on the last line, HBLANK-IN at the chip's dot (`e5faebbacad`); timer 0 and timer 1 (`edb7930781c`); VBLANK-IN line (`3674a79cc9f`)
- [ ] IST: cleared when the interrupt is delivered; check against the manual/MiSTer; the ISM 0-to-1 acknowledge
- [ ] Delay between an event and the SCU IRQ (SCU at about 14 MHz)
- [ ] V counter roll-back and where it increments (end of line, dot 0x15A), H counter values, latch behaviour
- [ ] Timer 1 against the H counter table in the header: re-check with the new event dots
- [ ] No vblank/hblank IRQs when DISP is off (Yabause claim)
- [ ] `saturn.cpp`: edge triggered?; send a real reset to the connected devices
- [ ] `saturn_vdp2.cpp`: PAL 256 only mode, HBLANK with DISP off, interlace eats one line (262.5), divider compensation, exclusive modes, guard a wrong DOTSEL from SMPC, reserved VRESO, `static constexpr` 263/313, an unused test case, privatize the header members

### 12.4 `saturn_scu.cpp`, `scudsp.cpp`, `scudspdasm.cpp`
- [ ] SCU: attached-device penalties, A-bus penalties from the $b0-$b7 registers, A-bus wait states and external interrupts; more DMA rules (no same-bus transfer in direct mode, indirect mode same-bus quirks, cross-region DMA such as gunblaze, Road Blaster 1-byte quirk); SDRAM refresh overhead; which buses indirect mode may use; "yield until DSP" guess; guardherj 0x23000 FMV transfer; "other rules still apply"; DMA clock "should be /4 but the BIOS disagrees"; PAD IRQ from the SMPC (light gun, mice)
- [ ] DSP: DTACK the CPUs during DMA instead of stalling (partly done by `19b5657aef8`: re-read the note), fix the disassembler ("bad mem" in MVI), timings (no info), control flags, scheduler corrupts the debugger with the DRC, convert CTx to an array, vkyoute2 VDP1 vertices, flags in MVI/JMP partly guessed

### 12.5 `smpc.cpp` / `smpc.h`
- [ ] Header: timings, "INTBACK must fall between VBLANK-IN and OUT" (done by `7ee6344e4ae`: delete the note), clean-ups, RTC subdevice, battery NVRAM on the ST-V
- [ ] Inline: odd-address latch; INTBACK 700 us and the code after it "looks wrong"; command allowed outside vblank; ireg2 = 0xf0 check; diagnostic wants bit 3; NetLink; SEC_GETSEED/VERIFY; system region; oreg[31]; multitap controller check; 3VINT period; the nullptr check in `smpc.h`

### 12.6 `saturn_cd_hle.cpp`
- [ ] Replaced by the LLE (section 8). The 48 notes each describe a firmware behaviour; re-test the named games (azelpanztai, daytoncej, Choice Cuts, X-Men COTA, Waku Waku 7, Madou Monogatari, leynos2, Galaxy Fight, Area 51) after the LLE

### 12.7 `sh2.cpp`, `sh7604.*`, `sh7604_bus/sci/wdt.*`
- [ ] `sh7604.cpp`: use the `sh7604_wdt_device`, `sh7604_sci_device`, `sh7604_bus_device` sub-devices (the BSC could drive the bus cost model in `saturn_bus.cpp`); cps3boot callback; internal map too big when mirrored; FRT external clock; pulirula slave 0 cycles; items to test; output levels A/B; NMIE edge select; undocumented interrupt level; bare-bones unit for 32x:aburnerju
- [~] `dma_kludge` callback: cps3 only, kept until cps3 has another way (not a Saturn item); `sh2.cpp` has the same "spurious irqs" hack for the SH-1 family and "timing is a guess"; remove when the CD block LLE needs it
- [ ] `sh7604_bus.cpp` (16-bit access only, 8-bit invalid, host CPU setter, timer clock), `sh7604_sci.cpp` (diserial, RX/TX callbacks, verify), `sh7604_wdt.cpp` (host CPU setter, memory map)

### 12.8 `scsp.cpp`, `cdda`
- [ ] The notes in `scsp.cpp`: an empty TODO, "needs to be timer-ized" (SCSP DMA), "do parameters auto-update"
- [ ] `cdda.cpp`: no notes; verify its sync with the CD block LLE when that lands

### 12.9 SH-1 (`sh7014*`, `sh7032`) used by the CD block
- [ ] CMT, A/D converter, power-down, C/D ports, DMAC priority and external DREQ/DACK (the CD block uses external requests), MTU modes, SCI RX and the "full data transmit on sync" hack, WDT reset and WDTOVF pin, ADC trigger, port special functions. Each is a blocker for the firmware (section 8)

### 12.10 Other
- [ ] `saturn_dcc.cpp`: real part number, 16-bit MINIT/SINIT checked per accessor, sync barriers, slave IRQ acknowledge; games tight on interleaving (blastwnd, choroqpk)
- [ ] `segabill.cpp`: interrupt frequency of the vs298
- [ ] `keybd.cpp`: lock keys, MCU, key repeat, kana keys, shift behaviour; other controllers have no notes: confirm against the SMPC INTBACK work
- [ ] `m68000`: unintended level-7 interrupts when one or two IPL lines are asserted (the SCSP drives them); 68000 cycle accuracy against the SCSP bus
- [ ] `nvram.cpp` width/endianness (the backup RAM relies on it), `ticket.cpp` output tag, `cdrom.cpp` four notes (short-read error, endianness, `osd_file` string_view, track length guess)

## Note counts per file (generated: do not edit)

<!-- BEGIN GENERATED: note counts (scripts/saturn_checklist.py scan) -->

| File | Notes |
|---|---|
| `src/devices/bus/sat_ctrl/keybd.cpp` | 3 |
| `src/devices/cpu/scudsp/scudsp.cpp` | 3 |
| `src/devices/cpu/scudsp/scudspdasm.cpp` | 2 |
| `src/devices/cpu/sh/sh2.cpp` | 2 |
| `src/devices/cpu/sh/sh7014.cpp` | 4 |
| `src/devices/cpu/sh/sh7014.h` | 2 |
| `src/devices/cpu/sh/sh7014_adc.cpp` | 1 |
| `src/devices/cpu/sh/sh7014_dmac.cpp` | 2 |
| `src/devices/cpu/sh/sh7014_mtu.cpp` | 1 |
| `src/devices/cpu/sh/sh7014_port.cpp` | 1 |
| `src/devices/cpu/sh/sh7014_sci.cpp` | 6 |
| `src/devices/cpu/sh/sh7014_sci.h` | 2 |
| `src/devices/cpu/sh/sh7014_wdt.cpp` | 1 |
| `src/devices/cpu/sh/sh7604.cpp` | 27 |
| `src/devices/cpu/sh/sh7604.h` | 3 |
| `src/devices/cpu/sh/sh7604_bus.cpp` | 3 |
| `src/devices/cpu/sh/sh7604_sci.cpp` | 2 |
| `src/devices/cpu/sh/sh7604_wdt.cpp` | 1 |
| `src/devices/machine/nvram.cpp` | 2 |
| `src/devices/machine/ticket.cpp` | 1 |
| `src/devices/sound/scsp.cpp` | 3 |
| `src/lib/util/cdrom.cpp` | 4 |
| `src/mame/sega/315-5881_crypt.cpp` | 3 |
| `src/mame/sega/315-5881_crypt.h` | 1 |
| `src/mame/sega/315_5649.cpp` | 1 |
| `src/mame/sega/sat_console.cpp` | 6 |
| `src/mame/sega/saturn.cpp` | 6 |
| `src/mame/sega/saturn_bus.cpp` | 1 |
| `src/mame/sega/saturn_cd_hle.cpp` | 48 |
| `src/mame/sega/saturn_dcc.cpp` | 2 |
| `src/mame/sega/saturn_scu.cpp` | 9 |
| `src/mame/sega/saturn_vdp1.cpp` | 1 |
| `src/mame/sega/saturn_vdp2.cpp` | 16 |
| `src/mame/sega/saturn_vdp2.h` | 1 |
| `src/mame/sega/segabill.cpp` | 1 |
| `src/mame/sega/smpc.cpp` | 15 |
| `src/mame/sega/smpc.h` | 1 |
| `src/mame/sega/stv.cpp` | 28 |
| `src/mame/sega/stvdev.cpp` | 1 |
| `src/mame/shared/rax.cpp` | 1 |
| **40 files with notes, 73 searched files without** | **218** |

<!-- END GENERATED -->
