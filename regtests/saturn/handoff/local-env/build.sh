#!/usr/bin/env bash
# Build this tree natively so the Saturn fixtures run for real instead of skipping.
#
# Nothing here is exotic: it is the same `make` the CI runs (`.github/workflows/
# ci-linux.yml`, "Build" step).  The only addition is the `saturn` symlink, because
# every fixture in regtests/saturn/ defaults to --executable <repo>/saturn, expecting
# a driver-filtered subtarget that this branch does not ship a project scaffold for
# (there is no projects/saturn/, and no src/mame/saturn.lst).  Pointing that name at
# the normal binary is what makes `./gates.sh` work with no arguments at all.
set -euo pipefail

usage() {
  cat <<'USAGE'
usage: ./build.sh [-jN] [--clean] [--regen] [--verbose] [--dry-run]

  -jN        parallel jobs (default: nproc).  Also honoured as JOBS=N.
  --clean    make clean first, then rebuild.
  --regen    REGENIE=1: re-run genie so the generated project files match the current
             makefile and source lists, keeping every object.  Try this first.
  --verbose  pass VERBOSE=1 to make.
  --dry-run  print the make command line and exit (checks what the flags resolve to).
USAGE
}

JOBS=${JOBS:-}
CLEAN=
REGEN=
VERBOSE=
for a in "$@"; do
  case "$a" in
    -j*) JOBS=${a#-j} ;;
    --clean) CLEAN=1 ;;
    --regen) REGEN=1 ;;
    --verbose|-v) VERBOSE=1 ;;
    --dry-run) DRYRUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $a" >&2; usage; exit 2 ;;
  esac
done
if [ -n "$JOBS" ]; then
  JOBS_SRC='from $JOBS'
else
  JOBS=$( (nproc 2>/dev/null || echo 4) ); JOBS_SRC='nproc'
fi

cd "$(dirname "$(readlink -f "$0")")/../../../.."
ROOT=$PWD

if [ ! -f "$ROOT/regtests/saturn/test_cd_lle.py" ]; then
  echo "not at the repository root ($ROOT) - run this from inside your mame checkout" >&2
  exit 2
fi

MAKE_ARGS=(-j"$JOBS")
[ -n "$REGEN" ] && MAKE_ARGS=(REGENIE=1 "${MAKE_ARGS[@]}")
[ -n "$VERBOSE" ] && MAKE_ARGS+=(VERBOSE=1)
[ -n "${EXTRA_MAKE_ARGS:-}" ] && MAKE_ARGS+=($EXTRA_MAKE_ARGS)

echo "== building in $ROOT (-j$JOBS, $JOBS_SRC)$([ -n "$REGEN" ] && echo ' REGENIE=1')$([ -n "$CLEAN" ] && echo ' + make clean')"
echo "== first build is slow (thousands of translation units); later ones are incremental"
if ! git -C "$ROOT" diff --quiet HEAD -- src makefile; then
  echo "!! note: src/ differs from HEAD here, so the binary will not match any commit"
fi

if [ "${DRYRUN:-}" = 1 ]; then
  echo "make ${MAKE_ARGS[*]}"
  exit 0
fi

if [ -n "$CLEAN" ]; then
  echo "== make clean"
  make clean >/dev/null
fi

if ! make "${MAKE_ARGS[@]}"; then
  cat >&2 <<'HINT'

-- If the failure is at "Linking mame..." rather than in a compile, read this.
   Symptoms:  undefined reference to `vtable for X_device'  /  `typeinfo for X_device'
   where X.o is named from a build/*/bin/**/*.a archive.  The object list and the
   archive membership then disagree: a device .o is linked in without the library
   that emits its key function, which is what a partially built or reconfigured
   build/ tree looks like -- not a source error.  Fix in this order:
     ./build.sh --regen     # regenerate the project files, keep the objects
     ./build.sh --clean     # if that does not clear it
   Both keep working from the same checkout; only the first build afterwards is long.
HINT
  exit 1
fi

BIN=""
for c in ./saturn ./mame ./mametiny build/*/bin/saturn build/*/bin/mame; do
  if [ -f "$c" ] && [ -x "$c" ] && [ ! -L "$c" ]; then BIN="$c"; break; fi
done
if [ -z "$BIN" ]; then
  echo "build finished but no binary was found; run the gates by hand with" >&2
  echo "  SATURN_EXE=/path/to/binary ./gates.sh" >&2
  exit 1
fi

ln -sfn "$BIN" "$ROOT/saturn"
echo "== $ROOT/saturn -> $BIN"
echo "== sanity: $BIN -version"
"$BIN" -version | head -2
echo
echo "Next: ./gates.sh"
