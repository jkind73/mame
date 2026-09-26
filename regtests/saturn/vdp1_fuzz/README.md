# VDP1 differential fuzz (MAME vs Ymir)

Single-command VDP1 cases (normal/scaled/distorted sprite, polygon, polyline, line; 16 and 8 bpp frame buffer)
are generated, drawn in Ymir and replayed in MAME with both SH-2s parked; the displayed frame buffers are compared.

1. Build `vdp1fuzz.cpp` as a Ymir client (needs ymir-core; it uses `#define private public` to reach `VDP1GetDisplayFramebuffer`).
2. `python fzdrive.py <seed> <count> <prefix>` runs each case in its own process (a Ymir VDP left in some states stops
   rendering frames, so cases must not share state) and writes `<prefix>_cases.bin`, `_ymir.bin`, `_desc.txt`.
   `FZ_ECD=1` forces ECD=1 in every case (removes the end-code cases where Ymir differs from Mednafen/MiSTer).
3. `FZ_PREFIX=<prefix> FZ_COUNT=<count> mame saturnjp -nothrottle -video none -sound none -autoboot_script vdp1fuzz.lua`
   writes `<prefix>_mame.bin`. The Lua script clears the frame buffer through the bus (MAME's own erase is line-timed).
4. `python fzcmp.py <prefix>` summarises per command kind; `python fzshow.py <prefix> <case>` lists differing pixels.
