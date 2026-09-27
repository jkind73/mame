#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Two documented, previously-mismodelled memory holes in sat_console_state::saturn_mem.

Source: the Yabause wiki's SH-2CPU memory map, which credits Charles
MacDonald's Sega Saturn hardware notes (not in the official SCU/SH-2 manuals):

  00300000-003FFFFF   a separate 1 MB hole immediately after the 1 MB Work RAM
                      Low window (00200000-002FFFFF), documented as reading
                      back random data, mostly $00 - not a mirror of work RAM.
  00800000-00FFFFFF   always reads back the repeating pattern
                      $0000,0001,0002,...,0007 (each 16-bit half is its own
                      index mod 8).

Before this fix, workram_l's map() entry carried an unexplained extra
mirror(0x00100000) bit (present unchanged since the driver's 2013 MESS/MAME
split) that folded the first hole into work RAM, and 00800000-00FFFFFF was
simply unmapped (silently read as 0 for the whole 8 MB range). Modelled here
as a fixed $00000000 return for the first hole, since only "mostly $00" is
documented rather than an exact random distribution - not a claim of genuine
bus-noise randomness.

Requires a built driver-filtered binary and BIOS ROMs. Skips with exit status
0 when they are absent so run_all.py stays ROM-free.
"""
from pathlib import Path
import argparse
import os
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]

LUA = r"""
local m = manager.machine
local sp = m.devices[":maincpu"].spaces["program"]
local fails = {}
local function chk(label, got, want)
    if got ~= want then fails[#fails+1] = string.format("%s got=%08x want=%08x", label, got, want) end
end
emu.register_frame_done(function()
    -- Work RAM Low must not be aliased into 00300000-003FFFFF, in either
    -- direction: a write into the hole must not land in work RAM (this needs
    -- the stray mirror bit actually removed from workram_l's map() entry -
    -- the hole's own read-only handler alone would still leave the write side
    -- landing in work RAM's backing store if the two declarations overlapped).
    sp:write_u32(0x00201000, 0xdeadbeef)
    chk("hole1_not_aliased_to_workram", sp:read_u32(0x00301000), 0x00000000)
    sp:write_u32(0x00301000, 0x12345678)
    chk("hole1_write_does_not_reach_workram", sp:read_u32(0x00201000), 0xdeadbeef)

    -- 00300000-003FFFFF reads back zero across the whole 1 MB hole.
    chk("hole1_start", sp:read_u32(0x00300000), 0x00000000)
    chk("hole1_mid", sp:read_u32(0x00312340), 0x00000000)
    chk("hole1_end", sp:read_u32(0x003ffffc), 0x00000000)

    -- 00800000-00FFFFFF cycles $0000,0001,...,0007 every 4 dwords (16 bytes),
    -- and the whole 8 MB range repeats that same 16-byte block.
    local pattern = {0x00000001, 0x00020003, 0x00040005, 0x00060007}
    for i = 0, 7 do
        local addr = 0x00800000 + i * 4
        chk(string.format("hole2_%08x", addr), sp:read_u32(addr), pattern[(i % 4) + 1])
    end
    chk("hole2_far_repeat", sp:read_u32(0x00ffFFF0), pattern[1])

    for _, f in ipairs(fails) do print("MM_HOLES FAIL " .. f) end
    if #fails == 0 then print("MM_HOLES OK") end
    m:exit()
end)
print("MM_HOLES armed")
"""


def run(executable, rompath, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    script = outdir / "mm_holes.lua"
    script.write_text(LUA)
    for sub in ("nvram", "cfg"):
        (outdir / sub).mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    result = subprocess.run([
        str(executable), "saturnjp", "-rompath", str(rompath),
        "-noreadconfig", "-skip_gameinfo", "-nodrc",
        "-video", "none", "-sound", "none", "-nothrottle",
        "-autoboot_delay", "0", "-autoboot_script", str(script),
        "-seconds_to_run", "30",
        "-nvram_directory", str(outdir / "nvram"),
        "-cfg_directory", str(outdir / "cfg"),
        "-state_directory", str(outdir),
        "-snapshot_directory", str(outdir),
    ], cwd=outdir, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=300)
    text = result.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
    if result.returncode or "LUA ERROR" in text or "MM_HOLES FAIL" in text:
        raise AssertionError(f"Lua error or failure:\n{text}")
    if not re.search(r"^MM_HOLES OK$", text, re.M):
        detail = "\n".join(l for l in text.splitlines() if "MM_HOLES" in l) or text[-1500:]
        raise AssertionError(f"assertions did not run to completion:\n{detail}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--executable", type=Path, default=ROOT / "saturn")
    p.add_argument("--rompath", type=Path, default=ROOT / "regtests")
    a = p.parse_args()
    a.executable = a.executable.resolve()
    a.rompath = a.rompath.resolve()

    if not a.executable.is_file():
        print(f"SKIP: no binary at {a.executable} "
              f"(build a driver-filtered subtarget first)")
        return 0
    if not (a.rompath / "saturnjp.zip").is_file():
        print(f"SKIP: no saturnjp BIOS set in {a.rompath}")
        return 0

    with tempfile.TemporaryDirectory(prefix="mm-holes-") as tmp:
        run(a.executable, a.rompath, Path(tmp))

    print("Memory-map holes 00300000-003FFFFF and 00800000-00FFFFFF verified "
          "against the Yabause wiki / Charles MacDonald hardware notes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
