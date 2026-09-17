# Agent C — devices handoff ledger (sound / storage / peripherals / ST-V / expansions)

This file is the live interface contract and status ledger for the device-side
work owned by implementation agent C.  Agent four integrates and qualifies the
whole system; nothing here is a claim of full Saturn/ST-V completion.

* **Baseline commit (start of this session):** `03c19a78e4cee7e9008a1100118934e8d84c0ea5`
* **Branch:** `arena/01a0ac86-mame` (platform-assigned; the only branch touched)
* **Checkout:** `/home/user/mame`
* **Upstream fork:** `https://github.com/jkind73/mame.git`

---

## 1. Build environment (reproduce this exactly)

The sandbox has **no** SDL2 / X11 / fontconfig development headers and **no**
Debian package network (`deb.debian.org` is unreachable; `github.com`,
`codeload.github.com` and `pypi.org` are).  A vendored toolchain was built
outside tracked source:

| Component | Source | Revision / tag | Installed at |
|---|---|---|---|
| SDL2 (static) | `github.com/libsdl-org/SDL` | `release-2.30.11` | `/home/user/sdk/sdl2` |
| fontconfig headers | `github.com/fontconfig/fontconfig` | `2.13.1` (`FC_MAJOR 2 FC_MINOR 13 FC_REVISION 1`, verified in `fontconfig.h:54-56`) | `/home/user/sdk/inc/fontconfig` |
| FreeType headers | `github.com/freetype/freetype` | `VER-2-13-2` | `/home/user/sdk/inc/freetype2` |
| pkg-config shim | local script | — | `/home/user/sdk/bin/pkg-config` |
| `libSDL2_ttf.a` | **stub object, 8 real symbols** (see below) | — | `/home/user/sdk/lib` |
| `libX11.a`, `libXinerama.a`, `libXext.a`, `libXi.a`, `libEGL.a` | empty archives | — | `/home/user/sdk/lib` |
| `SDL2/SDL_ttf.h` | API-subset stub header | — | `/home/user/sdk/sdl2/include/SDL2` |
| `inc/SDL2` | symlink → `sdl2/include/SDL2` | — | `/home/user/sdk/inc/SDL2` |

SDL2 configure line (all optional backends off, static only):

```
./configure --prefix=/home/user/sdk/sdl2 --enable-static --disable-shared \
  --disable-video-x11 --disable-video-wayland --disable-video-opengl \
  --disable-video-opengles --disable-video-kmsdrm --disable-video-vivante \
  --disable-video-cocoa --disable-render-d3d --disable-audio-pipewire \
  --disable-libudev --disable-dbus --disable-ibus --disable-fcitx \
  --disable-sdl2-config --disable-oss --disable-alsa --disable-pulseaudio \
  --disable-jack --disable-esd --disable-nas --disable-sndio
```

FreeType note: the release tarball has `include/freetype/`, **not**
`include/freetype2/`. The `freetype2` wrapper directory is created by
`make install`, so when taking headers straight from the archive you must build
that level yourself (`cp -r include/freetype inc/freetype2/` plus
`include/ft2build.h`).

The shim must emit **both** `-I$SDL/include/SDL2` (for `<SDL.h>`) and `-I$INC`
with the `inc/SDL2` symlink (for `<SDL2/SDL.h>`), and both `-L$LIBS` and
`-L$SDL/lib` on `--libs` — `libSDL2.a` installs under `$SDL/lib`, not `$LIBS`.

Notes on the stubs (honest labelling — these are build-time link satisfiers, not
working libraries):

* **`libSDL2_ttf.a` must not be empty.** An earlier revision of this ledger said
  it could be, on the grounds that `grep -rn "TTF_" src/osd/` returned no call
  sites. That is false: the grep returns **54** hits, all in
  `src/osd/modules/font/font_sdl.cpp` (`TTF_Init`, `TTF_Quit`, `TTF_GetError`,
  `TTF_OpenFontIndex`, `TTF_CloseFont`, `TTF_SetFontStyle`, `TTF_FontLineSkip`,
  `TTF_RenderUTF8_Solid`). An empty archive fails the link with undefined
  symbols, so the archive now contains a stub object defining exactly those
  eight entry points. **Consequence: this build renders no UI text.**
  `font_sdl.cpp:165` guards on `if (drawsurf)` and `TTF_OpenFontIndex` returning
  `nullptr` is handled, so the binary runs headless correctly — but it is not
  shippable.
* `libX11/Xinerama/Xext/Xi/EGL.a` are empty because SDL2 was configured without
  those backends, so no X11/EGL symbol is referenced. Note this is independent
  of MAME's own `input_x11.cpp`, which needs `NO_USE_XINPUT=1` — see
  `build_satdev.sh`.
* `fontconfig` links against the image's `libfontconfig.so.1` via a
  `libfontconfig.so` symlink. Header version (2.13.1) differs from the runtime
  (2.14.x); the `Fc*` entry points MAME uses are unchanged between them.

### Driver-filtered subtarget build

A full `make` builds every MAME driver (~10k translation units) — impractical on
the 2-core / 3 GB sandbox.  `regtests/saturn/handoff/build_satdev.sh` builds a
Saturn/ST-V-only binary through MAME's existing driver-filter mechanism
(`src/mame/satdev.flt` + `scripts/build/makedep.py filterproject`), which
computes the device dependency closure automatically.

```
sh regtests/saturn/handoff/build_satdev.sh          # -> ./mamesatdev
```

Effective options, and why each is needed:

| Option | Reason |
|---|---|
| `SUBTARGET=satdev` | filter file lists `sega/sat_console.cpp`, `sega/stv.cpp`, `sega/stvdev.cpp`; makedep pulls in `saturn*.cpp`, `smpc.cpp`, `315_5649.cpp`, `315-5838_317-0229_comp.cpp`, `315-5881_crypt.cpp`, `315_5338a.cpp`, `segabill.cpp`, `shared/rax.cpp` |
| `NOWERROR=1` | gcc-12 emits a false-positive `-Wrestrict`/`-Warray-bounds` inside libstdc++ `basic_string` when compiling `src/emu/device.cpp` (`device_t::subtag`).  Not a defect in this fork. |
| `NO_X11=1` | no X11 headers; also makes bgfx use `BGFX_CONFIG_RENDERER_OPENGLES=1` so its bundled `3rdparty/bgfx/3rdparty/khronos` headers are used instead of `GL/gl.h` |
| `NO_OPENGL=1` | no GL headers; drops the OSD OpenGL module |
| `OPT_FLAGS=-DUSE_OZONE …ggc params` | `-DUSE_OZONE` stops bgfx' bundled `EGL/eglplatform.h` from including `X11/Xlib.h`; the `--param=ggc-*` values cap `cc1plus` peak RSS (~2 GB → ~1.4 GB) so two parallel jobs survive on 3 GB |
| `USE_QTDEBUG=0` | no Qt moc |
| `NO_USE_{MIDI,PORTAUDIO,PULSEAUDIO,PIPEWIRE}=1` | no audio backend headers |

`src/mame/satdev.flt` is regenerated by the script and is listed in
`.git/info/exclude` — it is a local build accelerator, not a shipped target.

---

## 2. Per-ID status

Labels: **M** missing, **P** partial, **V** verification open, **R** research
required, **D** done this session, **—** not started this session.

| ID | Status | Summary of verified state at baseline |
|---|---|---|
| SND-01 | P/V — | `sat_console.cpp:1098` runs the sound `M68000` at 11 289 600 Hz with `sound_mem`; `stv.cpp` mirrors it. Sound-RAM window is 512 KiB with the upper half unmapped (`stv.cpp:1245` comment cites ST-077 Figure 1.3). |
| SND-02 | V/R — | 32-voice engine, FM, envelopes, LFO and DSP present in `src/devices/sound/scsp.cpp` (1766 lines). No chip-wide hardware audit exists. |
| SND-03 | P — | Timers re-armed from a `timer_sync`/`timer_arm` pair, `exec_dma()` present, `main_irq_cb` routed to `saturn_scu_device::sound_req_w`. MIDI in/out FIFOs implemented over `device_serial_interface`. |
| SND-04 | V/R — | `scspdsp.cpp` is 326 lines. Not audited against ST-077 chapter 6. |
| SND-05 | P — | `device_post_load()` exists and MIDI/DMA state is in `save_item`s. Round-trip under live envelopes/DMA not yet qualified. |
| CD-01 | P — | `saturn_cd_hle.cpp` (4249 lines) implements the full CR1–CR4 command set. **Known open:** `device_reset()` sets `hirqreg = 0x0001` with a `FIXME` saying zero "breaks CD auto load and azelpanztai". |
| CD-02 | P — | `cdrom`/`cdda` subdevices; seek/sector timers. Drive timing not calibrated against hardware. |
| CD-03 | M — | `saturn_cdb.cpp` is a 52-line skeleton. The SH-1 is instantiated **and disabled**: `cdbcpu.set_disable(); // we're not actually using the CD Block ROM for now`. Only `map(0, 0xffff).rom()` exists — no YGR019 registers, no sound/CD RAM, no host interface. |
| CD-04 | P — | `cmd_check_copy_protection` / `cmd_get_disc_region` implemented in the HLE. |
| CD-05 | P — | transfer state saved (`xfertype`, `xfertype32`, `xfer*`). Reset/abort paths not qualified. |
| IO-01 | P — | `src/devices/bus/sat_ctrl/`: joy, racing, analog, mission, gun, pointer, mouse, keybd, joy_md, multitap, segatap. `read_pdr()` hook exists for direct-mode line protocols. |
| IO-02 | M/P — | Inventory incomplete. No modem/NetLink device; `saturn/st17xx.cpp` is a skeleton. |
| CART-01 | P — | `src/devices/bus/saturn/`: `sat_bram_{4,8,16,32mb}`, `sat_dram_{8,32mb}`, `sat_rom`, `sat_cart_slot`. Capacity/bank/lane qualification outstanding. |
| NVR-01 | P — | backup RAM + SMPC RTC exist. Cold-start/battery-loss behaviour not qualified. |
| STV-01 | P — | `stv.cpp` board wiring, EEPROM `AK93C45F` modelled as `EEPROM_93C46_16BIT`. |
| STV-02 | M/P — | `sega_315_5838_comp_device::get_decompressed_byte()` returns **`machine().rand()`** in `HACK_MODE_NO_KEY`, which 20+ drivers select via `init_decathlt_nokey()`. The keyed cipher is not implemented. |
| STV-03 | P — | `315_5649.cpp` implements ports A–G, direction register, analog mux and G-counter mode. |
| STV-04 | M/P — | printer/hopper hooks exist (`m_hopper`, `m_billboard`); protocol depth unverified. |
| STV-05 | M — | `315_5649.cpp` RS-422 status register is `data = 0x0c; // HACK, recv buffers always full, transmit buffers always empty`. `stvdev.cpp` is a 76-line i486 skeleton (`stvdev_io()` empty). |
| STV-06 | V — | 66 `MACHINE_NOT_WORKING` configurations in `stv.cpp` (see §4). |
| EXP-01 | M — | no MPEG card device exists anywhere in `src/`. MPEG commands are answered by the CD HLE (`mpeg_bringup`, `cmd_mpeg_*`). |
| EXP-02 | M — | nothing to accept yet. |

---

## 3. Verified build + runtime results

Binary: `mamesatdev`, MAME v0.289 (unknown), driver-filtered subtarget
(`src/mame/satdev.flt`), `-O1`, `REGENIE=0` incremental.

```
sha256  0309955846af7591083447a5c5edf0e7ac63e00521ab365425acca2313b888e2  mamesatdev
        (second build, toolchain recreated from scratch after the first was wiped)
sha256  b3d285886ba75656fd0efc317d5b2db80a1fc12765dcef3241f700a91280e255  mamesatdev
        (first build; superseded, no longer on disk)
size    87 772 768 bytes
```

**This binary links against a stub SDL_ttf and therefore renders no UI text. It
is a test vehicle, not a shippable build.** See §1.

| Check | Command | Result |
|---|---|---|
| Static validation | `./mamesatdev -validate` | **exit 0**, no diagnostics |
| Driver list | `-listxml` | all 8 present: `saturn saturnjp saturneu saturnkr vsaturn hisaturn stvbios stvdev` |
| BIOS boot + save/load replay | `run_vdp2_runtime.py --system saturnjp --bios` | **PASS** `time=15.560998664 pc=06040226 full-image replay identical` |
| " | `--system saturneu` | **PASS** `time=18.439710253 pc=060402e4` |
| " | `--system stvbios` | **PASS** `time=15.543578728 pc=060154a8` |
| " | `--system saturn` (needs `saturneu.zip` copied to `saturn.zip` — parent set is only packaged under the clone) | **PASS** `time=15.560998664 pc=060402e4` |
| " | `saturnkr` direct (not a `--system` choice in `run_vdp2_runtime.py`) | **PASS** `time=15.560998664 pc=06040226` |
| Unit fixture | `regtests/saturn/test_ioga_serial.py` | **PASS**, 4113 cases; `MUTATE_IOGA=1` fails |
| Unit fixture | `regtests/saturn/test_sat_cart.py` | **PASS**, 24 cases; `MUTATE_CART=1` fails with `runtime error: division by zero` / SIGFPE |
| Compile | `g++ -fsyntax-only -std=c++20` on `dram.cpp`, `bram.cpp`, `315_5649.cpp` | **PASS** |

`run_vdp2_runtime.py --system saturnkr` is rejected by its own argparse
`choices`; invoke `mamesatdev` directly with `bios_runtime.lua` instead.

### Which changed code each check actually reaches

* `315_5649.cpp` — **reached.** `stvbios` instantiates two `315_5649` devices
  (`-listdevices`), so the passing ST-V BIOS boot executes the modified
  `read`/`write` paths, including status `0x0d`.
* `dram.cpp` / `bram.cpp` — **not reached by any runtime check I ran**, but the
  devices are wired up and *are* reachable. An earlier revision of this ledger
  claimed no slot option was registered anywhere; that was wrong. Corrected
  account:

  `sat_console.cpp:1191-1198` registers all seven cards —
  `rom`, `ram8`, `ram32`, `bram4`, `bram8`, `bram16`, `bram32` — via
  `device_slot_interface::option_add_internal()`. Per `src/emu/dislot.h:146` an
  *internal* option is deliberately not user-selectable (contrast `option_add`,
  documented at `dislot.h:120-126` as selectable "via the command line"), which
  is exactly why `-listxml saturnjp` renders `<slot name="exp"></slot>` with no
  `<slotoption>` children. The empty slot element is not evidence of missing
  wiring.

  The intended entry point is the software list: `SOFTWARE_LIST(config,
  "cart_list").set_original("sat_cart")`, and `hash/sat_cart.xml` carries
  `ram8`, `ram32`, `bram4`, `bram8`, `bram16`, `bram32` whose
  `feature name="slot"` values match those internal option names one for one.

  **Corrected, and now measured.** An earlier revision of this ledger said those
  softlist entries declare no data area, so every `*_alloc()` is skipped and the
  vectors stay empty. That was wrong — it came from a regex that matched only the
  single-line `<feature>` element and missed the `<dataarea>` elements, which
  span two lines. `-listsoftware saturnjp` shows `ram8` actually declares:

  ```xml
  <part name="cart" interface="sat_cart">
      <feature name="slot" value="ram8" />
      <dataarea name="dram0" size="524288"></dataarea>
      <dataarea name="dram1" size="524288"></dataarea>
  </part>
  ```

  So `call_load()` takes the non-ROM branch, finds both regions and calls
  `dram0_alloc(524288)` / `dram1_alloc(524288)` — each vector gets
  `524288 / sizeof(uint32_t)` = `0x20000` words. **Not empty**, so the
  `m_ext_dramN.empty()` guard is *not* what `ram8` exercises; what it exercises
  is the aliasing branch, 512 KiB of chip answering inside the 2 MiB window.

  Measured with the rebuilt binary:

  * `-listdevices saturnjp -cart ram8` shows `exp / ram8 — Saturn Data RAM 8Mbit
    Cart`; the same command without `-cart` shows the `exp` slot with no child.
    The device is genuinely instantiated.
  * A 300-frame BIOS run with `-cart ram8`, counting via
    `install_read_tap` / `install_write_tap` on the main CPU program space:
    `dram0 read=0 write=0 dram1 read=0 write=0`.
  * Control on the same script, same run: `CONTROL_workram_read=3077295` over
    `0x06000000-0x060fffff`. The tap mechanism works, so the zeros are real.

  **Conclusion, stated plainly: the BIOS never touches the cartridge DRAM
  windows.** That is expected — only a title that uses a Data RAM cart (`kof95`,
  `ultraman`) would — and there are no game ROMs here. So `dram.cpp` and
  `bram.cpp` are instantiated at runtime but their accessors are still **not
  executed** by any test I can run. The unit fixture `test_sat_cart.py`, which
  extracts the production handlers verbatim and drives 24 cases including the
  empty-region one, remains the only executed coverage of that code.

## 4. Endpoint contracts

*(filled in as endpoints are implemented — see the per-section notes below)*

## 5. NOT_WORKING inventory in owned drivers

`src/mame/sega/stv.cpp` carries 66 `MACHINE_NOT_WORKING` entries:

* ~45 are Atlus **Print Club / Purikura** titles on `stvpc_state` (external
  "837-12764 486 BD FOR ST-V" i486 board) → **STV-05**.
* 8 use `init_decathlt_nokey()` (`pclove`, `pclove2`, `pcpooh2`, `pcpooh3`,
  `pclubsc5`, `pclubsc6`, `pclubnbc`, `nameclub`) → **STV-02**.
* remainder: `aclub`, `chalgolf`, `choroqhr`, `decathlt`, `decathlto`, `dfeverg`,
  `fanzonem`, `finlarch`, `magzun`, `myfairld`, `sackids`, `sfish2`, `sfish2j`,
  `slotbatt`, `smleague`, `stress`, `tsuribor`, `twcup98`, `twsoc98`, `vfremix`,
  `wasafari`, `wwshin`, `yattrmnp`, plus `pckobe99`, `nclubdis`, `nclubv2`.

All six Saturn console configurations (`saturn`, `saturnjp`, `saturneu`,
`saturnkr`, `vsaturn`, `hisaturn`) are `MACHINE_NOT_WORKING` at
`sat_console.cpp:1343-1353`.

---

## 6. Log

| Date | Commit | What |
|---|---|---|
| 2026-09-16 | `03c19a78` | session start; baseline recorded; vendored build environment established |
| 2026-09-16 | `e64f5e50` | `dram.cpp` / `bram.cpp` bounds from region size; `315_5649` RS-422 loopback + port G counter reset; `build_satdev.sh`; this ledger |
| 2026-09-16 | `f25b191e` | `test_ioga_serial.py` — 4113 cases, `MUTATE_IOGA` control |
| 2026-09-16 | `31694ccf` | `test_sat_cart.py` — 24 cases, `MUTATE_CART` control |
| 2026-09-16 | `341a556f` | `build_satdev.sh`: `NO_USE_XINPUT=1` is the knob that excludes `input_x11.cpp` |
| 2026-09-17 | (this commit) | subtarget links; `-validate` clean; BIOS boot/replay PASS on `saturn`, `saturnjp`, `saturneu`, `saturnkr`, `stvbios`. Recorded that the `exp` cart slot registers no options, so `dram.cpp` / `bram.cpp` are not runtime-reachable |
| 2026-09-17 | `9add769b` | drop `regtests/saturn.zip` (a 1 014 371-byte ROM archive) that `946a2184` had swept in via `git add -A`; ROMs stay outside tracked source |
| 2026-09-17 | (this commit) | **corrected the previous row's claim.** The `exp` slot *does* register all seven carts (`sat_console.cpp:1191-1198`, `option_add_internal`); they are reachable through the `sat_cart` software list, not the command line. The `size() == 0` softlist path is exactly what the DRAM guard protects. See §3 |
| 2026-09-17 | `9a50420f` | `devices.md` §1 rewritten after rebuilding the toolchain; two false claims removed (`libSDL2_ttf.a` cannot be empty — 54 `TTF_` call sites in `font_sdl.cpp`; fontconfig is `fontconfig/fontconfig@2.13.1`, not a maintainer fork at `master`) |
| 2026-09-17 | (this commit) | toolchain recreated, subtarget rebuilt (`03099558…`), all §3 results re-run and identical to the first build. **Corrected the `ram8` account**: it *does* declare `dram0`/`dram1` data areas, so the vectors are allocated and the empty-region guard is not what it exercises. Measured with a memory tap: the BIOS makes **zero** accesses to either DRAM window (control 3 077 295 workram reads in the same run), so `dram.cpp`/`bram.cpp` accessors remain unexecuted at runtime |

### Reproducibility, and the sandbox note

The toolchain that produced the first binary lived at `/home/user/sdk`, outside
the repository, and was wiped from the sandbox along with `mamesatdev`. It was
then recreated from scratch per §1 and the subtarget rebuilt. The two
independently built binaries — different `libSDL2.a`, different object files,
different link — produce **identical** boot/replay results on every
configuration: `saturnjp time=15.560998664 pc=06040226`,
`saturneu time=18.439710253 pc=060402e4`,
`stvbios time=15.543578728 pc=060154a8`,
`saturn time=15.560998664 pc=060402e4`,
`saturnkr time=15.560998664 pc=06040226`, each with full-image replay identical.

Every result in §3 above has been re-run against the current `03099558…` binary.
The `-lEGL`, `Fc*` and `315_5195` / `315_5296` / `315-6154` link failures that
were flagged as a risk in an earlier revision did **not** occur; the subtarget
links cleanly with the flags in `build_satdev.sh`.
