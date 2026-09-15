# After Burner II graphics capture: 3c31f363

## Identified defect: HSS forces ECD and draws LUT END pixels

The archive contains three successful video captures, each 2,391,134 bytes,
at 59.499904569, 61.390649568 and 65.021549256 emulated seconds. The first two
show black regions around effects; the third supplies a scene without the same
conspicuous rectangular background. The capture tool worked on the live build.

Capture 001's displayed framebuffer index is 0. In the explosion rectangle,
framebuffer coordinates (134,99) and (134,100) contain **8000**, not transparent
0000 or palette data. With the game's mixed RGB/palette sprite format, that is
opaque RGB black. This locates the problem before final VDP2 palette blending.

The captured explosion LUT at byte address 05D40 (CMDCOLR=0BA8) is:

```
8000 9068 906C 9090 90B3 9137 91DC 921E
8000 8000 8000 8000 8000 8000 8000 8000
```

The source textures at CMDSRCA=4D40/4DB8 use indices 0–7 and F. F resolves to
8000; it must be rejected as END when ECD=0 rather than displayed as that LUT
color. Index zero remains separately governed by SPD.

The accompanying log at 59.456322774 / 59.456350934 identifies two commands:

- CTRL=0001, PMOD=1808, COLR=0BA8, SIZE=043C (source 32x60);
- SRCA=4D40, bounds (154,99)–(173,135), destination 20x37;
- SRCA=4DB8, bounds (153,99)–(134,135), destination 20x37.

These bounds locate the visible rectangle. PMOD=1808 has HSS=1, ECD=0, SPD=0,
LUT mode, and preclipping disabled. The old code replaces effective HSS with
ECD during horizontal reduction, allowing sampled F values to reach the LUT
and write opaque black. Capture 002 likewise shows rectangles on smaller
effects while a large foreground effect has an irregular silhouette.

Caveat: screen pixels, display-bank state and command RAM are captured at a
frame callback, not at each historical draw. The current command list has
already changed by the snapshot; the associated log is needed to identify
these earlier bounds. This analysis does not claim a full pixel-perfect replay
of the entire captured frame.

## Correction and source conflict

Keep the guest ECD setting unchanged in all three texture paths: synchronous
scaled rectangles, queued scaled rectangles, and native textured spans.
Retain an effective HSS bit only on reduced rows so the source-row visibility
helper bypasses two-END termination. Individual END texels remain rejected by
the pixel writer when ECD=0. ECD=1 still allows their colors to be drawn.

Primary document ST-013-R3-061694 p.86 explicitly says END pixels become
transparent with ECD=0, but its HSS/reduction table says END processing is
disabled and the color is expressed. The latter wording conflicts with the
following two independent implementations; do not claim that table alone
proves this correction:

- Ymir 6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/vdp/renderer/vdp_renderer_sw.cpp`,
  `VDP1PlotTexturedLine`: HSS initializes `endCodeCount` to a very negative
  value, disabling two-END termination, but `hasEndCode` still follows ECD
  and prevents plotting the sample.
- MiSTer a95b085038ace57fa621558d60a7adc7a3c53f78,
  `rtl/Saturn/VDP1/VDP1.sv`: `IS_PAT_EC` includes `!HSS_EN` for row handling,
  while `FB_DRAW_WE` separately uses `(~EC | CMD.CMDPMOD.ECD)` with no HSS
  override. `VDP1_pkg.sv::GetPattern` identifies the LUT F marker independently
  of its resolved color.

The change follows those implementations and the captured game's failure
mechanism. It is not based on a new physical-hardware measurement or an
identified Sega erratum. No game-specific conditional, forced LUT-MSB
transparency, palette edit, VDP2 black-color exception or geometry offset.
The earlier RGB transparency correction remains independent and unchanged.

## Validation and acceptance

- Four focused synthetic LUT cases, synchronous/queued and ECD=0/1: HSS
  samples F,F,1,2. With ECD=0 the two markers preserve the background, **and
  later red/green texels still draw**. ECD=1 draws the LUT's black entries.
- Updated the existing scaled HSS/EOS and native-quad independent image
  oracles to distinguish marker suppression from row termination.
- Restoring forced ECD fails a rendered-pixel assertion. The initial mutation
  harness count needed adjustment for three call sites; the final mutation
  was compiled and failed in the C++ pixel test, not merely in test setup.
- All 22 Python regression scripts and eleven object compilations pass.
- No extracted graphics assets or generated framebuffer images are committed;
  the focused regression uses synthetic texels/colors.

**Rebuild required.** This fixes the identified HSS/LUT path; user confirmation
of corrected explosions is still pending. After Burner II boot remains
user-confirmed. Other logo/title displacement is a separate open issue.
