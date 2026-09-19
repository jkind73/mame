# Timeout/edge-history source regression evidence — 2781f96b

The complete 55-script local regression batch passed. Three optional live
runners skipped because their default `./saturn` executable is absent; the
verified historical binaries are deliberately kept elsewhere. These skips do
not qualify the new source. Native CI 35299792272 is building this revision.

Focused checks also passed: SMPC/driver full translation-unit C++20 syntax,
73,728 timeout state combinations, four edge/order checks, 5,402 transport
cases, 1,175 handshake cases, and existing sync tests. Eight timeout mutants
compiled and assertion-failed. Recording endpoint/source-registration tests
are not native save-manager evidence.

The genuine linked negative timeout and H/V edge save-load logs are preserved
under ../234c-live/. Their positive counterparts require this new binary.
