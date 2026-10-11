# Full-state startup determinism

The startup discrepancy was actual uninitialized saved storage. It was not removed from the comparison.

The previously unnamed byte belongs to `Sega315-5338A I/O Controller/:billboard:io/0/m_cmd`. The device constructor now initializes its command byte to zero. Old Die Hard captures contained 122 versus 123; old Virtua Fighter Kids captures contained 78 versus 124 at frame 60. Those bytes were heap contents, not a legitimate game-state difference.

The VDP2 horizontal and vertical counter latches have explicit cold-construction values of zero, in addition to their reset initialization. Other saved VDP2 control, status and display fields have explicit cold defaults as well. Existing dormant SCU DMA storage remains value-initialized. This does not introduce a new command reset on a soft reset of the I/O controller.

Lua previously split registered names at the first slash. The module description `I/O Controller` contains a slash, hiding this device's saved fields from `device.items`. The lookup now matches the complete device-tag component. `emu.item(index).name` additionally exposes the complete registered name directly. Its userdata object is explicitly constructed before assigning the string. The capture script records these canonical names, including all previously unnamed storage.

## Verification

`scripts/saturn_state_items_test.lua` checks the command byte and both VDP2 latches at startup, resolves their indices through `device.items`, checks canonical names, and retains a userdata object through 10,000 temporary item constructions and full garbage collection. Both SH-2 cores pass with macOS heap pre-scribbling enabled.

`scripts/saturn_startup_state_test.py` runs Die Hard Arcade, Virtua Fighter Kids and PAL Virtua Fighter 2 with both SH-2 cores. Each pair uses independently rebuilt executables, identical per-game NVRAM seeds, separate writable directories, fixed RTC `20000101000000`, and different `MallocPreScribble` settings. Each run captures frames 1, 60, 300, 600, 1200 and 1800. Video presentation and audio output are disabled, but emulated rendering and captured pixels remain enabled.

The comparison checks the entire save file, including its header and compressed payload, and captured pixels. No differing bytes are masked, normalized or excluded. Named field diagnostics are only used to explain failures. This verifies startup parity for the tested configuration and current implementation, not equality between arbitrarily different implementations or accuracy against physical Saturn hardware.

All 36 final comparisons passed: complete save files and captured pixels were identical at every tested frame. Both item-lifetime checks also passed.

Final test artifacts: `/private/tmp/saturn-startup-final-parity-20261010/comparison.json`. Independently rebuilt executables and item-lifetime logs: `/private/tmp/saturn-startup-final-builds-20261010`.
