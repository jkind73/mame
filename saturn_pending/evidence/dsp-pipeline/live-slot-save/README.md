# DSP-03: actual pending address-00 branch-slot save replay

Verified ca63041f executable SHA256:
642af2f549c682ec391aa78109cfa732a727bd06b93fddb5a6d52b4d44162312
Build35341486010/export35343850525, same binary as the accepted full consumer.

`test_scudsp_slot_save_runtime.py` passes scheduled save/mutate/load with a
wrapped pending branch slot. All writes use mapped SCU host ports. A repeating
FF->03 jump has its slot at00; public PC and a data-RAM marker distinguish the
pending slot from its already-executed state. After save the slot executes, the
DSP is reset and its marker poisoned, then file load restores the pending PC and
marker. Advancing90ns executes the pending slot exactly as in the original path.
The shared runner validates the actual MAMESAVE file, not an in-memory state copy.

This is JP/interpreter coverage at the existing emulated dot-clock rates. Public
PC's current PC+1 convention is explicitly part of fixture phase identification;
this is not hardware proof of that convention or exact prefetch timing. It does
not cover other delay-slot types/configurations. Thirteen output-parser controls
pass separately. The next full native consumer includes this gate.
