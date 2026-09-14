# VDP1 completion audit — 2026-09-14

**Status: in progress, not a complete VDP1 implementation.** The existing renderer
is synchronous; completing its timing and interruptible execution requires more
than filling register handlers. No BIOS/game or hardware trace has been run here.

## Implemented in this pass

- Recognize CMDCTRL.END independently of the other control bits.
- Wrap sequential command fetch at the 512 KiB VRAM boundary.
- Generate SCU draw-end at the existing completion callback, alongside CEF, not
  unconditionally eight scanlines after VBlank. A host iteration-limit exit or
  unsupported command is not reported as a fetched END. Starting another list
  cancels the old outstanding completion estimate.
- Fix the upper two data lanes of CPU framebuffer writes in 8-bit modes. Preserve
  masked-off bytes and keep accesses on the selected drawing bank.
- Implement outside-user-clipping in all five pixel writers, keeping system
  clipping enabled. Inside includes the rectangle boundary; outside excludes it.
  Reject negative coordinates before indexing framebuffer line pointers. Outside
  mode rasterizes against the system rectangle, not the excluded user rectangle.

These remove a title-specific periodic IRQ workaround rather than adding one.
They can expose software that depended on the old fabricated completion; runtime
regression coverage is required before claiming improved game compatibility.

## Evidence

Primary: [Sega ST-013-R3-061694](https://github.com/jkind73/saturnsdk/blob/0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73/ST-013-R3-061694.pdf).
The PDF was downloaded/extracted outside Git, with 178 pages.

- §3.1 printed p.19 / PDF p.34: command fetch wraps after 07FFFFH.
- Printed p.20 / PDF p.35: CPU accesses the drawing framebuffer; byte access is
  allowed in 8-bit display, prohibited in 16-bit display. The lane repair follows
  the existing big-endian CPU register interface; no prohibited-access behavior
  is invented.
- §4.6 printed p.52 / PDF p.67: END fetch sets CEF and produces an interrupt;
  unreachable/missing END leaves CEF clear. This does not establish our delay.
- §7.10 printed p.132 / PDF p.147: END is bit15; the remaining command is ignored.
- §6.3 and §7.1/7.2: system clipping always applies, with inclusive rectangle
  boundaries; user clipping can select inside or outside. Technical Bulletin 15
  corrects swapped Clip/Cmod prose in an earlier manual edition. This edition's
  §6.3 also has contradictory Cmod boundary prose; §7.2 explicitly treats points
  on the line as inside, consistent with the diagram and reference renderer.

Cross-check: [Ymir VDP](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/vdp/vdp.cpp)
uses `control.end`, masks the next address to 0x7ffff and emits draw-end in
`VDP1EndFrame`. Its [software renderer](https://github.com/jkind73/Ymir/blob/6d779960127ced72087a418c1daefc637d0aaa80/libs/ymir-core/src/ymir/hw/vdp/renderer/vdp_renderer_sw.cpp)
checks system clipping and complements the inclusive user test for outside mode.
Reference agreement is not hardware timing proof, and no source was imported.

## Executed coverage

`python regtests/saturn/test_vdp1.py` extracts production bodies and runs ASan/UBSan:

- 32,775 command/completion cases: every END control combination, a looping list
  replacing pending completion, CALL/RETURN at the final VRAM slot, sequential
  wrap, and dispatcher clip-rectangle selection.
- 288 CPU framebuffer cases: both banks, normal and 8-bit modes, four payloads,
  all legal byte-lane combinations (only word accesses tested in 16-bit mode),
  readback and preservation of the other bank.
- 24,500 actual pixel-writer cases: fast and generic variants, both clip bits,
  inside/outside/boundary/system rejection and negative coordinates.
- `--baseline commands`, `--baseline framebuffer`, and `--baseline clipping`
  substitute the pre-fix bodies and fail independently.

Rasterizers, time conversion, and SCU IRQ delivery are recording endpoints in
this harness. Generic color calculation is not tested here. No claim follows
about full rendering, actual IRQ latency or MAME save-manager restoration.
The full validator passes **18 scripts and nine object compilations**.

## Remaining implementation and acceptance gates

| Area | Current gap | Required implementation/verification |
|---|---|---|
| Command scheduling / ENDR | Whole lists rasterize synchronously; ENDR still only logs. | Incremental command/pixel execution with saved active command, return address and pending work; stop after documented approximately 30 VDP1 clocks, without undoing already drawn pixels or inventing END. Test stop during every command family and reset/save-load. |
| Timing / transfer-over | Completion still estimates 16 SH-2 cycles per fetched command; pixel/bus costs are absent. | Model fetch/pixel/VRAM arbitration and elapsed drawing across frames; measure against primary constraints and traces, not title delays. |
| PTMR / FBCR / EDSR / pointers | Automatic start/swap/erase timing and BEF/LOPR/COPR remain incomplete. | Resolve latch points and reset behavior from manuals/supplements; test manual erase/change, automatic draw, busy writes and transfer-over. Do not equate each VBlank with a framebuffer change. |
| Command control | Unsupported commands/returns abort; loop limit cannot resume when guest edits VRAM. | Define documented branch/call/return semantics, retain live fetch state and park/resume loops safely. Test all eight jump modes; investigate illegal-command behavior separately. |
| Framebuffer formats | CPU lane fix is not full 8-bit rasterization. | Packed 8-bit drawing, 16-bit drawing, double-interlace/EOS, rotated layouts, erase bounds and framebuffer readout integration with VDP2. |
| Rasterization | Affine quad/line code has known vertex, stipple and zoom differences. | Hardware-consistent line/polygon edge coverage and sprite scaling; pixel-golden tests for degenerates, flips, all zoom anchors, clipping and negative coordinates. |
| Texture / color | End-code support only skips a matching texel; full scanline termination is absent. | Two-end-code behavior in texture traversal, transparent pixels, high-speed shrink, mesh, MSBON, shadow/half-luminance/transparency and Gouraud combinations. |
| Save/reset | Existing framebuffers/timer saved, but future in-flight execution needs persistent state. | Real MAME round trips during drawing/erase, before END, after ENDR and across framebuffer changes; verify reconstructed pointers and no duplicate IRQs. |
| Runtime | No linked executable in this sandbox. | Install documented SDL/pkg-config dependencies, link and `-validate`, then BIOS and legally available Saturn/ST-V smoke/pixel comparisons (including prior workaround titles). |

Do not mark this table complete from standalone tests or an absence of TODOs.
