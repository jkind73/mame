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
