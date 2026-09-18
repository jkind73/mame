# Native-qualified parallel-bus source2e14f275

Source2e14f275f08dd192dcff621264d5b47fbfa0db41, build35369703506,
export35370407444; binary SHA256
a70a4c1663ec5c6366ce157172dfc57d8bbfa4b94d06fd42080f8aa9296f0223.
Full64-script local/CI batches pass (three optional scripts skip locally, then
run live in the consumer). Complete native consumer exit0; before/after source/
binary provenance and BIOS hash checks pass.

576 parallel RAM/register/counter programs pass across JP/interpreter, JP/DRC,
PAL/DRC and ST-V/DRC. Actual active parallel-copy file replay restores the64-word
output image and multiplier result after source/output RAM, CT/LOP, input/product
registers and program mutation. Phase observation uses legal PPAF-only reads.
All preceding loop/multiplier/arithmetic/count/DMA/program/slot/device/save and
four BIOS/background gates also pass. Raw DSP output retained.

Native pass means the selected implementation contract passes, NOT that all
undocumented collision behavior is hardware-qualified. The X/D1 register-priority
and immediate-collision CT-bit disagreements remain open in ../dsp-parallel/README.md.
No working flags promoted or complete DSP/gameplay acceptance inferred.
