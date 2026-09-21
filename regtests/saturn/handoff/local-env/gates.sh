#!/usr/bin/env bash
# Run the Saturn/ST-V gate set against a native binary and print PASS / SKIP / FAIL
# for every fixture, one line each.
#
# Why this exists instead of `python3 regtests/saturn/run_all.py`: that runner uses
# subprocess.run(check=True) and therefore stops at the first failure, so it can
# never tell you how much of the suite is actually healthy -- and a fixture that
# exits 0 because it found no binary is a *skip*, not a pass.  This script runs
# every script independently, keeps the logs, and refuses to call a skip a pass.
#
# Usage:
#   ./gates.sh                      # uses ./saturn or ./mame, rompath regtests
#   SATURN_EXE=/path/to/saturn ./gates.sh
#   ROMPATH=/path/to/dumps ./gates.sh
#   WITH_IMPL_CHECKS=1 ./gates.sh   # also run the implementation-probe batch, if present
set -uo pipefail

cd "$(dirname "$(readlink -f "$0")")/../../../.."
ROOT=$PWD
REG=$ROOT/regtests/saturn
ROMPATH=${ROMPATH:-$ROOT/regtests}
EXE=${SATURN_EXE:-}
if [ -z "$EXE" ]; then
  for c in ./saturn ./mame ./mametiny; do
    if [ -f "$c" ] && [ -x "$c" ]; then EXE=$PWD/${c#./}; break; fi
  done
fi
[ -n "$EXE" ] && [ -x "$EXE" ] || EXE=""

OUT=${GATE_DIR:-$ROOT/.saturn-gates}
rm -rf "$OUT"; mkdir -p "$OUT/logs"

# Headless, deterministic, no config or nvram surprises from your profile.
export SDL_VIDEODRIVER=${SDL_VIDEODRIVER:-dummy}
export SDL_AUDIODRIVER=${SDL_AUDIODRIVER:-dummy}
export HOME="${HOME:-$ROOT}"

V=SKIP
if [ -z "$EXE" ]; then
  echo "!! no native binary found: every live fixture will SKIP"
  echo "!! build one first (./build.sh) or point SATURN_EXE at it; a skip is not a pass"
  echo
else
  echo "== binary: $EXE"
  printf '%-34s' "saturn -validate"
  if timeout 900 "$EXE" -validate >"$OUT/logs/validate.log" 2>&1; then
    echo "PASS"; V=PASS
  else
    echo "FAIL (see .saturn-gates/logs/validate.log)"; V=FAIL
  fi
  echo
fi

printf '%-34s%-8s%s\n' "fixture" "result" "detail"
fails=0; passes=0; skips=0
for script in "$REG"/test_*.py; do
  name=$(basename "$script")
  [ "$name" = "run_all.py" ] && continue
  args=()
  # Only fixtures that advertise these options talk to a machine; the rest are
  # source-level harnesses that take no arguments at all.
  if grep -q -- '--executable' "$script"; then
    if [ -n "$EXE" ]; then
      args=(--executable "$EXE" --rompath "$ROMPATH")
    else
      printf '%-34s%-8s%s\n' "$name" "SKIP" "no native binary"
      skips=$((skips+1)); continue
    fi
  fi
  out="$OUT/logs/${name%.py}.log"
  if timeout 1800 python3 "$script" "${args[@]}" >"$out" 2>&1; then
    if grep -q '^SKIP' "$out"; then
      result=SKIP; detail=$(head -1 "$out" | cut -c1-64); skips=$((skips+1))
    else
      result=PASS; detail=$(tail -1 "$out" | cut -c1-64); passes=$((passes+1))
    fi
  else
    result=FAIL; detail="exit=$? $(tail -1 "$out" | cut -c1-52)"; fails=$((fails+1))
  fi
  printf '%-34s%-8s%s\n' "$name" "$result" "$detail"
done

# The BIOS save/load round trip is its own thing: it drives the machine through a
# real save, a reload and a full-image replay comparison.
if [ -n "$EXE" ] && [ -f "$REG/run_vdp2_runtime.py" ]; then
  printf '%-34s' "run_vdp2_runtime --bios"
  if timeout 1800 python3 "$REG/run_vdp2_runtime.py" --bios --system saturnjp \
       --executable "$EXE" --rompath "$ROMPATH" --output "$OUT/saveload" \
       >"$OUT/logs/vdp2_runtime.log" 2>&1; then
    echo "PASS | $(grep -o 'BIOS_RUNTIME PASS.*' "$OUT/logs/vdp2_runtime.log" | head -1 | cut -c1-60)"
    passes=$((passes+1))
  else
    echo "FAIL | $(tail -1 "$OUT/logs/vdp2_runtime.log" | cut -c1-60)"
    fails=$((fails+1))
  fi
fi

if [ "${WITH_IMPL_CHECKS:-0}" = "1" ] && [ -d "$ROOT/saturn_pending/impl_checks" ]; then
  echo
  echo "== implementation probes (each compiles its own harness: expect ~25 min,"
  echo "   and do NOT run them alongside a build -- CPU contention produced a false"
  echo "   failure here once, and it looked like a product defect)"
  ip=0; ic=0
  for probe in "$ROOT"/saturn_pending/impl_checks/check_*.py; do
    if timeout 900 python3 "$probe" >"$OUT/logs/$(basename "$probe").log" 2>&1; then
      ip=$((ip+1))
    else
      ic=$((ic+1)); echo "  conflict: $(basename "$probe")"
    fi
  done
  echo "   probes: $ip exit0 / $ic conflicts"
fi

echo
echo "== tally: $passes pass, $skips skip, $fails fail (validate: ${V:-n/a})"
echo "== logs: $OUT/logs"
if [ "$skips" -gt 0 ]; then
  echo "!! $skips fixture(s) did not run.  Report them as skips, never as done."
fi
[ "$fails" -eq 0 ] && [ "$V" != FAIL ]
