# Saturn test environment, on your own machine

Everything the Saturn/ST-V gates need, defined in the repository instead of in an
ephemeral sandbox.  The Arena sandbox this work has been developed in has been
recycled several times, and each recycle silently removed exactly the same things:
the dependency prefix, `build/`, the native binary, the probe scripts, and the
shim that made a build possible at all.  Every "verified" number I have quoted had
to be re-established after that happened; on your machine it never will, because
`build/` stays warm and incremental rebuilds take seconds instead of an hour.

Nothing here is a fixture.  No test expectations live in this directory, and the
scripts never edit a file outside `.saturn-gates/`.

## Quick start

```sh
git clone https://github.com/jkind73/mame.git ~/saturn-mame
cd ~/saturn-mame
git checkout arena/01a09f50-mame
cd regtests/saturn/handoff/local-env
./setup-deps.sh        # needs sudo once; the package list is copied from this repo's CI
./build.sh             # first build is long, later ones are incremental
./gates.sh             # PASS / SKIP / FAIL per fixture
```

`build.sh` ends by symlinking `<repo>/saturn` to the binary it built, because every
live fixture defaults to `--executable <repo>/saturn`.  If you build a real
driver-filtered `saturn` subtarget instead, that name already exists and is used
as-is (see "subtarget gap" below).

Useful overrides for `gates.sh`:

| variable | default | why you would set it |
|---|---|---|
| `SATURN_EXE` | `./saturn`, then `./mame` | point at any binary, e.g. a build from another worktree |
| `ROMPATH` | `<repo>/regtests` | where your BIOS/dump zips live |
| `WITH_IMPL_CHECKS` | unset | also run the implementation-probe batch if `saturn_pending/impl_checks/` is present |
| `GATE_DIR` | `<repo>/.saturn-gates` | where per-fixture logs are written |
| `JOBS` (build.sh) | `nproc` | drop to `-j2` on a small machine |

## ROMs

The runtime fixtures need the BIOS and CD-block dumps in `regtests/` next to the
fixture scripts.  **They are not tracked by git** (this repo does not carry ROMs),
so a fresh clone needs them copied in once, and that is the one manual step.  If a
zip is missing, the fixture prints `SKIP: no <zip> in <rompath>` and exits 0 -- the
gates script turns that into a loud `SKIP` line, never a pass.

Verify what you have against the set the gates were measured with:

```sh
cd regtests && sha1sum *.zip | column -t
```

    satcdb.zip        101309  c93053018c13057af2030a07ef4086fceb92e37f
    saturn2.zip        10754  edd79d6ef1fc9dfcce2021c938b95a33a928bd11
    saturneu.zip     1014371  715074ae33fd4de18182d96a166c681aaf172d15
    saturnjp.zip     1457637  b9dae5d1853daf4c0af283276fbb36a3cffaaa2c
    saturnkr.zip      551211  ac2939e3ceb1d9147ee96fa1be0f7a048373c38b
    saturnzi.zip       30645  56fb8772c06c84d6c8d9297a92cfa80abb6d16d0
    segabill.zip        3117  4631db7f7f5160a3a6591d3102722be869710f66
    stvbios.zip       3458138  a5c64cefd986993f78ffe0d54bcb9cac05767326

## Reading the report

`gates.sh` runs every `regtests/saturn/test_*.py` independently, plus
`saturn -validate` and the BIOS save/load round trip (`run_vdp2_runtime.py --bios`,
which saves, reloads and compares a full-image replay).  It deliberately does not
use `regtests/saturn/run_all.py`: that runner is `subprocess.run(check=True)`, so
it stops at the first failing script and cannot tell you the shape of the damage,
and it counts a fixture that skipped for lack of a binary the same as one that
passed.  `gates.sh` exits non-zero on any FAIL or on a failed `-validate`.

## What NOT to copy from the sandbox

Every one of these existed only because the sandbox could not do the ordinary
thing.  If a guide or a shell history entry mentions them, they are noise locally:

* **X11 header stubs** in `/usr/include/X11`.  There was no network package access;
  `NO_X11=1`/`NO_OPENGL=1` do *not* skip bgfx, so the build needed `Xlib.h`.  Install
  `libx11-dev` (tier 1 covers the rest) instead of stubbing headers.
* **A `g++` wrapper capping GCC's GC heap** for the `luaengine*.cpp` translation
  units.  Pure OOM guard for a 3.9 GB box with `-j2`.
* **`LDFLAGS=-Wl,--copy-dt-needed-entries`** and a hand-written link line, plus
  `-lfreetype` juggling.  Consequence of the same missing packages.
* **`REGENIE=1`** -- only needed when the generated project files are absent or
  stale.  A plain `make` handles it.
* **sourcing a private `build-env.sh`** from a dependency prefix: that file only
  existed because the sandbox could not install system packages.

## Subtarget gap (real, and not papered over)

The fixtures say `SKIP: no binary at .../saturn (build a driver-filtered subtarget
first)`, i.e. they expect a filtered build.  This branch tracks no scaffold for
that: `projects/` holds only `README.md`/`.gitignore`, and `src/mame/` has
`mame.lst`, `tiny.lst`, `dummy.lst` but no `saturn.lst`.  So either pass
`--executable`, or use the symlink `build.sh` creates, or add the filter properly
(`src/mame/saturn.lst` plus `projects/saturn/scripts/target/saturn/saturn.lua`,
which is what `makefile:909-911` requires when `PROJECT=` is set).  I have not
verified that scaffold end to end, so it is offered as the shape of the fix, not as
a tested instruction.

## After any wipe, in the sandbox

```sh
cd /home/user/mame
git fetch -q origin arena/01a09f50-mame && git reset --hard FETCH_HEAD
grep -c "lba_to_msf_alt(cd_curfad)" src/mame/sega/saturn_cd_hle.cpp   # 1 == my work is back
```

Recycles restore the workspace over the base commit `868d72fc669`, and untracked
files (including the `regtests/*.zip` dumps and any probe scripts) are what go
first.  Commit and push constantly; a local clone plus this directory is the only
copy that has never been lost.

## How this kit itself was checked

`gates.sh` was run in the sandbox against this branch with no binary present (the
recycle had taken it, along with `/tmp` and everything else untracked): **69 pass,
6 skip, 0 fail**, the six skips being exactly the live-machine fixtures, each shown
as `SKIP  no native binary` and counted apart from the passes.  So the argument
detection, the per-script isolation, the SKIP/FAIL classification and the tally are
all exercised; `build.sh`/`setup-deps.sh` are syntax-checked and use only the
package list and `make` invocation this repo's own CI runs.  The live path (the
`-validate` run, the `--executable` fixtures, the save/load round trip) could not
be re-exercised here for lack of a binary, but it is the same command shape used
against a native build earlier: `-validate` exit 0, `test_cd_hirq`,
`test_backup_ram`, `test_cart_runtime`, `test_sound_boot`, `test_smpc_transport`
all exit 0, and `run_vdp2_runtime.py --bios` replaying bit-identically after a
save/load.

## Link errors, and `git describe` noise

`./build.sh` now takes `-jN` (also honoured as `JOBS=N`) and prints where the number
came from, because ignoring a `-j2` and quietly running `-j$(nproc)` is how a small
VM gets its compiler killed: the giant `luaengine*.cpp` translation units each want
roughly 2.4 GB of RSS, which is why `-j2` is the right answer under ~8 GB of RAM.
`--dry-run` shows the resolved `make` command line without building anything.

If the failure is at `Linking mame...` rather than in a compile, the usual shape is:

    undefined reference to `vtable for X_device'
    undefined reference to `typeinfo for X_device'
    ... named from build/*/bin/**/libsomething.a(X.o)

The classes involved always define their key function out of line, so the vtable has
to be emitted in that object file; when the link says it is missing, the object set
and the generated project files disagree about which archive owns which `.o`, and
the library that would have provided it is not on the link line.  That is stale build
state (an interrupted first build, or a reconfigure that left archives behind), not a
source error -- `make -j3` of this tree links clean in CI.  In order:

```sh
./build.sh --regen      # REGENIE=1: regenerate project files, keep every object
./build.sh --clean      # make clean, then rebuild
```

Also benign, on this fork specifically:

    fatal: No names found, cannot describe anything.

The makefile asks git for a version via `git describe`, and `jkind73/mame` has **no
tags at all** (`git tag | wc -l` -> 0), so that line appears on every build of every
branch and MAME falls back to its compiled-in version.  It is not a sign your clone is
wrong -- `git rev-parse HEAD` is the check that matters.
