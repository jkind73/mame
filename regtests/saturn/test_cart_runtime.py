#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Drive the Saturn cartridge memory windows inside a running machine (CART-01).

test_sat_cart.py compiles the production accessors out of
src/devices/bus/saturn/{dram,bram}.cpp and drives them directly, which covers
their logic but not their wiring. This script closes that gap from the other
end: it boots a real machine with a cartridge selected through the sat_cart
software list and reads/writes the cartridge windows through the main CPU's
program space, so the sat_console.cpp handler installation, the address decode
and the accessors are all exercised together.

What it asserts

  ram8  (Saturn Data RAM 8Mbit, cart ID 0x5a)
    dram0 and dram1 each get a 0x80000-byte data area, i.e. 0x20000 words,
    inside a fixed 2 MiB window per chip. Accesses therefore alias four times
    over the window; dram1 must be independent storage.

  bram4 (Saturn Battery RAM 4Mbit, cart ID 0x21)
    A 0x80000-byte chip inside an 8 MiB window. The chip keeps only the two
    byte lanes of a longword, so values round-trip byte-spread, and the first
    address past the chip is open bus rather than a mirror.

Not covered here, and why

  Partial-lane writes are untestable from Lua: space:write_u32 binds to
  addr_space::mem_write(offs_t, T) at luaengine_mem.cpp:364, which takes no
  mem_mask, so any third argument is silently dropped. test_sat_cart.py calls
  the extracted handler directly and does cover the lane masks.

Requires a built driver-filtered binary and BIOS ROMs. Skips with exit status 0
when they are absent so run_all.py stays ROM-free.
"""
from pathlib import Path
import argparse
import os
import re
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]

DRAM_LUA = r"""
local m = manager.machine
local sp = m.devices[":maincpu"].spaces["program"]
local frames = 0
local fails = {}
local function chk(label, got, want)
    if got ~= want then fails[#fails+1] = string.format("%s got=%08x want=%08x", label, got, want) end
end
emu.register_frame_done(function()
    frames = frames + 1
    if frames ~= 10 then return end
    chk("cart_id", sp:read_u8(0x04ffffff), 0x5a)
    sp:write_u32(0x02400000, 0x11223344)
    chk("dram0.w0", sp:read_u32(0x02400000), 0x11223344)
    -- 512 KiB chip inside a 2 MiB window => the chip answers four times
    chk("dram0.alias1", sp:read_u32(0x02480000), 0x11223344)
    chk("dram0.alias2", sp:read_u32(0x02500000), 0x11223344)
    chk("dram0.alias3", sp:read_u32(0x02580000), 0x11223344)
    -- the next word is separate storage, and writing it leaves word 0 alone
    sp:write_u32(0x02400004, 0xdeadbeef)
    chk("dram0.w1", sp:read_u32(0x02400004), 0xdeadbeef)
    chk("dram0.w1.alias", sp:read_u32(0x02480004), 0xdeadbeef)
    chk("dram0.w0.intact", sp:read_u32(0x02400000), 0x11223344)
    -- dram1 is a second chip, not more of dram0
    chk("dram1.unwritten", sp:read_u32(0x02600000), 0x00000000)
    sp:write_u32(0x02600000, 0xa5a5a5a5)
    chk("dram1.w0", sp:read_u32(0x02600000), 0xa5a5a5a5)
    chk("dram0.unaffected", sp:read_u32(0x02400000), 0x11223344)
    if #fails == 0 then print("CART_RUNTIME PASS dram (ram8)")
    else for _, f in ipairs(fails) do print("CART_RUNTIME FAIL " .. f) end end
    m:exit()
end)
print("CART_RUNTIME armed")
"""

BRAM_LUA = r"""
local m = manager.machine
local sp = m.devices[":maincpu"].spaces["program"]
local frames = 0
local fails = {}
local function chk(label, got, want)
    if got ~= want then fails[#fails+1] = string.format("%s got=%08x want=%08x", label, got, want) end
end
emu.register_frame_done(function()
    frames = frames + 1
    if frames ~= 10 then return end
    chk("cart_id", sp:read_u8(0x04ffffff), 0x21)
    -- bits 16-23 of 0xaabbccdd are 0xbb and bits 0-7 are 0xdd; those are the
    -- only two lanes the chip stores, so the longword comes back spread
    sp:write_u32(0x04000000, 0xaabbccdd)
    chk("bram.w0", sp:read_u32(0x04000000), 0x00bb00dd)
    -- rewriting sets both lanes again
    sp:write_u32(0x04000000, 0x11223344)
    chk("bram.w0.rewrite", sp:read_u32(0x04000000), 0x00220044)
    -- 512 KiB chip: the last valid word offset is 0x3ffff = byte 0x040ffffc
    sp:write_u32(0x040ffffc, 0x0000beef)
    chk("bram.lastword", sp:read_u32(0x040ffffc), 0x000000ef)
    -- the 8 MiB window is far larger than the chip; past the end is open bus
    chk("bram.oob", sp:read_u32(0x04100000), 0xffffffff)
    if #fails == 0 then print("CART_RUNTIME PASS bram (bram4)")
    else for _, f in ipairs(fails) do print("CART_RUNTIME FAIL " .. f) end end
    m:exit()
end)
print("CART_RUNTIME armed")
"""

CASES = (("ram8", "dram (ram8)", DRAM_LUA), ("bram4", "bram (bram4)", BRAM_LUA))


def run_case(executable, rompath, hashpath, cart, label, lua, outdir):
    script = outdir / f"{cart}.lua"
    script.write_text(lua)
    for sub in ("nvram", "cfg"):
        (outdir / sub).mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    command = [
        str(executable), "saturnjp", "-cart", cart,
        "-rompath", str(rompath), "-hashpath", str(hashpath),
        "-noreadconfig", "-skip_gameinfo", "-nodrc",
        "-video", "none", "-sound", "none", "-nothrottle",
        "-autoboot_delay", "0", "-autoboot_script", str(script),
        "-seconds_to_run", "60",
        "-nvram_directory", str(outdir / "nvram"),
        "-cfg_directory", str(outdir / "cfg"),
        "-state_directory", str(outdir),
        "-snapshot_directory", str(outdir),
    ]
    result = subprocess.run(command, cwd=outdir, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=600)
    text = result.stdout.decode("utf-8", "replace")
    if result.returncode or "LUA ERROR" in text or "CART_RUNTIME FAIL" in text:
        raise AssertionError(f"{cart}: Lua error:\n{text}")
    if re.search(rf"^CART_RUNTIME PASS {re.escape(label)}$", text, re.M):
        return text
    detail = "\n".join(line for line in text.splitlines()
                       if "CART_RUNTIME" in line) or text[-2000:]
    raise AssertionError(f"{cart}: assertions failed:\n{detail}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--executable", type=Path, default=ROOT / "saturn")
    p.add_argument("--rompath", type=Path, default=ROOT / "regtests")
    p.add_argument("--hashpath", type=Path, default=ROOT / "hash")
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
    if not (a.hashpath / "sat_cart.xml").is_file():
        print(f"SKIP: no sat_cart software list in {a.hashpath}")
        return 0

    passed = 0
    with tempfile.TemporaryDirectory(prefix="saturn-cart-rt-") as tmp:
        outdir = Path(tmp)
        for cart, label, lua in CASES:
            run_case(a.executable, a.rompath, a.hashpath, cart, label, lua, outdir)
            print(f"  {label}: PASS")
            passed += 1
    print(f"Saturn cart runtime: {passed} cartridges exercised in a live machine")
    return 0


if __name__ == "__main__":
    sys.exit(main())
