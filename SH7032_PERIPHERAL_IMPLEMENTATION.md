# Saturn SH-1 peripheral implementation

The selected scope is Saturn's SH7032 CD-block processor. The former register-array placeholder in `src/devices/cpu/sh/sh7032.cpp` is replaced by executing peripheral state machines. The SH7014-only CMT, MTU, port D and synchronous-transmit hack mentioned in the unchanged checklist wording do not belong to Saturn's processor. Their SH-1 counterparts are implemented here.

## Implemented behavior

- Four-channel DMAC: all priority modes; byte/word transfers; fixed/increment/decrement addressing; zero count as 65536; level/edge external DREQ; physical DACK polarity and phase; single-address device callbacks; dual-address read/write phases; internal SCI/ITU/ADC requests and acknowledgment; completion and address-error interrupts; WAIT holds; burst/cycle-steal CPU ownership. Transfers commit at their bus phase boundaries, rather than copying the whole count immediately.
- Five-channel ITU: internal prescalers, external clock edges, compare outputs, capture and buffers, synchronized counting/clearing/preset, normal PWM, phase counting, reset-synchronized PWM and complementary PWM with dead-time counter sequencing. TPC implements grouped timer triggers and non-overlap pattern updates.
- Two SCI channels: timed asynchronous and synchronous pin transmission/reception, external clock input, baud selection, data/parity/stop formats, receive errors and overrun, multiprocessor filtering, queued transmit data, interrupts and DMA requests. No instantaneous full-byte synchronous transmission.
- Eight-input ADC: conversion and sample intervals, scan groups, external ADTRG edge, left-aligned results and temporary read latch, flag acknowledgment, interrupt and DMA request.
- Watchdog: keyed writes, interval interrupt, watchdog overflow output pulse, selectable reset vectors, reset-state differences and overflow flag retention.
- Sleep/software standby: interrupt qualification, continued peripheral operation during sleep, module reset and retained I/O during standby, high-impedance outputs, NMI settling and wake. Serial pad state is retained independently of the reset serial engine.
- Ports A/B and input-only C: data/direction and PFC selection, SCI/ITU/DMA/IRQ/clock/ADC routing and output masks. External IRQ priority and level/edge behavior are implemented.
- Correct 28-bit address mask, peripheral aliases, and 8 KiB internal RAM. State machines, pending bus transactions, pin levels and cold-start storage are initialized and saved.

## Validation

`tests/saturn/sh7032_device.cpp` creates an enabled real SH7032 at the same 16 MHz currently configured for the Saturn CD block. `scripts/sh7032_device_test.py` builds this isolated diagnostic target and runs `scripts/sh7032_device_test.lua` with both DRC and interpreter cores. The temporary driver registration is restored after building.

Both cores pass the functional suite, including all DMA priorities, WAIT/DACK hold and restore, zero-count burst ownership, real guest interrupt handlers, both watchdog reset types, standby settling, serial pin loopback and errors, ADC scan/trigger/restore, external timer capture/counting, all PWM families, quadrature and TPC. Every registered SH7032 saved field is compared byte-for-byte after an in-flight DMA restore; no CPU fields or bytes are excluded. The DMA then completes exactly once. Whole-machine buffer reloads also change Lua resume-timer and scheduler queue metadata, so the diagnostic does not claim whole-buffer reload identity.

The SH7032 and diagnostic-driver objects were instrumented with ASan/UBSan, with generated compiler flags and the linked ASan runtime confirmed. Both cores pass without sanitizer errors. Supporting MAME libraries were reused; this is not a claim that every MAME object was instrumented. Logs: `/private/tmp/sh7032-sanitized-confirmed-20261010`.

The normal Saturn target builds with SDL3. Saturn JP and Die Hard driver validation pass. Independent normal rebuilds were compared at frames 1, 60, 300, 600, 1200 and 1800, with different heap fills. VF2 (Saturn CD) and VF Kids (ST-V cartridge) match complete saves and pixels on both CPU cores. Die Hard (ST-V cartridge) matches on the interpreter; its DRC repeat with host input providers disabled also matches all six captures. The initial DRC run had three differing game-RAM bytes at frames 60/300; the isolated repeat passed, so that initial run is not represented as a passing full suite. No bytes were masked. Logs: `/private/tmp/sh7032-corrected-parity-20261010` and `/private/tmp/sh7032-input-isolated-parity-20261010`.

This regression exposed two previously uninitialized SCU timer registers (`m_t0c`, `m_t1s`), now cold-initialized to zero. Their game-written contents and soft-reset behavior are otherwise unchanged. The comparison script now disables live keyboard/mouse/joystick/lightgun providers to keep host input out of deterministic captures.

## Evidence and limits

The implementation follows the Renesas SH7032/SH7034 manual, particularly DMA, ITU/TPC, watchdog, SCI, ADC, power and ports. Local MiSTer and Ymir implementations were secondary comparisons; their code was not copied.

The local `satcdb.zip` firmware `cdb106.bin` is exactly 65536 bytes, CRC32 `3681d3b0`, SHA-1 `b3c20fbe57cd2eb595e9edac86817e5948dccae4`, matching the supplied identification.

No real hardware verification validates this implementation. The diagnostic exercises the actual CPU device with controlled peripheral inputs, not the complete CD firmware board. The existing Saturn CDB CPU remains disabled: CD ASIC wiring and activating firmware-driven CD emulation are separate existing work. This change does not establish that the firmware boots or replaces the HLE CD block.

The BSC provides DMA bus costs and WAIT qualification, rather than a complete electrical bus-strobe or DRAM page-timing simulation. UBC comparisons, general CPU external-memory wait accounting and register-access collision timing are not claimed by this peripheral implementation. No hardware-calibrated timing claim is made.

Reference: https://www.renesas.com/en/document/mah/sh7032-sh7034-hardware-manual (REJ09B0272-0700).
