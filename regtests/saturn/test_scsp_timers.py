#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Drive the SCSP prescaler timers inside a running machine (SND-03).

ST-077-R2 section 4 "Timer Register" documents three 8-bit up-counters A, B and
C, each with its own prescaler, and gives the increment table explicitly:

    TACTL[2:0] / TBCTL[2:0] / TCCTL[2:0]   Increment Cycle
    0  once every sample       4  once every 16 samples
    1  once every 2 samples    5  once every 32 samples
    2  once every 4 samples    6  once every 64 samples
    3  once every 8 samples    7  once every 128 samples

MAME encodes that as `inc_clocks = SAMPLE_CLOCKS << prescale` with
`SAMPLE_CLOCKS = 512` and a 22 579 200 Hz SCSP clock (sat_console.cpp:1169,
8.4672 MHz * 8 / 3), so one increment period is `(1 << prescale) / 44100`
seconds. This script measures the counter's real advancement against that table
for all eight settings rather than assuming the shift is right.

It also checks the completion path: timer_cb raises SCIPD (common control 0x20)
bit 6 for timer A.

Method note that cost a wrong first result: the unmodified BIOS programs the
SCSP timers during sound initialisation, so measuring from Lua while it runs
produces garbage - a first pass read timer A advancing by 230 counts in one
frame at prescale 4, where the table predicts 46. The three CPUs are therefore
parked first, using the same technique as vdp2_runtime.lua: `bra` to self plus
`nop` at 0x06000000 for the two SH-2s, `bra *` (0x60fe) in sound RAM for the
68EC000, with SR/ interrupt level raised so nothing resumes them.

Tolerance: timer_sync advances base_time by whole increment periods, so a
measurement window that is not an exact multiple of the increment period carries
a remainder into the next one. A window of N increments is therefore asserted as
N or N+1, which still separates every entry in the table by a factor of two.

This test covers the prescaler table and the interrupt. It deliberately does NOT
try to measure the number of count cycles between a TIMx write and the first
interrupt: that is a single-count-cycle question (22.7 us at prescale 0) and Lua
only samples at frame boundaries, so the measurement cannot resolve it. A
one-count-cycle discrepancy against the manual's formula was found by reading
the code and is recorded, unmeasured, in
regtests/saturn/handoff/devices.md (SND-03).

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
local fails = {}
local function chk(label, got, want_lo, want_hi)
    if got < want_lo or got > want_hi then
        fails[#fails+1] = string.format("%s got=%d want=%d..%d", label, got, want_lo, want_hi)
    end
end

-- membership rather than a range: the window may straddle a 256 boundary
local function chk_in(label, got, a, b)
    if got ~= a and got ~= b then
        fails[#fails+1] = string.format("%s got=%d want=%d or %d", label, got, a, b)
    end
end

-- SCSP common control registers as seen by the main CPU
local C = 0x05b00400
local TA    = C + 0x18      -- TACTL[10:8] prescale | TIMA[7:0] live counter
local SCIPD = C + 0x20

local SAMPLE_RATE = 44100

-- Park every CPU so the BIOS sound init cannot touch the timers underneath us.
local function park()
    sp:write_u32(0x06000000, 0xaffe0009)          -- bra to self, nop
    for _, tag in ipairs({":maincpu", ":slave"}) do
        local cpu = m.devices[tag]
        if cpu then cpu.state["SR"].value = 0xf0; cpu.state["PC"].value = 0x06000000 end
    end
    local snd = m.devices[":audiocpu"]
    if snd then
        local ssp = snd.spaces["program"]
        ssp:write_u16(0x00000100, 0x60fe)         -- bra *
        snd.state["SR"].value = 0x2700
        snd.state["PC"].value = 0x00000100
    end
end

local WINDOW = 3          -- frames per measurement
local prescale = 0
local phase = "park"
local frames = 0
local t_start, c_start, count_left

emu.register_frame_done(function()
    frames = frames + 1
    if frames < 30 then return end

    if phase == "park" then
        park()
        sp:write_u16(TA, prescale << 8)           -- prescale p, reload 0
        phase = "run"

    elseif phase == "run" then
        if t_start == nil then
            t_start = tonumber(emu.time())
            c_start = sp:read_u16(TA) & 0xff
            phase = "count"
            count_left = WINDOW
        end

    elseif phase == "count" then
        count_left = count_left - 1
        if count_left > 0 then return end

        local t_end = tonumber(emu.time())
        local c_end = sp:read_u16(TA) & 0xff
        local dt = t_end - t_start
        local meas = (c_end - c_start) & 0xff
        local pred = math.floor(dt * SAMPLE_RATE / (2 ^ prescale))
        local want = pred % 256
        chk_in(string.format("prescale%d_rate", prescale), meas, want, (want + 1) % 256)
        print(string.format("PRESCALE %d dt=%.9f predicted=%5d measured(mod256)=%3d window=%5d",
            prescale, dt, pred, meas, pred))

        prescale = prescale + 1
        t_start = nil
        if prescale < 8 then
            sp:write_u16(TA, prescale << 8)
            phase = "run"
        else
            -- completion path: fastest timer, shortest reload
            sp:write_u16(SCIPD, 0x0000)       -- acknowledge anything pending
            sp:write_u16(TA, 0x00fe)          -- prescale 0, reload 0xfe
            phase = "irq"
        end

    elseif phase == "irq" then
        local pd = sp:read_u16(SCIPD)
        chk("timer_a_irq_raised", (pd >> 6) & 1, 1, 1)
        print(string.format("SCIPD=%04x timer_a_bit6=%d", pd, (pd >> 6) & 1))

        if #fails == 0 then print("SCSP_TIMER_RUNTIME PASS")
        else for _, f in ipairs(fails) do print("SCSP_TIMER_RUNTIME FAIL " .. f) end end
        m:exit()
    end
end)
print("SCSP_TIMER_RUNTIME armed")
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

    with tempfile.TemporaryDirectory(prefix="scsp-timers-") as tmp:
        outdir = Path(tmp)
        script = outdir / "scsp_timers.lua"
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
    if "SCSP_TIMER_RUNTIME PASS" in text:
        rates = [l for l in text.splitlines() if l.startswith("PRESCALE")]
        print("SCSP timers: all eight ST-077-R2 prescaler divisions measured in a "
              f"live machine and the timer A interrupt confirmed ({len(rates)} rates)")
        for l in rates:
            print("  " + l)
        return 0
    detail = "\n".join(l for l in text.splitlines()
                       if "SCSP_TIMER_RUNTIME" in l) or text[-2000:]
    raise AssertionError(f"assertions failed:\n{detail}")


if __name__ == "__main__":
    sys.exit(main())
