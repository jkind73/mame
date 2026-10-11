# SH7604 FRT clocks, outputs and timer repairs

Implemented 2026-10-09 against the local SH7604 hardware manual, fourth
edition, September 2001: chapter 11 (printed pp. 295–318), especially 11.2.2,
11.2.6/7, 11.4.1–7 and 11.7. The assignment includes the related defects
found while implementing external-clock counting and output-compare pins.

`frt_clock_w` supplies FTCI; rising edges count once in external-clock mode.
Falling edges, repeated levels and transitions while clocks are stopped do not
count. Physical input levels survive reset/save/load and are tracked while
stopped, preventing a fabricated edge on restart. The manual requires external
clock pulse widths of at least six system clocks; timed tests use valid pulses.
FTI remains an independent capture input with TCR-selected edge polarity.

`frt_output_a_handler` and `frt_output_b_handler` expose FTOA/FTOB. Compare
matches drive the selected OLVLA/B level; merely writing TOCR does not change
the pin. Pins initialize to zero and redrive their saved levels after load.
Compare flags, pin changes and clear-on-A continue functioning after a match
flag has already been set. Simultaneous A/B matches, unreachable B compares
under clear-on-A, wrapping and overflow are handled together. Section 11.4.6
places the match signal on the clock leaving the matching count; the old code
signalled a count early. Clear-on-A takes precedence over overflow.

Internal f/8, f/32 and f/128 counting retains fractional prescaler phase across
reads and writes. DRC pending instruction cycles are included during execution;
a stale pending value is excluded during host/timer callbacks. A high-to-low
selected-clock switch produces the extra count described by table 11.4.
Module restart and standby wake restart from the initialized timer phase.
Active clock changes reschedule compare events and preserve capture delay in
clock units; CKIO pause freezes events and resumes the remaining delay.

Counter state advances through every clock, including recurring clear-on-A
cycles when flags/pins already hold their target values. Timer callbacks wake
for observable flag/pin changes. A zero OCRA with clear enabled therefore
holds FRC at zero without an event storm, while a later OLVL change still
produces its next compare output. The event-jump calculation is checked against
a per-clock reference over 1,000 randomized cases.

The CPU transaction collision rules in 11.7 are implemented: lower OCR writes
suppress their concurrent compare, FRC writes defeat increment, and compare-A
clear defeats an FRC write. An upper FICR read overlapping input capture defers
capture by one f/4 drive clock, preserving the shared TEMP read sequence.
Reset/module stop cancels deferred capture. Debugger reads do not arm qualified
clears, alter TEMP or invoke the FTCSR status observer.

Both power-on and manual reset now initialize OCRA/B to FFFF, as specified by
11.2.2; the old final reset assignments incorrectly overwrote them with zero.
FRT registers and output levels initialize for standby/module stop. GPIO input
levels remain physical pin state. A reset during an output callback cannot
leak a stale second output from the canceled compare event.

A related interrupt defect was exposed by the real-device test: debugger SR
changes could accept an interrupt inside an interpreter branch delay slot or
create an unstacked DRC exception. SR edits now request normal boundary testing
for both execution cores. Compare IRQ enable, mask, priority, vector and stack
behavior are verified through actual guest execution.

## Verification

```sh
python3 scripts/sh7604_frt_test.py
python3 scripts/sh7604_register_test.py
python3 scripts/sh7604_sci_standby_test.py
python3 scripts/sh7604_ubc_test.py
python3 scripts/sh7604_device_test.py --binary ./saturn \
    --output /private/tmp/sh7604-new-run --dma
python3 scripts/sh7604_device_test.py --binary ./saturn \
    --output /private/tmp/sh7604-new-ideal-run --only frt --ideal-bus
```

Output directories must be new. The sanitizer fixtures compile actual production
methods with ASan/UBSan. The real-device harness generates diagnostic ROMs,
injects controlled register/program state, and runs one emulator at a time at
low priority with isolated configuration, NVRAM, diff and save directories.
Both DRC and interpreter are tested. FRT cases cover actual pin levels, flags,
external and internal saved phase/deadlines, module-stop/capture cancellation,
zero-period clears, continuous guest FRC polling, reset values and compare IRQ
stacking. The earlier SCI, UBC, DMA, reset and standby regressions also run.

The macOS build includes Saturn and ST-V:

```sh
make SUBTARGET=saturn SOURCES=src/mame/sega/sat_console.cpp,src/mame/sega/stv.cpp \
    OSD=sdl3 USE_LIBSDL=0 -j2
```

Final validation: macOS Saturn/ST-V SDL3 build passes; all four actual-method
ASan/UBSan fixtures pass; all 28 full-suite cases pass (14 per core), plus both
FRT and both UBC cases with bus wait timing disabled. Logs and isolated state
files are in `/private/tmp/sh7604-frt-final-suite`,
`/private/tmp/sh7604-frt-ideal-final` and
`/private/tmp/sh7604-frt-ubc-ideal-final`.
Checklist/source inventory consistency and whitespace checks pass.
Only the original FRT completion marker changed; its wording is unchanged.
