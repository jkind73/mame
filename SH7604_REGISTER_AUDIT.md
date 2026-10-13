# SH7604 on-chip register audit

Audited 2026-10-08 against `saturnsdk/sh7604.pdf`, fourth edition,
September 2001: Appendix B.1/B.2, printed pages 565–614 (PDF pages
581–630), with chapters 5–14 resolving access and state transitions.
The active implementation is `src/devices/cpu/sh/sh7604.cpp` and its
cache model. The separate `sh7604_sci_device`, `sh7604_bus_device` and
`sh7604_wdt_device` are not instantiated by this CPU; their handlers do
not establish conformance of the active CPU.

**The audit is complete; the peripheral implementation is not compliant.**
Follow-up repairs on 2026-10-08 close the FRT TEMP interface, DMAC visible progress/qualified flag clears/reserved-bit storage, and RTCSR qualified CMF clears. The 2026-10-09 SCI DMA/standby implementation is detailed in `SH7604_SCI_STANDBY_AUDIT.md` and supersedes those original FAIL/Missing verdicts. The serial pin/bit engine and UBC are implemented; the refresh engine is now implemented and verified by `SH7604_MODULE_RECONCILIATION.md` (2026-10-11).

There are 68 named registers, counting OCRA/B and both DMA channels separately,
at 67 distinct starting addresses. The eleven originally missing UBC register mappings are implemented in the 2026-10-09 follow-up.
The matrix below covers every named register, including aliases and reserved
regions separately. “Matches” means the inspected map/storage/read-back rule
matches the manual, not that peripheral timing has been verified on hardware.
All widths are in bits; hexadecimal addresses and masks omit the `0x` prefix.
Undefined power-on values are not treated as failures when initialized to zero.

## Historical SCI findings (superseded by the 2026-10-09 implementation) — Appendix B pp. 574–578; chapter 13

| Register | Address | Legal access | Read-back / reset | Active implementation verdict |
|---|---|---|---|---|
| SMR | FFFFFE00 | 8 R/W | FF mask / 00 | Address/storage match; format and clock controls have no serial behavior. |
| BRR | FFFFFE01 | 8 R/W | FF / FF | Storage/reset match; baud generator absent. |
| SCR | FFFFFE02 | 8 R/W | FF / 00 | Storage/reset match; enable, clock, interrupt and MPIE transitions absent. |
| TDR | FFFFFE03 | 8 R/W | FF / FF | Storage/reset match; TSR transfer, queue and DMA acknowledgement absent. |
| SSR | FFFFFE04 | 8 R/W, qualified flags | Reset 84; bits 7–3 read-one/write-zero; bits 2–1 RO; bit 0 R/W | FAIL: read forces 84, write replaces every bit without read qualification. |
| RDR | FFFFFE05 | 8 R only | FF / 00 | Address/RO match; returns constant zero, no received-data storage. |

### Historical SCI state-machine audit (superseded by the 2026-10-09 implementation) — 13.2.1–13.2.8, 13.3.1–13.3.4

| Event / mode | Required hardware behavior | Active CPU |
|---|---|---|
| Reset / standby / module standby | SMR=00, BRR=FF, SCR=00, TDR=FF, SSR=84, RDR=00; shift state reset. | Reset and full-standby stored values match; no shift state; module-stop behavior missing. |
| CPU queues transmit byte | Store TDR; read TDRE=1 then write TDRE=0 makes data valid and clears TEND. Writing TDR alone is not the CPU flag-clear sequence. | Data stored; SSR sequence missing and read forces TDRE/TEND high. |
| TDR moves to TSR | TDRE becomes 1; transmit continues for the selected frame duration; next byte can be queued while TSR shifts. | No TSR, transfer event or bit scheduling. |
| Last transmitted bit | Set TEND if TDRE=1; otherwise continue with queued data. | No completion event. |
| TE becomes 0 | Stop transmitter and restore TDRE/TEND=1; observe initialization/re-enable rules. | SCR storage only. |
| Successful receive | Sample RXD/start/data/parity/stop as configured, RSR→RDR, RDRF=1. CPU reads RDR, then uses qualified SSR clear. | No RXD/RSR/data storage or RDRF event. |
| RE becomes 0 | Stop receiver; **retain** RDR, RDRF, ORER, FER, PER and MPB (13.2.7). | No receiver; existing data/error states cannot be represented correctly. |
| Receive overrun | Existing RDRF=1 at receive completion sets ORER; retain old RDR, discard new character; reception blocked until error cleared. | Missing. |
| Parity / framing error | Set PER/FER; transfer receive data to RDR without setting RDRF. For two stop bits, only the first is checked. Preserve error until qualified clear. | Missing. |
| SSR CPU write | Bits 7–3 cannot be set by software; clear only after a side-effecting read observed 1. TEND/MPB cannot be overwritten; MPBT writable. | All bits overwritten, no read latch. Debugger reads would need to avoid arming clears. |
| TXI / RXI / ERI / TEI | Apply SCR enables, flag conditions and INTC priority/vector routing (VCRA/B, IPRB); honor source ordering. | `sh2_recalc_irq` omits all SCI sources. |
| DMA transmit / receive | DRCR selects TXI/RXI; DMA TDR write clears TDRE/TEND, DMA RDR read clears RDRF. CPU accesses have different flag semantics. | DRCR bits stored; requests/acknowledgements absent. |
| Asynchronous format | 7/8 bits, even/odd optional parity, 1/2 stop bits, internal/external clock selection and start-bit sampling. | SMR/SCR storage only. |
| Multiprocessor format | Send MPBT; capture MPB; MPIE filters data characters, address character releases wait according to 13.3.3. | Missing. |
| Clocked synchronous format | Eight-bit synchronous shifting with internal/external SCK, simultaneous transmission/reception and specified error behavior. | Missing. |
| BRR / CKS / CKE setup | Baud timing and initialization delay from 13.2.8 and 13.3; changing modes follows documented initialization procedure. | No baud timing or serial pins/callbacks. |
| Save/restore during character | Preserve shifters, remaining bit phase, queued byte, receive/error state and read-qualified flags. | Only five visible SCI storage bytes saved; no engine exists. |

Do not replace the forced-ready SSR workaround with instant “successful”
transmission. A conforming repair needs the serial engine, status transitions,
interrupts and DMA distinction together, with pin/bit-time fixtures. The unused
SCI subdevice is also a stub (enabling TX/RX is fatal), not a ready replacement.

## FRT — Appendix B pp. 579–582; chapter 11

| Register | Address | Legal access | Read-back / reset | Verdict |
|---|---|---|---|---|
| TIER | FFFFFE10 | 8 R/W | Writable 8E, bit 0 fixed 1 / 01 | FIXED reserved-bit read-back/write storage; IRQ enables present. |
| FTCSR | FFFFFE11 | 8 R/W | Flags 8E qualified clear, CCLRA bit 0 R/W / 00 | FIXED bits 6–4; existing read-qualified flags retained. Timer flag timing, recurring compares/clear, overflow and write-contention priorities implemented and tested. |
| FRC | FFFFFE12 | Ordered high/low 8-bit operations | FFFF / 0000 | FIXED shared TEMP: high write latches, low write commits; high read captures low byte. |
| OCRA | FFFFFE14, TOCR.OCRS=0 | Ordered high/low 8-bit operations | FFFF / FFFF | FIXED shared write TEMP; selection matches. OCR reads bypass TEMP as specified in 11.3. |
| OCRB | FFFFFE14, TOCR.OCRS=1 | Ordered high/low 8-bit operations | FFFF / FFFF | Same as OCRA. Chapter 11.2.2 specifies FFFF for reset, standby and module stop; the old reset-to-zero implementation is corrected. |
| TCR | FFFFFE16 | 8 R/W | 83 / 00 | Internal/external counting, retained prescaler phase and clock-switch edges implemented and tested. |
| TOCR | FFFFFE17 | 8 R/W | Writable 13, fixed E0 / E0 | FTOA/FTOB callbacks and saved output levels implemented; OLVL changes apply at the next match. |
| FICR | FFFFFE18 | Ordered high/low 8-bit reads | FFFF / 0000 | FIXED atomic low-byte TEMP read; capture input/edge selection and one-drive-clock ICR-read collision deferral implemented. |

Chapter 11.3 explicitly shares an 8-bit TEMP across FRC/OCR/FICR. A high
write stores TEMP, a low write commits the full word; a high FRC/FICR read
latches the low byte. OCRA/B reads are the documented exception. The updated
16-bit handlers use lane masks to supply these semantics, and debugger reads do not change TEMP. Native word accesses
are not the documented software sequence. The 2026-10-09 FRT implementation
fixes external counting, compare outputs and the related counter/timing defects;
see [`SH7604_FRT_IMPLEMENTATION.md`](SH7604_FRT_IMPLEMENTATION.md).

## INTC — Appendix B pp. 583–587; chapter 5 and 9.2.5/10.2.4

| Register | Address | Legal access | Read-back / reset | Verdict |
|---|---|---|---|---|
| IPRB | FFFFFE60 | 8/16 R/W | FF00 / 0000 | Masks/priority storage match; SCI priority has no producer. |
| VCRA | FFFFFE62 | 8/16 R/W | 7F7F / 0000 | Mask/storage match; SCI ERI/RXI routing absent. |
| VCRB | FFFFFE64 | 8/16 R/W | 7F7F / 0000 | Mask/storage match; SCI TXI/TEI routing absent. |
| VCRC | FFFFFE66 | 8/16 R/W | 7F7F / 0000 | Masks and FRT capture/compare vectors match. |
| VCRD | FFFFFE68 | 8/16 R/W | 7F00 / 0000 | Mask and FRT overflow vector match. |
| ICR | FFFFFEE0 | 8/16 R/W | NMIL RO bit 15, writable 0101 / input level | Read-back reports physical NMI level, correct per B.2; nearby “flip meaning” TODO is misleading. NMIE selects edge, not NMIL inversion. |
| IPRA | FFFFFEE2 | 8/16 R/W | FFF0 / 0000 | Masks and DIVU/DMAC/WDT priorities match. |
| VCRWDT | FFFFFEE4 | 8/16 R/W | 7F7F / 0000 | WDT and BSC compare-match vectors routed to their active interrupt sources; shared priority and WDT tie precedence. |
| VCRDIV | FFFFFF0C | 16/32 R/W | B.2 lower 16 R/W; vector uses 7 bits / undefined | Retain lower-sixteen read-back: B.2/10.2.4 charts and YabauseUT’s 0102 write/read expectation agree; vector uses seven bits. Contradictory prose documented in SH7604_DIVU_REGISTER_EVIDENCE.md; no new hardware measurement. |
| VCRDMA0 | FFFFFFA0 | 32 R/W | Low 8 R/W; software must write VC7=0 / undefined low byte | Implementation masks to 7F; legal 0–127 vectors match. VC7 read-back after prohibited write is not evidence for a safe fix. |
| VCRDMA1 | FFFFFFA8 | 32 R/W | Same as VCRDMA0 | Same verdict. |

Narrow INTC accesses use MAME lane masks. Other handlers often also accept
widths not specified by the manual. Such accesses do not establish a documented
return value; no generic zero/open-bus rule is invented in this audit.

## WDT, standby and cache — Appendix B pp. 588–589, 613–614

| Register | Read / write address | Legal access | Read-back / reset | Verdict |
|---|---|---|---|---|
| WTCSR | FFFFFE80 / FFFFFE80 | 8 R; 16 W, A5 key | Bits 4–3 fixed 1; OVF qualified clear / 18 | FIXED atomic keyed word access. Interval/watchdog scheduling and flag qualifiers present. |
| WTCNT | FFFFFE81 / FFFFFE80 | 8 R; 16 W, 5A key | FF / 00 | FIXED atomic key; count read resynchronization present. |
| RSTCSR | FFFFFE83 / FFFFFE82 | 8 R; 16 W, A5 flag / 5A control key | Low 5 bits fixed 1, high E0 / 1F | FIXED atomic key; WOVF qualified clear and controls present. |
| SBYCR | FFFFFE91 | 8 R/W | DF / 00 | FIXED reserved bit 5. Entry initialization, clock halt, NMI settling, module stop and HIZ/CKPACK implemented and verified; see `SH7604_SCI_STANDBY_AUDIT.md`. |
| CCR | FFFFFE92 | 8 R/W | CF on read; CP bit 4 write-only, bit 5 reserved / 00 | `write_ccr` masks reserved/CP, executes purge and stores other bits; matches inspected rules. Cache arrays are outside Appendix B register inventory. |

WDT write protection is per bus transaction; two byte writes cannot assemble a
valid key. The fixture exercises a stale prior key and both byte orders. WDT's
own reset preserves RSTCSR as chapter 12 requires; power/manual reset and
standby remain distinct. Register flags being implemented is not proof of
every watchdog timing edge.

## DIVU — Appendix B pp. 590–592; chapter 10

| Register | Address | Legal access | Read-back / reset | Verdict |
|---|---|---|---|---|
| DVSR | FFFFFF00 | 32 R/W | FFFFFFFF / undefined | Map/storage match chapter 10 and B.1; B.2's FFFFFE00 is a misprint (SCI conflict). |
| DVDNT | FFFFFF04 | 32 R/W | Quotient on read; dividend write starts 32/32 division / undefined | Start/wait/result handlers present; not a plain storage register. B.2 FFFFFE04 misprint. |
| DVCR | FFFFFF08 | 16/32 R/W | 00000003 / 00000000 | OVF/OVFIE writable; reserved read bits zero; completion waits/IRQ present. |
| DVDNTH | FFFFFF10 | 32 R/W | Remainder on read; high dividend storage / undefined | Matches inspected start/result behavior. |
| DVDNTL | FFFFFF14 | 32 R/W | Quotient on read; low write starts 64/32 division / undefined | Matches inspected start/result behavior. |

The existing model schedules 39/6 cycles and stalls accesses while busy. The
extra read-after-write cycle from 10.4.1 remains a separately tracked hardware
question. This audit does not revalidate arithmetic timing. VCRDIV is in the
INTC table above to avoid double-counting.

## UBC — Appendix B pp. 593–601; chapter 6

| Register | Address | Legal access | Read-back / reset | Verdict |
|---|---|---|---|---|
| BARAH | FFFFFF40 | 16/32 R/W | FFFF / 0000 | Implemented address comparison; longword access spans AH/AL. |
| BARAL | FFFFFF42 | 16 R/W | FFFF / 0000 | Implemented address comparison. |
| BAMRAH | FFFFFF44 | 16/32 R/W | FFFF / 0000 | Implemented with the listed width/mask and chapter-6 comparison semantics. |
| BAMRAL | FFFFFF46 | 16 R/W | FFFF / 0000 | Implemented with the listed width/mask and chapter-6 comparison semantics. |
| BBRA | FFFFFF48 | 16/32 R/W | 00FF / 0000 | Implemented with the listed width/mask and chapter-6 comparison semantics. |
| BARBH | FFFFFF60 | 16/32 R/W | FFFF / 0000 | Implemented channel B address comparison. |
| BARBL | FFFFFF62 | 16 R/W | FFFF / 0000 | Implemented address comparison. |
| BAMRBH | FFFFFF64 | 16/32 R/W | FFFF / 0000 | Implemented with the listed width/mask and chapter-6 comparison semantics. |
| BAMRBL | FFFFFF66 | 16 R/W | FFFF / 0000 | Implemented with the listed width/mask and chapter-6 comparison semantics. |
| BBRB | FFFFFF68 | 16/32 R/W | 00FF / 0000 | Implemented with the listed width/mask and chapter-6 comparison semantics. |
| BDRBH | FFFFFF70 | 16/32 R/W | FFFF / 0000 | Implemented with the listed width/mask and chapter-6 comparison semantics. |
| BDRBL | FFFFFF72 | 16/32 R/W (B.2) | FFFF / 0000 | Implemented lower data halfword; paired longwords follow the big-endian bus lanes. |
| BDMRBH | FFFFFF74 | 16/32 R/W | FFFF / 0000 | Implemented with the listed width/mask and chapter-6 comparison semantics. |
| BDMRBL | FFFFFF76 | 16 R/W | FFFF / 0000 | Implemented with the listed width/mask and chapter-6 comparison semantics. |
| BRCR | FFFFFF78 | 16/32 R/W | F4DC / 0000 | Implemented flags, mode/sequencing/data controls and fixed-priority vector-12 exceptions. |

Implemented 2026-10-09: CPU instruction/data and on-chip DMA comparisons,
external bus monitoring, address/data masks, independent/sequential channels,
SH7000 compatibility, before/after exceptions and deferred masked requests.
Three-cycle setting latency, dummy-read synchronization, fetch-pair snapshots,
save/load and reset retention are verified. Full standby stops the UBC clock.
See [`SH7604_UBC_IMPLEMENTATION.md`](SH7604_UBC_IMPLEMENTATION.md) for the
implementation and reproducible validation.

## DMAC — Appendix B pp. 602–606; chapter 9

| Register | Address | Legal access | Read-back / reset | Verdict |
|---|---|---|---|---|
| SAR0 | FFFFFF80 | 32 R/W | FFFFFFFF / undefined | FIXED visible progress after each completed unit, preserving original alias bits. |
| DAR0 | FFFFFF84 | 32 R/W | FFFFFFFF / undefined | FIXED visible destination progress after each completed unit. |
| TCR0 | FFFFFF88 | 32 R/W | 00FFFFFF / undefined | FIXED remaining count follows each completed unit; 24-bit mask retained. |
| CHCR0 | FFFFFF8C | 32 R/W | 0000FFFF; TE read-one/write-zero / 00000000 | FIXED upper reserved bits/read mask, read-qualified TE clear and lane preservation. |
| SAR1 | FFFFFF90 | 32 R/W | FFFFFFFF / undefined | Same as SAR0. |
| DAR1 | FFFFFF94 | 32 R/W | FFFFFFFF / undefined | Same as DAR0. |
| TCR1 | FFFFFF98 | 32 R/W | 00FFFFFF / undefined | Same as TCR0. |
| CHCR1 | FFFFFF9C | 32 R/W | 0000FFFF; TE qualified clear / 00000000 | Same as CHCR0. |
| DRCR0 | FFFFFE71 | 8 R/W | 03 / 00 | Mask matches; SCI RXI/TXI request selection and acknowledgement implemented. External pin level/edge selection, DACK and arbitration are implemented and tested. |
| DRCR1 | FFFFFE72 | 8 R/W | 03 / 00 | Same as DRCR0. |
| DMAOR | FFFFFFB0 | 32 R/W | 0000000F / 00000000 | FIXED qualified AE/NMIF clears and transfer inhibition when either flag is set; AE generation, NMI inhibition, external/SCI request selection and channel priority implemented and tested. |

The active controller gates grants on AR/DRCR and the selected physical DREQ
level/edge. Alignment and illegal on-chip widths raise AE before erroneous
payload accesses; NMI inhibits new grants. Single-address input/output and
DACK phase/polarity use real peripheral callbacks. A shared owner implements
fixed/cycle-steal/burst and retained round-robin priority. Accepted valid units
finish before abort; TE follows the final-unit conditions in 9.3.8.
Active requests, payload/beat state, priority, pins and deadlines are saved.
Both-core connected-device regressions, full Saturn device regressions and
actual-method ASan/UBSan fixtures pass. See
[`SH7604_DMAC_IMPLEMENTATION.md`](SH7604_DMAC_IMPLEMENTATION.md) for interfaces,
request timing, arbitration, save/load and validation evidence. No hardware
measurement validates the absolute bus-cost model.
VCRDMA0/1 are counted in INTC above.

## BSC — Appendix B pp. 607–612; 7.1.4 and 7.2

| Register | Address | Legal access | Read-back / power reset | Verdict |
|---|---|---|---|---|
| BCR1 | FFFFFFE0 | 32 R/W; 16 R at E2 | Writable 1FF7, MASTER RO 8000 / 03F0 + MASTER | FIXED keyed-write width and reserved/upper read-back. MASTER driven by CPU configuration. |
| BCR2 | FFFFFFE4 | 32 R/W; 16 R at E6 | 00FC / 00FC | FIXED key/width and reserved bits. |
| WCR | FFFFFFE8 | 32 R/W; 16 R at EA | FFFF / AAFF | FIXED key/width and upper-word read-back. |
| MCR | FFFFFFEC | 32 R/W; 16 R at EE | FEFC / 0000 | FIXED key/width and reserved/upper read-back. |
| RTCSR | FFFFFFF0 | 32 R/W; 16 R at F2 | 00F8; CMF qualified clear / 0000 | FIXED key/width and read-qualified CMF clears (software cannot set CMF); refresh clock, CMF and CMI implemented. |
| RTCNT | FFFFFFF4 | 32 R/W; 16 R at F6 | 00FF / 0000 | FIXED key/width; seven clock divisors, eight-bit count/wrap, compare/clear, standby and saved phase implemented. |
| RTCOR | FFFFFFF8 | 32 R/W; 16 R at FA | 00FF / 0000 | FIXED key/width; refresh compare/reset implemented and tested. |

All seven registers accept writes only as a single 32-bit transaction with
upper word A55A; the key is never readable. Manual reset retains these registers.
The Saturn driver supplies external bus costs; BCR/WCR/MCR storage is not a
complete implementation of the programmable generic SH7604 memory interfaces,
bus-size selection or DRAM/SDRAM refresh/arbitration. CS2 endian conversion is
implemented and tested as documented in SH7604_BSC_REMAINDER_AUDIT.md (2026-10-13).

## Reserved regions, extra mappings and documentation conflicts

- Appendix B.1 lists reserved gaps through the on-chip region. No extra named
  Appendix B register was omitted from the matrix. Reserved holes are unmapped
  except the following existing extensions; their read value is not assumed to
  be zero merely because reserved named-register bits read zero.
- FMR at FFFFFE90: documented in section 3.3.2/table 3.6, printed pp.55–56,
  despite Appendix B's omission. Mapping corroborated; the existing handler
  only logs frequency changes. No clock engine is claimed by this evidence item.
- DVDNTUH/DVDNTUL result copies at FFFFFF18/1C and FFFFFF38/3C:
  YabauseUT requires writable storage and division-result replacement.
  Implemented as saved writable copies; all DIVU +20 register aliases mapped.
  See SH7604_DIVU_REGISTER_EVIDENCE.md for evidence and hardware limits.
- B.1's FRC/OCR address labels are displaced in the printed table. B.2 and
  chapter 11 agree on FRC FE12/13, OCRA/B FE14/15, TCR FE16. Those addresses
  match the code; the malformed overview is not grounds to remap them.
- B.2 misprints DVSR/DVDNT as FFFFFE00/04. Chapter 10 and B.1 use FFFFFF00/04.
- VCRDIV read-back follows the sixteen-bit charts, corroborated by YabauseUT
  requiring 0102 read-back. The prose conflict is resolved as an implementation
  decision, not represented as a new hardware experiment.
- VCRDMA's chart includes VC7, but 9.2.5 forbids setting it. Legal vector range
  is 0–127. The existing 7F mask agrees for all permitted writes.
- ICR.NMIL reflects pin level, independent of edge selection. The source TODO
  suggesting inversion is not supported by the manual's register chart.

## Validation and limits

`python3 scripts/sh7604_register_test.py` compiles extracted **actual** methods
with Clang ASan/UBSan. It checks all seven BSC key/width/read-mask rules,
master/slave MASTER read-back, all 256 write values for TIER/FTCSR/SBYCR,
FTCSR qualified clears, and WDT stale-key/byte-write rejection. Scheduling is
stubbed deliberately; this is not a peripheral timing or CPU bus-dispatch test.
The original mask/key fixture compiled against the pre-audit revision and failed an assertion; later interface tests use the updated method signatures.

macOS build passes with the user's Saturn/ST-V source selection and SDL3 (`OSD=sdl3 USE_LIBSDL=0 -j2`).
One isolated, low-priority VF Kids run (`-seconds_to_run 3`, video/sound off)
exits successfully; this is an initialization smoke test, not gameplay coverage.
Missing engines identified here are follow-up implementation tasks, not
failures of the audit process and not marked complete in the checklist.
No hardware test, complete SCI transmission test, full-library sweep or illegal
access-width bus-value measurement is claimed.

Follow-up fixture coverage: actual FRT methods test rollover between byte reads,
shared TEMP between counter/capture/compare accesses, deferred high writes,
OCR selection and debugger noninterference. Both DMAC channels test reserved
bits, software attempts to set TE, qualified clears and lane preservation.
DMAOR AE/NMIF and RTCSR CMF test read-qualified clears and debugger reads.
All new latch state is registered for save states; DMAC clear state resets in
standby, RTCSR clear state follows BSC power/manual reset retention.
The real-device Lua fixture `scripts/sh7604_dma_test.lua` verifies a longword
auto-request transfer, payload, final SAR/DAR alias preservation, TCR and TE.
It also verifies full/short 16-byte bursts (9.3.8): all four source words are fetched, but only the remaining count is written; count is no longer rounded down. The bus-cost helper charges the actual number of destination writes.
It isolates CPU execution in an IRQ-masked WRAM loop; it is not a game test.

Final follow-up validation: macOS Saturn/ST-V SDL3 build passes; sanitizer
register fixture passes; burst counts 1–7 pass in all 14 real-device runs
(interpreter and DRC, sequentially), with untouched destination guards. A final
isolated 20-second VF Kids run exits normally with video/audio output disabled.
These checks do not establish long-run/gameplay/audio or hardware timing parity.

SCI DMA and standby implementation follow-up (2026-10-09): [`SH7604_SCI_STANDBY_AUDIT.md`](SH7604_SCI_STANDBY_AUDIT.md) documents implemented request/acknowledgement and power-down transitions. Its pin engine, SCI status/IRQ/DMA and standby implementation supersedes the historical SCI and standby failure verdicts in this audit.


BSC follow-up 2026-10-11: refresh register sampling now includes pending DRC
sequence cycles, with actual-method interpreter/DRC boundary and no-double-count
regressions. The remaining generic BCR/WCR/MCR effects are enumerated in
SH7604_BSC_REMAINDER_AUDIT.md; the original broader item remains incomplete.
