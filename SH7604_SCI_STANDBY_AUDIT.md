# SH7604 SCI DMA and standby implementation

Implemented 2026-10-09 in `src/devices/cpu/sh/sh7604.cpp/.h`, with a common
SLEEP entry hook in `sh.cpp/.h` for interpreter and DRC. This document supersedes
the 2026-10-08 audit-only findings. The checklist item covers SCI DMA request /
acknowledgement and standby entry / exit; it is not closed by documentation alone.

Authority: the local fourth-edition SH7604 hardware manual,
[`saturnsdk/sh7604.pdf`](saturnsdk/sh7604.pdf), September 2001. References are
printed pages; add 16 for PDF page numbers. Relevant sections are 9.2.6/9.3.2
(pp. 242, 247–249), 12.3.3 (p. 328), 13.2.6/13.2.7 (pp. 339–345),
13.4/13.5 (pp. 380, 383), and 14.2–14.5 (pp. 387–393).

## SCI DMA request and acknowledgement

- CHCR.AR overrides DRCR for auto-request. With AR=0, DRCR=1 waits for
  RDRF plus SCR.RIE; DRCR=2 waits for TDRE plus SCR.TIE. Reserved RS=3
  produces no request. CPU interrupt masking/priority does not gate DMA.
- DE/DME/TE/AE/NMIF eligibility remains in the existing DMAC. A SCI channel
  can wait before starting and between transfer units, then resume on the next
  byte event or enable change without restarting its source/destination/count.
- The transfer origin is set only around actual DMA byte reads/writes. DMA
  writes of TDR clear TDRE/TEND; DMA reads of RDR clear RDRF. CPU TDR/RDR
  accesses do not acknowledge these flags, and debugger reads do not qualify
  SSR clears. A cleared/reasserted flag cannot reuse an old read qualification.
- On-chip DMA addresses retain their full address. Applying the external bus
  alias mask to FFFFFE03/FFFFFE05 previously redirected accesses away from SCI.
  Programmer-visible external aliases still survive progress updates.
- SSR bits 7–3 use read-one/write-zero qualification; TEND/MPB are read-only;
  MPBT is writable. TE=0 restores ready/end; RE=0 retains received data/error
  state. The old forced-ready read workaround is replaced with actual status.
- TXI/RXI/ERI/TEI route through IPRB and VCRA/B in the manual's default order
  ERI > RXI > TXI > TEI. Only RXI/TXI can activate SCI DMA.
- The pin engine shifts TSR/RSR with TXD/RXD/SCK callbacks. Asynchronous
  operation supports 7/8 data bits, even/odd parity, one/two stop bits,
  internal baud clocks and external 16x clocks. Start bits are validated at
  their centre; parity/framing/overrun errors block reception until cleared.
  Multiprocessor mode transmits MPBT, records MPB and applies MPIE filtering.
- Synchronous operation supports internal/external SCK and simultaneous TX/RX:
  data changes on falling edges and is sampled on rising edges. Internal SCK
  idles high. The transmitter holds the final MSB after completion.
- Tables 13.3/13.4 supply 128 or 16 system clocks times (BRR+1) times
  4^CKS per bit for asynchronous or synchronous mode. The next TSR byte is
  prefetched when the stop bit/MSB is output; TDRE and TEND follow that event.
  External-clock operation advances only from supplied clock edges.
- Visible registers, shifters, queued byte, bit positions, parity/error state,
  external-clock dividers, physical pin levels and timer phase are saved.
  Post-load redrives output pins. Completed-byte observation remains available;
  receive/completion helpers are private implementation details.

Manual editorial corrections used: RS is in DRCR, not CHCR; the SCI priority
register is IPRB, not the nonexistent IPRC–IPRE references in 9.3.2. The request
sources are RXI/TXI despite the RX2/TX1 spelling in the 9.2.6 note. Table 9.6
specifies cycle-steal for SCI; its general last-transfer burst acknowledgement
sentence does not establish an additional supported SCI burst mode.

## Standby entry, wake and module clocks

- SBYCR.SBY cannot be set while WDT.TME is set. SLEEP with SBY=0 keeps the
  normal sleep path and peripheral clocks running. SLEEP with SBY=1 performs
  table 14.3 initialization **on entry**, then suspends CPU clock execution.
- Both interpreter and DRC call the same entry method. DRC entry timestamps
  include uncharged sequence cycles, so NMI inhibition is based on the actual
  instruction time rather than the start of the scheduler slice.
- Full standby clears FRT registers and TEMP, SCI registers/queue, CHCR0/1 and
  DMAOR, and WDT high control bits/RSTCSR. SAR/DAR/TCR/DRCR, WTCNT/CKS,
  INTC, UBC, BSC and SBYCR retain their existing state. DIVU pending work is
  canceled; its contents are undefined by the standby table. FMR remains the
  pre-existing unofficial clock-control extension; standby does not change it.
- FRT, SCI, WDT, DIVU and DMA timer activity stops. DMA cancellation does not
  leave a burst's CPU HALT behind. A module-stop bit cannot bypass the full
  standby DMA cancellation. External FRT input levels are tracked while stopped
  without producing capture events or a spurious edge on restart.
- Maskable interrupts cannot cancel full standby. The selected physical NMI
  edge is ignored during SLEEP and the following five clocks, then starts the
  WDT-selected settling interval. CPU execution and FRT remain stopped until
  overflow. The wake exception returns to the instruction following SLEEP.
  WTCNT reaches zero at overflow without manufacturing an interval IRQ.
- NMIE selects falling/rising physical edges; ICR.NMIL reflects the physical
  pin level independently. The base SH2 interrupt-assertion interface remains
  separate from the physical pin level.
- Reset cancels standby/wake timers and clears the suspension. CPU clock changes
  reassert standby suspension after the execute interface's normal CLOCK resume,
  so SMPC PLL switching cannot release the CPU prematurely.
- MSTP0/1 initialize and stop SCI/FRT independently, retaining INTC vectors;
  clearing MSTP1 restarts FRT from its initialized state. MSTP4/2 stop/resume
  DMAC/DIVU timers while retaining their state. MULT has no independently
  scheduled activity to cancel; its accumulator/state is retained. As specified
  in 14.5, software must stop modules while idle and must not access stopped
  modules; no invented values are supplied for prohibited accesses.
- HIZ is exported through a standby output callback. CKPREQ low in standby
  asserts CKPACK low; the host can then change/stop its supplied CKIO clock.
  Qualified NMI plus settling releases CKPACK on wake. These signal hooks do
  not synthesize an analog oscillator or alter the clock behind the host's back.
- Standby phase, NMI pin state, module timer remainder and clock-pause state are
  saved. Post-load restores the suspension and redrives HIZ/CKPACK/TXD/SCK. Cache/RAM
  contents that the manual declares undefined do not acquire a fabricated reset
  value; software's disable/purge requirement around standby still applies.

## Verification

Reproduce the actual-method checks:

```sh
python3 scripts/sh7604_register_test.py
python3 scripts/sh7604_sci_standby_test.py
```

The fixtures compile the real C++ methods with ASan/UBSan. They verify SCI IRQ
vectors/order, qualified/RO flags and debugger behavior, CPU-versus-DMA access,
TX queue/bit timing, external clocks and connected synchronous full duplex, RX waits/rearming/payload
on both channels, source/count progress, overrun, auto-request override,
entry initialization/retention, five-cycle inhibition, NMIE polarity, settling,
clock-change suspension, HIZ/CKPACK/post-load outputs and independent module stop.

The real-device suite is portable and runs one emulator at a time at low
priority, with isolated configuration/NVRAM/state directories:

```sh
python3 scripts/sh7604_device_test.py --binary ./saturn \
    --output /private/tmp/sh7604-new-test-run --dma
```

The output directory must not already exist. The harness generates its own tiny
SH2 diagnostic ROM: reset vectors plus a BRA/NOP parking loop. The disabled CD
CPU receives an unused zero-filled placeholder. These are not retail BIOS files;
MAME's expected checksum warnings are intentional. Lua installs the diagnostic
WRAM program and vectors before testing. It uses CURPC for entry so an existing
interpreter branch-delay target is cleared. This suite does not claim BIOS boot.

- `sh7604_power_test.lua`: disabled-TIE DMA wait, CPU-masked TX DMA rearming,
  payload/end state, initialization before NMI, frozen FRT, maskable-wake
  rejection, delayed NMI, restored exception stack, suspended save/load/wake.
- `sh7604_sci_state_test.lua`: queued transmitter plus stalled DMA save/load,
  remaining character time, source progress, byte order and final status.
- `sh7604_pll_test.lua`: actual SMPC CKCHG352 and CKCHG320 through standby,
  entry initialization, stopped FRT, NMI settling and exception-stack restoration.
- `sh7604_reset_test.lua`: reset during NMI settling cancels the wake timer,
  exits standby and restarts CPU/FRT; its persistent guard avoids repeated resets
  when MAME reloads the autoboot script.
- `sh7604_sci_pin_test.lua`: timed GPIO TX/RX format and error tests, external
  asynchronous TX, both RX DMA channels, synchronous full duplex and save/load
  halfway through both synchronous shifters.
- `sh7604_dma_test.lua`: all seven existing full/short burst counts, payload,
  SAR/DAR alias preservation, TCR and TE. Each runs with DRC and interpreter.

The macOS Saturn/ST-V SDL3 build uses:

```sh
make SUBTARGET=saturn SOURCES=src/mame/sega/sat_console.cpp,src/mame/sega/stv.cpp \
    OSD=sdl3 USE_LIBSDL=0 -j2
```

Real-ROM smoke runs before the ROM drive disconnected: VF Remix and Die Hard
Arcade each ran for 62 emulated seconds with isolated settings. Frame 3600
pictures show VF Remix's title and Die Hard's attract fight. These are startup /
attract checks, not a claim of full-library, audio or hardware conformance.

Final validation on 2026-10-09: both actual-method ASan/UBSan fixtures pass;
the macOS Saturn/ST-V SDL3 build passes; all **24 real-device cases pass**
(12 per core), including timed pin I/O and mid-character save/load.
Logs and isolated state files: `/private/tmp/sh7604-full-engine-final`.
Checklist/source inventory consistency and whitespace checks pass.
