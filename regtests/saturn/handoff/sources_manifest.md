# Saturn/ST-V Per-Parent Source Manifest — Agent A
**Branch:** arena/01a0ac88-mame
**Baseline:** 03c19a78e4cee7e9008a1100118934e8d84c0ea5
**Date:** 2026-09-17 UTC
**Task:** Faithful practical reproduction, maintain per-parent manifest, reuse when license permits with attribution.

This file tracks which pinned external sources contributed to each modified file in this branch, per the task requirement.

## Pinned Sources
- saturnsdk 0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73 — Sega official docs PDFs (ST-013, ST-058, ST-097, ST-169, ST-210)
- Ymir 6d779960127ced72087a418c1daefc637d0aaa80 — https://github.com/jkind73/Ymir (MIT)
- MiSTer Saturn a95b085038ace57fa621558d60a7adc7a3c53f78 — https://github.com/MiSTer-devel/Saturn_MiSTer (GPL-2.0? check LICENSE)
- mednafen-git f0ee9d59 — https://github.com/jkind73/mednafen-git (GPL-2.0)
- Yabause (audit) — https://github.com/Yabause/yabause (GPL-2.0)
- SaturnRecomp (audit) — https://github.com/SaturnRecomp/SaturnRecomp (MIT?)
- Cassini (audit) — to be pinned

## File-Level Manifest

### src/emu/devcpu.cpp
- **Change:** access_before_delay forced retry for cycles>=1024 (BUS-04)
- **Parents:** Independent implementation of MAME's built-in deferred transaction contract (read_interruptible returning 0, write skip, timeslice abort). Threshold derived from saturn_bus get_cpu_wait returning 1024-10000 for owned/not-ready (our own design). No external code copied.
- **License:** BSD-3-Clause (MAME core)

### src/devices/cpu/sh/sh2.cpp
- **Change:** execute_run snapshot save/restore of r[16], ea, m_delay, pr/sr/gbr/vbr/mach/macl, pc for CPU-04 deferred retry (choroqpk double R15 fix)
- **Parents:** Independent, based on SH7604 HW manual delay-slot and exception stacking behavior. Cross-checked Ymir SH2 interpreter for register preservation idea, but implementation is original.
- **License:** BSD-3-Clause

### src/devices/cpu/sh/sh.cpp
- **Change:** DRC guards after all CALLH memory ops: CMP icount,0; EXHc LE,out_of_cycles,pc; pre-dec I0=Rn-size before CALLH, SUB after guard (MOVBM/WM/LM, STSMMACH etc); TRAPA/RTE guards; TAS/ANDM/XORM/ORM RMW guards
- **Parents:** Independent DRC implementation using existing MAME UML patterns (sh2_notify_dma_data_available pattern for out_of_cycles). No Ymir/MiSTer DRC code copied (their DRC is different architecture). Concept of abort/retry via icount from MAME's devcpu contract.
- **License:** BSD-3-Clause

### src/mame/sega/saturn_bus.{h,cpp}
- **Change:** Introduce saturn_bus_device arbiter, master/bus enums, flags_to_bus, address_to_flags, flags_to_penalty, request/release, acquire_dma_buses, release_dma_buses, get_cpu_wait with forced retry 1024-10000 for owned bus and device-not-ready, penalty-only <1024 for B_BUS waits
- **Parents:**
  - A-Bus wait formula AnNW+3 from ST-097 §? and ST-210 errata No.09, cross-checked MiSTer A-Bus sequencer (MiSTer a95b085 RTL: A-BUS wait counter AnNW+3+ARWT) — penalty table implemented from MiSTer B_BUS values: VDP1 9/14, VDP2 3/20, SCSP 13/24, SCU 4/8 (MiSTer Saturn_MiSTer/rtl/Saturn/VDP1/VDP1.sv and SCU DMA notes). No Verilog copied, values documented.
  - Deferred transaction model: Ymir SCU bus stall handling (Ymir 6d779960 libs/ymir-core/include/ymir/hw/scu/scu.hpp bus acquire/release) and mednafen SCU DMA bus hog (mednafen f0ee9d59 src/ss/scu.cpp) — independent C++ implementation using std::function ready_cb, not copied.
  - Same-bus indirect allowed vs direct illegal from ST-097 and Ymir notes.
- **License:** BSD-3-Clause, attribution in file header: MiSTer a95b085, Ymir 6d779960, mednafen f0ee9d59, Sega docs.

### src/mame/sega/saturn_scu.cpp / saturn_scu.h
- **Change:** DMA legality, indirect descriptor 20-bit count zero=1MiB, WUP/RUP, held trigger ST-210 No.22, forced stop DSTP, bus arbiter integration (acquire before WAIT->MOVE, release between indirect chunks, release before descriptor fetch, illegal before acquire), hog via steal callbacks, timer edge handling T0 compare zero at VBlank-OUT, T1 zero=512, T1 reload only when stopped, IRQ mask reset to 0xbfff on vector fetch, A-Bus external IRQ ack latch
- **Parents:**
  - Legality: ST-097 §3.2 (A-Bus read-only dest, VDP2 dest-only, SCU reg illegal, same-bus direct illegal) and ST-210 No.01/02/22/30/31/33.
  - Indirect: Ymir DMAReadIndirectTransfer (Ymir 6d779960 libs/ymir-core/src/hw/scu/scu_dma.cpp) — 20-bit count, END flag bit31, index increment 0x0c; mednafen NextIndirect (mednafen f0ee9d59 src/ss/scu.cpp) — same.
  - Arbitration priority Level2>1>0, BK bits, held trigger once: ST-097 and Ymir/Mednafen/MiSTer.
  - Timer: ST-210 No.30/31, Ymir UpdateHBlank, Mednafen SCU_SetHBVB.
  - IRQ: ST-097-R5 figure 3.21 mask reset 0xbfff, mednafen SCU_MSH2VectorFetch, Ymir AcknowledgeExternalInterrupt; IMS15 active-high mask from ST-097 §3.5.
  - A-Bus ASR: ST-097 register table, TB47, MiSTer A-Bus sequencer.
- **License:** BSD-3-Clause, no direct copy, cross-checked.

### src/mame/sega/saturn_dcc.cpp / saturn_dcc.h
- **Change:** MINIT/SINIT 16-bit trigger rule (byte/longword ignored), writer-origin enforcement via executing() check (master for MINIT, slave for SINIT), cache-through aliases 0x21000000/0x21800000 via mirror(0x20000000), quantum workaround for FRT sync
- **Parents:** ST-013? Actually Sega memory-map notes for DCC 16-bit rule, SH7604 FRT wiring for origin, Ymir DCC handling (Ymir 6d779960) cross-checked but independent.
- **License:** BSD-3-Clause

### src/mame/sega/smpc.cpp / smpc.h
- **Change:** Preserve existing: command timing table m_cmd_table_timing usec, INTBACK CONTINUE 700us BREAK cancel, IOSEL/EXLE reset false ST-169 Table 3.1, SR 0x40 always-on, CKCHG 5 ticks with syshalt 3-4 frames, SNDON/SNDOFF controlling 68k RESET not SCSP IPL with last-line tracking, m68k_reset_trigger 100us, RTC cold reset 12/31/93 Fri 23:59:59 and BCD increment with leap-year
- **Parents:** ST-169 (SMPC), ST-077 Figure 1.3 sound RAM map, MiSTer RAM chip select, Ymir CPU mapping for sound RAM alias removal, Sega ST-169 pp.30-31 SCSP reset power-on defaults, mednafen SMPC_SetRTC for RTC init, Ymir m_STE flag for SETTIME.
- **License:** BSD-3-Clause, LGPL-2.1+ historical

### src/mame/sega/saturn.cpp / saturn.h / sat_console.cpp / stv.cpp
- **Change:** Clock tree MASTER_CLOCK_352=14.318181*4, MASTER_CLOCK_320=14.318181*3.75, SH2 /2, SCU /4, DCC 352, VDP2 320, SMPC HLE 4MHz + RTC 1Hz; dot_select_w PLL handling now resets SCU/VDP2 only, NOT SCSP per SYS-CLK01 sound-preservation correction (video clock change must not spuriously reset sound; sound CPU reset via m_sndres line). Preserves AB2/Power Drift/OutRun fixes. CKCHG 5 ticks syshalt qualified. HALT OR-ing via update_halt_lines preserving SMPC halt; fastram BIOS-only for DRC bus fidelity; machine_start no longer forces no-DRC; is_vdp1_cpu_accessible / is_vdp2_cpu_accessible readiness gates via VDP1 drawing/erase state and VDP2 slot check
- **Parents:** Sega schematics, ST-169 (SMPC CKCHG reset of VDP1/VDP2/SCU per manual p.3 and smpc.cpp comment "VDP1, VDP2 and SCU are also reset by this (done in client)"), MiSTer dot-select wiring (a95b085), Ymir clock tree (6d779960), independent correction for SCSP non-reset per task acceptance (AB2 boot/explosions, Power Drift, OutRun flashing fixes preserved).
- **License:** LGPL-2.1+

### src/mame/sega/saturn_vdp2.cpp / saturn.cpp VDP1 section
- **Change:** (Agent B) Hardware-faithful drawing costs, memory arbitration, erase budgets, rotation parameters, etc. — preserved per acceptance.
- **Parents:** ST-013, ST-058, MiSTer a95b085, Ymir 6d779960, mednafen f0ee9d59 — detailed in video.md and game_blockers.md
- **License:** LGPL-2.1+, BSD-3-Clause with attribution

## License Policy
- All new arbiter/bus code is BSD-3-Clause, compatible with MAME.
- MiSTer code is GPL-2.0, not copied verbatim; only wait-state numbers documented and independently implemented.
- Ymir is MIT, can be adapted with attribution; we have not copied verbatim but cross-checked logic.
- Mednafen is GPL-2.0, not copied.
- Sega docs are primary reference, no license issue.

## Reuse vs Independent
- No game-name specific tests or host sleeps introduced (per constraints).
- All cross-device calls via devcb, device_delegate, std::function ready_cb (devices/delegates).
- Penalties from ASR registers or MiSTer documented table, not guessed.

## Outstanding
- Cassini pinning TBD.
- Indirect same-bus quirks (ST-097 says quirks, specifics TBD) still open — currently allows same-bus but does not model quirks.
- B-Bus dynamic ARWT refresh term not modeled (only fixed AnNW+3).
- VDP1/VDP2 readiness granularity per-dot vs per-line still approximate.
