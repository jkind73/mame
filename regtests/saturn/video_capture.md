# Read-only graphics capture

Use this on an existing build containing 94cc6b24 or later. No rebuild is needed.
This replaces the sound probe for the unresolved After Burner II explosion
rectangles; **do not enable verbose logging for this capture**.

```sh
mame saturnjp aburner2 -autoboot_delay 0 -autoboot_script regtests/saturn/video_capture.lua
```

While a bad explosion is visible, press **F12**. MAME also takes its normal
screenshot. The Lua script captures the screen pixels and graphics backing
state in `saturn-video-YYYYMMDD-HHMMSS-NNN.bin` in the working directory.
It accepts up to three presses per launch. Zip the `.bin` file(s) and upload
that zip. Each capture is approximately 2–3 MB before compression, instead of
hundreds of MB of event logging. Existing capture files are never overwritten.

Includes:
- physical VDP1 framebuffer banks and displayed-bank index;
- first 512 KiB of VDP1 VRAM, including command lists, textures and LUTs;
- VDP1/VDP2 registers, VDP2 VRAM and color RAM;
- small VDP1 command/framebuffer state and the visible screen's RGB pixels.

Uses `emu.item():read_block()` and `screen:pixels()`, not MMIO reads, CPU writes,
or memory taps. F12 has its usual MAME screenshot action as well. Dumping can
briefly stall the host. The capture is at a frame callback, not a historical
record of every draw-time VRAM access; display pixels may reflect state from
earlier in the field. Both framebuffer banks and both command-list areas are
retained to help distinguish that timing issue.

The standalone fixture checks binary records, byte limits, screen correspondence,
three-capture cap, filename collision avoidance and missing-state failure:

```sh
# Run in an otherwise empty temporary directory, with absolute script paths:
lua /path/test_video_capture.lua /path/video_capture.lua
```

## Container format

Magic: `SATURN-VIDEO-1\n` (15 bytes). Records repeat until EOF:
1. name length: big-endian unsigned 32-bit;
2. name: that many bytes, ASCII;
3. element size: big-endian unsigned 32-bit;
4. payload byte length: big-endian unsigned 32-bit;
5. payload: exactly that many bytes.

`metadata` contains newline-separated system/time/width/height/endian fields.
`screen.pixels` is native-endian 32-bit RGB values in visible-area row order.
All save-item payloads retain the recorded host endianness and declared element
size. For example, VDP1 VRAM is native-endian uint32 words representing big-endian
emulated memory, while framebuffer words are native-endian uint16. Do not treat
those payloads as already byte-ordered SH-2 memory. Names are canonical save-item
leaves (e.g. `m_vdp1_vram`, `m_vdp1_legacy.framebuffer[0]`).
