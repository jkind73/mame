# Agent C — devices handoff ledger (sound / storage / peripherals / ST-V / expansions)

This file is the live interface contract and status ledger for the device-side
work owned by implementation agent C.  Agent four integrates and qualifies the
whole system; nothing here is a claim of full Saturn/ST-V completion.

* **Baseline commit (start of this session):** `03c19a78e4cee7e9008a1100118934e8d84c0ea5`
* **Branch:** `arena/01a0ac86-mame` (platform-assigned; the only branch touched)
* **Checkout:** `/home/user/mame`
* **Upstream fork:** `https://github.com/jkind73/mame.git`
* **Current binary:** `mamesatdev` sha256 `3d536a7a076f730d32f37f3ede0163fd863f185f9a92e6d7d039ee10a1d9b736`
  — a test vehicle linked against a stub SDL_ttf, not a shippable build. Full
  history and the verification each one was used for: §3.

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
| SND-02 | P/V **D** | 32-voice engine, FM, envelopes, LFO and DSP present in `src/devices/sound/scsp.cpp` (1766 lines). **Slot register word 0 now checked field-by-field against ST-077-R2 Figure 4.2, and the voice engine is now exercised end to end at runtime by `test_scsp_voice.py`** (KEY_ON → audible output → KEY_OFF → silence, captured from the WAV). See §3. Still unaudited: FM cross-modulation, LFO, and the DSP (SND-04). |
| SND-03 | P/V **D** | Timers re-armed from a `timer_sync`/`timer_arm` pair, `exec_dma()` present, `main_irq_cb` routed to `saturn_scu_device::sound_req_w`. MIDI in/out FIFOs implemented over `device_serial_interface`. **DMA now verified at runtime against ST-077 Figure 4.3 by `test_scsp_dma.py`** — see §3. **The prescaler timers are now verified at runtime too: `test_scsp_timers.py` measures all eight ST-077-R2 increment divisions and the timer A interrupt.** The `reg_addr & 0xffe` wrap I had flagged as unsupported by the manual is in fact exactly the documented `DRGA[11:1]` field. |
| SND-04 | V/R — | `scspdsp.cpp` is 326 lines. Not audited against ST-077 chapter 6. |
| SND-05 | P/V **D** | `device_post_load()` exists and MIDI/DMA state is in `save_item`s. **Timer round-trip now verified at runtime by `test_scsp_savestate.py`** — counter, prescaler and the `base_time` rebase in `device_post_load()` all confirmed, with a mutation control. See §3. Still unqualified: round-trip while **voices/envelopes and DMA are actively running**, and MIDI FIFO state. |
| CD-01 | P/V **D** | `saturn_cd_hle.cpp` (4249 lines) implements the full CR1–CR4 command set. **Fixed this session:** `hirq_r()` force-cleared DCHG on every read, which made the documented tray-open detection path unobservable to software — see §3 "CD block host interface". CMOK command completion, HIRQ write-to-clear and DCHG reporting are now verified at runtime by `test_cd_hirq.py`, with mutation controls. **Still open:** `device_reset()` sets `hirqreg = 0x0001` with a `FIXME` saying zero "breaks CD auto load and azelpanztai"; and `hirq_r()` ignores `side_effects_disabled()` (unlike `hirqmask_r()`), so peeking HIRQ from a debugger or cheat mutates it. Both left alone — resolving them needs ST-172, which is not in the local corpus. |
| CD-02 | P — | `cdrom`/`cdda` subdevices; seek/sector timers. Drive timing not calibrated against hardware. |
| CD-03 | M — | `saturn_cdb.cpp` is a 52-line skeleton. The SH-1 is instantiated **and disabled**: `cdbcpu.set_disable(); // we're not actually using the CD Block ROM for now`. Only `map(0, 0xffff).rom()` exists — no YGR019 registers, no sound/CD RAM, no host interface. |
| CD-04 | P — | `cmd_check_copy_protection` / `cmd_get_disc_region` implemented in the HLE. |
| CD-05 | P/V — | transfer state saved (`xfertype`, `xfertype32`, `xfer*`). **`hirqreg` round-trip now verified at runtime** by `test_scsp_savestate.py` (DCHG survives save/load, `0421` → `0421`). Still unqualified: the transfer state itself under an in-flight read, and the reset/abort paths. |
| IO-01 | P/V **D** | `src/devices/bus/sat_ctrl/`: joy, racing, analog, mission, gun, pointer, mouse, keybd, joy_md, multitap, segatap. `read_pdr()` hook exists for direct-mode line protocols. **Audited this session against ST-169-R1 (SMPC User's Manual), extracted from the corpus: every peripheral ID, data size and data-byte layout checked out with no defect** — see §3 "Controller formats". Two things remain: the keyboard shift/kana semantics (**research required**, corpus exhausted — see §3) and the INTBACK report being truncated at 32 OREG bytes rather than using the manual's 15/255-byte port modes (**agent A's SMPC transport layer**). |
| IO-02 | P/V **D** | **Inventory completed this session** — see §3 "Communication devices". **Corrected:** `saturn/st17xx.cpp` is *not* a communication device, it is 10 skeleton DVD-player consoles (ST-1700h…ST-1714). Implemented and tested: the 315-5649 IOGA RS-422 link. Stubbed: SMPC `NETLINKON`/`NETLINKOFF`. Missing entirely: NetLink modem, Sega Saturn modem, XBAND. One game-motivated hardcoded byte found inside the CD block map and flagged, not fixed. |
| CART-01 | P — | `src/devices/bus/saturn/`: `sat_bram_{4,8,16,32mb}`, `sat_dram_{8,32mb}`, `sat_rom`, `sat_cart_slot`. Capacity/bank/lane qualification outstanding. |
| NVR-01 | P/V **D** | backup RAM + SMPC RTC exist. Persistence and byte-lane behaviour now verified by `test_backup_ram.py` — see §3. **Characterised limitation:** loading a save state does *not* restore backup RAM. Cold-start/battery-loss still unqualified. |
| STV-01 | P — | `stv.cpp` board wiring, EEPROM `AK93C45F` modelled as `EEPROM_93C46_16BIT`. |
| STV-02 | M/P — | `sega_315_5838_comp_device::get_decompressed_byte()` returns **`machine().rand()`** in `HACK_MODE_NO_KEY`. **Corrected count:** that mode is selected only by `stv_state::init_decathlt_nokey()` (`stv.cpp:1123`), which is referenced by exactly **9** `GAME()` entries (`nameclub nclubv2 pclove pclove2 pclubnbc pclubsc5 pclubsc6 pcpooh2 pcpooh3`) — not the "20+ drivers" an earlier revision of this ledger claimed. The other hack mode, `HACK_MODE_DOA`, has a single user (`model2.cpp:7619`, Dead or Alive) and returns a hardcoded Tecmo string. Everything else uses `HACK_MODE_NONE`, the constructor default, which takes the **real** tree/dictionary decompressor at `315-5838_317-0229_comp.cpp:98`. So the keyed cipher is missing for 10 drivers total, not the platform. **Determinism:** `machine().rand()` is MAME's LCG with a fixed seed `0x9d14abd7` (`machine.cpp:106`) and the seed is a `save_item` (`machine.cpp:283`), so these bytes are reproducible run-to-run and stable across save states — the gap is a missing cipher, **not** a non-determinism or replay hazard. |
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
sha256  3d536a7a076f730d32f37f3ede0163fd863f185f9a92e6d7d039ee10a1d9b736  mamesatdev
        (fourth build; current. Adds the CD block HIRQ DCHG fix.)
        size 85 745 792 bytes
sha256  00dd75d13557adaa52f152432a72eab9a4dc595b8d07d81e551e45a3a5afb890  mamesatdev
        (third build; produced by bootstrap_toolchain.sh + build_satdev.sh)
        size 87 772 768 bytes
sha256  0309955846af7591083447a5c5edf0e7ac63e00521ab365425acca2313b888e2  mamesatdev
        (second build; superseded, no longer on disk)
sha256  b3d285886ba75656fd0efc317d5b2db80a1fc12765dcef3241f700a91280e255  mamesatdev
        (first build; superseded, no longer on disk)
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
| Live fixture | `regtests/saturn/test_cart_runtime.py` | **PASS**, `ram8` + `bram4` carts in a live machine; two mutation controls |
| Live fixture | `regtests/saturn/test_scsp_dma.py` | **PASS**, SCSP DMA mem→reg / reg→mem / DGATE / completion; three mutation controls |
| Live fixture | `regtests/saturn/test_backup_ram.py` | **PASS**, 4 emulator runs: lane behaviour, provenance, write, expect |
| Live fixture | `regtests/saturn/test_scsp_voice.py` | **PASS**, KEY_ON→audio→KEY_OFF→silence from a captured WAV; one of two mutation controls caught, the other's limit recorded |
| Live fixture | `regtests/saturn/test_scsp_savestate.py` | **PASS**, timer counter/prescaler + CD HIRQ round-trip via `device_post_load`; one mutation control |
| Live fixture | `regtests/saturn/test_scsp_timers.py` | **PASS**, all 8 ST-077-R2 prescaler divisions + timer A interrupt; two mutation controls |
| Live fixture | `regtests/saturn/test_cd_hirq.py` | **PASS**, CMOK handshake + HIRQ write-to-clear + DCHG reporting; two mutation controls (see "CD block host interface") |
| Compile | `g++ -fsyntax-only -std=c++20` on `dram.cpp`, `bram.cpp`, `315_5649.cpp` | **PASS** |

All five live fixtures re-ran **PASS** on the current binary `3d536a7a…`, and
`-validate` is exit 0 on it.

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

  **The BIOS never touches the cartridge DRAM windows** — expected, since only a
  title using a Data RAM cart (`kof95`, `ultraman`) would, and there are no game
  ROMs here. So BIOS runs alone leave `dram.cpp` and `bram.cpp` unexecuted.

  **That gap is now closed by `regtests/saturn/test_cart_runtime.py`**, which
  drives the windows from Lua through the main CPU program space on a real
  machine booted with a cartridge selected via the `sat_cart` software list — so
  the `sat_console.cpp` handler installation, the address decode and the
  accessors are exercised together rather than separately:

  * `ram8`: cart ID `0x5a`; `dram0` round-trip; the 4× aliasing of a 512 KiB
    chip across its 2 MiB window at `+0x80000`, `+0x100000`, `+0x180000`; the
    next word being separate storage; `dram1` independent of `dram0`.
  * `bram4`: cart ID `0x21`; byte-lane spread (`0xaabbccdd` → `0x00bb00dd`);
    the last valid word at `0x040ffffc`; open bus at `0x04100000`, the first
    address past the chip inside the 8 MiB window.

  Sensitivity was proven by mutation rather than assumed. With
  `read_ext_dram1` pointed at `m_ext_dram0`, the run fails with
  `dram1.unwritten got=11223344 want=00000000` and
  `dram1.w0 got=11223344 want=a5a5a5a5`. With the BRAM bound widened from
  `size()/2` to `size()`, it fails with `bram.oob got=00000000 want=ffffffff`.
  Restoring both files reproduces the original binary exactly — same sha256
  `03099558…` — so the revert is byte-exact and not merely "looks right".

  Partial-lane writes cannot be driven from Lua: `space:write_u32` binds to
  `addr_space::mem_write(offs_t, T)` at `luaengine_mem.cpp:364`, which takes no
  `mem_mask`, so a third argument is silently dropped. That case stays with
  `test_sat_cart.py`, which calls the extracted handler directly. The test skips
  with exit 0 when no binary or BIOS set is present, so `run_all.py` remains
  ROM-free.

### SCSP DMA verified at runtime (SND-03)

`regtests/saturn/test_scsp_dma.py` drives the SCSP DMA controller from Lua on a
live `saturnjp`, through the main CPU's view of the SCSP register window
(`0x05b00400`), and asserts:

| case | assertion |
|---|---|
| mem → reg, 2 words | timer A high byte `0x12`, timer B high byte `0x56` — both addresses stepped |
| reg → mem, ungated | `MCIEB` (`0x0055`) lands byte-exact in sound RAM |
| reg → mem, `DGATE = 1` | destination stores `0x0000`, not the register value |
| completion | `SCIPD` bit 4 raised, `DEXE` clears itself |

Timer registers can only be compared by high byte: `UpdateRegR` (`scsp.cpp`,
cases `0x18`–`0x1d`) deliberately replaces the low byte with the live counter on
read, so a full-word comparison would never be stable.

**An audit note of mine was wrong and is retracted here.** I had recorded that
`exec_dma`'s `reg_addr & 0xffe` wrap "is not backed by ST-077, which implies
≤ `0xEE3`". ST-077-R2 Figure 4.3 defines the field as `DRGA[11:1]` — a 12-bit
byte address, i.e. a 4 KB window — so `& 0xffe` is exactly right, and the same
figure's `DMEA[19:1]` and `DTLG[11:1]` match MAME's `& 0xffffe` and `& 0x0ffe`
masks. There was no defect to fix, and the code should not be "corrected".

Sensitivity proven by mutation, then reverted to the identical binary
(sha256 `00dd75d1…` both before and after):

* dropping `m_udata.data[0x20/2] |= 0x10;` → `dma_end_irq got=0000 want=0010`
* changing `write_word(mem_addr, gate ? 0 : tmp)` to ignore the gate →
  `gate_zeroes got=0055 want=0000`

One trap worth recording: `DRGA` is in the same address space as
`scsp_device::r16`/`w16`, where `0x000-0x3FF` are **slot** registers and the
common control registers start at `0x400`. A first attempt used `DRGA = 0x018`
and silently wrote slot 0; the correct destination is `0x418`.

### Backup RAM persistence characterised (NVR-01)

`regtests/saturn/test_backup_ram.py` runs the emulator four times and asserts:

| case | assertion |
|---|---|
| byte lanes | `0x1122` reads back `0x0022`, `0xffff` reads back `0x00ff` |
| provenance | a fresh `-nvram_directory` does *not* already hold the pattern |
| persistence | a second run reusing the same `-nvram_directory` does |

The even-byte holes are deliberate: `saturn_state::backupram_r`
(`src/mame/sega/saturn.cpp`) returns 0 for even offsets with the comment *"yes,
it makes sure the 'holes' are there"*. Storage is a plain `uint8_t[]` passed to
the NVRAM device with `set_base()`.

**Verified limitation, deliberately not frozen into a test.** Loading a save
state does not restore backup RAM. Measured on binary `00dd75d1`: with a pattern
written and saved, the memory clobbered, and the state loaded, the clobbered
value is what reads back. The cause is structural — `nvram_device::set_base`
registers no `save_item`; `src/devices/machine/nvram.cpp` only `read()`s and
`write()`s the nvram file. So the file is the sole persistence path, and it does
work across sessions (asserted above).

This is recorded rather than "fixed" because MAME drivers are split on it: of
the drivers using `set_base`, some call `save_pointer` for the region
(`adds/multivision.cpp`, `akai/mpc60.cpp`, `amiga/cubo.cpp`) and most do not.
Changing it would touch shared state in `saturn.h` / `sat_console.cpp` for a
behaviour that may be intentional, so it needs the integration agent's call. A
test asserting the current behaviour was left out on purpose — it would fail the
day someone fixes it.

### CD block host interface verified, and one defect fixed (CD-01)

Test: `regtests/saturn/test_cd_hirq.py` (live `saturnjp`). Registers are the
`0x80000` mirror of the CD block inside the `0x05800000` window:
`HIRQ 0x05880008`, `CR1 0x05880018` … `CR4 0x05880024`.

**The defect.** `hirq_r()` began with `rv &= ~DCHG; // always clear bit 6 (tray
open)` and then stored the masked value back into `hirqreg`. So although
`set_tray_open()` does `hirqreg |= DCHG` and raises the interrupt line, any read
of HIRQ destroyed the bit before returning it. Software taking the interrupt
could not discover that the tray was the cause. ST-136-R2 states the opposite is
required: *"a '1' value for the DCHG bit (bit 5) of the interrupt factor register
(HIRQREQ) of the CD block is also treated as a tray open condition"* — reading
HIRQ **is** the detection path.

Measured before the fix (tray opened at frame 30 via the driver's own
`:RESET / Tray Open Button` input, read at frame 40):

```
DCHG before: HIRQ=0401 (bit5=0)
DCHG after tray open: first read=0401 bit5=0, second read=0401 bit5=0
```

After the fix (removing the force-clear so only `hirq_w()` may clear it):

```
DCHG after tray open: first read=0421 bit5=1, second read=0421 bit5=1
```

It reads 1 twice, which is the point: DCHG is a level request, not a
read-clear flag.

**Also verified, same test:**

- `hirq_w()` is an AND-mask (`hirqreg &= data`): writing `0xFFFE` clears CMOK and
  writing `0xFFDF` clears DCHG while leaving other bits alone.
- Command completion: with CMOK cleared, issuing Get CD Status (`0x00`) raises
  CMOK. The gate is `cmd_pending == 0xf && !(hirqreg & CMOK)`, i.e. a command is
  only accepted while the previous one has been acknowledged.

**Two behaviours discovered while driving this, recorded for agent A/four:**

1. **CR4 arms the command timer; CR1 disarms it.** `cr4_w()` does
   `m_sh1_timer->adjust(attotime::from_hz(get_timing_command()))` while `cr1_w()`
   does `m_sh1_timer->adjust(attotime::never)`. The host must therefore write
   `CR1..CR4` in ascending order and finish on CR4. My first probe wrote CR4
   first and the command never executed — HIRQ stayed `0400` for the whole
   window. This is an ordering constraint the HLE imposes and real software
   happens to satisfy; it is not itself verified against hardware.
2. **Reading HIRQ is not side-effect free.** `hirq_r()` overlays live BFUL/CSCT
   state onto the stored value, writes it back, calls `update_hirq()`, and does
   not check `side_effects_disabled()` — unlike `hirqmask_r()`, which does. Left
   alone (see CD-01 row); the test deliberately avoids BFUL/CSCT so its
   assertions stay stable.

**Mutation controls** (each rebuilt, each caught, source then restored):

| Mutation | Result |
|---|---|
| restore `rv &= ~DCHG;` in `hirq_r()` | `FAIL dchg_reported got=0000 want=0020`, `FAIL dchg_survives_read got=0000 want=0020` (CMOK assertions still passed — the test isolates DCHG) |
| `hirq_w()`: `hirqreg &= data` → `hirqreg \|= data` | `FAIL cmok_cleared_by_write got=0001 want=0000`, `FAIL dchg_cleared_by_ack got=0020 want=0000` |

**No boot regression.** All five runnable BIOS configs were re-run on the fixed
binary and match the pre-fix baseline `time=` exactly:

```
saturnjp  PASS time=15.560998664 pc=06040226 full-image replay identical
saturn    PASS time=15.560998664 pc=060402e4
saturneu  PASS time=18.439710253 pc=060402e4
saturnkr  PASS time=15.560998664 pc=06040226
stvbios   PASS time=15.543578728 pc=060154a8
```

**Honest limits.** ST-172, the CD block register manual, is not in the local SDK
corpus, so command *response encodings* (the CR2/CR4 contents returned by e.g.
Get Hardware Info) are **not** asserted here — doing so would mean inventing a
spec. Nor is any game or disc image exercised: the fix is verified against the
documented detection path and against no-boot-regression, not against a title
that actually reacts to a tray change. `hisaturn` could not be included in the
five — it requires `mpr-18100.bin`, which is not in `regtests/`; that is a ROM
availability limit, not a defect.

### SCSP prescaler timers verified against ST-077 (SND-03)

Test: `regtests/saturn/test_scsp_timers.py` (live `saturnjp`, all three CPUs
parked). ST-077-R2 §4 gives the increment table explicitly — TACTL/TBCTL/TCCTL
`[2:0]` = 0..7 → once every 1, 2, 4, 8, 16, 32, 64, 128 samples. MAME encodes
that as `inc_clocks = SAMPLE_CLOCKS << prescale` with `SAMPLE_CLOCKS = 512` and a
22 579 200 Hz SCSP clock (`sat_console.cpp:1169`, 8.4672 MHz × 8 / 3), so one
increment period is `(1 << prescale) / 44100` s.

Measured over a 3-frame window (`dt = 0.050196770` s in every case):

| prescale | predicted increments | measured (mod 256) | predicted (mod 256) |
|---|---|---|---|
| 0 | 2213 | 166 | 165 |
| 1 | 1106 | 82 | 82 |
| 2 | 553 | 42 | 41 |
| 3 | 276 | 21 | 20 |
| 4 | 138 | 138 | 138 |
| 5 | 69 | 69 | 69 |
| 6 | 34 | 35 | 34 |
| 7 | 17 | 18 | 17 |

Every entry is the predicted value or predicted + 1. The +1 is not sloppiness:
`timer_sync` advances `base_time` by whole increment periods, so a window that is
not an exact multiple carries its remainder into the next measurement. The
assertion therefore accepts N or N+1, which still separates adjacent table
entries by a factor of two — a wrong shift cannot pass.

`timer_cb` raising SCIPD (common control `0x20`) bit 6 for timer A is asserted
separately with the fastest timer and the shortest reload.

**Mutation control** (both applied in one build, both caught, then reverted and
the binary restored to the identical sha256 `3d536a7a…`):

| Mutation | Result |
|---|---|
| `t.prescale = (data >> 8) & 0x7` → `& 0x3` | `FAIL prescale4_rate got=166 want=138 or 139`, and likewise prescale 5/6/7 — prescales 0–3 still passed, so the fixture localises the fault |
| comment out `m_udata.data[0x20 / 2] \|= 0x40 << idx` in `timer_cb` | `FAIL timer_a_irq_raised got=0 want=1..1` |

**Method note that cost a wrong first result.** The unmodified BIOS programs the
SCSP timers during sound init, so measuring from Lua while it runs produces
nonsense: a first pass read timer A advancing 230 counts in one frame at
prescale 4, where the table predicts 46. The test parks all three CPUs first —
`bra` to self plus `nop` at `0x06000000` with SR = 0xf0 for the two SH-2s (the
technique `vdp2_runtime.lua` already uses), and `bra *` (`0x60fe`) in sound RAM
with SR = 0x2700 for the 68EC000.

**One count cycle, found by reading and NOT measured.** ST-077-R2 states
*"Interrupt Time = {255 (FFH) – TIMA (B, C) settings} × count cycle time"* and
*"Counting begins immediately after the settings are set to TIMA"*. Taken
literally, from a TIMA write to the interrupt is `(0xff - reload)` increment
periods. `timer_sync` instead consumes one tick to load the pending value
(`t.counter = t.reload; … steps--;`), so `timer_arm` schedules
`0x100 - reload` periods — one count cycle later, ≈22.7 µs at prescale 0.

I tried to measure this and **could not**, and am recording the attempt so nobody
repeats it: I predicted the counter one frame after a `TIMA = 0` write as
`floor(dt × 44100)` = 737 (so 224 under MAME's model, 225 under the manual's) and
observed **0** on the first try, then 225 on a cleaner run. Both predictions were
wrong for the same reason — `timer_sync` leaves a sub-increment remainder in
`base_time`, so the elapsed tick count is `dt + r`, not `dt`, and `steps` comes
out 738. Resolving a single 22.7 µs difference needs sub-frame sampling, which
the Lua frame callback cannot do.

So: **code-derived, unmeasured, and deliberately not changed.** It touches sound
timing, which is explicitly protected behaviour, and the difference is one count
cycle. Handed to agent A / agent four as a candidate, with the ST-077 wording
quoted above so it can be settled against the hardware or a real title. It is
also deliberately **not** frozen into a test — a future fix would break it.

### Controller formats audited against ST-169-R1 (IO-01)

New primary source extracted this session: `ST-169-R1-072694.pdf`, SMPC User's
Manual, 118 pages → `/tmp/st169.txt`. Figure 3.15 defines the peripheral ID as
`[bit7:4 Peripheral Type][bit3:0 Data Size]`, and Figure 3.19 states that an
unconnected tap peripheral reports ID `FFH`.

Every device in `src/devices/bus/sat_ctrl/` was checked against that scheme and
against its own data-format table. **No defect found.** The declared data size
matches the number of `read_ctrl` offsets each device implements in every case:

| Device | MAME ID | type / size | Data bytes implemented | Manual |
|---|---|---|---|---|
| `joy.cpp` standard pad | `0x02` | 0 / 2 | offsets 0–1 | Table 3.18: 1st = R L D U Start A C B, 2nd = R X Y Z L + `111` ✓ |
| `joy_md.cpp` MD 3-button | `0xe1` | E / 1 | offset 0 | 1st = R L D U Start A C B ✓ |
| `joy_md.cpp` MD 6-button | `0xe2` | E / 2 | offsets 0–1 | 2nd = MODE X Y Z `1111` ✓ |
| `mouse.cpp` Saturn mouse | `0xe3` | E / 3 | offsets 0–2 | Table 3.16: 1st = Y Over, X Over, Y Sign, X Sign, Start, Middle, Right, Left; 2nd = XD; 3rd = YD ✓ |
| `keybd.cpp` keyboard | `0x34` | 3 / 4 | offsets 0–3 | Table 3.13 ✓ |
| `racing.cpp` wheel | `0x13` | 1 / 3 | offsets 0–2 | ✓ |
| `pointer.cpp` trackball | `0x23` | 2 / 3 | offsets 0–2 | ✓ |
| `mission.cpp` mission stick | `0x15` | 1 / 5 | offsets 0–4 | ✓ |
| `gun.cpp` light gun | `0xa0` | A / 0 | none — uses `read_pdr()` | size 0 is consistent: the Virtua Gun speaks its own line protocol in SH-2 direct mode, so it has no standard data table |

Two details worth recording because they are the kind of thing that is easy to
get backwards and both are right:

* **The mouse buttons are active *high*** ("Start, Middle, Right, Left: Becomes 1
  when button is pushed"), opposite the pad, whose buttons "become 0 when the
  button is pushed". `mouse.cpp` uses `IP_ACTIVE_HIGH` for all four and
  `joy.cpp`/`joy_md.cpp` use `IP_ACTIVE_LOW`. Correct.
* **The keyboard's game-key mapping matches Table 3.13's Button/Key table on all
  12 entries**: Right/Left/Down/Up, Start = ESC, A TRG = Z, C TRG = C, B TRG = X,
  R TRG = Q, X TRG = A, Y TRG = S, Z TRG = D, L TRG = E. `get_game_key()` in
  `keybd.cpp:276` implements exactly this. Its status byte (`m_status | 6`) also
  matches: bit7 = 0, bit6 Caps Lock, bit5 Num Lock, bit4 Scroll Lock, bit3 Make,
  bits 2 and 1 forced to 1, bit0 Break — and `key_make`/`key_break`
  (`keybd.cpp:256,263`) set Make and Break mutually exclusively, as the table
  requires.

Port status bytes (the low nibble is the peripheral count that
`smpc.cpp:read_saturn_ports` iterates over): single controllers `0xf1` (one
peripheral), `multitap.h` `0x16` (six connectors), `segatap.h` `0x04` — which is
**exactly** Table 3.17's "Multitap ID `0H`, No. of Connectors `4H`".

### Two IO-01 findings that are *not* what they first looked like

**1. `read_id`/`read_status` returning 0 for an absent card is latent, not live.**
`saturn_control_port_device::read_id()` and `read_status()` (`ctrl.cpp:79-89`)
return **0** when `m_device` is null, whereas the interface defaults in `ctrl.h`
are `0xff` and `0xf0` and Figure 3.19 requires `FFH` for an unconnected
peripheral. I initially took this as the root cause of the bug MAME documents
itself at `smpc.cpp:838-842` ("if I put multitap in port2 with inserted joy1,
joy2 and joy4 it does not see joy4 … The same happens if I skip controllers with
id = 0xff … how did a real unit behave in this case?").

**It is not.** The path is unreachable: `-listxml` shows `ctrl1` has 12 slot
options (`segatap joy_md6 mouse joy_md3 trackball multitap keyboard lightgun
analog mission racing joypad`) and **no `none`/disabled option**, and the tap
sub-ports are hardwired in `device_add_mconfig` to `SATURN_CONTROL_PORT(config,
port, saturn_joys, "joypad")` where `saturn_joys` offers only `"joypad"`. So
`m_device` is never null in any configuration the user can select, and the code
is defensive only. I also tried to demonstrate the empty-port case at runtime and
could not: `-ctrl1 none` is rejected ("Unknown slot option"), and OREG stayed
`ff` for 900 frames so I could not observe an INTBACK fill from Lua either.
Recorded as a latent inconsistency, **not** a defect and **not** a cause.

**2. The INTBACK report is truncated, and the fix is not mine.**
`read_saturn_ports()` stops filling at `sizeof(m_oreg)` = 32 bytes (the guard's
comment cites mamedev MT06893, two multitaps at once). One multitap already needs
1 + 6×(1+2) = 19 bytes, so two need 38. ST-169-R1 Table 3.8/3.9 address exactly
this with 15-byte and 255-byte **port modes** selected via IREG1, which MAME does
not model. That is SMPC transport (agent A); flagged with the table reference
rather than patched across the boundary.

### Keyboard shift / kana — corpus exhausted, research required

`keybd.cpp:308` carries `TODO: how shift key actually works? EGWord uses it in
order to switch between hiragana and katakana modes.`, and `keybd.cpp:82` declares
a key literally named `"KANA SHIFT?"` with **no `PORT_CODE`**, so it can never be
pressed.

I searched all 103 PDFs in the corpus for `hiragana` / `katakana` / `kana` before
calling this a blocker. Hits: `ST-151-R4` (SW Development Standards),
`ST-160-R1`, `ST-193`, `ST-203`, `e702090_superh`. **Every one is about font
files or text rendering, not keyboard input** — `ST-160-R1-092994.pdf`, which I
had not previously catalogued, turns out to be a 9-page font specification
(`ASCII.FON`, `KANA.FON`, `KANJI.FON`, JIS code tables). ST-169-R1 itself contains
no occurrence of "shift", "kana", "hiragana" or "katakana" anywhere in 118 pages.

So the corpus genuinely does not define the kana toggle. Left as
**research-required**, unchanged — inventing a key mapping for a Japanese
word-processor title without a source would be worse than the honest gap.

### SCSP save-state round-trip verified (SND-05, CD-05)

Test: `regtests/saturn/test_scsp_savestate.py` (live `saturnjp`, all three CPUs
parked).

`scsp_device::device_post_load()` (`scsp.cpp:330-341`) exists specifically because
the timers are scheduled against machine time:

```cpp
// timers are scheduled against machine time, rebase and reschedule them
for (int i = 0; i < 3; i++) {
  m_timers[i].base_time = machine().time();
  timer_arm(i);
}
```

`counter`, `prescale`, `reload` and `reload_pending` are `save_item`s
(`scsp.cpp:242-245`) but **`base_time` is not**, so it has to be rebuilt on load.
Because `timer_read` derives the counter from `base_time` on every access, a stale
`base_time` is immediately visible as a wrong counter — which is what makes this
testable. Nothing exercised the path before.

Measured, saving at frame 34 and loading at frame 42 with timer A at prescale 7:

```
SAVESTATE advanced=46 rewind=0.016732 drift=5 hirq 0421->0421
PRESCALE_AFTER_LOAD dt=0.050196770 predicted=17 measured=17
```

| Assertion | Value | Meaning |
|---|---|---|
| timer advanced before load | 46 | 8 frames × 5.75 increments ≈ 46 — the timer really was running, so the test is not vacuous |
| clock rewound | 0.016732 s | exactly one frame, not the 0.134 s of the 8 elapsed frames — `machine:load()` restored machine time |
| counter drift after load | 5 | c1 + one frame's worth (≈6), **not** c1 + 46 — the counter was restored, not left running |
| HIRQ before → after | `0421` → `0421` | CD block `hirqreg` survived, **including DCHG (bit 5)** — see CD-05 |
| prescaler after load | 17 / 17 | re-measured over 3 frames against ST-077-R2's prescale-7 rate; exact |

**Mutation control** (rebuilt, caught, then reverted and the binary restored to the
identical sha256 `3d536a7a…`):

| Mutation | Result |
|---|---|
| delete `m_timers[i].base_time = machine().time();` from `device_post_load()` | `FAIL prescale_survived got=0 want=17 or 18` |

The failure mode is instructive and confirms the assertion is the right one: with
`base_time` left at its pre-save value it is now *ahead* of the rewound machine
time, so `timer_sync` takes its `now <= t.base_time` early return and the restored
timer **freezes** until machine time catches up. The other four assertions still
passed — including `counter_restored`, because a frozen counter trivially satisfies
"did not keep running" — which is why the prescaler re-measurement is the load-bearing
check and `counter_restored` is deliberately a weak bound.

**Still open for SND-05:** this qualifies the timers and the CD interrupt register.
It does **not** qualify a round-trip while voices/envelopes or a DMA transfer are
actively in flight, nor MIDI FIFO state.

### SCSP voice engine verified by listening to it (SND-02)

Test: `regtests/saturn/test_scsp_voice.py` (live `saturnjp`, CPUs parked, audio
captured with `-wavwrite`).

Everything else in this suite observes registers, but the voice engine has no
register that reports whether it is making sound — `UpdateSlotRegR()`
(`scsp.cpp:1111`) is an empty function, so a slot's envelope and phase are not
readable from either CPU. The only ground truth is the mixer output, so this test
listens.

**Register check first.** ST-077-R2 Figure 4.2 gives slot word 0 as
`KX KB SBCTL SSCTL LPCTL 8B SA[19:16]`. MAME's macros (`scsp.cpp:65-73`) are:

| Field | Manual position | MAME | |
|---|---|---|---|
| KYONEX | bit 12 | `0x1000` | ✓ |
| KYONB | bit 11 | `0x0800` | ✓ |
| SBCTL[1:0] | 10:9 | `>> 9 & 3` | ✓ |
| SSCTL[1:0] | 8:7 | `>> 7 & 3` | ✓ |
| LPCTL[1:0] | 6:5 | `>> 5 & 3` | ✓ |
| PCM8B | bit 4 | `0x0010` | ✓ |
| SA[19:16] | 3:0 | `& 0xF` | ✓ |

The seven fields plus three unused top bits fill the word exactly. The KEY_ON
semantics also match: ST-077 says a `1` in KYONEX "will execute KEY_ON, OFF for
all of the slots" and that "there is no need to write a `0B` in KYONEX after
writing a `1B`" — `UpdateSlotReg` (`scsp.cpp:925-944`) loops all 32 slots and
then clears bit 12 itself.

**Runtime result.** A 512-sample ±0x4000 square wave in sound RAM, slot 0 with
TL = 0, DISDL = 7, DIPAN = centre, MVOL = 0xf, AR = 0x1f, D1R = D2R = 0 (hold),
DL = 0x1f, RR = 0x1f:

```
onset  frame 30.12   (KYONEX written with KYONB set   at frame 30)
offset frame 60.40   (KYONEX written with KYONB clear at frame 60)
peak 17434, 12403 non-zero samples, silent tail exact (max abs 0)
```

Onset and offset land on the exact frames the keys were written — derived, not
hardcoded, from the interleaved 2-channel 48 kHz WAV (stereo frame = index/2,
seconds = stereo/48000, frame = seconds×60).

**A configuration trap that produced a wrong first result.** `StopSlot(slot, 1)`
(`scsp.cpp:807`) does **not** silence a slot:

```cpp
if (keyoff) slot->EG.state = SCSP_RELEASE;
else        slot->active = 0;
```

It puts the slot into the release phase and lets the envelope decay. My first
attempt used the undocumented EGBYP full-volume bypass (slot word 5 bit 15) with
RR = 0, which pins the envelope open — so key-off never reached silence and the
slot sounded to the end of the run (`offset_frame got=99.37`). Switching to a real
envelope fixed it and exercises the envelope generator properly, which is better
coverage anyway. An intermediate attempt with D1R = 0x1f decayed the note away in
0.27 frames, before key-off — D1R must be 0 to hold.

**Mutation controls** — one caught, one not, and the second is the more
instructive:

| Mutation | Result |
|---|---|
| `UpdateSlotReg`: `if (KEYONEX(slot))` → `if (false)` | **caught** — `WAV is entirely silent - key-on produced no audio at all` |
| `StopSlot`: `if (keyoff)` → `if (false)` | **NOT caught** — test still passed, `offset frame 60.24`, silent tail exact |

The second is a genuine limit of this fixture and is recorded as such rather than
papered over: with `keyoff` false, `StopSlot` takes its `else` branch and sets
`active = 0`, stopping the slot *immediately* instead of via the release
envelope. Audio still stops at key-off, so an assertion about silence cannot tell
the two apart. What this test therefore proves is that **KEY_ON produces audio and
KEY_OFF ends it**; it does **not** prove that KEY_OFF goes through the release
phase. Distinguishing that would need asserting a decay *duration*, which needs a
hardware-calibrated release-rate table I do not have a source for — so it is left
out rather than invented.

Binary restored to the identical sha256 `3d536a7a…` after both mutations.

### Communication devices — inventory completed (IO-02)

**Correction first.** An earlier revision of this ledger cited
`src/mame/saturn/st17xx.cpp` as evidence under IO-02 ("is a skeleton"). That was
wrong: the file is a skeleton for **Saturn ST-17xx series DVD players** (Mediatek
MT1379/MT1389), defining ten `CONS` entries `st1700h`, `st1701`–`st1708`, `st1714`,
all `MACHINE_NO_SOUND | MACHINE_NOT_WORKING`. They are standalone DVD consoles, not
communication devices.

**Implemented and tested**

| Device | Where | Status |
|---|---|---|
| 315-5649 IOGA RS-422 serial (ST-V) | `src/mame/sega/315_5649.cpp` | **verified** — `test_ioga_serial.py`, 4113 cases, `MUTATE_IOGA=1` fails. Loopback (mode bit 4) forwards writes to `m_serial_wr_cb[ch]`, latches `m_serial_rx_data[ch]`, and read-back clears the latch. `m_serial_rx_data` is a `save_item` (`315_5649.cpp:62`) |
| SCSP MIDI in/out FIFOs | `src/devices/sound/scsp.cpp` | implemented over `device_serial_interface` — 32-entry `m_MidiStack`/`m_MidiOutStack`, both `save_item`s; TX drains via `tra_complete`, RX fills via `rcv_complete`; the MIDI-out-empty interrupt is raised on both the SCIPD and MCIPD sides. **Not yet exercised at runtime** — no fixture drives it |

**Stubbed**

SMPC commands `0x0a` (`NETLINKON`/`COPON`) and `0x0b` (`NETLINKOFF`/`COPOFF`) at
`smpc.cpp:469-478` fall through to a log line and a `popmessage("%s: NetLink
enabled")`. The code's own TODO asks the right question: *"understand where
NetLink actually lies and implement delegation accordingly (is it really an SH1
device like suggested by the space access or it overlays on CS2 bus?)"*. There is
no NetLink device in the tree to delegate to. The command decode is agent A's SMPC
core; the delegation **target** is IO-02/EXP-02.

**A game-motivated hardcoded byte inside the CD block — flagged, not fixed**

`saturn_cd_hle.cpp:296-299`:

```cpp
// NetLink/ Sega Saturn modem access
// dragndrm expects this value, most likely for status
// TODO: move out of here, breaks daytoncej boot
map(0x85029, 0x85029).lr8(NAME([]() -> u8 { return 0x11; }));
```

`amap()` is installed at `0x05800000-0x0589ffff` (`sat_console.cpp:667-668`), so
this reads `0x11` at **`0x05885029`** — inside the CD block's own 640 KiB window.
Two things are wrong with that on its face: a modem status byte does not belong in
the CD block's address space (the NetLink and the Sega Saturn modem were cartridge
slot devices on CS2), and the comment records that the placement **breaks
`daytoncej` boot**.

**I did not change it.** Moving it requires knowing which game regresses, and
neither `dragndrm` nor `daytoncej` ROMs are available here, so any relocation would
be unverifiable — exactly the situation in which a "fix" becomes a new guess.
Handed to agent four, who has the integrated build and the ROM set to test both
sides. This is also the pattern the project brief rules out (game-specific values
substituted for real hardware), so it should not be extended.

**Missing entirely**

NetLink modem (US), Sega Saturn modem (JP), XBAND. None has a device, a slot
option, or a `sat_cart` softlist entry — the softlist contains only `kof95`,
`ultraman`, `test1f`, `ar`, `pssat`, `ram8`, `ram32`, `bram4`, `bram8`, `bram16`,
`bram32`.

**Source note.** ST-169-R1 contains no occurrence of "serial", "communication",
"modem", "RS-232" or "SMSH" in 118 pages, so the SMPC manual documents no
communication port and the corpus gives no register-level basis for implementing
one. The 315-5649 RS-422 link is the only communication path here with a
primary-source basis.

### A pre-existing `run_all.py` failure, not mine

`run_all.py` auto-discovers `test_*.py` (29 currently) and aborts at
`test_vcounter.py`, which runs `git show
868d72fc669765f8a0b9af6503a59642d293cbae:src/mame/sega/saturn_vdp2.cpp`. That
object does not exist in this repository (`git cat-file -t` → "could not get
object info"), and the file was committed at baseline `03c19a78`, not by this
agent. It is VDP2 territory (agent B). My tests all run before it:
`test_cd_hirq.py` prints its PASS line inside `run_all.py`.

## 4. Endpoint contracts

Only behaviours this session actually drove and asserted are listed; each links
to the fixture that proves it.

### CD block host interface (CD-01) — `saturn_cd_hle_device`

Seen from the main CPU at the `0x80000` mirror of the CD block window:

| Register | Address | Semantics as verified |
|---|---|---|
| `HIRQ` | `0x05880008` | read: stored value **or** live BFUL/CSCT overlaid, written back; write: `hirqreg &= data`, so writing a bit as 0 clears it |
| `HIRQMASK` | `0x0588000c` | read/write, honours `side_effects_disabled()` |
| `CR1`–`CR4` | `0x05880018`–`0x05880024` | write sets `cmd_pending |= 1/2/4/8`. **CR4 arms the command timer, CR1 disarms it** — write ascending, finish on CR4 |

Invariants asserted by `test_cd_hirq.py`:

* A command executes only when `cmd_pending == 0xf` **and** CMOK is clear
  (`saturn_cd_hle.cpp:3404`); completion raises CMOK (bit 0).
* DCHG (bit 5) survives reads and is cleared only by `hirq_w()`. ST-136-R2
  makes reading it the documented tray-open detection path.
* `hirq_r()` is **not** side-effect free: it calls `update_hirq()` and does not
  check `side_effects_disabled()`. Anything peeking HIRQ (debugger, cheat,
  watchpoint handler) mutates the register. Flagged, not fixed.

### SCSP DMA (SND-03) — `scsp_device`

Base `0x05b00400` from the main CPU (the `0x000-0x3FF` sub-range of the
`r16`/`w16` space is slot registers, **not** common control — this cost a wrong
first result). `DMEA[19:1]` masked `& 0xffffe`, `DRGA[11:1]` masked `& 0xffe`,
`DTLG[11:1]` masked `& 0x0ffe`, all matching ST-077-R2 Figure 4.3. `DGATE=1`
stores zero. Completion raises SCIPD bit 4 and self-clears DEXE. Reading the
timer registers `0x18-0x1d` is destructive (`UpdateRegR` substitutes the live
counter into the low byte), so only the high byte is stable evidence.

### Backup RAM (NVR-01) — `saturn_state::backupram_r/w`

Window at `0x00180000`, odd bytes only by design (`saturn.cpp:235`): a longword
write of `0x1122` reads back `0x0022`. Persistence is via the `-nvram_directory`
file **only** — `nvram_device::set_base` registers no `save_item`, so a save
state does not restore it. Deliberately characterised, not fixed, and not frozen
into a test (it would break the day someone fixes it). See §3.

## 5. NOT_WORKING inventory in owned drivers

`src/mame/sega/stv.cpp` carries 66 `MACHINE_NOT_WORKING` entries:

* ~45 are Atlus **Print Club / Purikura** titles on `stvpc_state` (external
  "837-12764 486 BD FOR ST-V" i486 board) → **STV-05**.
* 9 use `init_decathlt_nokey()` (`pclove`, `pclove2`, `pcpooh2`, `pcpooh3`,
  `pclubsc5`, `pclubsc6`, `pclubnbc`, `nameclub`, `nclubv2`) → **STV-02**.
  Verified as the complete set: `init_decathlt_nokey` appears in exactly 9
  `GAME()` lines and nowhere else. An earlier revision of this ledger said 8 and
  listed `nclubv2` under the remainder instead.
* remainder: `aclub`, `chalgolf`, `choroqhr`, `decathlt`, `decathlto`, `dfeverg`,
  `fanzonem`, `finlarch`, `magzun`, `myfairld`, `sackids`, `sfish2`, `sfish2j`,
  `slotbatt`, `smleague`, `stress`, `tsuribor`, `twcup98`, `twsoc98`, `vfremix`,
  `wasafari`, `wwshin`, `yattrmnp`, plus `pckobe99`, `nclubdis`.

All six Saturn console configurations (`saturn`, `saturnjp`, `saturneu`,
`saturnkr`, `vsaturn`, `hisaturn`) are `MACHINE_NOT_WORKING` at
`sat_console.cpp:1343-1353`.

---

## 6. Log

| Date | Commit | What |
|---|---|---|
| 2026-09-16 | `03c19a78` | session start; baseline recorded; vendored build environment established |
| 2026-09-17 | `e64f5e50` | `dram.cpp` / `bram.cpp` bounds from region size; `315_5649` RS-422 loopback + port G counter reset; `build_satdev.sh`; this ledger |
| 2026-09-17 | `f25b191e` | `test_ioga_serial.py` — 4113 cases, `MUTATE_IOGA` control |
| 2026-09-17 | `31694ccf` | `test_sat_cart.py` — 24 cases, `MUTATE_CART` control |
| 2026-09-17 | `341a556f` | `build_satdev.sh`: `NO_USE_XINPUT=1` is the knob that excludes `input_x11.cpp` |
| 2026-09-17 | `946a2184` | subtarget links; `-validate` clean; BIOS boot/replay PASS on `saturn`, `saturnjp`, `saturneu`, `saturnkr`, `stvbios`. Recorded that the `exp` cart slot registers no options, so `dram.cpp` / `bram.cpp` are not runtime-reachable |
| 2026-09-17 | `9add769b` | drop `regtests/saturn.zip` (a 1 014 371-byte ROM archive) that `946a2184` had swept in via `git add -A`; ROMs stay outside tracked source |
| 2026-09-17 | `290d50cf` | **corrected the previous row's claim.** The `exp` slot *does* register all seven carts (`sat_console.cpp:1191-1198`, `option_add_internal`); they are reachable through the `sat_cart` software list, not the command line. The `size() == 0` softlist path is exactly what the DRAM guard protects. See §3 |
| 2026-09-17 | `9a50420f` | `devices.md` §1 rewritten after rebuilding the toolchain; two false claims removed (`libSDL2_ttf.a` cannot be empty — 54 `TTF_` call sites in `font_sdl.cpp`; fontconfig is `fontconfig/fontconfig@2.13.1`, not a maintainer fork at `master`) |
| 2026-09-17 | `ab0cc2e1` | toolchain recreated, subtarget rebuilt (`03099558…`), all §3 results re-run and identical to the first build. **Corrected the `ram8` account**: it *does* declare `dram0`/`dram1` data areas, so the vectors are allocated and the empty-region guard is not what it exercises. Measured with a memory tap: the BIOS makes **zero** accesses to either DRAM window (control 3 077 295 workram reads in the same run), so `dram.cpp`/`bram.cpp` accessors remain unexecuted at runtime |
| 2026-09-17 | `c7a4f33e` | `test_cart_runtime.py` — live-machine cart fixture with mutation controls; proves the BIOS never touches the cart windows (0 accesses vs 3 077 295 workram reads) |
| 2026-09-17 | `ae11863e` | `bootstrap_toolchain.sh` recreates the vendored toolchain from scratch in 68 s and self-verifies against MAME's real include set |
| 2026-09-17 | `860da5ee` | **retracted** the cross-build "identical results" claim; disproved the missing-parent-ROM hypothesis for `pc=` variation |
| 2026-09-17 | `8d7d137b` | `test_scsp_dma.py` — SCSP DMA verified against ST-077-R2 Figure 4.3 at runtime, three mutation controls; `exec_dma` masking confirmed correct |
| 2026-09-17 | `d691cddc` | `test_backup_ram.py` — backup RAM lanes and nvram-file persistence; recorded that save state does **not** restore backup RAM |
| 2026-09-17 | `834a5609` | **CD-01:** removed the force-clear of DCHG in `hirq_r()`, which had made the ST-136-R2 tray-open detection path unobservable; added `test_cd_hirq.py` (CMOK handshake, HIRQ write-to-clear, DCHG reporting) with two mutation controls. All five BIOS configs re-verified at their pre-fix baseline times. New binary `3d536a7a…` |
| 2026-09-17 | `c97eaa9b` | **STV-02 count corrected twice.** `machine().rand()` in `HACK_MODE_NO_KEY` is MAME's fixed-seed LCG (`machine.cpp:106`, seed `0x9d14abd7`) whose seed is a `save_item`, so it is reproducible and save-state stable — a missing cipher, not a determinism hazard. `init_decathlt_nokey` is used by **9** `GAME()` entries, not "20+" (§2) and not 8 (§5); `nclubv2` belongs in the STV-02 group. Both figures verified from `grep` over `src/mame/sega/*.cpp`. |
| 2026-09-17 | `22d2d525` | **SND-03:** `test_scsp_timers.py` measures all eight ST-077-R2 prescaler divisions and the timer A interrupt in a live machine, with two mutation controls. Records a one-count-cycle discrepancy against the manual's interrupt-time formula as **code-derived and unmeasured** — the attempted measurement is written up and retracted, since `timer_sync`'s sub-increment remainder defeats frame-granular sampling. Not changed (sound timing is protected) and not frozen into a test. |
| 2026-09-17 | `5cfafcad` | resolved the two remaining `(this commit)` placeholders in the log table; every row now carries a real hash. Documentation only. |
| 2026-09-17 | (this commit) | **IO-01:** audited all eleven `sat_ctrl` devices against ST-169-R1 (extracted this session). Peripheral IDs, data sizes and data-byte layouts all correct, including the mouse's active-high buttons and the keyboard's 12-entry Button/Key mapping. Two non-findings recorded honestly: `read_id`/`read_status` returning 0 for an absent card is **unreachable** (no `none` slot option, tap sub-ports hardwired), so it is not the cause of the `smpc.cpp:838` comment; and the 32-byte OREG truncation belongs to agent A's SMPC transport. Keyboard kana confirmed **research-required** after searching all 103 corpus PDFs. No code change. |
| 2026-09-17 | (this commit) | **SND-05 / CD-05:** `test_scsp_savestate.py` round-trips the SCSP timer counter, prescaler and CD `hirqreg` (DCHG included) through `machine:save`/`machine:load`, exercising `scsp_device::device_post_load()`. Measured advanced=46, rewind=0.016732 s, drift=5, HIRQ `0421`→`0421`, prescaler 17/17. Mutation control: deleting the `base_time` rebase fails `prescale_survived got=0` because the stale base sits ahead of the rewound clock and `timer_sync` freezes the timer. Binary restored to the identical sha256. |
| 2026-09-17 | (this commit) | **SND-02:** slot word 0 checked field-by-field against ST-077-R2 Figure 4.2 (all seven fields correct); `test_scsp_voice.py` keys a voice on and off and listens to the WAV — onset frame 30.12, offset 60.40, peak 17434, silent tail exact. Records that `StopSlot` enters the release phase rather than silencing, which is why an EGBYP + RR=0 configuration never goes quiet; and records that the `StopSlot` mutation was **not** caught because its `else` branch also stops the slot, so the fixture proves KEY_ON/KEY_OFF but not the release path. |
| 2026-09-17 | (this commit) | **IO-02:** communication-device inventory completed. **Corrected** the ledger's claim that `saturn/st17xx.cpp` is a communication device — it is ten skeleton DVD-player consoles (`CONS` `st1700h`, `st1701`–`st1708`, `st1714`). Recorded the 315-5649 RS-422 link as the only verified comm path, the SMPC `NETLINKON`/`NETLINKOFF` stubs, the absent NetLink/Saturn-modem/XBAND devices, and a hardcoded `0x11` at `0x05885029` inside the CD block map (`saturn_cd_hle.cpp:299`) added for `dragndrm` whose own comment says it breaks `daytoncej` — flagged for agent four, not fixed, because neither ROM is available to verify a relocation. |

### Reproducibility — and a claim retracted

An earlier revision of this ledger said two independently built binaries
"produce **identical** boot/replay results on every configuration", quoting
matching `pc=` values as the evidence. **That was not a supported claim.** The
emulated timestamp is stable; the sampled PC is not.

Measured on a single binary (`00dd75d1…`), same ROM set, fresh output directory
each time, `saturnjp`:

| runs | `time=` | `pc=` |
|---|---|---|
| first pair | `15.560998664` | `06040226` |
| one earlier run | `15.560998664` | `06040228` |
| six later runs | `15.560998664` | `0604022a` |

`time=` is identical in every single run, including across two separately
bootstrapped toolchains. `pc=` took three different values, all even and within
two instructions of each other. Removing and restoring the `saturn` parent ROM
set did not change it, and I could not attribute the variation to any specific
cause.

**Consequence: `pc=` must not be used as a reproducibility fingerprint, and
matching `pc=` values between two builds are not evidence of equivalence.** The
invariant that does hold, and the one the fixture actually asserts, is
*within-run* save/load determinism — "full-image replay identical" — which
passed on every run without exception. Use that, plus `time=`, for comparison.

All five configurations still pass, on the current binary and the previous one:
`saturnjp`, `saturneu`, `stvbios`, `saturn`, `saturnkr`, each reporting
full-image replay identical.

The `-lEGL`, `Fc*` and `315_5195` / `315_5296` / `315-6154` link failures that
were flagged as a risk in an earlier revision did **not** occur; the subtarget
links cleanly with the flags in `build_satdev.sh`.

### Sandbox note

Everything the build depends on outside the repository — `$MAME_SDK`, `build/`
and the `mamesatdev` binary — is wiped whenever the sandbox is recycled, which
has happened three times mid-session. `bootstrap_toolchain.sh` recreates the
toolchain from a clean slate in about a minute; `build_satdev.sh` then rebuilds
the subtarget. Results recorded above were produced by binaries that no longer
exist on disk, so the binary hashes are the only way to tie a result to a build.
