# Native-qualified multiplier source25f13c07

Source25f13c07f3e750e88d852c083acf9769fa352d2d, build35365374912,
export35366355244; binary SHA256
abbff49ba52a4f0e232ab2a3499c24deb484ce657ed35d6f81b7e55612f9aa34.
Full62-script local/CI batches and complete corrected native consumer pass.
Both provenance checks and BIOS hashes pass. All256 multiplier programs/four
configurations,844 arithmetic programs, true48-bit ALU/latched-V file replay,
and every preceding counter/loader/save/device/BIOS gate pass. Raw DSP logs here.

The first attempt correctly failed an ordinary-fixture/save-runner binding
mistake; no source change or bypass was used. Fixed runner binding, added a
contract control, reran the entire consumer from provenance through final checks.

Parallel X/D1 RX priority controls preserve existing MAME/Beetle behavior, which
differs from Ymir; not hardware-priority proof. Exact timing and complete DSP
remain open. No working flags promoted or commercial-game acceptance inferred.
