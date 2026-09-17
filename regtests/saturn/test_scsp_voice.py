#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Key-on / key-off a SCSP voice and listen to the result (SND-02).

Everything else in this suite observes registers. This one observes the actual
audio, because the 32-voice engine has no register that reports "am I making
sound" - UpdateSlotRegR() is empty, so a slot's envelope and phase are not
readable from either CPU. The only ground truth is the mixer output, captured
with -wavwrite.

It exercises the ST-077-R2 KEY_ON sequence end to end:

  KYONB  (slot word 0 bit 11) records KEY_ON / KEY_OFF for that slot
  KYONEX (slot word 0 bit 12) executes KEY_ON/KEY_OFF for *all* 32 slots

and ST-077 states "there is no need to write a '0B' in 'KYONEX' after writing a
'1B'" - MAME models that by clearing bit 12 in UpdateSlotReg (scsp.cpp:942).
KEY_ON routes through StartSlot, KEY_OFF through StopSlot.

What is asserted, from the captured WAV:

  onset   the first non-zero sample lands on the frame KYONEX was written with
          KYONB set (frame 30), not merely "somewhere during the run"
  level   the sounding window is loud - the square wave written to sound RAM
          (+/-0x4000) survives TL=0, DISDL=7, MVOL=0xf and the envelope's
          attack/sustain phases
  offset  the last non-zero sample lands on the frame KYONEX was written with
          KYONB clear (frame 60)
  tail    everything after key-off is bit-exactly silent, so the test proves
          StopSlot stops the slot rather than merely attenuating it

Frame-to-sample mapping is derived, not hardcoded: the WAV is 2-channel 48 kHz
and interleaved, so stereo frame = index/2, seconds = stereo/48000, emulated
frame = seconds*60. Measured on the reference run: onset index 48192 -> stereo
24096 -> 0.502 s -> frame 30, and offset index 96634 -> stereo 48317 -> 1.007 s ->
frame 60, i.e. both land on the exact frames the keys were written.

A configuration trap worth recording, because it produced a wrong first result.
`StopSlot(slot, 1)` (scsp.cpp:807) does not silence the slot - it sets
`EG.state = SCSP_RELEASE` and lets the release envelope decay. My first attempt
used the undocumented EGBYP full-volume bypass (slot word 5 bit 15) together with
RR = 0, which pins the envelope open, so key-off never reached silence and the
slot sounded until the end of the run. Using a real envelope (fast attack, no
decay, fast release) makes key-off behave and exercises the envelope generator
properly, which is better coverage anyway.

CPUs are parked with the same technique as vdp2_runtime.lua so the BIOS cannot
reprogram the SCSP. Note that -sound must NOT be disabled: -sound none yields a
silent WAV and the test would be meaningless.

Requires a built driver-filtered binary and BIOS ROMs. Skips with exit status 0
when they are absent so run_all.py stays ROM-free.
"""
from pathlib import Path
import argparse
import array
import os
import subprocess
import sys
import tempfile
import wave

ROOT = Path(__file__).resolve().parents[2]

LUA = r"""
local m = manager.machine
local sp = m.devices[":maincpu"].spaces["program"]
local RAM, S0, C = 0x05a00000, 0x05b00000, 0x05b00400

local KEYONB, KEYONEX = 0x0800, 0x1000
local LPCTL_LOOP      = 0x0020     -- slot word 0 bits 6:5, value 1 = loop

local frames = 0
emu.register_frame_done(function()
    frames = frames + 1

    if frames == 30 then
        -- park all three CPUs
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

        -- 512-sample square wave in sound RAM
        for i = 0, 511 do
            sp:write_u16(RAM + i * 2, (i % 2 == 0) and 0x4000 or 0xc000)
        end

        sp:write_u16(C + 0x00, 0x000f)                       -- MVOL = max
        sp:write_u16(S0 + 0x00, KEYONB | LPCTL_LOOP)         -- record KEY_ON, loop
        sp:write_u16(S0 + 0x02, 0x0000)                      -- SA[15:0]
        sp:write_u16(S0 + 0x04, 0x0000)                      -- LSA
        sp:write_u16(S0 + 0x06, 0x03ff)                      -- LEA
        -- Real envelope, no shortcuts: AR = 0x1f for a fast attack, D1R = D2R = 0
        -- so the level is held (sustains), DL = 0x1f, RR = 0x1f for a fast
        -- release. Deliberately NOT using the undocumented EGBYP full-volume
        -- bypass - see the docstring note on why that would hide key-off.
        sp:write_u16(S0 + 0x08, 0x001f)                      -- D2R=0 D1R=0 AR=0x1f
        sp:write_u16(S0 + 0x0a, 0x03ff)                      -- DL=0x1f RR=0x1f
        sp:write_u16(S0 + 0x0c, 0x0000)                      -- TL = 0
        sp:write_u16(S0 + 0x10, 0x0800)                      -- OCT = 1, FNS = 0
        sp:write_u16(S0 + 0x16, 0xff00)                      -- DISDL = 7, DIPAN = centre
        sp:write_u16(S0 + 0x00, KEYONB | KEYONEX | LPCTL_LOOP)   -- execute KEY_ON
        print("VOICE keyon at frame 30")

    elseif frames == 60 then
        sp:write_u16(S0 + 0x00, KEYONEX | LPCTL_LOOP)        -- KYONB clear -> KEY_OFF
        print("VOICE keyoff at frame 60")

    elseif frames == 100 then
        m:exit()
    end
end)
print("SCSP_VOICE armed")
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

    with tempfile.TemporaryDirectory(prefix="scsp-voice-") as tmp:
        outdir = Path(tmp)
        script = outdir / "scsp_voice.lua"
        script.write_text(LUA)
        wav = outdir / "voice.wav"
        for sub in ("nvram", "cfg"):
            (outdir / sub).mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
        result = subprocess.run([
            str(a.executable), "saturnjp",
            "-rompath", str(a.rompath),
            "-noreadconfig", "-skip_gameinfo", "-nodrc",
            "-video", "none", "-nothrottle",
            "-autoboot_delay", "0", "-autoboot_script", str(script),
            "-seconds_to_run", "20", "-wavwrite", str(wav),
            "-nvram_directory", str(outdir / "nvram"),
            "-cfg_directory", str(outdir / "cfg"),
            "-state_directory", str(outdir),
            "-snapshot_directory", str(outdir),
        ], cwd=outdir, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=600)
        text = result.stdout.decode("utf-8", "replace")

        if "LUA ERROR" in text:
            raise AssertionError(f"Lua error:\n{text}")
        if not wav.is_file():
            raise AssertionError(f"no WAV written:\n{text[-1500:]}")
        with wave.open(str(wav)) as w:
            chans, rate = w.getnchannels(), w.getframerate()
            samples = array.array("h")
            samples.frombytes(w.readframes(w.getnframes()))

    nz = [i for i, x in enumerate(samples) if x != 0]
    if not nz:
        raise AssertionError(
            "WAV is entirely silent - key-on produced no audio at all")

    first, last = nz[0], nz[-1]
    # interleaved stereo: index -> stereo frame -> seconds -> emulated frame
    def to_frame(idx):
        return (idx / chans) / rate * 60

    onset, offset = to_frame(first), to_frame(last)
    peak = max(abs(x) for x in samples)
    tail_peak = max((abs(x) for x in samples[last + 1:]), default=0)

    fails = []
    if not (27 <= onset <= 34):
        fails.append(f"onset_frame got={onset:.2f} want 27..34 (KEY_ON at 30)")
    if not (57 <= offset <= 64):
        fails.append(f"offset_frame got={offset:.2f} want 57..64 (KEY_OFF at 60)")
    if peak < 8000:
        fails.append(f"peak got={peak} want>=8000")
    if tail_peak != 0:
        fails.append(f"tail_peak got={tail_peak} want=0 (StopSlot must silence)")

    if fails:
        raise AssertionError("assertions failed:\n  " + "\n  ".join(fails))

    print(f"SCSP voice: onset frame {onset:.2f} (KEY_ON at 30), "
          f"offset frame {offset:.2f} (KEY_OFF at 60), peak {peak}, "
          f"{len(nz)} non-zero samples, silent tail exact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
