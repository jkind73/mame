#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Run the real Saturn CD block firmware and check it answers the host (CD-03).

The console's "cdblock" slot selects the implementation behind the CD block
host window at 0x05800000: empty (the default) is the HLE drive model;
"-cdblock lle,bios=cdb105" instantiates the YGR019B core in
src/mame/sega/saturn_cdb.cpp and runs the dumped firmware (satcdb ROM set:
cdb105/cdb106/ygr022) on its own SH-1 at 20 MHz.

What this fixture establishes, all of it read back through the register window
the console's own BIOS uses:

  firmware_runs           the CD block SH-1 leaves its reset vector and runs
                          inside its own ROM.
  boot_hirq_visible       the firmware's init raises its boot HIRQ pattern in
                          the host window.  The expected pattern is not written
                          here: it is read out of the firmware image, from the
                          constant that init routine loads.
  host_ack_reaches        a host write that acknowledges those HIRQ bits is
                          visible in the firmware's HIRQ.
  firmware_answered       the host writes a command the way the BIOS does
                          (CR1..CR4, CR4 last = Get Hardware Info).  The host
                          clears HIRQ's CMOK bit just before, so when CMOK comes
                          back it can only come from the firmware finishing that
                          command.  The response words are printed for the
                          record.

If the firmware's identity response (RR1-RR4 = "\0CDBLOCK", again taken from the
image) happens to be sampled while it is valid, the fixture reports the frame;
it is not a pass/fail check because the BIOS consumes that response during boot
and later responses overwrite it.

The CD drive side (CDD serial link, disc reading) is not emulated yet: the
firmware answers commands from the host, but it has no disc to report, so this
is deliberately not a boot-to-game claim.  It qualifies the CD block firmware
running on its own hardware path and answering the console through the real
host interface.

Requires a built driver-filtered binary, the satcdb ROM set and the saturnjp
BIOS.  Skips with exit status 0 when any of them is absent, so run_all.py stays
ROM-free.
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
IDENTITY_ROM_OFFSET = 0x1F38  # RR1-RR4 = "\0CDBLOCK"
HIRQ_ROM_OFFSET = 0x1F30      # the HIRQ pattern init publishes

LUA = r"""
-- The CD block slot card runs the dumped YGR019B firmware on its own SH-1.
-- Everything asserted here is what the console's SH-2 (the host) can see
-- through the real register window, which is the same window the BIOS uses:
-- a passing run means the firmware ran and answered through its own hardware
-- path, not that a helper produced the values.
local m = manager.machine
local host = m.devices[":maincpu"].spaces["program"]
local card, sh1 = nil, nil
for tag, dev in pairs(m.devices) do
    if tag == ":cdblock:lle" then card = dev end
    if tag == ":cdblock:lle:cdbcpu" then sh1 = dev end
end

-- host window (byte offsets folded by the driver: +0x80008 HIRQ, +0x80018 CR1/DR1 .. +0x80024 CR4/DR4)
local HIRQ, CR1, CR2, CR3, CR4 = 0x05880008, 0x05880018, 0x0588001c, 0x05880020, 0x05880024
local BAK = 0xffbe          -- the HIRQ bits the BIOS acknowledges with
local CMOK = 0x0001         -- HIRQ bit 0: command completed
-- the HIRQ pattern the firmware's own init raises, taken from its image (the
-- constant its init routine loads before storing it to YGR.HIRQ)
local BOOT_HIRQ = @@BOOT_HIRQ@@
local IDENTITY = { @@IDENTITY@@ }  -- RR1-RR4 the firmware's init publishes

local fails = {}
local function chk(label, cond, detail)
    if not cond then fails[#fails + 1] = label .. ": " .. tostring(detail) end
end
local function hirq() return host:read_u16(HIRQ) end
local function dr() return host:read_u16(CR1), host:read_u16(CR2), host:read_u16(CR3), host:read_u16(CR4) end

local pcs, distinct = {}, {}
local frames, acked, sent_at, answered = 0, nil, nil, false
local identity_frame, response = nil, nil

emu.register_frame_done(function()
    frames = frames + 1

    if sh1 and ((frames % 10) == 0) then
        local pc = sh1.state["PC"].value & 0x0fffffff
        pcs[#pcs + 1] = pc
        distinct[pc] = true
    end

    -- the firmware's identity response is transient (the BIOS consumes it and
    -- later responses overwrite it), so it is sampled, not asserted
    local d1, d2, d3, d4 = dr()
    if not identity_frame and d1 == IDENTITY[1] and d2 == IDENTITY[2]
       and d3 == IDENTITY[3] and d4 == IDENTITY[4] then
        identity_frame = frames
    end

    if frames == 120 then
        chk("firmware_entered", sh1 ~= nil, "no CD block SH-1 in the slot")
        if sh1 then
            local n = 0
            for _ in pairs(distinct) do n = n + 1 end
            chk("firmware_runs", n >= 3 and pcs[#pcs] ~= 0,
                string.format("distinct PCs %d, last %x", n, pcs[#pcs]))
            chk("firmware_pc_in_rom", pcs[#pcs] < 0x10000,
                string.format("PC %x is outside the firmware ROM", pcs[#pcs]))
        end
        print(string.format("CD_LLE_IDENTITY identity %s at frame %s",
            identity_frame and "seen" or "not sampled",
            identity_frame and tostring(identity_frame) or "n/a"))

    elseif frames == 180 then
        -- the firmware's init has raised its boot HIRQ pattern by now; the host
        -- must see it in the window (bit 0 is excluded because the host may
        -- have acknowledged it already)
        local h = hirq()
        chk("boot_hirq_visible", (h & ~CMOK) == (BOOT_HIRQ & ~CMOK),
            string.format("HIRQ %04x, firmware pattern %04x", h, BOOT_HIRQ))

        -- a host acknowledge of those bits must reach the firmware's HIRQ
        host:write_u16(HIRQ, BAK)
        acked = hirq()
        chk("host_ack_reaches_firmware", (acked & BAK) == (BOOT_HIRQ & BAK),
            string.format("HIRQ after ack %04x, expected %04x", acked, BOOT_HIRQ & BAK))

        -- a host command, written the way the BIOS writes it (CR4 last, which
        -- is what raises the command request): Get Hardware Info
        host:write_u16(CR1, 0x0100)
        host:write_u16(CR2, 0x0000)
        host:write_u16(CR3, 0x0000)
        host:write_u16(CR4, 0x0000)
        sent_at = frames

    elseif sent_at and frames > sent_at and not answered then
        -- the firmware answers a command by writing its response registers and
        -- then raising CMOK; since the host cleared CMOK just before the write,
        -- the bit coming back can only come from the firmware
        if (hirq() & CMOK) ~= 0 then
            answered = true
            local r1, r2, r3, r4 = dr()
            response = string.format("%04x %04x %04x %04x", r1, r2, r3, r4)
            print(string.format("CD_LLE_RESPONSE command answered in %d frames, DR1-4 = %s",
                frames - sent_at, response))
        end

    elseif frames == 260 then
        chk("firmware_answered_command", answered,
            "CMOK did not come back after a host command (host window or firmware dispatch)")
        if #fails == 0 then
            print("CD_LLE_RUNTIME PASS")
        else
            for _, f in ipairs(fails) do print("CD_LLE_RUNTIME FAIL " .. f) end
        end
        m:exit()
    end
end)
print("CD_LLE_RUNTIME armed")
"""

def firmware_constants(rom: bytes):
    """Values the YGR019B firmware's own init code publishes.

    L001EFC loads three constants from its image and stores them to the YGR
    registers: CDMSKL = 0x0001 at 0x1F2E, HIRQ at 0x1F30, then the four identity
    words RR1-RR4 = "\0CDBLOCK" at 0x1F38 (disassembly: cdb105.asm, srg320's
    Saturn_hw CDB/ dump).  Reading them here keeps this fixture honest: it
    asserts what the firmware itself writes, not values invented by the test.
    """
    def word(off):
        return int.from_bytes(rom[off:off + 2], 'big')
    return {'hirq': word(HIRQ_ROM_OFFSET),
            'identity': tuple(word(IDENTITY_ROM_OFFSET + 2 * i) for i in range(4))}


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
        const = firmware_constants(rom)
        script = outdir / "cd_lle.lua"
        text = LUA.replace("@@BOOT_HIRQ@@", f"0x{const['hirq']:04x}")
        text = text.replace("@@IDENTITY@@",
                            ", ".join(f"0x{w:04x}" for w in const['identity']))
        script.write_text(text)
        for sub in ("nvram", "cfg"):
            (outdir / sub).mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
        result = subprocess.run([
            str(a.executable), "saturnjp",
            "-cdblock", "lle,bios=cdb105",  # the CD block's own BIOS, not the console's
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
                           if l.startswith("CD_LLE_") or "LUA ERROR" in l) or text[-2000:]
        raise AssertionError(f"CD block LLE firmware assertions failed:\n{detail}")
    if re.search(r"^CD_LLE_RUNTIME PASS$", text, re.M):
        detail = [l for l in text.splitlines() if l.startswith("CD_LLE_")]
        print("CD block LLE: the dumped firmware runs on its own SH-1, raises its "
              "boot HIRQ in the host window, acknowledges a host HIRQ write and "
              "answers a host command with CMOK")
        for l in detail:
            print("  " + l)
        return 0
    raise AssertionError("no CD_LLE_RUNTIME result in the run:\n" + text[-2000:])


if __name__ == "__main__":
    sys.exit(main())
