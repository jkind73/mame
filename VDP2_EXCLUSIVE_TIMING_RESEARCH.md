# Exclusive-monitor timing: Mednafen cross-check

Checked 2026-10-09. The exclusive-monitor scan-timing checklist item remains incomplete. No source or checklist changes are justified by this cross-check.

## Correction after inspecting MiSTer's sequential logic

The user supplied a further analysis on 2026-10-09. Inspection of current upstream `rtl/Saturn/VDP2/VDP2.sv` confirms that its break comparison uses the current pre-edge phase, not the incremented phase. An executed trace starting at zero, stepping by two, and jumping after 0x158 to 0x3B0 (A) or after 0x176 to 0x3D0 (B) produces exactly 213 and 212 slots respectively. At four system clocks per slot these are 852 and 848 clocks, matching Sega Table 4.4. The earlier claim that MiSTer's dedicated-B target necessarily gives the wrong raster length was incorrect.

Current MiSTer also compares the dedicated-B V-counter increment against 0x16A, before the horizontal break at 0x176. Thus counter increment and horizontal jump must not be treated as the same event for that mode. Its TVSTAT blanking state uses the discontinuous counter, while its external HBL state uses the separate linear counter.

These checks establish internal arithmetic consistency and make MiSTer a usable candidate approximation under the user's authorization to implement without hardware verification. They do not independently establish hardware correctness. The checklist text is left untouched under the user's marker-only restriction; its sentence about the 0x3D0 target is superseded by this correction.

Source inspected: https://github.com/MiSTer-devel/Saturn_MiSTer/blob/main/rtl/Saturn/VDP2/VDP2.sv

## Sources inspected

- Mednafen 1.32.1 `src/ss/vdp2.cpp`: https://sources.debian.org/src/mednafen/1.32.1%2Bdfsg-2/src/ss/vdp2.cpp/
- Mednafen release listing: https://mednafen.github.io/releases/
- Mirror of upstream VDP2 source: https://github.com/libretro-mirrors/mednafen-git/blob/master/src/ss/vdp2.cpp
- Mirror ChangeLog: https://github.com/libretro-mirrors/mednafen-git/blob/master/ChangeLog

The release listing identifies 1.32.1 as its newest listed release. Both inspected VDP2 files use the same horizontal timing approach. No GPL source code was copied into MAME.

## Findings

The horizontal table has only two entries, selected by HRes bit 0. HRes bit 2, which selects exclusive-monitor operation, does not select a separate horizontal timing table or clock divider in the update path.

The table boundaries are 0x140 / 0x15B / 0x1AB for the 320 family and 0x160 / 0x177 / 0x1C7 for the 352 family. The update advances once per four SH-2 timestamp units. These are emulator constants, not established exclusive-monitor hardware measurements.

Both the VDP1/SCU HBLANK output and TVSTAT HBLANK bit derive from the same horizontal phase condition. Consequently this implementation cannot corroborate distinct signal and flag edges such as those proposed by MiSTer.

The latched H counter uses the same two timing entries, offsets its value during the sync phase, and doubles the result. There is no dedicated-mode branch establishing the exclusive H-counter units or jump positions. The inspected timing code gives no hardware capture, measurement procedure, or exclusive-mode provenance for these values. The ChangeLog search did not identify an exclusive-monitor timing measurement or correction.

## Consequence for this source tree

### Follow-up arithmetic verification

Executed a counter trace using the timing table parsed directly from the inspected 1.32.1 source. This checks the implementation's arithmetic, not hardware accuracy or a rendered game.

For HRES 4/6, the period is 427 increments, or 1708 SH-2 timestamp cycles. For HRES 5/7, it is 455 increments, or 1820 cycles. The latched counter jumps from 0x2B4 to 0x360 in the first family, and from 0x2EC to 0x360 in the second. Both traces terminate at 0x3FE and wrap cleanly. Thus Mednafen's counter arithmetic is internally consistent, unlike the reported MiSTer dedicated-352 line-length discrepancy.

However, this does not make its exclusive operation correct: it preserves ordinary line duration. VDP1 Table 4.4 (`segahtml/hard/vdp1/hon/p04_14.htm`) gives raster budgets of 1708/1820 for ordinary NTSC/PAL, but 852 for 31KC and 848 for HDTV. The Mednafen update has no exclusive-mode rate adjustment. VDP2 2.5 (`segahtml/hard/vdp2/hon/p02_50.htm`) also specifies one-dot counter units for dedicated normal, and two-dot units for dedicated high resolution; Mednafen doubles the latched counter identically in every mode. Its dedicated-normal counter therefore advances by two instead of the documented one-dot unit. These are concrete reasons that its internally consistent ordinary-mode method cannot be adopted as a verified exclusive-mode implementation.

Mednafen does not supply the missing corroboration. Adopting its ordinary-mode table for exclusive operation would leave the requested behavior unverified. The existing exclusive-mode TODOs in `src/mame/sega/saturn_vdp2.cpp` must remain open.

Closure still requires hardware measurements establishing, for both horizontal families and their high-resolution variants, the HBLANK output edges, TVSTAT flag edges, counter units and discontinuities. Total line length alone cannot determine the positions of these events. A software counter/TVSTAT sampling trace can establish register behavior; a synchronized signal capture is needed to establish the physical HBLANK output independently.
