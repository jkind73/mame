#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Backup RAM persistence and byte-lane behaviour (NVR-01).

The Saturn's 32 KiB internal backup RAM is mapped at 0x00180000 and driven by
saturn_state::backupram_r/backupram_w (src/mame/sega/saturn.cpp), which return 0
and ignore writes on even byte offsets - the comment there calls them "holes".
Storage is a plain uint8_t[] handed to the NVRAM device via set_base(), so the
only persistence path is the nvram file.

What this asserts, by running the emulator more than once:

  byte lanes   a 16-bit write only lands in the odd byte, so 0x1122 reads back
               0x0022 and 0xffff reads back 0x00ff
  persistence  the pattern written in one run is present on the next run that
               reuses the same -nvram_directory
  provenance   the same pattern is absent from a fresh -nvram_directory, so the
               second run really is reading the file and not a constant

Deliberately NOT asserted: whether loading a save state restores backup RAM.
Measured on binary 00dd75d1, it does not - nvram_device::set_base registers no
save_item (src/devices/machine/nvram.cpp only reads/writes the file), so after
machine:load() the backup RAM keeps whatever was in memory. Other MAME drivers
are split on calling save_pointer for this, so it is recorded as a characterised
limitation in regtests/saturn/handoff/devices.md rather than frozen into a test
that would fight a future fix.

Requires a built driver-filtered binary and BIOS ROMs. Skips with exit status 0
when they are absent so run_all.py stays ROM-free.
"""
from pathlib import Path
import argparse
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BACKUP_RAM = 0x00180000

LUA = r"""
local m = manager.machine
local sp = m.devices[":maincpu"].spaces["program"]
local mode = os.getenv("SATURN_BRMODE")
local frames = 0
local fails = {}
local function chk(label, got, want)
    if got ~= want then fails[#fails+1] = string.format("%s got=%04x want=%04x", label, got, want) end
end
emu.register_frame_done(function()
    frames = frames + 1
    if frames ~= 30 then return end
    local a = 0x00180000
    if mode == "lanes" then
        sp:write_u16(a, 0x1122)
        chk("odd_byte_only", sp:read_u16(a), 0x0022)
        sp:write_u16(a, 0xffff)
        chk("even_byte_is_hole", sp:read_u16(a), 0x00ff)
    elseif mode == "write" then
        sp:write_u16(a, 0x115a)
        chk("write_back", sp:read_u16(a), 0x005a)
    elseif mode == "expect" then
        chk("persisted_from_nvram_file", sp:read_u16(a), 0x005a)
    elseif mode == "expect_absent" then
        -- a fresh nvram directory must not already contain the pattern
        if sp:read_u16(a) == 0x005a then
            fails[#fails+1] = "fresh nvram dir already held the pattern"
        end
    end
    for _, f in ipairs(fails) do print("BACKUP_RAM FAIL " .. f) end
    if #fails == 0 then print("BACKUP_RAM OK " .. mode) end
    m:exit()
end)
print("BACKUP_RAM armed " .. mode)
"""


def run(executable, rompath, outdir, mode):
    outdir.mkdir(parents=True, exist_ok=True)
    script = outdir / f"br_{mode}.lua"
    script.write_text(LUA)
    for sub in ("nvram", "cfg"):
        (outdir / sub).mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
               SATURN_BRMODE=mode)
    result = subprocess.run([
        str(executable), "saturnjp", "-rompath", str(rompath),
        "-noreadconfig", "-skip_gameinfo", "-nodrc",
        "-video", "none", "-sound", "none", "-nothrottle",
        "-autoboot_delay", "0", "-autoboot_script", str(script),
        "-seconds_to_run", "60",
        "-nvram_directory", str(outdir / "nvram"),
        "-cfg_directory", str(outdir / "cfg"),
        "-state_directory", str(outdir),
        "-snapshot_directory", str(outdir),
    ], cwd=outdir, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=600)
    text = result.stdout.decode("utf-8", "replace")
    if "LUA ERROR" in text:
        raise AssertionError(f"{mode}: Lua error:\n{text}")
    if f"BACKUP_RAM OK {mode}" not in text:
        detail = "\n".join(l for l in text.splitlines()
                           if "BACKUP_RAM" in l) or text[-1500:]
        raise AssertionError(f"{mode}: assertions failed:\n{detail}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--executable", type=Path, default=ROOT / "mamesatdev")
    p.add_argument("--rompath", type=Path, default=ROOT / "regtests")
    a = p.parse_args()

    if not a.executable.is_file():
        print(f"SKIP: no binary at {a.executable} "
              f"(build a driver-filtered subtarget first)")
        return 0
    if not (a.rompath / "saturnjp.zip").is_file():
        print(f"SKIP: no saturnjp BIOS set in {a.rompath}")
        return 0

    with tempfile.TemporaryDirectory(prefix="backup-ram-") as tmp:
        base = Path(tmp)
        # byte-lane behaviour, independent of persistence
        run(a.executable, a.rompath, base / "lanes", "lanes")
        # a fresh directory must not already hold the pattern
        run(a.executable, a.rompath, base / "fresh", "expect_absent")
        # write, then re-run against the SAME nvram directory
        run(a.executable, a.rompath, base / "persist", "write")
        run(a.executable, a.rompath, base / "persist", "expect")

    print("Backup RAM: odd-byte-only lanes, nvram-file persistence and "
          "fresh-directory provenance all verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
