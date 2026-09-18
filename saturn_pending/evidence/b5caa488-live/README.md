# Native b5caa488 DSP DMA qualification

CI 35306849889, binary SHA256
5d5f978c7938a0553c21009885f5a995f0fbd5e73604d3d594c7d5205d88b8f2.
The complete native consumer exited zero, with before/after input-tree and binary
verification. It includes 32 actual DSP B-bus programs and actual scheduled
save/mutate/load during a 60,000-word transfer. The entire memory image replays
exactly; earlier 79f36021 left 59,979 words wrong after loading.

Additional DRC runs each pass all 32 DMA addressing programs: Saturn JP, Saturn
PAL and ST-V BIOS. Together with JP/interpreter in the full consumer, this is
128 addressing cases in four machine/engine configurations. Per-run JSON records
binary/BIOS/Lua hashes and the selected machine/engine. This is shared-device
program execution, not commercial-gameplay or cycle-accurate bus qualification.

A separate b5caa488 ST-V/DRC run reproduces the five wrapped-control-flow faults,
just like JP/interpreter. That negative is in ../dsp-pipeline/. The pipeline fix
is integrated in 89764c08 and awaits its own native rebuild. The current consumer
now additionally requires pipeline positives and this four-configuration DSP
matrix; it must not be used to retroactively claim b5 passes the new pipeline gate.
