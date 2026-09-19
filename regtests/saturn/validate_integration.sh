#!/usr/bin/env bash
# license:BSD-3-Clause
# Reproducible validation for the reviewed cartridge/CD WIP. No automatic flag
# promotion, source mutation, commit or push. Results are not hardware acceptance.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
LOG_DIR=${LOG_DIR:-/home/user/saturn-validation}
SDK_PREFIX=${SDK_PREFIX:-/home/user/.cache/saturn/linked-sdk}
mkdir -p "$LOG_DIR"
LOG_DIR=$(cd "$LOG_DIR" && pwd)
case "$LOG_DIR/" in "$ROOT/"*) echo 'Use a log directory outside the repository' >&2; exit 2;; esac
phase=preflight
trap 'rc=$?; if ((rc)); then printf "FAIL phase=%s exit=%s\n" "$phase" "$rc" | tee "$LOG_DIR/status.txt"; fi' EXIT
# Do not accidentally attribute uncommitted production/test inputs to HEAD.
git diff --exit-code HEAD -- src regtests/saturn 3rdparty scripts makefile hash > "$LOG_DIR/input-diff.log"
git rev-parse HEAD > "$LOG_DIR/source-commit.txt"
git rev-parse HEAD:src HEAD:regtests/saturn HEAD:3rdparty HEAD:scripts HEAD:makefile HEAD:hash > "$LOG_DIR/input-trees.txt"
for rom in saturnjp saturneu stvbios; do
    test -s "regtests/$rom.zip" || { echo "Missing user-supplied $rom BIOS" >&2; exit 2; }
done
sha256sum regtests/saturnjp.zip regtests/saturneu.zip regtests/stvbios.zip > "$LOG_DIR/bios.sha256"
phase=dependencies
echo "[$phase]"
if [[ ! -f "$SDK_PREFIX/build-env.sh" ]]; then
    python regtests/saturn/bootstrap_linked_deps.py --prefix "$SDK_PREFIX" > "$LOG_DIR/dependencies.log" 2>&1
fi
# The existing helper supplies real SDL/SDL_ttf libraries, not link-only stubs.
source "$SDK_PREFIX/build-env.sh"
export CXXFLAGS='--param=ggc-min-expand=10 --param=ggc-min-heapsize=32768'
phase=build
echo "[$phase] one compiler job to avoid sandbox memory pressure"
make -j1 SUBTARGET=saturn REGENIE=1 SYMBOLS=0 OPTIMIZE=1 \
    SOURCES=src/mame/sega/saturn.cpp,src/mame/sega/sat_console.cpp,src/mame/sega/stv.cpp \
    USE_QTDEBUG=0 NO_X11=1 NO_USE_XINPUT=1 NO_OPENGL=1 NO_USE_MIDI=1 \
    NO_USE_PORTAUDIO=1 NO_USE_PULSEAUDIO=1 NO_USE_PIPEWIRE=1 > "$LOG_DIR/build.log" 2>&1
sha256sum saturn > "$LOG_DIR/binary.sha256"
phase=configuration
echo "[$phase]"
./saturn -validate > "$LOG_DIR/validate.log" 2>&1
phase=regressions
echo "[$phase] includes linked CD/cart fixtures now that the binary exists"
python regtests/saturn/run_all.py > "$LOG_DIR/regressions.log" 2>&1
# These checks distinguish actually executed device fixtures from their optional
# no-binary/no-ROM skips. run_all exit status alone is not live-device evidence.
grep -q 'CD block HIRQ: CMOK command handshake' "$LOG_DIR/regressions.log"
grep -q 'Saturn cart runtime: 2 cartridges exercised' "$LOG_DIR/regressions.log"
grep -q 'fresh-directory provenance and save/mutate/load all verified' "$LOG_DIR/regressions.log"
for spec in 'saturnjp drc' 'saturnjp interpreter' 'saturneu drc' 'stvbios drc'; do
    read -r system engine <<< "$spec"
    args=()
    if [[ "$engine" == drc ]]; then args+=(--drc); fi
    for mode in bios background; do
        phase="$system-$engine-$mode"
        echo "[$phase]"
        mode_args=()
        if [[ "$mode" == bios ]]; then mode_args+=(--bios); fi
        python regtests/saturn/run_vdp2_runtime.py --executable "$ROOT/saturn" \
            --rompath "$ROOT/regtests" --system "$system" "${args[@]}" "${mode_args[@]}" \
            --output "$LOG_DIR/$phase" > "$LOG_DIR/$phase.log" 2>&1
    done
done
phase=provenance
git diff --exit-code HEAD -- src regtests/saturn 3rdparty scripts makefile hash > "$LOG_DIR/final-input-diff.log"
# Permit checkpoint-only commits elsewhere, but never changes to build/test
# inputs. Keep the starting commit, rather than relabeling an existing binary.
git rev-parse HEAD:src HEAD:regtests/saturn HEAD:3rdparty HEAD:scripts HEAD:makefile HEAD:hash > "$LOG_DIR/final-input-trees.txt"
cmp "$LOG_DIR/input-trees.txt" "$LOG_DIR/final-input-trees.txt"
sha256sum -c "$LOG_DIR/binary.sha256"
sha256sum -c "$LOG_DIR/bios.sha256"
printf 'PASS: build, validate, regression batch, required CD/cart execution, four BIOS/background replay configurations. Not gameplay/hardware acceptance.\n' | tee "$LOG_DIR/status.txt"
