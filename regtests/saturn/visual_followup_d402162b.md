# Visual follow-up: d402162b (2026-09-15)

## Latest: explosion rectangles still present (d0166ac6)

User confirms the 94cc6b24 RGB correction did **not** resolve After Burner II's
explosion transparency. The new archive contains 670,624 scaled command records;
every one uses color mode 1 (4-bit lookup table), not RGB texture mode 5. That
rules out describing the preceding RGB fix as this symptom's solution. The boot
fix remains user-confirmed. No new emulation change is justified from these
records alone: texture/LUT contents and framebuffer words are not logged.

Added `regtests/saturn/video_capture.lua`: on F12, capture the visible image,
VDP1 texture/LUT/command RAM, both framebuffer banks, VDP2 RAM/CRAM/registers
and small VDP1 state together. No rebuild or verbose log is needed. Standalone
Lua mocks pass (schema, byte bounds, cap, collisions, missing-item failure);
live MAME capture delivery is not yet tested. Instructions and binary format:
`regtests/saturn/video_capture.md`. Geometry and explosion artifacts remain open.

### d0166ac6 evidence details

`regtests/saturn/error.zip` contains one 276,239,113-byte error.log. The new
console identifies After Burner II, unlike the preceding multi-game console.
Scaled commands are overwhelmingly PMOD=0808 (LUT, SPD=0, ECD=0, preclip disabled),
with some 1808 HSS commands. Examples include COLR=0bc4 (LUT byte address 05e20),
SRCA=7980/79f0 and CMDSIZE=0437, drawing two oppositely oriented 32x55 halves.
These examples are not proven to be the explosion commands. SPCTL=1325 appears
in the active game: mixed RGB/palette, sprite type 5. A LUT texel may therefore
produce RGB, palette, or special sprite data depending on the table entry.
The raw 4-bit index, resolved 16-bit LUT word and displayed framebuffer pixel
are the missing discriminators. Do not add a LUT-MSB transparency rule: LUT
indices are not RGB texture words, and palette output is legal.


## Acceptance and evidence

The user confirms **After Burner II now boots**, following the shared SH DRC
interrupt-check fix d68770ea. Do not continue treating its sound/DMA startup
wait as open. This is boot acceptance, not full gameplay/graphics acceptance.

The seven supplied screenshots show several distinguishable symptoms:

- `015426`/`015444`: black rectangular regions around After Burner II effects.
- `015729`: another After Burner II attract scene; not every effect has the
  same visible rectangle. Treat changing size/mode as relevant, not proof of
  a particular draw command.
- `233647`: Power Drift title with white/displaced/clipped artwork.
- `042824`/`043304`: clipped SEGA artwork at different screen positions.
- `015553`: landscape gameplay with conspicuous dark/flat foreground regions.
  The screenshot itself does not identify the title.

`console.log` records After Burner II, OutRun, then Power Drift being launched.
The root probe is the last run's 20/21/22-second snapshots (PC 0602f036/3c),
not a graphics capture tied to every screenshot. The root error log ends at
25.16 seconds. Do not attribute every log entry to After Burner II or assume
that the old sound probe captures sprite/display state.

## Implemented: independent RGB END and transparency tests

`drawpixel_generic` previously turned RGB values below 7FFF into the
transparent comparison value, but explicitly excluded 7FFF. Thus ECD=1,
SPD=0 wrote 7FFF into the framebuffer. HSS reduction also disables END
processing, exposing the same error even when the command's ECD is clear.
A written 7FFF is not an RGB black pixel: it has MSB clear and can be decoded
as palette/priority/shadow data by VDP2. The visible result depends on SPCTL
and palette state.

The fix preserves the raw texel for END comparison and SPD-enabled writes,
while rejecting **all MSB-clear RGB texels** when SPD=0. ECD=0 still rejects
7FFF as END; ECD=1 does not disable the independent transparent-pixel gate.
No palette hack, game name condition, geometry offset, or DMA timing change.

### Primary/reference sources

- Sega VDP1 ST-013-R3-061694, pp.86–88: ECD, HSS and SPD are distinct controls.
  The p.88 table lists 0000 as RGB transparency; it does **not** by itself prove
  behavior for every MSB-clear word. Do not describe that table as saying so.
- MiSTer Saturn a95b085038ace57fa621558d60a7adc7a3c53f78,
  `rtl/Saturn/VDP1/VDP1_pkg.sv`, GetPattern: RGB TP=`~DATA[15]`,
  EC=`DATA==7FFF`; `VDP1.sv` combines TP/SPD and EC/ECD separately.
- Ymir 6d779960127ced72087a418c1daefc637d0aaa80,
  `libs/ymir-core/src/ymir/hw/vdp/renderer/vdp_renderer_sw.cpp`,
  VDP1PlotTexturedLine: END detection precedes independent `!bit15` transparency.

### Validation

262,144 RGB word/ECD/SPD combinations pass against the production pixel helper.
The deterministic prohibited ECD=0/SPD=1 combination is exercised but is not
claimed to be a supported software configuration. Normal-sprite, queued normal,
and scaled HSS/EOS image oracles now retain the background for MSB-clear RGB
END words with SPD=0. Removing the fix fails the normal-sprite image assertion.
All 22 Python regression scripts and eleven object compilations pass.

This is a verified pixel-path defect relevant to the effect rectangles, **not
confirmation that the screenshots' rectangles are all caused by this case**.
That requires running the rebuilt executable.

## Displacement/scaling remains unresolved

A scaled command near the end of the supplied log is CTRL=0a01, SIZE=226d,
A=(180,88), B=(272,109), local=(0,0); decoded bounds are (44,34)–(316,143).
Those are the expected center-anchor endpoint bounds. They do not establish
where the image ultimately appears: TVMR=2 selects rotated framebuffer readout.
Neither its six parameter-A values nor the VDP2 normal-layer scroll/zoom state
was present in the previous trace. Changing this command's anchor based solely
on the screenshot would be speculative.

Sega ST-058-R2 p.159 uses parameter A's Xst, Yst, deltaXst, deltaYst, deltaX,
deltaY for sprite rotation. The existing Q9 truncation was cross-checked with
MiSTer's ScrnStartToRC/ScrnIncToRC and is not changed here. Ymir's sprite affine
readout agrees on the six parameter fields, although its precision differs.

The existing `-verbose -log` trace now adds once-per-field `readout` records:
RPTA, the six decoded parameter-A words (zero when rotation is disabled), SPCTL,
BGON, CHCTLA, and both normal layers' scroll/zoom register pairs. Sprite command
records now include COLR. These read backing state only. They are field-boundary
samples, not per-dot parameter-latch timing proof.

**Next runtime check:** rebuild, check After Burner II effects and the displaced
logos/title screens. For a remaining geometry problem, retain a screenshot and
that run's `error.log` using `-verbose -log`. Copy/rename the log before starting
another title: MAME overwrites `error.log`. The sound-startup Lua script is not
needed for this graphics check. No displacement fix or full VDP1 completion is
claimed in this increment.
