# Native-qualified arithmetic source ea9a7a7c

Source ea9a7a7cb334675e85114d245df67f2d27bf5001, successful build35363539017,
export35364567357, full expanded native consumer exit0. Binary SHA256:
0a3c6e7a1fd2f0df9051c783c57fd3ebab6c69d74e398a1963ff49200b8756a7.
Before/after provenance and BIOS checks passed. Full61-script local/CI passes.

844 arithmetic programs pass in JP/interpreter, JP/DRC, PAL/DRC, ST-V/DRC;
includes eight multiplier-built48-bit overflow boundary programs per configuration.
Actual file save/mutate/load restores full48-bit ALU and latched/read-cleared V
(JP/interpreter), without private device-state writes or polling away overflow.
All prior count-source128, count96, pipeline48, DMA128, PRAM128, read4096,
real256-word data/program and pending-slot saves, plus the complete earlier
integration and four BIOS/background gates pass. Raw DSP output retained below.

No working flags promoted, commercial gameplay acceptance or complete DSP parent
claimed. Reference caveats remain in ../dsp-alu/README.md; OR workaround unchanged.
