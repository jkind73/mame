# WIP recovery checkpoint — 2026-09-17

This preserves the source state found after the local checkout returned to
868d72fc and the external recovery directory/background jobs disappeared.
It is **not** a reviewed implementation merge or a validation result.
The checkpoint commit leaves the remote production tree unchanged.

- `tracked-workspace.patch`: all tracked differences against the exact base
  recorded in manifest.json, including unrelated changes. Do not apply blindly.
- `untracked-source.tar.gz`: selected untracked source, tests and documents.
  Extract only into an isolated recovery directory and review against the base.
- `manifest.json`: source inventory, exclusions and artifact SHA-256 hashes.

ROMs, SDK/cache/build downloads, screenshots and runtime logs are not added here.
Previously reported tests and candidate corrections cannot be reconstructed from
this archive unless their corresponding files are present; lost external logs
are not fresh validation evidence. Restart the baseline build and verify inputs.

Pending reviewed findings from the preceding work: the supplied IOGA loopback
patch must clear m_serial_rx_valid on device_reset; otherwise stale local data
survives reset. Proposed CD/cart runtime runners must reject nonzero exit codes,
FAIL/Lua-error output and malformed PASS markers, not accept substring matches.
The isolated corrections/tests were executed previously, but their external
candidate files and logs are absent in this workspace and must be recreated.
No Agent1 working-status promotion or generic forced-retry change is approved.

Checkpoint policy: push small explicitly labelled WIP commits before long builds
and after coherent edits; record completed/pending/failed tests accurately.
Resume implementation after checkpoints rather than using them as stopping points.
