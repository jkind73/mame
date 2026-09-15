# VDP2 register ledger — first-pass source inventory

2026-09-15. Scope: every halfword through 0x11E, plus remaining backing storage.
**A03 is not complete.** Local symbols/backing handlers are inventoried, not proof
that every hardware bit has a functional implementation. Each Open cell needs a
primary-document reference and an appropriate production test before closure.

The first six registers are overlaid by the VDP2 device's register map. Generic
renderer registers merge masked writes and mirror the 0x200-byte file. Their writes
invalidate window caches; color-offset writes dirty faded pens; CRMD changes rebuild
palette data. They do not generally preserve already-scanned output before mutation.

| Offset | Local symbol / device register | Local handling | Hardware mask/reset/latch audit  MiSTer write-mask cross-reference (not primary verification) |
|---|---|---|---|---|
| `000` | TVMD | Decoded R/W; reset cleared; test_tvmd.py | Open  `TVMD` / `TVMD_MASK` = `81F3/81F7` |
| `002` | EXTEN | Decoded R/W and latching; reset cleared; test_exten.py | Open  `EXTEN` / `EXTEN_MASK` = `0303` |
| `004` | TVSTAT | Status read with side-effect flag clear | Open  No matching DI-mask write case; inspect device/status path |
| `006` | VRSIZE | VRAMSZ high-byte write; version placeholder | Open  `VRSIZE` / `VRSIZE_MASK` = `8000` |
| `008` | HCNT | Read-only latch | Open  No matching DI-mask write case; inspect device/status path |
| `00A` | VCNT | Read-only latch; test_vcounter.py | Open  No matching DI-mask write case; inspect device/status path |
| `00C` | No direct symbol found | Generic backing R/W; functional consumers require individual audit | Open  `RSRV0` / `RSRV_MASK` = `0000` |
| `00E` | RAMCTL | Generic backing R/W; functional consumers require individual audit | Open  `RAMCTL` / `RAMCTL_MASK` = `B3FF` |
| `010` | CYCA0L | Generic backing R/W; functional consumers require individual audit | Open  `CYCA0L` / `CYCx0L_MASK` = `FFFF` |
| `012` | CYCA0U | Generic backing R/W; functional consumers require individual audit | Open  `CYCA0U` / `CYCx0U_MASK` = `FFFF` |
| `014` | CYCA1L | Generic backing R/W; functional consumers require individual audit | Open  `CYCA1L` / `CYCx1L_MASK` = `FFFF` |
| `016` | CYCA1U | Generic backing R/W; functional consumers require individual audit | Open  `CYCA1U` / `CYCx1U_MASK` = `FFFF` |
| `018` | CYCA2L | Generic backing R/W; functional consumers require individual audit | Open  `CYCB0L` / `CYCx0L_MASK` = `FFFF` |
| `01A` | CYCA2U | Generic backing R/W; functional consumers require individual audit | Open  `CYCB0U` / `CYCx0U_MASK` = `FFFF` |
| `01C` | CYCA3L | Generic backing R/W; functional consumers require individual audit | Open  `CYCB1L` / `CYCx1L_MASK` = `FFFF` |
| `01E` | CYCA3U | Generic backing R/W; functional consumers require individual audit | Open  `CYCB1U` / `CYCx1U_MASK` = `FFFF` |
| `020` | BGON | Generic backing R/W; functional consumers require individual audit | Open  `BGON` / `BGON_MASK` = `1F3F` |
| `022` | MZCTL | Generic backing R/W; functional consumers require individual audit | Open  `MZCTL` / `MZCTL_MASK` = `FF1F` |
| `024` | SFSEL | Generic backing R/W; functional consumers require individual audit | Open  `SFSEL` / `SFSEL_MASK` = `001F` |
| `026` | SFCODE | Generic backing R/W; functional consumers require individual audit | Open  `SFCODE` / `SFCODE_MASK` = `FFFF` |
| `028` | CHCTLA | Generic backing R/W; functional consumers require individual audit | Open  `CHCTLA` / `CHCTLA_MASK` = `3F7F` |
| `02A` | CHCTLB | Generic backing R/W; functional consumers require individual audit | Open  `CHCTLB` / `CHCTLB_MASK` = `7733` |
| `02C` | BMPNA | Generic backing R/W; functional consumers require individual audit | Open  `BMPNA` / `BMPNA_MASK` = `3737` |
| `02E` | BMPNB | Generic backing R/W; functional consumers require individual audit | Open  `BMPNB` / `BMPNB_MASK` = `0037` |
| `030` | PNCN0 | Generic backing R/W; functional consumers require individual audit | Open  `PNCN0` / `PNCNx_MASK` = `C3FF` |
| `032` | PNCN1 | Generic backing R/W; functional consumers require individual audit | Open  `PNCN1` / `PNCNx_MASK` = `C3FF` |
| `034` | PNCN2 | Generic backing R/W; functional consumers require individual audit | Open  `PNCN2` / `PNCNx_MASK` = `C3FF` |
| `036` | PNCN3 | Generic backing R/W; functional consumers require individual audit | Open  `PNCN3` / `PNCNx_MASK` = `C3FF` |
| `038` | PNCR | Generic backing R/W; functional consumers require individual audit | Open  `PNCR` / `PNCR_MASK` = `C3FF` |
| `03A` | PLSZ | Generic backing R/W; functional consumers require individual audit | Open  `PLSZ` / `PLSZ_MASK` = `FFFF` |
| `03C` | MPOFN_ | Generic backing R/W; functional consumers require individual audit | Open  `MPOFN` / `MPOFN_MASK` = `7777` |
| `03E` | MPOFR_ | Generic backing R/W; functional consumers require individual audit | Open  `MPOFR` / `MPOFR_MASK` = `0077` |
| `040` | MPABN0 | Generic backing R/W; functional consumers require individual audit | Open  `MPABN0` / `MPABNx_MASK` = `3F3F` |
| `042` | MPCDN0 | Generic backing R/W; functional consumers require individual audit | Open  `MPCDN0` / `MPCDNx_MASK` = `3F3F` |
| `044` | MPABN1 | Generic backing R/W; functional consumers require individual audit | Open  `MPABN1` / `MPABNx_MASK` = `3F3F` |
| `046` | MPCDN1 | Generic backing R/W; functional consumers require individual audit | Open  `MPCDN1` / `MPCDNx_MASK` = `3F3F` |
| `048` | MPABN2 | Generic backing R/W; functional consumers require individual audit | Open  `MPABN2` / `MPABNx_MASK` = `3F3F` |
| `04A` | MPCDN2 | Generic backing R/W; functional consumers require individual audit | Open  `MPCDN2` / `MPCDNx_MASK` = `3F3F` |
| `04C` | MPABN3 | Generic backing R/W; functional consumers require individual audit | Open  `MPABN3` / `MPABNx_MASK` = `3F3F` |
| `04E` | MPCDN3 | Generic backing R/W; functional consumers require individual audit | Open  `MPCDN3` / `MPCDNx_MASK` = `3F3F` |
| `050` | MPABRA | Generic backing R/W; functional consumers require individual audit | Open  `MPABRA` / `MPABRx_MASK` = `3F3F` |
| `052` | MPCDRA | Generic backing R/W; functional consumers require individual audit | Open  `MPCDRA` / `MPCDRx_MASK` = `3F3F` |
| `054` | MPEFRA | Generic backing R/W; functional consumers require individual audit | Open  `MPEFRA` / `MPEFRx_MASK` = `3F3F` |
| `056` | MPGHRA | Generic backing R/W; functional consumers require individual audit | Open  `MPGHRA` / `MPGHRx_MASK` = `3F3F` |
| `058` | MPIJRA | Generic backing R/W; functional consumers require individual audit | Open  `MPIJRA` / `MPIJRx_MASK` = `3F3F` |
| `05A` | MPKLRA | Generic backing R/W; functional consumers require individual audit | Open  `MPKLRA` / `MPKLRx_MASK` = `3F3F` |
| `05C` | MPMNRA | Generic backing R/W; functional consumers require individual audit | Open  `MPMNRA` / `MPMNRx_MASK` = `3F3F` |
| `05E` | MPOPRA | Generic backing R/W; functional consumers require individual audit | Open  `MPOPRA` / `MPOPRx_MASK` = `3F3F` |
| `060` | MPABRB | Generic backing R/W; functional consumers require individual audit | Open  `MPABRB` / `MPABRx_MASK` = `3F3F` |
| `062` | MPCDRB | Generic backing R/W; functional consumers require individual audit | Open  `MPCDRB` / `MPCDRx_MASK` = `3F3F` |
| `064` | MPEFRB | Generic backing R/W; functional consumers require individual audit | Open  `MPEFRB` / `MPEFRx_MASK` = `3F3F` |
| `066` | MPGHRB | Generic backing R/W; functional consumers require individual audit | Open  `MPGHRB` / `MPGHRx_MASK` = `3F3F` |
| `068` | MPIJRB | Generic backing R/W; functional consumers require individual audit | Open  `MPIJRB` / `MPIJRx_MASK` = `3F3F` |
| `06A` | MPKLRB | Generic backing R/W; functional consumers require individual audit | Open  `MPKLRB` / `MPKLRx_MASK` = `3F3F` |
| `06C` | MPMNRB | Generic backing R/W; functional consumers require individual audit | Open  `MPMNRB` / `MPMNRx_MASK` = `3F3F` |
| `06E` | MPOPRB | Generic backing R/W; functional consumers require individual audit | Open  `MPOPRB` / `MPOPRx_MASK` = `3F3F` |
| `070` | SCXIN0 | Generic backing R/W; functional consumers require individual audit | Open  `SCXIN0` / `SCXINx_MASK` = `07FF` |
| `072` | SCXDN0 | Generic backing R/W; functional consumers require individual audit | Open  `SCXDN0` / `SCXDNx_MASK` = `FF00` |
| `074` | SCYIN0 | Generic backing R/W; functional consumers require individual audit | Open  `SCYIN0` / `SCYINx_MASK` = `07FF` |
| `076` | SCYDN0 | Generic backing R/W; functional consumers require individual audit | Open  `SCYDN0` / `SCYDNx_MASK` = `FF00` |
| `078` | ZMXIN0 | Generic backing R/W; functional consumers require individual audit | Open  `ZMXIN0` / `ZMXINx_MASK` = `0007` |
| `07A` | ZMXDN0 | Generic backing R/W; functional consumers require individual audit | Open  `ZMXDN0` / `ZMXDNx_MASK` = `FF00` |
| `07C` | ZMYIN0 | Generic backing R/W; functional consumers require individual audit | Open  `ZMYIN0` / `ZMYINx_MASK` = `0007` |
| `07E` | ZMYDN0 | Generic backing R/W; functional consumers require individual audit | Open  `ZMYDN0` / `ZMYDNx_MASK` = `FF00` |
| `080` | SCXIN1 | Generic backing R/W; functional consumers require individual audit | Open  `SCXIN1` / `SCXINx_MASK` = `07FF` |
| `082` | SCXDN1 | Generic backing R/W; functional consumers require individual audit | Open  `SCXDN1` / `SCXDNx_MASK` = `FF00` |
| `084` | SCYIN1 | Generic backing R/W; functional consumers require individual audit | Open  `SCYIN1` / `SCYINx_MASK` = `07FF` |
| `086` | SCYDN1 | Generic backing R/W; functional consumers require individual audit | Open  `SCYDN1` / `SCYDNx_MASK` = `FF00` |
| `088` | ZMXIN1 | Generic backing R/W; functional consumers require individual audit | Open  `ZMXIN1` / `ZMXINx_MASK` = `0007` |
| `08A` | ZMXDN1 | Generic backing R/W; functional consumers require individual audit | Open  `ZMXDN1` / `ZMXDNx_MASK` = `FF00` |
| `08C` | ZMYIN1 | Generic backing R/W; functional consumers require individual audit | Open  `ZMYIN1` / `ZMYINx_MASK` = `0007` |
| `08E` | ZMYDN1 | Generic backing R/W; functional consumers require individual audit | Open  `ZMYDN1` / `ZMYDNx_MASK` = `FF00` |
| `090` | SCXN2 | Generic backing R/W; functional consumers require individual audit | Open  `SCXN2` / `SCXNx_MASK` = `07FF` |
| `092` | SCYN2 | Generic backing R/W; functional consumers require individual audit | Open  `SCYN2` / `SCYNx_MASK` = `07FF` |
| `094` | SCXN3 | Generic backing R/W; functional consumers require individual audit | Open  `SCXN3` / `SCXNx_MASK` = `07FF` |
| `096` | SCYN3 | Generic backing R/W; functional consumers require individual audit | Open  `SCYN3` / `SCYNx_MASK` = `07FF` |
| `098` | ZMCTL | Generic backing R/W; functional consumers require individual audit | Open  `ZMCTL` / `ZMCTL_MASK` = `0303` |
| `09A` | SCRCTL | Generic backing R/W; functional consumers require individual audit | Open  `SCRCTL` / `SCRCTL_MASK` = `3F3F` |
| `09C` | VCSTAU | Generic backing R/W; functional consumers require individual audit | Open  `VCSTAU` / `VCSTAU_MASK` = `0007` |
| `09E` | VCSTAL | Generic backing R/W; functional consumers require individual audit | Open  `VCSTAL` / `VCSTAL_MASK` = `FFFE` |
| `0A0` | LSTA0U | Generic backing R/W; functional consumers require individual audit | Open  `LSTA0U` / `LSTAxU_MASK` = `0007` |
| `0A2` | LSTA0L | Generic backing R/W; functional consumers require individual audit | Open  `LSTA0L` / `LSTAxL_MASK` = `FFFE` |
| `0A4` | LSTA1U | Generic backing R/W; functional consumers require individual audit | Open  `LSTA1U` / `LSTAxU_MASK` = `0007` |
| `0A6` | LSTA1L | Generic backing R/W; functional consumers require individual audit | Open  `LSTA1L` / `LSTAxL_MASK` = `FFFE` |
| `0A8` | LCTAU | Generic backing R/W; functional consumers require individual audit | Open  `LCTAU` / `LCTAU_MASK` = `8007` |
| `0AA` | LCTAL | Generic backing R/W; functional consumers require individual audit | Open  `LCTAL` / `LCTAL_MASK` = `FFFF` |
| `0AC` | BKTAU | Generic backing R/W; functional consumers require individual audit | Open  `BKTAU` / `BKTAU_MASK` = `8007` |
| `0AE` | BKTAL | Generic backing R/W; functional consumers require individual audit | Open  `BKTAL` / `BKTAL_MASK` = `FFFF` |
| `0B0` | No direct symbol found | Generic backing R/W; functional consumers require individual audit | Open  `RPMD` / `RPMD_MASK` = `0003` |
| `0B2` | RPRCTL | Generic backing R/W; functional consumers require individual audit | Open  `RPRCTL` / `RPRCTL_MASK` = `0707` |
| `0B4` | KTCTL | Generic backing R/W; functional consumers require individual audit | Open  `KTCTL` / `KTCTL_MASK` = `1F1F` |
| `0B6` | KTAOF | Generic backing R/W; functional consumers require individual audit | Open  `KTAOF` / `KTAOF_MASK` = `0707` |
| `0B8` | OVPNRA | Generic backing R/W; functional consumers require individual audit | Open  `OVPNRA` / `OVPNRx_MASK` = `FFFF` |
| `0BA` | OVPNRB | Generic backing R/W; functional consumers require individual audit | Open  `OVPNRB` / `OVPNRx_MASK` = `FFFF` |
| `0BC` | RPTAU | Generic backing R/W; functional consumers require individual audit | Open  `RPTAU` / `RPTAU_MASK` = `0007` |
| `0BE` | RPTAL | Generic backing R/W; functional consumers require individual audit | Open  `RPTAL` / `RPTAL_MASK` = `FFFE` |
| `0C0` | WPSX0 | Generic backing R/W; functional consumers require individual audit | Open  `WPSX0` / `WPSXx_MASK` = `03FF` |
| `0C2` | WPSY0 | Generic backing R/W; functional consumers require individual audit | Open  `WPSY0` / `WPSYx_MASK` = `01FF` |
| `0C4` | WPEX0 | Generic backing R/W; functional consumers require individual audit | Open  `WPEX0` / `WPEXx_MASK` = `03FF` |
| `0C6` | WPEY0 | Generic backing R/W; functional consumers require individual audit | Open  `WPEY0` / `WPEYx_MASK` = `01FF` |
| `0C8` | WPSX1 | Generic backing R/W; functional consumers require individual audit | Open  `WPSX1` / `WPSXx_MASK` = `03FF` |
| `0CA` | WPSY1 | Generic backing R/W; functional consumers require individual audit | Open  `WPSY1` / `WPSYx_MASK` = `01FF` |
| `0CC` | WPEX1 | Generic backing R/W; functional consumers require individual audit | Open  `WPEX1` / `WPEXx_MASK` = `03FF` |
| `0CE` | WPEY1 | Generic backing R/W; functional consumers require individual audit | Open  `WPEY1` / `WPEYx_MASK` = `01FF` |
| `0D0` | WCTLA | Generic backing R/W; functional consumers require individual audit | Open  `WCTLA` / `WCTLA_MASK` = `BFBF` |
| `0D2` | WCTLB | Generic backing R/W; functional consumers require individual audit | Open  `WCTLB` / `WCTLB_MASK` = `BFBF` |
| `0D4` | WCTLC | Generic backing R/W; functional consumers require individual audit | Open  `WCTLC` / `WCTLC_MASK` = `BFBF` |
| `0D6` | WCTLD | Generic backing R/W; functional consumers require individual audit | Open  `WCTLD` / `WCTLD_MASK` = `BF8F` |
| `0D8` | LWTA0U | Generic backing R/W; functional consumers require individual audit | Open  `LWTA0U` / `LWTAxU_MASK` = `8007` |
| `0DA` | LWTA0L | Generic backing R/W; functional consumers require individual audit | Open  `LWTA0L` / `LWTAxL_MASK` = `FFFE` |
| `0DC` | LWTA1U | Generic backing R/W; functional consumers require individual audit | Open  `LWTA1U` / `LWTAxU_MASK` = `8007` |
| `0DE` | LWTA1L | Generic backing R/W; functional consumers require individual audit | Open  `LWTA1L` / `LWTAxL_MASK` = `FFFE` |
| `0E0` | SPCTL | Generic backing R/W; functional consumers require individual audit | Open  `SPCTL` / `SPCTL_MASK` = `373F` |
| `0E2` | SDCTL | Generic backing R/W; functional consumers require individual audit | Open  `SDCTL` / `SDCTL_MASK` = `013F` |
| `0E4` | CRAOFA | Generic backing R/W; functional consumers require individual audit | Open  `CRAOFA` / `CRAOFA_MASK` = `7777` |
| `0E6` | CRAOFB | Generic backing R/W; functional consumers require individual audit | Open  `CRAOFB` / `CRAOFB_MASK` = `0077` |
| `0E8` | LNCLEN | Generic backing R/W; functional consumers require individual audit | Open  `LNCLEN` / `LNCLEN_MASK` = `003F` |
| `0EA` | SFPRMD | Generic backing R/W; functional consumers require individual audit | Open  `SFPRMD` / `SFPRMD_MASK` = `03FF` |
| `0EC` | CCCR | Generic backing R/W; functional consumers require individual audit | Open  `CCCTL` / `CCCTL_MASK` = `F77F` |
| `0EE` | SFCCMD | Generic backing R/W; functional consumers require individual audit | Open  `SFCCMD` / `SFCCMD_MASK` = `03FF` |
| `0F0` | PRISA | Generic backing R/W; functional consumers require individual audit | Open  `PRISA` / `PRISA_MASK` = `0707` |
| `0F2` | PRISB | Generic backing R/W; functional consumers require individual audit | Open  `PRISB` / `PRISB_MASK` = `0707` |
| `0F4` | PRISC | Generic backing R/W; functional consumers require individual audit | Open  `PRISC` / `PRISC_MASK` = `0707` |
| `0F6` | PRISD | Generic backing R/W; functional consumers require individual audit | Open  `PRISD` / `PRISD_MASK` = `0707` |
| `0F8` | PRINA | Generic backing R/W; functional consumers require individual audit | Open  `PRINA` / `PRINA_MASK` = `0707` |
| `0FA` | PRINB | Generic backing R/W; functional consumers require individual audit | Open  `PRINB` / `PRINB_MASK` = `0707` |
| `0FC` | PRIR | Generic backing R/W; functional consumers require individual audit | Open  `PRIR` / `PRIR_MASK` = `0007` |
| `0FE` | No direct symbol found | Generic backing R/W; functional consumers require individual audit | Open  `RSRV1` / `RSRV_MASK` = `0000` |
| `100` | CCRSA | Generic backing R/W; functional consumers require individual audit | Open  `CCRSA` / `CCRSA_MASK` = `1F1F` |
| `102` | CCRSB | Generic backing R/W; functional consumers require individual audit | Open  `CCRSB` / `CCRSB_MASK` = `1F1F` |
| `104` | CCRSC | Generic backing R/W; functional consumers require individual audit | Open  `CCRSC` / `CCRSC_MASK` = `1F1F` |
| `106` | CCRSD | Generic backing R/W; functional consumers require individual audit | Open  `CCRSD` / `CCRSD_MASK` = `1F1F` |
| `108` | CCRNA | Generic backing R/W; functional consumers require individual audit | Open  `CCRNA` / `CCRNA_MASK` = `1F1F` |
| `10A` | CCRNB | Generic backing R/W; functional consumers require individual audit | Open  `CCRNB` / `CCRNA_MASK` = `1F1F` |
| `10C` | CCRR | Generic backing R/W; functional consumers require individual audit | Open  `CCRR` / `CCRR_MASK` = `001F` |
| `10E` | CCRLB | Generic backing R/W; functional consumers require individual audit | Open  `CCRLB` / `CCRLB_MASK` = `1F1F` |
| `110` | CLOFEN | Generic backing R/W; functional consumers require individual audit | Open  `CLOFEN` / `CLOFEN_MASK` = `007F` |
| `112` | CLOFSL | Generic backing R/W; functional consumers require individual audit | Open  `CLOFSL` / `CLOFSL_MASK` = `007F` |
| `114` | COAR | Generic backing R/W; functional consumers require individual audit | Open  `COAR` / `COxR_MASK` = `01FF` |
| `116` | COAG | Generic backing R/W; functional consumers require individual audit | Open  `COAG` / `COxG_MASK` = `01FF` |
| `118` | COAB | Generic backing R/W; functional consumers require individual audit | Open  `COAB` / `COxB_MASK` = `01FF` |
| `11A` | COBR | Generic backing R/W; functional consumers require individual audit | Open  `COBR` / `COxR_MASK` = `01FF` |
| `11C` | COBG | Generic backing R/W; functional consumers require individual audit | Open  `COBG` / `COxG_MASK` = `01FF` |
| `11E` | COBB | Generic backing R/W; functional consumers require individual audit | Open  `COBB` / `COxB_MASK` = `01FF` |
| `120–1FE` | No functional register asserted here | Generic backing remains addressable | Reserved/open-bus behavior open  Reserved range; not inferred from a general mask |

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

## Mask cross-reference provenance

The final column is extracted from MiSTer Saturn VDP2.sv register-write cases and
VDP2_pkg.sv at `a95b085038ace57fa621558d60a7adc7a3c53f78`. Conditional mask alternatives
are retained rather than selecting one silently. This is a comparison aid, **not**
a recommendation to copy masks into MAME, and does not close the primary reset/
latch audit. Hardware write masks and software's obligation to write reserved bits
as zero are not automatically the same assertion.
