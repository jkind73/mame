# CD firmware peripheral scope audit

The existing checklist item at `SATURN_REWRITE_CHECKLIST.md:206` combines TODOs from two incompatible processor families. The checklist wording is preserved. The user selected Saturn as the implementation scope.

## Processor used by Saturn

`src/mame/sega/saturn_cdb.cpp` instantiates SH7032 and disables it. The original `src/devices/cpu/sh/sh7032.cpp` implemented the peripheral range as a saved array of register words, without peripheral state machines. That placeholder has now been replaced. SH7032 is the ROMless member of the SH7032/SH7034 SH-1 family. The integrated-ROM SH7034 has the same peripheral family, with different on-chip memory capacities. The Saturn CD firmware uses a 64 KiB ROM.

The SH7032/SH7034 manual, section 1.1 table 1.1 and sections 9–16, specifies four DMA channels, five ITU channels, a timing pattern controller, two SCI channels, a watchdog, an eight-input 10-bit ADC, ports A/B and input-only C, and sleep/software standby. It does not specify a CMT, an MTU or port D.

## Where the listed TODOs actually originate

| Listed feature | Current source | Family distinction |
| --- | --- | --- |
| CMT | `sh7014.cpp` unmapped FFFF83D0–FFFF83DF | SH7014-family two-channel CMT; absent from SH7032/SH7034 |
| A/D converter | `sh7014.cpp`, `sh7014_adc.cpp` | SH7014 high-speed ADC differs from the implemented SH7016/7017 mid-speed ADC; SH7032/SH7034 has its own eight-input converter |
| Power-down | `sh7014.cpp` | Both families need their own standby registers and wake rules |
| C/D ports | `sh7014.cpp` | Comment concerns SH7016/7017 variants; SH7032/SH7034 has input-only C and no D |
| DMA priority and external requests/acknowledgments | `sh7014_dmac.cpp` | SH7014 has two channels with fixed channel-0 priority; SH7032/SH7034 has four channels and selectable priority |
| MTU modes | `sh7014_mtu.cpp` | SH7014 three-channel MTU; SH7032/SH7034 five-channel ITU is a different module |
| SCI RX and full synchronous transmit hack | `sh7014_sci.cpp` | Hack enabled in `src/mame/namco/namcos12_cdxa.cpp`; Saturn's disabled SH7032 does not use this SCI module |
| WDT reset/WDTOVF | `sh7014_wdt.cpp` | Both families require implementation, with variant-specific register addresses/reset controls |
| ADC trigger | `sh7014_adc.cpp` | Must follow the converter and timer module belonging to the selected CPU |
| Port special functions | `sh7014_port.cpp` | Pin assignment and selection bits are family-specific |

Adding missing SH7014 modules would not activate those functions in Saturn's SH7032. Reusing SH7014 register maps for SH7032 would be incorrect. The older SH7021 implementation also cannot be accepted as a complete replacement: its DMA transfers the whole count synchronously, synthesizes SCI transmit completion and leaves DMA interrupts unimplemented.

## References

- [Renesas SH7032/SH7034 Hardware Manual, REJ09B0272-0700](https://www.renesas.com/en/document/mah/sh7032-sh7034-hardware-manual), section 1.1 table 1.1; DMA chapter 9; ITU chapter 10; watchdog chapter 12; SCI chapter 13; ADC chapter 14; power chapter 15; ports chapter 16.
- [Renesas SH7014/SH7016/SH7017 Hardware Manual, REJ09B0398-0500](https://www.renesas.com/en/document/mah/sh7014-sh7016-sh7017f-ztattm-hardware-manual), section 1.1.1; two-channel fixed-priority DMA; three-channel MTU; chapter 15 CMT.
- Local MiSTer SH7034 RTL and Ymir SH-1 sources provide secondary implementation references. Neither changes which hardware the manuals describe.

The user selected the actual Saturn SH-1 peripherals. See `SH7032_PERIPHERAL_IMPLEMENTATION.md` for the implementation and validation. No SH7014 peripheral changes are included.
