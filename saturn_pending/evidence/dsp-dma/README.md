# DSP-02 / DSP-03 implementation checkpoint

Primary: Sega ST-097-R5-072694, printed pp.134/136/138/140 (PDF pp.150/152/154/156),
SCU manual blob `ffa8932249634ebd98947dad123621cebe3f24fa` in SDK commit
`0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73`. All eight B-bus additions apply after
each 16-bit beat, not each 32-bit source word, for immediate and RAM-sourced counts.
Ymir `6d779960127ced72087a418c1daefc637d0aaa80`,
`libs/ymir-core/src/ymir/hw/scu/scu_dsp.cpp` RunDMA independently corroborates
high/low halfword writes with an increment between them. No Ymir code imported.

Production separates the second-halfword stride from per-word advancement,
retains A/C-bus behavior, and does not mistake A-bus CS2 for B-bus. Remaining
A/C quirks, read increments, zero-count semantics, address updates at completion,
program-RAM DMA, bus arbitration and DSP stalls are not claimed complete.

Registered all DMA fields used by the timer state machine, including its state;
reset cancels its timer, T0/ex state and private HALT. The enum state storage uses
uint8_t to meet MAME save-manager type requirements (full-TU syntax checked).
The emulation framework owns timer/CPU suspension state, and SCU owns its saved
DDWT/DDMV status. m_update_mul is an intra-instruction temporary, not pending DMA.

Extracted actual methods pass ASan/UBSan: 768 bank/mode/hold/count-form/count
combinations, five state-replay cut points each, reset checks, read-direction
and A/CS2/C isolation. Five compiled mutants fail assertions: fixed second-beat
address, RAM-count stride, missing saved state, missing saved progress, missing
HALT cleanup. These are not real MAME save-manager tests or bus-cycle measurements.

The real 79f36021 binary is the before-fix negative: all 32 mapped DSP programs
execute and complete; only four add-one cases pass. Others write wrong B-bus
halfwords. The fixture uses SCU host ports and VDP1 RAM, not private DSP state.
Native positive for the new source is pending. Twelve parser controls pass.

A second genuine native negative now covers actual scheduled save/load during a
60,000-word DSP DMA: before save, T0/EX are busy and the unwritten tail is checked;
after completing, a read-direction HOLD transfer poisons the descriptor, then
file load restores the busy snapshot. All save/mutate/load notifications occur,
but 59,979 destination words remain wrong on 79f36021 because the pending DMA
state/progress was not restored. No private DSP fields are edited. The new
source must pass this gate as well; extracted state-copy tests are insufficient.
Thirteen DSP save parser controls and the shared runner's seventeen file/output
controls pass. The native-save negative is `79f36021-save-negative.log`.
