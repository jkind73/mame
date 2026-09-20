#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Run the real Saturn CD block firmware and check it takes over the host window (CD-03).

The console's "cdblock" slot selects the implementation behind the CD block
host window at 0x05800000: empty (default) is the HLE drive model, "-cdblock
lle" instantiates the YGR019B core (src/mame/sega/saturn_cdb.cpp) and runs the
dumped firmware (satcdb ROM set: cdb105/cdb106/ygr022) on its SH-1.

What this fixture establishes, all of it measured on the running machine:

  firmware_runs   the CD block SH-1 leaves its reset vector and executes: its
                  PC is sampled over time and must move through the firmware's
                  own address ranges, and its execution count must advance.

  identity        the firmware's init path (cdb105 at 0x1efc) writes the CD
                  block identity string into RR1-RR4 and raises the initial
                  HIRQ pattern.  The expected words are read out of the ROM
                  image itself at the addresses that code loads them from, so
                  the fixture asserts the firmware's real data, not a value
                  copied from the emulator.

  interrupts      YGR.CDMSKL (mask for the host command interrupt) must be
                  programmed to 1, which is what the firmware does before it
                  unmasks IRQ6 - i.e. the interrupt controller path the core
                  added is in use.

  command         a host command written to CR1..CR4 through the window must
                  be picked up: the firmware's IRQ6 handler runs (its IRQ
                  entry count grows) and it answers by writing RR1-RR4 and
                  raising CMOK.  This is the handshake the BIOS performs, and
                  it is what the HLE model used to be the only source of.

The drive side (CDD serial link, disc reading) is not emulated yet, so this is
deliberately not a boot-to-game claim: it qualifies the CD block firmware
booting and answering the host on its own hardware path.

Requires a built driver-filtered binary, the satcdb ROM set and the saturnjp
BIOS.  Skips with exit status 0 when any of them is absent, so run_all.py
stays ROM-free.
"""
from pathlib import Path
import argparse
import os
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]

# cdb105.bin's idle task calls L001EFC, which loads its identity string from
# 0x1f38 (srg320/Saturn_hw CDB/cdb105.asm).  The code moves the two long words
# through SWAP.W and back, so RR1-RR4 receive the bytes in memory order: the
# expected register values are the four words of the image itself, so they
# cannot drift from the ROM.  (cdb106/ygr022 are a different build with this
# data elsewhere, which is why the fixture pins -bios cdb105.)
IDENTITY_ROM_OFFSET = 0x1F38

LUA = r"""
local m = manager.machine
local main = m.devices[":maincpu"]
local sp = main.spaces["program"]
local cdb = m.devices[":cdblock:lle"]
local cpu = cdb and cdb.devices and nil
-- the firmware core's SH-1: the slot's card owns it
local sh1 = nil
for tag, dev in pairs(m.devices) do
    if tag:find(":cdblock") and tag:find("cdbcpu") then sh1 = dev end
end
local fails = {}
local function chk(label, cond, detail)
    if not cond then fails[#fails+1] = label .. " " .. tostring(detail) end
end

local HIRQ = 0x05880008
local CR1, CR2, CR3, CR4 = 0x05880018, 0x0588001c, 0x05880020, 0x05880024
local DR1, DR2, DR3, DR4 = CR1, CR2, CR3, CR4
local CMOK = 0x0001

local want_rr1, want_rr2, want_rr3, want_rr4 = @@RR1@@, @@RR2@@, @@RR3@@, @@RR4@@
local pcs, frames, irq_before, cycles0 = {}, 0, nil, nil

emu.register_frame_done(function()
    frames = frames + 1

    if frames <= 60 and sh1 and ((frames % 10) == 0) then
        pcs[#pcs+1] = sh1.state["PC"].value & 0x0fffffff
    end

    if frames == 60 then
        chk("firmware_entered", sh1 ~= nil, "no cdbcpu device in the slot")
        if sh1 then
            local distinct = {}
            local n = 0
            for _, pc in ipairs(pcs) do
                if not distinct[pc] then distinct[pc] = true; n = n + 1 end
            end
            -- the SH-1 boots at ROM address 0 and must leave it: the firmware
            -- sets up its stacks and scheduler and idles in its task loops
            chk("pc_leaves_reset", pcs[#pcs] ~= 0, string.format("last pc=%x", pcs[#pcs]))
            chk("pc_moves", n >= 3, "distinct PCs: " .. n)
            chk("pc_in_rom", pcs[#pcs] < 0x10000, string.format("pc=%x outside the 64KB ROM", pcs[#pcs]))
            cycles0 = sh1.state["CYCLES"].value
        end

        -- the identity registers the firmware wrote on its way into its tasks
        chk("rr1_identity", sp:read_u16(DR1), want_rr1)
        chk("rr2_identity", sp:read_u16(DR2), want_rr2)
        chk("rr3_identity", sp:read_u16(DR3), want_rr3)
        chk("rr4_identity", sp:read_u16(DR4), want_rr4)

        -- the firmware programs its own interrupt masks: CDMSKL = 1 enables
        -- the host command request on IRQ6
        local irq6_level = 0
        for tag, dev in pairs(m.devices) do
            if tag:find(":cdblock") and tag:find("cdbcpu") then
                irq6_level = dev.state["IRQ6"].value or 0
            end
        end
        chk("irq6_unmasked", irq6_level ~= 0, "IRQ6 line state " .. tostring(irq6_level))
        irq_before = sh1 and sh1.state["CYCLES"].value or 0

    elseif frames == 90 then
        -- a host command: Get Status (0x00), CR4 last (it is the write that
        -- latches the request on this hardware)
        sp:write_u16(HIRQ, 0xfffe)
        sp:write_u16(CR1, 0x0000)
        sp:write_u16(CR2, 0x0000)
        sp:write_u16(CR3, 0x0000)
        sp:write_u16(CR4, 0x0000)

    elseif frames == 150 then
        chk("cmok_raised_by_firmware", sp:read_u16(HIRQ) & CMOK, CMOK)
        if sh1 then
            chk("firmware_still_running", sh1.state["CYCLES"].value > irq_before,
                "cycle count did not advance")
        end

        if #fails == 0 then print("CD_LLE_RUNTIME PASS")
        else for _, f in ipairs(fails) do print("CD_LLE_RUNTIME FAIL " .. f) end end
        m:exit()
    end
end)
print("CD_LLE_RUNTIME armed")
"""


def identity_words(rom: bytes):
    """The four RR words the firmware's init code loads from the ROM."""
    return tuple(int.from_bytes(rom[IDENTITY_ROM_OFFSET + 2 * i:IDENTITY_ROM_OFFSET + 2 * i + 2], 'big')
                 for i in range(4))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--executable", type=Path, default=ROOT / "saturn")
    p.add_argument("--rompath", type=Path, default=ROOT / "regtests")
    a = p.parse_args()
    a.executable = a.executable.resolve()
    a.rompath = a.rompath.resolve()

    if not a.executable.is_file():
        print(f"SKIP: no binary at {a.executable} (build a driver-filtered subtarget first)")
        return 0
    for rom in ("saturnjp.zip", "satcdb.zip"):
        if not (a.rompath / rom).is_file():
            print(f"SKIP: no {rom} in {a.rompath}")
            return 0

    with tempfile.TemporaryDirectory(prefix="cd-lle-") as tmp:
        import zipfile
        outdir = Path(tmp)
        with zipfile.ZipFile(a.rompath / "satcdb.zip") as z:
            name = next(n for n in z.namelist() if n.endswith("cdb105.bin"))
            rom = z.read(name)
        words = identity_words(rom)
        script = outdir / "cd_lle.lua"
        text = LUA.replace("@@RR1@@", f"0x{words[0]:04x}")
        text = text.replace("@@RR2@@", f"0x{words[1]:04x}")
        text = text.replace("@@RR3@@", f"0x{words[2]:04x}")
        text = text.replace("@@RR4@@", f"0x{words[3]:04x}")
        script.write_text(text)
        for sub in ("nvram", "cfg"):
            (outdir / sub).mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
        result = subprocess.run([
            str(a.executable), "saturnjp",
            "-cdblock", "lle",
            "-bios", "cdb105",
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

    if result.returncode or "LUA ERROR" in text or "CD_LLE_RUNTIME FAIL" in text:
        detail = "\n".join(l for l in text.splitlines()
                           if "CD_LLE_RUNTIME" in l or "LUA ERROR" in l) or text[-2000:]
        raise AssertionError(f"CD block LLE firmware assertions failed:\n{detail}")
    if re.search(r"^CD_LLE_RUNTIME PASS$", text, re.M):
        print("CD block LLE: the dumped firmware boots on its own SH-1, programs "
              "its interrupt masks, publishes its identity registers and answers "
              "a host command with CMOK")
        return 0
    raise AssertionError("no CD_LLE_RUNTIME result in the run:\n" + text[-2000:])


if __name__ == "__main__":
    sys.exit(main())
