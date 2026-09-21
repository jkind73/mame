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

cd "$(dirname "$(readlink -f "$0")")/../../../.."
ROOT=$PWD

JOBS=${JOBS:-$( (nproc 2>/dev/null || echo 4) )}

if [ ! -f "$ROOT/regtests/saturn/test_cd_lle.py" ]; then
  echo "not at the repository root ($ROOT) - run this from inside your mame checkout" >&2
  exit 2
fi

echo "== building in $ROOT with -j$JOBS"
echo "== first build is slow (thousands of translation units); later ones are incremental"
make -j"$JOBS" ${EXTRA_MAKE_ARGS:-}

BIN=""
for c in ./saturn ./mame ./mametiny build/*/bin/saturn build/*/bin/mame; do
  if [ -f "$c" ] && [ -x "$c" ] && [ ! -L "$c" ]; then BIN="$c"; break; fi
done
if [ -z "$BIN" ]; then
  echo "build finished but no binary was found; run it by hand with" >&2
  echo "  SATURN_EXE=/path/to/binary ./gates.sh" >&2
  exit 1
fi

ln -sfn "$BIN" "$ROOT/saturn"
echo "== $ROOT/saturn -> $BIN"
echo "== sanity: $BIN -version"
"$BIN" -version | head -2
echo
echo "Next: ./gates.sh"
