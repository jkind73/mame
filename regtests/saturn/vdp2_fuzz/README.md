# VDP2 register-mutation differential (MAME vs Ymir)

Starting from a captured VDP2 state (`video_capture.lua`: VRAM, CRAM, registers), random register words are mutated
(1-3 registers, bit flips or random values, sprite priorities forced to 0 so VDP1 state does not matter). The same state is
rendered by Ymir (`vd2fuzz.cpp`, needs ymir-core) and by MAME (`vd2fuzz.lua`, CPUs parked, state written through the bus).

* `vd2tools.py gen <cap> <n> <seed> <mutfile>` - mutation list (first line is the unmutated baseline)
* `vd2run.ps1` - generate + run both + compare for a list of captures
* `vd2iso.ps1 -c <cap> -cases "<idx=val idx=val;...>"` - re-run each register of the given mutations alone
* `img.py <case> <prefix>` - side by side Ymir / MAME / difference image

Register words are indexed by word (byte offset / 2). Captures with mid-frame register changes (racing games) do not
reproduce a baseline and are excluded.
