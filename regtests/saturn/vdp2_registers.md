# VDP2 register ledger — first-pass source inventory

2026-09-15. Scope: every halfword through 0x11E, plus remaining backing storage.
**A03 is not complete.** Local symbols/backing handlers are inventoried, not proof
that every hardware bit has a functional implementation. Each Open cell needs a
primary-document reference and an appropriate production test before closure.

The first six registers are overlaid by the VDP2 device's register map. Generic
renderer registers merge masked writes and mirror the 0x200-byte file. Their writes
invalidate window caches; color-offset writes dirty faded pens; CRMD changes rebuild
palette data. They do not generally preserve already-scanned output before mutation.

| Offset | Local symbol / device register | Local handling | Hardware mask/reset/latch audit |
|---|---|---|---|
| `000` | TVMD | Decoded R/W; reset cleared; test_tvmd.py | Open |
| `002` | EXTEN | Decoded R/W and latching; reset cleared; test_exten.py | Open |
| `004` | TVSTAT | Status read with side-effect flag clear | Open |
| `006` | VRSIZE | VRAMSZ high-byte write; version placeholder | Open |
| `008` | HCNT | Read-only latch | Open |
| `00A` | VCNT | Read-only latch; test_vcounter.py | Open |
| `00C` | No direct symbol found | Generic backing R/W; functional consumers require individual audit | Open |
| `00E` | RAMCTL | Generic backing R/W; functional consumers require individual audit | Open |
| `010` | CYCA0L | Generic backing R/W; functional consumers require individual audit | Open |
| `012` | CYCA0U | Generic backing R/W; functional consumers require individual audit | Open |
| `014` | CYCA1L | Generic backing R/W; functional consumers require individual audit | Open |
| `016` | CYCA1U | Generic backing R/W; functional consumers require individual audit | Open |
| `018` | CYCA2L | Generic backing R/W; functional consumers require individual audit | Open |
| `01A` | CYCA2U | Generic backing R/W; functional consumers require individual audit | Open |
| `01C` | CYCA3L | Generic backing R/W; functional consumers require individual audit | Open |
| `01E` | CYCA3U | Generic backing R/W; functional consumers require individual audit | Open |
| `020` | BGON | Generic backing R/W; functional consumers require individual audit | Open |
| `022` | MZCTL | Generic backing R/W; functional consumers require individual audit | Open |
| `024` | SFSEL | Generic backing R/W; functional consumers require individual audit | Open |
| `026` | SFCODE | Generic backing R/W; functional consumers require individual audit | Open |
| `028` | CHCTLA | Generic backing R/W; functional consumers require individual audit | Open |
| `02A` | CHCTLB | Generic backing R/W; functional consumers require individual audit | Open |
| `02C` | BMPNA | Generic backing R/W; functional consumers require individual audit | Open |
| `02E` | BMPNB | Generic backing R/W; functional consumers require individual audit | Open |
| `030` | PNCN0 | Generic backing R/W; functional consumers require individual audit | Open |
| `032` | PNCN1 | Generic backing R/W; functional consumers require individual audit | Open |
| `034` | PNCN2 | Generic backing R/W; functional consumers require individual audit | Open |
| `036` | PNCN3 | Generic backing R/W; functional consumers require individual audit | Open |
| `038` | PNCR | Generic backing R/W; functional consumers require individual audit | Open |
| `03A` | PLSZ | Generic backing R/W; functional consumers require individual audit | Open |
| `03C` | MPOFN_ | Generic backing R/W; functional consumers require individual audit | Open |
| `03E` | MPOFR_ | Generic backing R/W; functional consumers require individual audit | Open |
| `040` | MPABN0 | Generic backing R/W; functional consumers require individual audit | Open |
| `042` | MPCDN0 | Generic backing R/W; functional consumers require individual audit | Open |
| `044` | MPABN1 | Generic backing R/W; functional consumers require individual audit | Open |
| `046` | MPCDN1 | Generic backing R/W; functional consumers require individual audit | Open |
| `048` | MPABN2 | Generic backing R/W; functional consumers require individual audit | Open |
| `04A` | MPCDN2 | Generic backing R/W; functional consumers require individual audit | Open |
| `04C` | MPABN3 | Generic backing R/W; functional consumers require individual audit | Open |
| `04E` | MPCDN3 | Generic backing R/W; functional consumers require individual audit | Open |
| `050` | MPABRA | Generic backing R/W; functional consumers require individual audit | Open |
| `052` | MPCDRA | Generic backing R/W; functional consumers require individual audit | Open |
| `054` | MPEFRA | Generic backing R/W; functional consumers require individual audit | Open |
| `056` | MPGHRA | Generic backing R/W; functional consumers require individual audit | Open |
| `058` | MPIJRA | Generic backing R/W; functional consumers require individual audit | Open |
| `05A` | MPKLRA | Generic backing R/W; functional consumers require individual audit | Open |
| `05C` | MPMNRA | Generic backing R/W; functional consumers require individual audit | Open |
| `05E` | MPOPRA | Generic backing R/W; functional consumers require individual audit | Open |
| `060` | MPABRB | Generic backing R/W; functional consumers require individual audit | Open |
| `062` | MPCDRB | Generic backing R/W; functional consumers require individual audit | Open |
| `064` | MPEFRB | Generic backing R/W; functional consumers require individual audit | Open |
| `066` | MPGHRB | Generic backing R/W; functional consumers require individual audit | Open |
| `068` | MPIJRB | Generic backing R/W; functional consumers require individual audit | Open |
| `06A` | MPKLRB | Generic backing R/W; functional consumers require individual audit | Open |
| `06C` | MPMNRB | Generic backing R/W; functional consumers require individual audit | Open |
| `06E` | MPOPRB | Generic backing R/W; functional consumers require individual audit | Open |
| `070` | SCXIN0 | Generic backing R/W; functional consumers require individual audit | Open |
| `072` | SCXDN0 | Generic backing R/W; functional consumers require individual audit | Open |
| `074` | SCYIN0 | Generic backing R/W; functional consumers require individual audit | Open |
| `076` | SCYDN0 | Generic backing R/W; functional consumers require individual audit | Open |
| `078` | ZMXIN0 | Generic backing R/W; functional consumers require individual audit | Open |
| `07A` | ZMXDN0 | Generic backing R/W; functional consumers require individual audit | Open |
| `07C` | ZMYIN0 | Generic backing R/W; functional consumers require individual audit | Open |
| `07E` | ZMYDN0 | Generic backing R/W; functional consumers require individual audit | Open |
| `080` | SCXIN1 | Generic backing R/W; functional consumers require individual audit | Open |
| `082` | SCXDN1 | Generic backing R/W; functional consumers require individual audit | Open |
| `084` | SCYIN1 | Generic backing R/W; functional consumers require individual audit | Open |
| `086` | SCYDN1 | Generic backing R/W; functional consumers require individual audit | Open |
| `088` | ZMXIN1 | Generic backing R/W; functional consumers require individual audit | Open |
| `08A` | ZMXDN1 | Generic backing R/W; functional consumers require individual audit | Open |
| `08C` | ZMYIN1 | Generic backing R/W; functional consumers require individual audit | Open |
| `08E` | ZMYDN1 | Generic backing R/W; functional consumers require individual audit | Open |
| `090` | SCXN2 | Generic backing R/W; functional consumers require individual audit | Open |
| `092` | SCYN2 | Generic backing R/W; functional consumers require individual audit | Open |
| `094` | SCXN3 | Generic backing R/W; functional consumers require individual audit | Open |
| `096` | SCYN3 | Generic backing R/W; functional consumers require individual audit | Open |
| `098` | ZMCTL | Generic backing R/W; functional consumers require individual audit | Open |
| `09A` | SCRCTL | Generic backing R/W; functional consumers require individual audit | Open |
| `09C` | VCSTAU | Generic backing R/W; functional consumers require individual audit | Open |
| `09E` | VCSTAL | Generic backing R/W; functional consumers require individual audit | Open |
| `0A0` | LSTA0U | Generic backing R/W; functional consumers require individual audit | Open |
| `0A2` | LSTA0L | Generic backing R/W; functional consumers require individual audit | Open |
| `0A4` | LSTA1U | Generic backing R/W; functional consumers require individual audit | Open |
| `0A6` | LSTA1L | Generic backing R/W; functional consumers require individual audit | Open |
| `0A8` | LCTAU | Generic backing R/W; functional consumers require individual audit | Open |
| `0AA` | LCTAL | Generic backing R/W; functional consumers require individual audit | Open |
| `0AC` | BKTAU | Generic backing R/W; functional consumers require individual audit | Open |
| `0AE` | BKTAL | Generic backing R/W; functional consumers require individual audit | Open |
| `0B0` | No direct symbol found | Generic backing R/W; functional consumers require individual audit | Open |
| `0B2` | RPRCTL | Generic backing R/W; functional consumers require individual audit | Open |
| `0B4` | KTCTL | Generic backing R/W; functional consumers require individual audit | Open |
| `0B6` | KTAOF | Generic backing R/W; functional consumers require individual audit | Open |
| `0B8` | OVPNRA | Generic backing R/W; functional consumers require individual audit | Open |
| `0BA` | OVPNRB | Generic backing R/W; functional consumers require individual audit | Open |
| `0BC` | RPTAU | Generic backing R/W; functional consumers require individual audit | Open |
| `0BE` | RPTAL | Generic backing R/W; functional consumers require individual audit | Open |
| `0C0` | WPSX0 | Generic backing R/W; functional consumers require individual audit | Open |
| `0C2` | WPSY0 | Generic backing R/W; functional consumers require individual audit | Open |
| `0C4` | WPEX0 | Generic backing R/W; functional consumers require individual audit | Open |
| `0C6` | WPEY0 | Generic backing R/W; functional consumers require individual audit | Open |
| `0C8` | WPSX1 | Generic backing R/W; functional consumers require individual audit | Open |
| `0CA` | WPSY1 | Generic backing R/W; functional consumers require individual audit | Open |
| `0CC` | WPEX1 | Generic backing R/W; functional consumers require individual audit | Open |
| `0CE` | WPEY1 | Generic backing R/W; functional consumers require individual audit | Open |
| `0D0` | WCTLA | Generic backing R/W; functional consumers require individual audit | Open |
| `0D2` | WCTLB | Generic backing R/W; functional consumers require individual audit | Open |
| `0D4` | WCTLC | Generic backing R/W; functional consumers require individual audit | Open |
| `0D6` | WCTLD | Generic backing R/W; functional consumers require individual audit | Open |
| `0D8` | LWTA0U | Generic backing R/W; functional consumers require individual audit | Open |
| `0DA` | LWTA0L | Generic backing R/W; functional consumers require individual audit | Open |
| `0DC` | LWTA1U | Generic backing R/W; functional consumers require individual audit | Open |
| `0DE` | LWTA1L | Generic backing R/W; functional consumers require individual audit | Open |
| `0E0` | SPCTL | Generic backing R/W; functional consumers require individual audit | Open |
| `0E2` | SDCTL | Generic backing R/W; functional consumers require individual audit | Open |
| `0E4` | CRAOFA | Generic backing R/W; functional consumers require individual audit | Open |
| `0E6` | CRAOFB | Generic backing R/W; functional consumers require individual audit | Open |
| `0E8` | LNCLEN | Generic backing R/W; functional consumers require individual audit | Open |
| `0EA` | SFPRMD | Generic backing R/W; functional consumers require individual audit | Open |
| `0EC` | CCCR | Generic backing R/W; functional consumers require individual audit | Open |
| `0EE` | SFCCMD | Generic backing R/W; functional consumers require individual audit | Open |
| `0F0` | PRISA | Generic backing R/W; functional consumers require individual audit | Open |
| `0F2` | PRISB | Generic backing R/W; functional consumers require individual audit | Open |
| `0F4` | PRISC | Generic backing R/W; functional consumers require individual audit | Open |
| `0F6` | PRISD | Generic backing R/W; functional consumers require individual audit | Open |
| `0F8` | PRINA | Generic backing R/W; functional consumers require individual audit | Open |
| `0FA` | PRINB | Generic backing R/W; functional consumers require individual audit | Open |
| `0FC` | PRIR | Generic backing R/W; functional consumers require individual audit | Open |
| `0FE` | No direct symbol found | Generic backing R/W; functional consumers require individual audit | Open |
| `100` | CCRSA | Generic backing R/W; functional consumers require individual audit | Open |
| `102` | CCRSB | Generic backing R/W; functional consumers require individual audit | Open |
| `104` | CCRSC | Generic backing R/W; functional consumers require individual audit | Open |
| `106` | CCRSD | Generic backing R/W; functional consumers require individual audit | Open |
| `108` | CCRNA | Generic backing R/W; functional consumers require individual audit | Open |
| `10A` | CCRNB | Generic backing R/W; functional consumers require individual audit | Open |
| `10C` | CCRR | Generic backing R/W; functional consumers require individual audit | Open |
| `10E` | CCRLB | Generic backing R/W; functional consumers require individual audit | Open |
| `110` | CLOFEN | Generic backing R/W; functional consumers require individual audit | Open |
| `112` | CLOFSL | Generic backing R/W; functional consumers require individual audit | Open |
| `114` | COAR | Generic backing R/W; functional consumers require individual audit | Open |
| `116` | COAG | Generic backing R/W; functional consumers require individual audit | Open |
| `118` | COAB | Generic backing R/W; functional consumers require individual audit | Open |
| `11A` | COBR | Generic backing R/W; functional consumers require individual audit | Open |
| `11C` | COBG | Generic backing R/W; functional consumers require individual audit | Open |
| `11E` | COBB | Generic backing R/W; functional consumers require individual audit | Open |
| `120–1FE` | No functional register asserted here | Generic backing remains addressable | Reserved/open-bus behavior open |

## Initial memory/register audit findings

- [x] CRAM mode-0 two-half write broadcast: ST-058 §3.4 pp.43–46; production tests added.
- [x] Preserve independent reads and unwritten lanes in halves that differ after a mode change; cross-checked with Ymir/MiSTer.
- [ ] Transcribe hardware writable/readable masks, resets and latch points for all entries.
- [ ] Verify reserved offsets, bits and prohibited accesses without inventing behavior.
- [x] Implement/test mode-2 physical bank mapping across mode changes and mode-1 coefficient reads (cross-implementation evidence; silicon qualification open).
- [ ] Audit physical RGB555 expansion (manual zero-fill versus MAME pal5bit), separately from CRAM storage.

The manual prohibits byte access; no new ignore rule is imposed. CRMD=3 remains a
legacy fallback, not a certified legal mode. See [vdp2_completion.md](vdp2_completion.md)
for the parent task IDs and acceptance requirements.
