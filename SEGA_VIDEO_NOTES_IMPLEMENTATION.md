# Sega STN-22, STN-23 and STN-24 implementation

Updated 2026-10-09. These changes have not been verified against real Saturn hardware. Checklist wording and markers are unchanged.

Sources: local `segahtml/info/hon/stn22.htm`, `stn23.htm`, `stn24.htm`; VDP1 4.4 Table 4.4 and VDP2 2.5.

## Changes

- STN-22: dedicated normal no longer halves sprite framebuffer X coordinates. Dedicated high resolution continues doubling normal framebuffer pixels. Existing ordinary-mode 8-bit/16-bit scaling and rotated framebuffer sampling remain in use.
- STN-23: when VDP2 uses single-density interlace and the displayed VDP1 buffer has DIE enabled, sprite readout now selects the field using the output field parity. Double-density output continues assembling current/previous VDP1 fields. DIE=0 retains single-density sprite rows in double-density VDP2 output.
- STN-24: high-resolution decoding ignores both vertical-cell-scroll enables, preventing table fetches and stale offsets from affecting output. Existing T0–T3 fetch scheduling, full-detail NBG output, half-detail RBG output, colour-calculation restrictions, and suppression of extended calculation/blur remain implemented.
- Dedicated raster geometry now uses 426/424 normal dots (852/848 system-clock periods), doubled in high resolution, rather than ordinary-mode 427/455. HDTV uses 562 lines; 31kHz uses 525. Dedicated VBLANK begins after 480 displayed lines, independently of VRESO, with one screen line per vertical count step.

## Verification

`scripts/saturn_video_modes_test.py` extracts actual sprite adapter, framebuffer readout and CRTC methods. ASan/UBSan fixtures cover horizontal mode scaling, all six documented LSMD/DIE combinations at both field parities, current/previous packed and unpacked framebuffer fields, and dedicated raster budgets. Adapter tests establish which source rows are requested; they do not establish physical video waveform timing.

`scripts/saturn_vdp_wip_test.py` links the actual renderer and checks cell-scroll decoding in all eight horizontal modes, alongside existing window/rotation and framebuffer erase fixtures.

## Remaining limits

These bulletins specify permitted settings and expected picture behavior. They do not specify a reproducible waveform or image for prohibited combinations; the emulator accepts the raw settings rather than inventing an exception or forcibly correcting software writes.

Exact exclusive-monitor HBLANK signal/flag edges and H-counter discontinuities remain approximate or absent. See `VDP2_EXCLUSIVE_TIMING_RESEARCH.md`. The period fixes above do not verify those positions. Physical half-line interlace timing also remains approximate; no real-hardware waveform validation was performed. Therefore this work does not claim complete hardware fidelity or close the existing exclusive scan-timing item.
