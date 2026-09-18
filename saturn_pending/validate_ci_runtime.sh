#!/usr/bin/env bash
# license:BSD-3-Clause
# Consume a completed, provenance-checked CI artifact; never rebuild MAME here.
set -euo pipefail
if (( $# != 2 )); then echo "Usage: $0 ARTIFACT_DIRECTORY RUN_ID" >&2; exit 2; fi
ROOT=$(cd "$(dirname "$0")/.." && pwd)
ARTIFACT=$(cd "$1" && pwd)
RUN_ID=$2
LOG_DIR=${LOG_DIR:-/home/user/saturn-ci-runtime-$RUN_ID}
SDK_PREFIX=${SDK_PREFIX:-/home/user/.cache/saturn/linked-sdk}
mkdir -p "$LOG_DIR"
LOG_DIR=$(cd "$LOG_DIR" && pwd)
case "$LOG_DIR/" in "$ROOT/"*) echo 'Use an external log directory' >&2; exit 2;; esac
cd "$ROOT"
phase=provenance
# Remove a stale success marker before any operation that may fail.
rm -f "$LOG_DIR/status.txt"
trap 'rc=$?; if ((rc)); then printf "FAIL phase=%s exit=%s\n" "$phase" "$rc" | tee "$LOG_DIR/status.txt"; fi' EXIT
python3 saturn_pending/verify_ci_artifact.py "$ARTIFACT" --run-id "$RUN_ID" > "$LOG_DIR/artifact.json"
# Artifact archives do not retain executable permission bits.
chmod u+x "$ARTIFACT/saturn"
for rom in saturnjp saturneu stvbios; do test -s "regtests/$rom.zip"; done
sha256sum regtests/saturnjp.zip regtests/saturneu.zip regtests/stvbios.zip > "$LOG_DIR/bios.sha256"
phase=dependencies
if [[ ! -f "$SDK_PREFIX/build-env.sh" ]]; then
    python3 regtests/saturn/bootstrap_linked_deps.py --prefix "$SDK_PREFIX" > "$LOG_DIR/dependencies.log" 2>&1
fi
source "$SDK_PREFIX/build-env.sh"
# CI links the distro SDL SONAMEs; the local SDK supplies real SDL binaries
# from the pygame wheel under auditwheel-hashed names. Add loader aliases,
# not replacement implementations, in the external per-run directory.
mkdir -p "$LOG_DIR/runtime-libs"
ln -sfn "$(readlink -f "$SDK_PREFIX/deps/lib/libSDL2.so")" "$LOG_DIR/runtime-libs/libSDL2-2.0.so.0"
ln -sfn "$(readlink -f "$SDK_PREFIX/deps/lib/libSDL2_ttf.so")" "$LOG_DIR/runtime-libs/libSDL2_ttf-2.0.so.0"
export LD_LIBRARY_PATH="$LOG_DIR/runtime-libs:$LD_LIBRARY_PATH"
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
phase=configuration
ldd "$ARTIFACT/saturn" > "$LOG_DIR/libraries.txt"
if grep -q 'not found' "$LOG_DIR/libraries.txt"; then cat "$LOG_DIR/libraries.txt"; exit 1; fi
"$ARTIFACT/saturn" -validate > "$LOG_DIR/validate.log" 2>&1
for fixture in test_cd_hirq test_cart_runtime test_backup_ram; do
    phase=$fixture
    echo "[$phase]"
    python3 "regtests/saturn/$fixture.py" --executable "$ARTIFACT/saturn" \
        --rompath "$ROOT/regtests" > "$LOG_DIR/$fixture.log" 2>&1
done
grep -q 'CD block HIRQ: CMOK command handshake' "$LOG_DIR/test_cd_hirq.log"
grep -q 'Saturn cart runtime: 2 cartridges exercised' "$LOG_DIR/test_cart_runtime.log"
grep -q 'fresh-directory provenance and save/mutate/load all verified' "$LOG_DIR/test_backup_ram.log"
phase=scsp-timers
python3 saturn_pending/test_scsp_timers.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" > "$LOG_DIR/scsp-timers.log" 2>&1
grep -q '24 timer/divisor rates and three clear/reassert paths verified live' "$LOG_DIR/scsp-timers.log"
phase=smpc-multitap
python3 saturn_pending/test_smpc_multitap_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/smpc-multitap" > "$LOG_DIR/smpc-multitap.log" 2>&1
grep -q 'SMPC multitap: six live transport cases passed' "$LOG_DIR/smpc-multitap.log"
for spec in 'saturnjp drc' 'saturnjp interpreter' 'saturneu drc' 'stvbios drc'; do
    read -r system engine <<< "$spec"
    args=()
    if [[ "$engine" == drc ]]; then args+=(--drc); fi
    for mode in bios background; do
        phase="$system-$engine-$mode"
        echo "[$phase]"
        mode_args=()
        if [[ "$mode" == bios ]]; then mode_args+=(--bios); fi
        python3 regtests/saturn/run_vdp2_runtime.py --executable "$ARTIFACT/saturn" \
            --rompath "$ROOT/regtests" --system "$system" "${args[@]}" "${mode_args[@]}" \
            --output "$LOG_DIR/$phase" > "$LOG_DIR/$phase.log" 2>&1
    done
done
phase=final-provenance
python3 saturn_pending/verify_ci_artifact.py "$ARTIFACT" --run-id "$RUN_ID" > "$LOG_DIR/final-artifact.json"
cmp "$LOG_DIR/artifact.json" "$LOG_DIR/final-artifact.json"
sha256sum -c "$LOG_DIR/bios.sha256"
echo 'PASS: CI-artifact configuration, CD/cart/backup, three SCSP timers, multitap transport, and four BIOS/background replay configurations. Not full gameplay or hardware acceptance.' | tee "$LOG_DIR/status.txt"
