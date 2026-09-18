# Counter build recovery: no-PCH controller include order

Build35347062472 failed, not accepted. Authenticated diagnostic run35352768461
verified its artifact ZIP digest/source and surfaced the first compiler errors.
The sandbox could not access the Actions/Azure log download hosts directly.

analog.cpp included analog.h before emu.h, reaching screen.h/divo.h without core
emulator definitions. Local full-TU compilation reproduced the exact error.
ctrl.cpp, racing.cpp, gun.cpp and mission.cpp had the same inverted include order.
All five now include emu.h first and pass full-TU C++20 syntax without a PCH.
A ROM-free regression compiles these five files rather than merely scanning text.
The DSP counter implementation is unchanged; all existing DSP suites still pass.

Failure annotations now preserve the first errors with context instead of a
possibly unrelated final25-line tail. The original failed build recorded392/594
cache hits,202 misses,4 uncacheable calls and about0.03GB cache. These partial-build
statistics are not a completed-build speedup measurement or native acceptance.
The no-PCH build experiment remains enabled; successful rebuild and full native
counter/save qualification are still required. Latest accepted binary: cd074b71.

The complete repaired local batch passed59 scripts (exit0), including the five
no-PCH translation units; three optional live skips are excluded. The SDK/runtime
dependencies have been restored outside Git. CI35352902888 remains in progress.

Repair35352902888 passed the controller compilation but failed at scspdsp.cpp,
which likewise included scspdsp.h before emu.h. The broader comment-stripped
source audit found no other local quoted header preceding emu.h in the device,
emulation, driver and front-end trees after this repair. OSD modules do have
earlier local headers; their separate interfaces were left unchanged, and this
audit is not a no-PCH compilation result for them. Standard-library includes
before emu.h are not changed.
The regression now compiles all six controller/sound-DSP units without PCH; all
six pass. This failure still does not qualify the counter binary. Further rebuild
and native qualification are required; no emulator arithmetic behavior changed.


Successful recovery: f1a65715 passed build35354598861 and its59-script CI batch.
The fresh full local59-script batch also exited0 (three optional live skips
excluded); see `complete-regressions.log`. Native consumption is pending.
