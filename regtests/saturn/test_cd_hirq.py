#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Drive the CD block host command/interrupt interface in a live machine (CD-01).

The Saturn host talks to the CD block through four command/response registers
(CR1-CR4 / DR1-DR4) plus HIRQ and HIRQMASK, all mirrored at 0x18000 inside the
0x05800000 window. ST-172 (the CD block register manual) is not in the local
SDK corpus, so this test deliberately asserts only protocol invariants that are
either documented elsewhere or unambiguous, and says so rather than inventing
response encodings:

  CMOK (bit 0) - command complete
    A command is only accepted while CMOK is clear, and is signalled complete by
    CMOK being raised (src/mame/sega/saturn_cd_hle.cpp, the cmd_pending == 0xf
    && !(hirqreg & CMOK) gate). Asserted by clearing CMOK, issuing Get CD Status
    (0x00) and seeing CMOK come back.

  HIRQ write clears the bits written as zero
    hirq_w() does hirqreg &= data, so 0xFFFE clears CMOK and 0xFFDF clears DCHG
    while leaving the rest alone. Both directions are asserted.

  DCHG (bit 5) - disc change / tray change
    ST-136-R2 states that "a '1' value for the DCHG bit (bit 5) of the interrupt
    factor register (HIRQREQ) of the CD block is also treated as a tray open
    condition", i.e. reading HIRQ is the documented detection path. The tray is
    opened through the driver's own "Tray Open Button" input, which calls
    set_tray_open(); DCHG must then read as 1, and must still read as 1 on a
    second read, because it is a level request that only hirq_w() may clear.
    Until the fix recorded in regtests/saturn/handoff/integration.md, hirq_r()
    force-cleared DCHG on every read, so software could never observe it.

Two behaviours worth recording that this test depends on:

  * CR4 arms the command timer (cr4_w adjusts m_sh1_timer) while CR1 disarms it
    (cr1_w adjusts it to never). The host must therefore write CR1..CR4 in
    ascending order and finish on CR4; writing CR4 first leaves the command
    permanently unexecuted. This test writes them in order.
  * Reading HIRQ is not side-effect free: hirq_r() overlays live BFUL/CSCT state
    onto the stored value and writes it back. The assertions here avoid BFUL
    (bit 11) and CSCT (bit 12) so they stay stable.

Requires a built driver-filtered binary and BIOS ROMs. Skips with exit status 0
when they are absent so run_all.py stays ROM-free.
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
local frames = 0
local fails = {}
local function chk(label, got, want)
    if got ~= want then fails[#fails+1] = string.format("%s got=%04x want=%04x", label, got, want) end
end

-- CD block host registers, base 0x05800000 + 0x80000 mirror
local HIRQ = 0x05880008
local CR1  = 0x05880018
local CR2  = 0x0588001c
local CR3  = 0x05880020
local CR4  = 0x05880024

local CMOK = 0x0001
local DCHG = 0x0020

emu.register_frame_done(function()
    frames = frames + 1

    if frames == 30 then
        -- 1. HIRQ write clears the bits written as zero
        sp:write_u16(HIRQ, 0xfffe)
        chk("cmok_cleared_by_write", sp:read_u16(HIRQ) & CMOK, 0x0000)

        -- 2. issue Get CD Status (0x00); CR4 must be written last
        sp:write_u16(CR1, 0x0000)
        sp:write_u16(CR2, 0x0000)
        sp:write_u16(CR3, 0x0000)
        sp:write_u16(CR4, 0x0000)

    elseif frames == 34 then
        -- 3. command completion handshake
        chk("cmok_raised_by_command", sp:read_u16(HIRQ) & CMOK, CMOK)

        -- open the tray through the driver's own input
        m.ioport.ports[":RESET"].fields["Tray Open Button"]:set_value(1)

    elseif frames == 44 then
        -- 4. DCHG is reported and survives a read
        local first = sp:read_u16(HIRQ)
        local second = sp:read_u16(HIRQ)
        chk("dchg_reported", first & DCHG, DCHG)
        chk("dchg_survives_read", second & DCHG, DCHG)

        -- 5. acknowledging clears it, and only it
        local before = second & ~DCHG
        sp:write_u16(HIRQ, 0xffdf)
        local after = sp:read_u16(HIRQ)
        chk("dchg_cleared_by_ack", after & DCHG, 0x0000)
        chk("ack_preserves_other_bits", after & before, before & before)

        if #fails == 0 then print("CD_HIRQ_RUNTIME PASS")
        else for _, f in ipairs(fails) do print("CD_HIRQ_RUNTIME FAIL " .. f) end end
        m:exit()
    end
end)
print("CD_HIRQ_RUNTIME armed")
"""


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--executable", type=Path, default=ROOT / "saturn")
    p.add_argument("--rompath", type=Path, default=ROOT / "regtests")
    a = p.parse_args()
    a.executable = a.executable.resolve()
    a.rompath = a.rompath.resolve()
    if hasattr(a, "hashpath"):
        a.hashpath = a.hashpath.resolve()

    if not a.executable.is_file():
        print(f"SKIP: no binary at {a.executable} "
              f"(build a driver-filtered subtarget first)")
        return 0
    if not (a.rompath / "saturnjp.zip").is_file():
        print(f"SKIP: no saturnjp BIOS set in {a.rompath}")
        return 0

    with tempfile.TemporaryDirectory(prefix="cd-hirq-") as tmp:
        outdir = Path(tmp)
        script = outdir / "cd_hirq.lua"
        script.write_text(LUA)
        for sub in ("nvram", "cfg"):
            (outdir / sub).mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
        result = subprocess.run([
            str(a.executable), "saturnjp",
            "-rompath", str(a.rompath),
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

    if result.returncode or "LUA ERROR" in text or "CD_HIRQ_RUNTIME FAIL" in text:
        raise AssertionError(f"Lua error:\n{text}")
    if re.search(r"^CD_HIRQ_RUNTIME PASS$", text, re.M):
        print("CD block HIRQ: CMOK command handshake, write-to-clear and DCHG "
              "tray-change reporting verified in a live machine")
        return 0
    detail = "\n".join(l for l in text.splitlines()
                       if "CD_HIRQ_RUNTIME" in l) or text[-2000:]
    raise AssertionError(f"assertions failed:\n{detail}")


if __name__ == "__main__":
    sys.exit(main())
