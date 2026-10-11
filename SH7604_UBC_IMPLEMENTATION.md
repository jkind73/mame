# SH7604 user-break controller implementation

Implemented against the local SH7604 hardware manual, fourth edition,
September 2001: chapter 6 (printed pp. 107–127), interrupt priority/vector
rules in chapter 5, reset retention in 4.2.3 and standby rules in chapter 14.
The original eleven missing register mappings now have functioning comparisons
and user-break exceptions behind them.

All fifteen named halfwords are mapped at FFFFFF40–48 and FFFFFF60–78.
Address/data pairs support big-endian longword accesses. BBRA/BBRB mask to
00FF, BRCR to F4DC; reserved holes read zero. Prohibited byte writes and DMAC
accesses cannot alter UBC registers. Power-on reset initializes registers;
manual reset and standby retain them. Transient instruction inhibition resets
with the CPU.

CPU instruction fetches and data accesses, including cache hits and exception
stack/vector accesses, feed the comparator. Both on-chip DMA channels feed
source reads and destination writes for byte, word, longword and burst modes.
Channel B data comparison applies byte duplication, word/longword width and
BDMRB masking. Address comparison applies BAMRA/B and the SH7604 operand
alignment rule. Read/write, instruction/data, CPU/peripheral and operand-size
qualifiers are all enforced.

Independent and sequential A→B matching use distinct bus events: simultaneous
A/B matches cannot satisfy a sequence. CPU/peripheral match flags are sticky
until written clear. SH7000-compatible mode uses channel A only, exact address
comparison, no match flags, and compares overrun-fetched instructions. SH7604
mode compares instructions actually executed, before or after as selected.
Changed settings become active after three CPU clocks; a side-effecting dummy
register read synchronizes them. The second instruction in an already fetched
longword retains its captured comparison settings. Debugger reads do not
synchronize settings.

User-break requests use fixed priority 15 and vector 12, ahead of IRL15 and
below NMI. Masked requests remain pending. Breaks defer across delayed branches
and LDC inhibition, with the saved PC pointing to the correct next instruction.
The shared interpreter supplies precise instruction boundaries while UBC is
armed, including immediate handoff from an existing compiled block when guest
code enables it. Pending interpreter delay slots finish before execution returns
to compiled code. Normal unarmed execution retains DRC. A debugger SR edit
queues interrupt testing rather than creating an unstacked DRC exception.

External bus input is exposed by `ubc_external_cycle`. EBBE and peripheral/data
qualifiers apply; operand size/data are ignored and addresses use A26–A0.
Saturn/ST-V connect peer SH-2 external cycles, including cache fills, and SCU
C-Bus DMA/DSP/indirect-descriptor cycles. Bus observation is independent of the
optional bus wait timing. Full standby stops comparisons and prevents UBC wake.

Registers, effective comparison settings, fetched-pair settings, activation
time, sequence state, pending request and instruction inhibition are saved.
The real-device test restores both an armed sequence and a masked request.

## Verification

```sh
python3 scripts/sh7604_ubc_test.py
python3 scripts/sh7604_register_test.py
python3 scripts/sh7604_sci_standby_test.py
python3 scripts/sh7604_device_test.py --binary ./saturn \
    --output /private/tmp/sh7604-new-run --dma
python3 scripts/sh7604_device_test.py --binary ./saturn \
    --output /private/tmp/sh7604-new-ideal-run --only ubc --ideal-bus
```

Output directories must be new. The real-device harness uses its own diagnostic
ROMs, runs one emulator at a time at low priority, and isolates configuration,
NVRAM, diff and save files. It tests both DRC selection and interpreter selection.
The UBC fixture compiles actual production methods with ASan/UBSan; the Lua test
checks actual guest register effects, exception stacks, DMA data and external
bus events. The build includes both Saturn and ST-V:

```sh
make SUBTARGET=saturn SOURCES=src/mame/sega/sat_console.cpp,src/mame/sega/stv.cpp \
    OSD=sdl3 USE_LIBSDL=0 -j2
```

Final validation, 2026-10-09: macOS Saturn/ST-V SDL3 build passes; all three
actual-method sanitizer fixtures pass; all 26 full-suite cases pass (13 per core),
plus both UBC cases with bus wait timing disabled. Full-suite logs are in
`/private/tmp/sh7604-ubc-final-v3`; ideal-bus logs are in
`/private/tmp/sh7604-ubc-ideal-final`. Inventory/checklist consistency and
whitespace checks pass. The UBC checklist item's wording is unchanged;
only its completion marker was changed.
