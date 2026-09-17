#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Drive the SCSP DMA controller inside a running machine (SND-03).

ST-077-R2 Figure 4.3 defines the DMA registers as DMEA[19:1], DRGA[11:1] and
DTLG[11:1]. MAME masks the register address with 0xffe while stepping it
(src/devices/sound/scsp.cpp exec_dma), which is exactly a 12-bit byte-address
field, and this script exercises that path end to end rather than by inspection.

What it asserts, all against a live saturnjp:

  mem -> reg (DDIR = 0)
    Two words staged in sound RAM are transferred to consecutive common-control
    registers, both addresses stepping. The timer registers are used as the
    destination: UpdateRegR replaces their low byte with the live counter on
    read, so only the high byte is evidence of the transfer - asserted
    accordingly rather than comparing a value that cannot be stable.

  reg -> mem (DDIR = 1)
    A value written to MCIEB (read back verbatim by UpdateRegR) is transferred
    into sound RAM and checked byte-for-byte.

  DGATE = 1
    The same transfer stores zero instead of the register value. ST-077 calls
    this "DMA transfer gate 0 clear".

  completion
    SCIPD bit 4 (DMA transfer end) is raised and DEXE clears itself.

Address-space note that cost a wrong first result: DRGA is in the same space as
scsp_device::r16/w16, where 0x000-0x3FF are slot registers and the common
control registers start at 0x400. DRGA = 0x018 therefore writes slot 0, not
timer A; the correct destination is 0x418.

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

LUA = r"""
local m = manager.machine
local sp = m.devices[":maincpu"].spaces["program"]
local frames = 0
local fails = {}
local function chk(label, got, want)
    if got ~= want then fails[#fails+1] = string.format("%s got=%04x want=%04x", label, got, want) end
end

-- SCSP common control registers as seen by the main CPU
local C   = 0x05b00400
local RAM = 0x05a00000
local REG_TIMER_A = 0x418
local REG_TIMER_B = 0x41a
local REG_MCIEB   = 0x42a
local REG_SCIPD   = 0x420
local REG_DTLG    = 0x416

emu.register_frame_done(function()
    frames = frames + 1
    if frames ~= 30 then return end

    -- 1. mem -> reg, two words, both addresses stepping
    sp:write_u16(RAM + 0x7f000, 0x1234)
    sp:write_u16(RAM + 0x7f002, 0x5678)
    sp:write_u16(C + 0x12, 0xf000)              -- DMEA[15:1]
    sp:write_u16(C + 0x14, 0x7000 | REG_TIMER_A) -- DMEA[19:16] | DRGA[11:1]
    local scipd_before = sp:read_u16(C + 0x20)
    sp:write_u16(C + 0x16, 0x0004)              -- DTLG = 4 bytes, DDIR = 0
    sp:write_u16(C + 0x16, 0x1004)              -- DEXE
    local scipd_after = sp:read_u16(C + 0x20)
    chk("dexe_selfclears", sp:read_u16(REG_DTLG) & 0x1000, 0x0000)
    chk("dma_end_irq", scipd_after & ~scipd_before & 0x10, 0x10)
    -- UpdateRegR overwrites the low byte with the live timer counter, so only
    -- the high byte proves the transfer landed
    chk("timerA_high", sp:read_u16(C + 0x18) & 0xff00, 0x1200)
    chk("timerB_high", sp:read_u16(C + 0x1a) & 0xff00, 0x5600)

    -- 2. reg -> mem, ungated: MCIEB reads back verbatim
    sp:write_u16(C + 0x2a, 0x0055)
    sp:write_u16(RAM + 0x7f100, 0xaaaa)         -- prove it is overwritten
    sp:write_u16(C + 0x12, 0xf100)              -- DMEA = 0x7f100
    sp:write_u16(C + 0x14, 0x7000 | REG_MCIEB)
    sp:write_u16(C + 0x16, 0x2002)              -- DTLG = 2, DDIR = 1
    sp:write_u16(C + 0x16, 0x3002)              -- DEXE
    chk("reg2mem", sp:read_u16(RAM + 0x7f100), 0x0055)

    -- 3. reg -> mem, gated: the stored value is forced to zero
    sp:write_u16(RAM + 0x7f102, 0xaaaa)
    sp:write_u16(C + 0x12, 0xf102)
    sp:write_u16(C + 0x14, 0x7000 | REG_MCIEB)
    sp:write_u16(C + 0x16, 0x6002)              -- DGATE = 1, DDIR = 1
    sp:write_u16(C + 0x16, 0x7002)              -- DEXE
    chk("gate_zeroes", sp:read_u16(RAM + 0x7f102), 0x0000)

    if #fails == 0 then print("SCSP_DMA_RUNTIME PASS")
    else for _, f in ipairs(fails) do print("SCSP_DMA_RUNTIME FAIL " .. f) end end
    m:exit()
end)
print("SCSP_DMA_RUNTIME armed")
"""


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

    with tempfile.TemporaryDirectory(prefix="scsp-dma-") as tmp:
        outdir = Path(tmp)
        script = outdir / "scsp_dma.lua"
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

    if "LUA ERROR" in text:
        raise AssertionError(f"Lua error:\n{text}")
    if "SCSP_DMA_RUNTIME PASS" in text:
        print("SCSP DMA: mem->reg, reg->mem, DGATE and completion all verified "
              "in a live machine")
        return 0
    detail = "\n".join(l for l in text.splitlines()
                       if "SCSP_DMA_RUNTIME" in l) or text[-2000:]
    raise AssertionError(f"assertions failed:\n{detail}")


if __name__ == "__main__":
    sys.exit(main())
