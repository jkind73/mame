#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Save-state round-trip for the SCSP timers (SND-05), plus CD HIRQ (CD-05).

`scsp_device::device_post_load()` (src/devices/sound/scsp.cpp:334-340) exists
because the timers are scheduled against machine time:

    // timers are scheduled against machine time, rebase and reschedule them
    m_timers[i].base_time = machine().time();
    timer_arm(i);

Nothing exercised it. A save state captures `counter`, `prescale`, `reload` and
`reload_pending` (scsp.cpp:242-245) but `base_time` is *not* a save_item, so it
has to be rebuilt on load or the restored timer runs at the wrong phase - and
because the counter is derived from base_time on every read, a stale base_time
shows up immediately as a wrong counter.

What this asserts, on a live saturnjp with all three CPUs parked:

  1. the timer genuinely advanced between save and load (so the test would be
     vacuous if the timer were not running);
  2. machine time rewound - the first callback after load is ~one frame after the
     save point, not ~eight frames;
  3. the counter was restored to the saved value rather than left running;
  4. the prescaler survived - measured again over a 3-frame window after load and
     compared against ST-077-R2's prescale-7 rate (once every 128 samples);
  5. CD block HIRQ state survived, including DCHG (bit 5), which only hirq_w()
     may clear - see test_cd_hirq.py.

CPUs are parked with the same technique as vdp2_runtime.lua so the BIOS cannot
reprogram the SCSP or acknowledge the CD interrupt underneath the test.

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
local function chk(label, ok, detail)
    if not ok then fails[#fails+1] = string.format("%s %s", label, detail) end
end

local C = 0x05b00400
local TA    = C + 0x18          -- TACTL[10:8] prescale | TIMA[7:0] counter
local SCIPD = C + 0x20
local HIRQ  = 0x05880008
local DCHG  = 0x0020

local SAMPLE_RATE = 44100
local PRESCALE = 7              -- once every 128 samples

local function park()
    sp:write_u32(0x06000000, 0xaffe0009)          -- bra to self, nop
    for _, tag in ipairs({":maincpu", ":slave"}) do
        local cpu = m.devices[tag]
        if cpu then cpu.state["SR"].value = 0xf0; cpu.state["PC"].value = 0x06000000 end
    end
    local snd = m.devices[":audiocpu"]
    if snd then
        snd.spaces["program"]:write_u16(0x100, 0x60fe)   -- bra *
        snd.state["SR"].value = 0x2700
        snd.state["PC"].value = 0x100
    end
end

local frames = 0
local phase = "park"
local t1, c1, t2, c2, hirq_before, rate_left
local outdir = os.getenv("SATURN_RUNTIME_OUTPUT") or "."

emu.add_machine_post_load_notifier(function() phase = "loaded" end)

emu.register_frame_done(function()
    frames = frames + 1
    if frames < 30 then return end

    if phase == "park" then
        park()
        sp:write_u16(TA, PRESCALE << 8)            -- prescale 7, reload 0
        m.ioport.ports[":RESET"].fields["Tray Open Button"]:set_value(1)
        phase = "run"

    elseif phase == "run" and frames == 34 then
        -- raise DCHG, then snapshot and save
        hirq_before = sp:read_u16(HIRQ)
        t1 = tonumber(emu.time())
        c1 = sp:read_u16(TA) & 0xff
        m:save(outdir .. "/scsp.sta")
        phase = "advance"

    elseif phase == "advance" and frames == 42 then
        t2 = tonumber(emu.time())
        c2 = sp:read_u16(TA) & 0xff
        m:load(outdir .. "/scsp.sta")

    elseif phase == "loaded" then
        local t3 = tonumber(emu.time())
        local c3 = sp:read_u16(TA) & 0xff
        local hirq_after = sp:read_u16(HIRQ)

        local advanced = (c2 - c1) & 0xff
        chk("timer_advanced_before_load", advanced >= 30,
            string.format("got=%d want>=30 (8 frames at prescale 7 ~ 46)", advanced))

        local rewind = t3 - t1
        chk("clock_rewound_to_save_point", rewind < 0.05,
            string.format("got=%.6f want<0.05 (8 frames would be ~0.134)", rewind))

        local drift = (c3 - c1) & 0xff
        chk("counter_restored", drift <= 8,
            string.format("got=%d want<=8 (one frame at prescale 7 ~ 6)", drift))

        chk("cd_hirq_restored", hirq_after == hirq_before,
            string.format("got=%04x want=%04x", hirq_after, hirq_before))
        chk("cd_dchg_restored", (hirq_after & DCHG) == DCHG,
            string.format("got=%04x bit5=%d", hirq_after, (hirq_after >> 5) & 1))

        print(string.format(
            "SAVESTATE advanced=%d rewind=%.6f drift=%d hirq %04x->%04x",
            advanced, rewind, drift, hirq_before, hirq_after))

        -- now re-measure the prescaler rate from the restored state
        phase = "rate1"

    elseif phase == "rate1" then
        t1 = tonumber(emu.time()); c1 = sp:read_u16(TA) & 0xff
        rate_left = 3
        phase = "rate2"

    elseif phase == "rate2" then
        rate_left = rate_left - 1
        if rate_left > 0 then return end
        local dt = tonumber(emu.time()) - t1
        local meas = ((sp:read_u16(TA) & 0xff) - c1) & 0xff
        local pred = math.floor(dt * SAMPLE_RATE / (2 ^ PRESCALE))
        local want = pred % 256
        chk("prescale_survived", meas == want or meas == (want + 1) % 256,
            string.format("got=%d want=%d or %d", meas, want, (want + 1) % 256))
        print(string.format("PRESCALE_AFTER_LOAD dt=%.9f predicted=%d measured=%d",
            dt, pred, meas))

        if #fails == 0 then print("SCSP_SAVESTATE PASS")
        else for _, f in ipairs(fails) do print("SCSP_SAVESTATE FAIL " .. f) end end
        m:exit()
    end
end)
print("SCSP_SAVESTATE armed")
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

    with tempfile.TemporaryDirectory(prefix="scsp-savestate-") as tmp:
        outdir = Path(tmp)
        script = outdir / "scsp_savestate.lua"
        script.write_text(LUA)
        for sub in ("nvram", "cfg"):
            (outdir / sub).mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
                   SATURN_RUNTIME_OUTPUT=str(outdir))
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
    if "SCSP_SAVESTATE PASS" in text:
        for l in text.splitlines():
            if l.startswith(("SAVESTATE", "PRESCALE_AFTER_LOAD")):
                print("  " + l)
        print("Save-state round-trip: SCSP timer counter, prescaler and CD HIRQ "
              "all restored, exercising scsp_device::device_post_load")
        return 0
    detail = "\n".join(l for l in text.splitlines()
                       if "SCSP_SAVESTATE" in l) or text[-2000:]
    raise AssertionError(f"assertions failed:\n{detail}")


if __name__ == "__main__":
    sys.exit(main())
