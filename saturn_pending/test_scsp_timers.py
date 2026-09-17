#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Live SCSP timer/divisor and interrupt fixture adapted from the supplied patch.

Checks all three timers and eight prescalers against ST-077-R2 pp.93-94.
The CPUs are parked to prevent BIOS timer writes. SCIPD is not an acknowledge
register: clear requests through SCIRE after loading a non-expired count,
assert that the request is clear, then program and observe a fresh interrupt.
Frame sampling qualifies rates and request delivery, not sub-tick phase,
reload latency, sound waveform quality or hardware-accurate timer behavior.

This auxiliary runner is outside the frozen integration inputs. Invoke with
--executable and --rompath to measure a built binary; no binary/BIOS is a skip,
not acceptance. All runs isolate configuration and NVRAM from the user's files.
"""
from pathlib import Path
import argparse
import os
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]

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
local SCIRE = C + 0x22

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
local timer = 0
local function timer_reg() return TA + timer * 2 end
local function timer_bit() return 1 << (6 + timer) end
local phase = "park"
local frames = 0
local t_start, c_start, count_left

emu.register_frame_done(function()
    frames = frames + 1
    if frames < 30 then return end

    if phase == "park" then
        park()
        sp:write_u16(timer_reg(), prescale << 8)           -- prescale p, reload 0
        phase = "run"

    elseif phase == "run" then
        if t_start == nil then
            t_start = tonumber(emu.time())
            c_start = sp:read_u16(timer_reg()) & 0xff
            phase = "count"
            count_left = WINDOW
        end

    elseif phase == "count" then
        count_left = count_left - 1
        if count_left > 0 then return end

        local t_end = tonumber(emu.time())
        local c_end = sp:read_u16(timer_reg()) & 0xff
        local dt = t_end - t_start
        local meas = (c_end - c_start) & 0xff
        local pred = math.floor(dt * SAMPLE_RATE / (2 ^ prescale))
        local want = pred % 256
        chk_in(string.format("timer%d_prescale%d_rate", timer, prescale), meas, want, (want + 1) % 256)
        print(string.format("PRESCALE %d %d dt=%.9f predicted=%5d measured(mod256)=%3d window=%5d",
            timer, prescale, dt, pred, meas, pred))

        prescale = prescale + 1
        t_start = nil
        if prescale < 8 then
            sp:write_u16(timer_reg(), prescale << 8)
            phase = "run"
        else
            -- Load a non-expired counter before clearing the pending flag.
            -- SCIRE can immediately re-pend a timer that still reads FF.
            sp:write_u16(timer_reg(), 0x0700)
            phase = "ack_irq"
        end

    elseif phase == "ack_irq" then
        sp:write_u16(SCIRE, timer_bit())
        chk("timer_irq_cleared", sp:read_u16(SCIPD) & timer_bit(), 0, 0)
        sp:write_u16(timer_reg(), 0x00fe)
        phase = "irq"

    elseif phase == "irq" then
        local pd = sp:read_u16(SCIPD)
        chk("timer_irq_raised", pd & timer_bit(), timer_bit(), timer_bit())
        print(string.format("TIMER_IRQ %d SCIPD=%04x", timer, pd))
        timer = timer + 1
        if timer < 3 then
            prescale = 0
            sp:write_u16(timer_reg(), 0)
            phase = "run"
            return
        end

        if #fails == 0 then print("SCSP_TIMER_RUNTIME PASS")
        else for _, f in ipairs(fails) do print("SCSP_TIMER_RUNTIME FAIL " .. f) end end
        m:exit()
    end
end)
print("SCSP_TIMER_RUNTIME armed")
"""


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

    if result.returncode != 0 or "SCSP_TIMER_RUNTIME FAIL" in text or "LUA ERROR" in text:
        raise AssertionError(f"Lua error:\n{text}")
    if re.search(r"^SCSP_TIMER_RUNTIME PASS$", text, re.MULTILINE):
        rates = [l for l in text.splitlines() if l.startswith("PRESCALE ")]
        measured = [tuple(map(int, m)) for m in re.findall(r"^PRESCALE ([0-2]) ([0-7]) dt=", text, re.MULTILINE)]
        assert len(measured) == 24 and set(measured) == {(t,p) for t in range(3) for p in range(8)}, text
        irqs = re.findall(r"^TIMER_IRQ ([0-2]) SCIPD=", text, re.MULTILINE)
        assert irqs == ['0','1','2'], text
        print("SCSP timers: 24 timer/divisor rates and three clear/reassert paths verified live")
        for l in rates:
            print("  " + l)
        return 0
    detail = "\n".join(l for l in text.splitlines()
                       if "SCSP_TIMER_RUNTIME" in l) or text[-2000:]
    raise AssertionError(f"assertions failed:\n{detail}")


if __name__ == "__main__":
    sys.exit(main())
