# SND-04 signed DSP address displacement — native WIP

ADREB must sign-extend ADRS_REG's twelve bits before the existing ring/TABLE
mask and RBP addition. Production changes only that addition. No GPL code copied.

Read-only independent implementation references:
- MiSTer Saturn a95b085038ace57fa621558d60a7adc7a3c53f78,
  rtl/Saturn/SCSP/SCSP.sv blob402dcb6eedca98547c34a799fea3dc56eddbca5a,
  line1146 explicitly sign-extends bit11 before addition. Lines1175–1177
  distinguish SHIFT3 and INPUTS ADRL sources; nonblocking updates use entry state.
- Ymir6d779960127ced72087a418c1daefc637d0aaa80, DSP header
  blob8c9e0c0230c4e3dba840c2ed0059011e3e56fcfe: sign_extend<12>.
- Beetle1382b85dcad2e98ef9a67426a775ba548eaf0c68, scsp.inc
  blob79ac3c31102f740b0faf432de696062f25e90485: sign_x_to_s32(12,...).
- Primary ST-077-R2-052594, SDK0fab2c30d6d1aff1a4836352e00a7fc5cd4c7f73,
  blob9383eb13fe65c807e3ec48f32e284b9999cd71b8, establishes register widths
  and ring/base maps, NOT an explicit signed ADREB instruction rule.

69632 additional actual-method UBSan cases pass, retaining6531 earlier cases
and the stopped control. Every twelve-bit SHIFT3 and eight-bit INPUTS ADRL
value is tested across four ring sizes, TABLE and ADREB; read/write and NXADR
vary with raw bits, as do MADRS, RBP and DEC. Two legal odd-slot requests per
case check entry ADRS during simultaneous ADRL and the subsequent latched value.
Four compiled address mutants (unsigned, wrong width, unconditional ADREB,
late-latch use) fail behavioral assertions, as do the existing five mutants.
Full translation-unit syntax and14 output-parser controls pass.

The mapped fixture adds216 programs to the original31:120 TABLE read/write,
16 INPUTS-source read/write and80 ring reads. TABLE guards distinguish the
old unsigned location; ring RAM contains address tags and a paired baseline
read reveals the current ring position without injecting/assuming DEC.
The 68000 parking loop is outside the tagged RAM region. An initial external
prototype overwrote its old parking loop; that invalid run is NOT evidence.

Qualified old source9baba980 (binary SHA256
45f44dfc487b4ed005f2e3aca523f2b37d1cd83e5b7fb8724d532f74f31f5500)
passes199/fails48 programs, including all original31 passing. The48 negative
address cases produce64 failed observations because16 writes also hit the
wrong-address guard. Raw old-native and method/mutant logs are included.
Matching rebuilt native acceptance is PENDING, not an accepted production
endpoint. Four profiles will require988 programs. Full DSP timing, bus
arbitration, final writes, IWT forwarding, waveform/game and whole-driver
acceptance remain open; no working flags changed.
