# Saturn / ST-V peripheral and communication configuration inventory

Scope: **IO-02 / STV-05 / EXP-02**, base configuration inventory at `3d18666d`, SCI update at `20c1e822` on
`arena/01a0b897-mame`. This lists implementation/configuration availability,
not hardware or game acceptance. It does not change the completion report's
status labels. An emulated SCI engine alone is not an emulated modem or cable.

## Present and selectable/configured (acceptance remains separate)

| Device or family | Current configuration support | Source basis |
|---|---|---|
| Saturn digital pad | `joypad`, default on both console control ports | `src/devices/bus/sat_ctrl/ctrl.cpp:123-136`; `src/mame/sega/sat_console.cpp:1186-1191` |
| Racing wheel, analog pad, mission stick | `racing`, `analog`, `mission` control-port options | `ctrl.cpp:125-127`; implementation files `racing.cpp`, `analog.cpp`, `mission.cpp` in the same directory |
| Lightgun, trackball, keyboard, mouse | `lightgun`, `trackball`, `keyboard`, `mouse` options; console lightgun latch callbacks are wired | `ctrl.cpp:128-133`; `sat_console.cpp:1186-1191` |
| Mega Drive pad adapters | `joy_md3`, `joy_md6` options | `ctrl.cpp:131-132`; `joy_md.cpp` |
| Multitap / Sega Tap | `multitap`, `segatap` options; subordinate ports restricted to the `saturn_joys` list (`joypad`) | `ctrl.cpp:134-140`; `multitap.cpp:39-43`, corresponding `segatap.cpp` configuration |
| ROM / DRAM / backup-RAM cartridges | Internal cartridge options `rom`, `ram8`, `ram32`, `bram4`, `bram8`, `bram16`, `bram32`; not modem emulation | `sat_console.cpp:1194-1202`; `src/devices/bus/saturn/{sat_slot,rom,dram,bram}.cpp` |
| ST-V base cabinet I/O | 315-5649 device, coin/lockout callbacks, analog and counter inputs; legacy overrides still exist for some cabinet configurations | `src/mame/sega/stv.cpp:135-290,1351-1375`; `315_5649.cpp` |
| ST-V hopper | Hopper device and PORT-D motor override exist in the `hopper` configuration | `stv.cpp:286-290,1514-1520` |
| ST-V Batman Forever sound board | `ACCLAIM_RAX` device and sound communications handler exist; do not classify every auxiliary board as absent | `stv.cpp:1469-1489` |

“Present” does not imply all advertised accessory variants, all SMPC transport
modes, exact pin timing, or successful runtime acceptance. This turn does not
reassess previously accepted controller, sound or game work.

## Partial interfaces, not complete external-device support

| Interface | Implemented candidate scope | Missing or unresolved |
|---|---|---|
| SH7604 SCI | Internal-clock async TX/RX callbacks and register/IRQ logic (IMPL-0007 through IMPL-0011), external 16x-clock async RX/TX (IMPL-0016/0017); external SCK synchronous RX/TX/full duplex candidates (IMPL-0013/0014), plus internal synchronous SCK output/pacing (IMPL-0015) and asynchronous baud-rate SCK output (IMPL-0018); SCI module-stop initialization/release (IMPL-0019) | No Saturn/ST-V machine-config binding of `txd_wr_callback` / `rxd_rd_callback` in `sat_console.cpp` or `stv.cpp`; no cable drives the new `sck_w` input. SCI-specific DMA request/ack routing remains absent. Async SCK output is 1x baud, not the 16x clock required by async external input. The new `sck_wr_callback` also has no configured peer. Physical sampling/status-edge phase, SCK high impedance, whole-chip standby, and native IRQ/save behavior remain open. |
| SH7604 FRT external clock | `ftci_w` rising-edge counter/compare API (IMPL-0025, `3fbbe2fe`) | No configured Saturn/ST-V FTCI source or external peripheral added; FTI capture is a separate input. Physical synchronization/pulse-width margins, FTO pin outputs and native IRQ/save qualification remain open. |
| ST-V 315-5649 RS-422 | Two byte-level channels, occupancy and loopback candidate IMPL-0001 | No timed wire/peer model, error-generation model, satellite protocol or external connection save/disconnect policy. `magzun` binds both receive callbacks to return zero (`stv.cpp:1428-1435`), not to an emulated microphone board. |
| Optional MPEG/Video CD path | HLE command/state handling exists | No configured board-level decode/composition acceptance. `src/mame/sega/saturn_cd_hle.cpp:2346+` is HLE, not evidence of a complete Movie Card. Tracked under EXP-01 / V2-H04, not a communication-device substitute. |

## Not supported as complete configurations in this checkout

| Requested hardware family | Configuration gap and evidence boundary | Next artifact needed |
|---|---|---|
| Saturn NetLink / regional modem variants | No modem option in the complete console cartridge/control-port option lists above, and no SCI peer binding in the console configuration. This is a source/configuration observation, not an assertion that every modem uses the SCI connector. | Exact variant/board identity, mapped interface specification or firmware/trace; establish which bus it actually uses before designing delegation. |
| Saturn serial/link cable and RS-232 adapter | CPU pin callbacks exist but no cable/transceiver/peer is configured. A host TCP connection is not a substitute for the hardware interface contract. | Connector pinout, master/slave clock contract, level conversion and peer protocol evidence for the chosen accessory. |
| ST-V CN18 linked cabinets / medal satellite peers | Byte interface only; no complete satellite peer in the reviewed configurations. Existing historical service-mode errors are not fresh diagnoses. | Peer controller identity/firmware and captured commands, timing and error/reconnect behavior. |
| ST-V external `i486BD` lead | `stv.cpp:4640` identifies a test-mode connection, not an implemented board. | Board model, firmware and interface map. |
| ST-V LAN/COM20020 lead | `stv.cpp:6525` names hardware; terminal game declarations retain `MACHINE_NODEVICE_LAN` (`:6909-6912`). No acceptance inferred from the comment alone. | Full auxiliary-board configuration, firmware and link protocol/trace. |

## Maintenance rule

Promote a row only when the matching production device, machine configuration
and protocol exist; record implementation commits and separate validator
acceptance evidence. Unknown accessories are **not inventoried**, rather than
silently grouped as unsupported. Host-backed external connections will also
need an explicit deterministic save/disconnect policy under EXP-02.
