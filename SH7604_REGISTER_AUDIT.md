# SH7604 on-chip register audit

Audited 2026-10-08 against `saturnsdk/sh7604.pdf`, fourth edition,
September 2001: Appendix B.1/B.2, printed pages 565–614 (PDF pages
581–630), with chapters 5–14 resolving access and state transitions.
The active implementation is `src/devices/cpu/sh/sh7604.cpp` and its
cache model. The separate `sh7604_sci_device`, `sh7604_bus_device` and
`sh7604_wdt_device` are not instantiated by this CPU; their handlers do
not establish conformance of the active CPU.

**The audit is complete; the peripheral implementation is not compliant.**
There are 68 named registers, counting OCRA/B and both DMA channels separately,
at 67 distinct starting addresses. Eleven UBC registers are unmapped.
The matrix below covers every named register, including aliases and reserved
regions separately. “Matches” means the inspected map/storage/read-back rule
matches the manual, not that peripheral timing has been verified on hardware.
All widths are in bits; hexadecimal addresses and masks omit the `0x` prefix.
Undefined power-on values are not treated as failures when initialized to zero.

## SCI — Appendix B pp. 574–578; chapter 13

| Register | Address | Legal access | Read-back / reset | Active implementation verdict |
|---|---|---|---|---|
| SMR | FFFFFE00 | 8 R/W | FF mask / 00 | Address/storage match; format and clock controls have no serial behavior. |
| BRR | FFFFFE01 | 8 R/W | FF / FF | Storage/reset match; baud generator absent. |
| SCR | FFFFFE02 | 8 R/W | FF / 00 | Storage/reset match; enable, clock, interrupt and MPIE transitions absent. |
| TDR | FFFFFE03 | 8 R/W | FF / FF | Storage/reset match; TSR transfer, queue and DMA acknowledgement absent. |
| SSR | FFFFFE04 | 8 R/W, qualified flags | Reset 84; bits 7–3 read-one/write-zero; bits 2–1 RO; bit 0 R/W | FAIL: read forces 84, write replaces every bit without read qualification. |
| RDR | FFFFFE05 | 8 R only | FF / 00 | Address/RO match; returns constant zero, no received-data storage. |

### SCI state-machine audit — 13.2.1–13.2.8, 13.3.1–13.3.4

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
| FTCSR | FFFFFE11 | 8 R/W | Flags 8E qualified clear, CCLRA bit 0 R/W / 00 | FIXED bits 6–4; existing read-qualified flags retained. Timer flag timing needs separate tests. |
| FRC | FFFFFE12 | Ordered high/low 8-bit operations | FFFF / 0000 | FAIL: word handler merges bytes directly; no shared TEMP; high-byte writes take effect too soon, low-byte reads are live. |
| OCRA | FFFFFE14, TOCR.OCRS=0 | Ordered high/low 8-bit operations | FFFF / 0000 | Selection matches; FAIL write TEMP absent. OCR reads bypass TEMP as specified in 11.3. |
| OCRB | FFFFFE14, TOCR.OCRS=1 | Ordered high/low 8-bit operations | FFFF / 0000 | Same as OCRA. Full standby value FFFF is distinct from reset 0000. |
| TCR | FFFFFE16 | 8 R/W | 83 / 00 | Mask/internal dividers match; external-clock counting is TODO. |
| TOCR | FFFFFE17 | 8 R/W | Writable 13, fixed E0 / E0 | Mask/OCR bank match; output levels/pins not implemented. |
| FICR | FFFFFE18 | Ordered high/low 8-bit reads | FFFF / 0000 | Capture input/edge selection present; FAIL atomic low-byte TEMP read missing. |

Chapter 11.3 explicitly shares an 8-bit TEMP across FRC/OCR/FICR. A high
write stores TEMP, a low write commits the full word; a high FRC/FICR read
latches the low byte. OCRA/B reads are the documented exception. The current
16-bit handler declarations do not supply these semantics. Native word accesses
are not the documented software sequence. External counting and output compare
pins remain implementation gaps, independent of masks fixed here.

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
| VCRWDT | FFFFFEE4 | 8/16 R/W | 7F7F / 0000 | WDT vector used; BSC compare-match vector stored but no refresh IRQ source. |
| VCRDIV | FFFFFF0C | 16/32 R/W | B.2 lower 16 R/W; vector uses 7 bits / undefined | Lower-word read-back matches B.2; chapter 10.2.4 separately says bits 31–7 read zero. Conflict retained for hardware verification. |
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
| SBYCR | FFFFFE91 | 8 R/W | DF / 00 | FIXED reserved bit 5. NMI wake applies full-standby initialization; entry/clock halt and individual MSTP/HIZ behavior need audit. |
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
| BARAH | FFFFFF40 | 16/32 R/W | FFFF / 0000 | Mapped storage only; 32-bit address access spans AH/AL; no break engine. |
| BARAL | FFFFFF42 | 16 R/W | FFFF / 0000 | Mapped storage only. |
| BAMRAH | FFFFFF44 | 16/32 R/W | FFFF / 0000 | UNMAPPED. |
| BAMRAL | FFFFFF46 | 16 R/W | FFFF / 0000 | UNMAPPED. |
| BBRA | FFFFFF48 | 16/32 R/W | 00FF / 0000 | UNMAPPED. |
| BARBH | FFFFFF60 | 16/32 R/W | FFFF / 0000 | Mapped storage only; no break engine. |
| BARBL | FFFFFF62 | 16 R/W | FFFF / 0000 | Mapped storage only. |
| BAMRBH | FFFFFF64 | 16/32 R/W | FFFF / 0000 | UNMAPPED. |
| BAMRBL | FFFFFF66 | 16 R/W | FFFF / 0000 | UNMAPPED. |
| BBRB | FFFFFF68 | 16/32 R/W | 00FF / 0000 | UNMAPPED. |
| BDRBH | FFFFFF70 | 16/32 R/W | FFFF / 0000 | UNMAPPED. |
| BDRBL | FFFFFF72 | 16/32 R/W (B.2) | FFFF / 0000 | UNMAPPED; preserve B.2's listed size pending chapter/bus verification. |
| BDMRBH | FFFFFF74 | 16/32 R/W | FFFF / 0000 | UNMAPPED. |
| BDMRBL | FFFFFF76 | 16 R/W | FFFF / 0000 | UNMAPPED. |
| BRCR | FFFFFF78 | 16/32 R/W | F4DC / 0000 | UNMAPPED: CPU/peripheral match flags, sequencing, data compare, interrupt controls absent. |

Full UBC repair needs CPU and peripheral bus comparisons, instruction/data
cycle qualifiers, address/data masks, channel sequencing and user-break
exceptions. Mapping dummy storage alone would leave the audit failures open.
Manual reset retains UBC, while power-on reset initializes it (4.2.3).

## DMAC — Appendix B pp. 602–606; chapter 9

| Register | Address | Legal access | Read-back / reset | Verdict |
|---|---|---|---|---|
| SAR0 | FFFFFF80 | 32 R/W | FFFFFFFF / undefined | Storage/map match; FAIL live progress: active source advances separately, SAR not updated. |
| DAR0 | FFFFFF84 | 32 R/W | FFFFFFFF / undefined | Storage/map match; active destination not reflected. |
| TCR0 | FFFFFF88 | 32 R/W | 00FFFFFF / undefined | Mask matches; FAIL remaining count not reflected until completion sets zero. |
| CHCR0 | FFFFFF8C | 32 R/W | 0000FFFF; TE read-one/write-zero / 00000000 | FAIL upper reserved bits retained/read; TE clears without read qualification. Partial writes overwrite other lanes. |
| SAR1 | FFFFFF90 | 32 R/W | FFFFFFFF / undefined | Same as SAR0. |
| DAR1 | FFFFFF94 | 32 R/W | FFFFFFFF / undefined | Same as DAR0. |
| TCR1 | FFFFFF98 | 32 R/W | 00FFFFFF / undefined | Same as TCR0. |
| CHCR1 | FFFFFF9C | 32 R/W | 0000FFFF; TE qualified clear / 00000000 | Same as CHCR0. |
| DRCR0 | FFFFFE71 | 8 R/W | 03 / 00 | Mask matches; external/SCI request selection not implemented by transfer starter. |
| DRCR1 | FFFFFE72 | 8 R/W | 03 / 00 | Same as DRCR0. |
| DMAOR | FFFFFFB0 | 32 R/W | 0000000F / 00000000 | Read mask matches; NMIF qualified clear missing, AE not generated for alignment faults; starter ignores NMIF/AE and request mode. |

`sh2_dmac_check` starts when DE/DME allow, without waiting for DRCR/AR
request selection; misaligned addresses are rounded instead of setting AE.
The active source/destination/count fields are separate from programmer-visible
registers. Existing DMAC bus timing does not resolve these state-machine gaps.
Round-robin PR and external handshake/single-address details also need
implementation-level validation; no conformance claim is made for them.
VCRDMA0/1 are counted in INTC above.

## BSC — Appendix B pp. 607–612; 7.1.4 and 7.2

| Register | Address | Legal access | Read-back / power reset | Verdict |
|---|---|---|---|---|
| BCR1 | FFFFFFE0 | 32 R/W; 16 R at E2 | Writable 1FF7, MASTER RO 8000 / 03F0 + MASTER | FIXED keyed-write width and reserved/upper read-back. MASTER driven by CPU configuration. |
| BCR2 | FFFFFFE4 | 32 R/W; 16 R at E6 | 00FC / 00FC | FIXED key/width and reserved bits. |
| WCR | FFFFFFE8 | 32 R/W; 16 R at EA | FFFF / AAFF | FIXED key/width and upper-word read-back. |
| MCR | FFFFFFEC | 32 R/W; 16 R at EE | FEFC / 0000 | FIXED key/width and reserved/upper read-back. |
| RTCSR | FFFFFFF0 | 32 R/W; 16 R at F2 | 00F8; CMF qualified clear / 0000 | FIXED key/width; FAIL CMF software set/clear permissions and refresh IRQ/timer absent. |
| RTCNT | FFFFFFF4 | 32 R/W; 16 R at F6 | 00FF / 0000 | FIXED key/width; FAIL refresh-clock count and compare not implemented. |
| RTCOR | FFFFFFF8 | 32 R/W; 16 R at FA | 00FF / 0000 | FIXED key/width; constant stored but no refresh compare. |

All seven registers accept writes only as a single 32-bit transaction with
upper word A55A; the key is never readable. Manual reset retains these registers.
The Saturn driver supplies external bus costs; BCR/WCR/MCR storage is not a
complete implementation of the programmable generic SH7604 memory interfaces,
endian conversion, bus-size selection or DRAM/SDRAM refresh/arbitration.

## Reserved regions, extra mappings and documentation conflicts

- Appendix B.1 lists reserved gaps through the on-chip region. No extra named
  Appendix B register was omitted from the matrix. Reserved holes are unmapped
  except the following existing extensions; their read value is not assumed to
  be zero merely because reserved named-register bits read zero.
- FMR at FFFFFE90: Appendix B calls this address reserved. The source records
  observed SH7604/CPS3 behavior but only logs clock changes. Retain and classify
  as a measured extension; it is not a documented Appendix B register.
- Read-only DVDNTH/DVDNTL mirrors at FFFFFF18/1C: Appendix B marks this area
  reserved; current implementation exposes division results there. Keep as
  undocumented mappings pending primary hardware evidence.
- B.1's FRC/OCR address labels are displaced in the printed table. B.2 and
  chapter 11 agree on FRC FE12/13, OCRA/B FE14/15, TCR FE16. Those addresses
  match the code; the malformed overview is not grounds to remap them.
- B.2 misprints DVSR/DVDNT as FFFFFE00/04. Chapter 10 and B.1 use FFFFFF00/04.
- VCRDIV lower-word R/W chart versus the prose's reserved read-zero statement
  is a genuine conflict; current read-back follows the chart. Do not silently
  report either interpretation as experimentally established.
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
The pre-audit revision compiles with the same fixture and fails an assertion.

macOS build passes with the user's Saturn/ST-V source selection and SDL3 (`OSD=sdl3 USE_LIBSDL=0 -j2`).
One isolated, low-priority VF Kids run (`-seconds_to_run 3`, video/sound off)
exits successfully; this is an initialization smoke test, not gameplay coverage.
Missing engines identified here are follow-up implementation tasks, not
failures of the audit process and not marked complete in the checklist.
No hardware test, complete SCI transmission test, full-library sweep or illegal
access-width bus-value measurement is claimed.
