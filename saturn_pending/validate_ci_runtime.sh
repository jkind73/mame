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
phase=dsp-disassembler
python3 saturn_pending/test_scudsp_disassembler_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-disassembler" > "$LOG_DIR/dsp-disassembler.log" 2>&1
grep -q 'DSP disassembler: 241 real debugger destination/parallel-command rows and three slot trace rows passed' "$LOG_DIR/dsp-disassembler.log"
phase=dsp-pause
python3 saturn_pending/test_scudsp_pause_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-pause" > "$LOG_DIR/dsp-pause.log" 2>&1
grep -q 'DSP pause: 20 pause/DMA/stopped-load/pending-slot cases passed live' "$LOG_DIR/dsp-pause.log"
phase=dsp-pause-save
python3 saturn_pending/test_scudsp_pause_save_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-pause-save" > "$LOG_DIR/dsp-pause-save.log" 2>&1
grep -q 'DSP pause save: paused active DMA and independent stall ownership restored' "$LOG_DIR/dsp-pause-save.log"
phase=dsp-hostflags
python3 saturn_pending/test_scudsp_hostflags_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-hostflags" > "$LOG_DIR/dsp-hostflags.log" 2>&1
grep -q 'DSP host flags: 112 guest-ALU/read-only/masked-write cases passed live' "$LOG_DIR/dsp-hostflags.log"
phase=dsp-pipeline
python3 saturn_pending/test_scudsp_pipeline_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-pipeline" > "$LOG_DIR/dsp-pipeline.log" 2>&1
grep -q 'DSP pipeline: 27 wrapped/control-flow/fetched-slot programs passed live' "$LOG_DIR/dsp-pipeline.log"
phase=dsp-count
python3 saturn_pending/test_scudsp_count_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-count" > "$LOG_DIR/dsp-count.log" 2>&1
grep -q 'DSP DMA count: 24 zero/width/direction/hold programs passed live' "$LOG_DIR/dsp-count.log"
phase=dsp-count_operand
python3 saturn_pending/test_scudsp_count_operand_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-count_operand" > "$LOG_DIR/dsp-count_operand.log" 2>&1
grep -q 'DSP count operand: 32 source-alias/increment/wrap programs passed live' "$LOG_DIR/dsp-count_operand.log"
phase=dsp-parallel
python3 saturn_pending/test_scudsp_parallel_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-parallel" > "$LOG_DIR/dsp-parallel.log" 2>&1
grep -q 'DSP parallel buses: 144 RAM/register/counter programs passed live' "$LOG_DIR/dsp-parallel.log"
phase=dsp-parallel-save
python3 saturn_pending/test_scudsp_parallel_save_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-parallel-save" > "$LOG_DIR/dsp-parallel-save.log" 2>&1
grep -q 'DSP parallel save: active copy loop, RAM, counters and multiplier replay restored' "$LOG_DIR/dsp-parallel-save.log"
phase=dsp-lop
python3 saturn_pending/test_scudsp_lop_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-lop" > "$LOG_DIR/dsp-lop.log" 2>&1
grep -q 'DSP loop counter: 80 write-path/BTM/LPS programs passed live' "$LOG_DIR/dsp-lop.log"
phase=dsp-lop-save
python3 saturn_pending/test_scudsp_lop_save_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-lop-save" > "$LOG_DIR/dsp-lop-save.log" 2>&1
grep -q 'DSP loop save: active 4096-iteration loop and 64-word output replay restored' "$LOG_DIR/dsp-lop-save.log"
phase=dsp-multiplier
python3 saturn_pending/test_scudsp_multiplier_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-multiplier" > "$LOG_DIR/dsp-multiplier.log" 2>&1
grep -q 'DSP multiplier: 64 RX write-path/product programs passed live' "$LOG_DIR/dsp-multiplier.log"
phase=dsp-alu_flow
python3 saturn_pending/test_scudsp_alu_flow_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-alu_flow" > "$LOG_DIR/dsp-alu_flow.log" 2>&1
grep -q 'DSP ALU dataflow: 192 entry-A/bypass/high-half programs passed live' "$LOG_DIR/dsp-alu_flow.log"
phase=dsp-alu
python3 saturn_pending/test_scudsp_alu_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-alu" > "$LOG_DIR/dsp-alu.log" 2>&1
grep -q 'DSP ALU: 438 arithmetic/flag/read-clear programs passed live' "$LOG_DIR/dsp-alu.log"
phase=dsp-alu-save
python3 saturn_pending/test_scudsp_alu_save_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-alu-save" > "$LOG_DIR/dsp-alu-save.log" 2>&1
grep -q 'DSP ALU save: 48-bit result and latched overflow restored through real file replay' "$LOG_DIR/dsp-alu-save.log"
phase=dsp-read
python3 saturn_pending/test_scudsp_read_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-read" > "$LOG_DIR/dsp-read.log" 2>&1
grep -q 'DSP read DMA: 1024 Work RAM-H mirror/mode programs passed live' "$LOG_DIR/dsp-read.log"
phase=dsp-dma
python3 saturn_pending/test_scudsp_dma_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-dma" > "$LOG_DIR/dsp-dma.log" 2>&1
grep -q 'DSP DMA: 32 mapped-program B-bus addressing cases passed live' "$LOG_DIR/dsp-dma.log"
phase=dsp-cbus
python3 saturn_pending/test_scudsp_cbus_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-cbus" > "$LOG_DIR/dsp-cbus.log" 2>&1
grep -q 'DSP C-bus: 512 mapped-program placement/WA0 cases passed live' "$LOG_DIR/dsp-cbus.log"
phase=dsp-cbus-save
python3 saturn_pending/test_scudsp_cbus_save_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-cbus-save" > "$LOG_DIR/dsp-cbus-save.log" 2>&1
grep -q 'DSP C-bus save: odd-phase cursor and WA0 replay verified' "$LOG_DIR/dsp-cbus-save.log"
phase=dsp-pram
python3 saturn_pending/test_scudsp_pram_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-pram" > "$LOG_DIR/dsp-pram.log" 2>&1
grep -q 'DSP program RAM: 32 mapped loader/overlay programs passed live' "$LOG_DIR/dsp-pram.log"
phase=dsp-pram-save
python3 saturn_pending/test_scudsp_pram_save_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-pram-save" > "$LOG_DIR/dsp-pram-save.log" 2>&1
grep -q 'DSP program RAM save: busy wrapped transfer and instruction image restored' "$LOG_DIR/dsp-pram-save.log"
phase=dsp-save
python3 saturn_pending/test_scudsp_save_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-save" > "$LOG_DIR/dsp-save.log" 2>&1
grep -q 'DSP save: busy transfer restored and 256-word replay verified' "$LOG_DIR/dsp-save.log"
# Default DSP fixtures above use JP/interpreter; exercise the other shared-core
# configurations explicitly rather than inferring DSP acceptance from BIOS boot.
for system in saturnjp saturneu stvbios; do
    for fixture in dma pipeline read pram count count_operand alu multiplier lop parallel cbus hostflags pause alu_flow; do
        phase="dsp-$fixture-$system-drc"
        python3 "saturn_pending/test_scudsp_${fixture}_runtime.py" \
            --executable "$ARTIFACT/saturn" --rompath "$ROOT/regtests" \
            --system "$system" --drc --output "$LOG_DIR/$phase" > "$LOG_DIR/$phase.log" 2>&1
        if [[ "$fixture" == dma ]]; then
            grep -q 'DSP DMA: 32 mapped-program B-bus addressing cases passed live' "$LOG_DIR/$phase.log"
        elif [[ "$fixture" == pipeline ]]; then
            grep -q 'DSP pipeline: 27 wrapped/control-flow/fetched-slot programs passed live' "$LOG_DIR/$phase.log"
        elif [[ "$fixture" == pram ]]; then
            grep -q 'DSP program RAM: 32 mapped loader/overlay programs passed live' "$LOG_DIR/$phase.log"
        elif [[ "$fixture" == count ]]; then
            grep -q 'DSP DMA count: 24 zero/width/direction/hold programs passed live' "$LOG_DIR/$phase.log"
        elif [[ "$fixture" == count_operand ]]; then
            grep -q 'DSP count operand: 32 source-alias/increment/wrap programs passed live' "$LOG_DIR/$phase.log"
        elif [[ "$fixture" == alu_flow ]]; then
            grep -q 'DSP ALU dataflow: 192 entry-A/bypass/high-half programs passed live' "$LOG_DIR/$phase.log"
        elif [[ "$fixture" == pause ]]; then
            grep -q 'DSP pause: 20 pause/DMA/stopped-load/pending-slot cases passed live' "$LOG_DIR/$phase.log"
        elif [[ "$fixture" == hostflags ]]; then
            grep -q 'DSP host flags: 112 guest-ALU/read-only/masked-write cases passed live' "$LOG_DIR/$phase.log"
        elif [[ "$fixture" == cbus ]]; then
            grep -q 'DSP C-bus: 512 mapped-program placement/WA0 cases passed live' "$LOG_DIR/$phase.log"
        elif [[ "$fixture" == parallel ]]; then
            grep -q 'DSP parallel buses: 144 RAM/register/counter programs passed live' "$LOG_DIR/$phase.log"
        elif [[ "$fixture" == lop ]]; then
            grep -q 'DSP loop counter: 80 write-path/BTM/LPS programs passed live' "$LOG_DIR/$phase.log"
        elif [[ "$fixture" == multiplier ]]; then
            grep -q 'DSP multiplier: 64 RX write-path/product programs passed live' "$LOG_DIR/$phase.log"
        elif [[ "$fixture" == alu ]]; then
            grep -q 'DSP ALU: 438 arithmetic/flag/read-clear programs passed live' "$LOG_DIR/$phase.log"
        else
            grep -q 'DSP read DMA: 1024 Work RAM-H mirror/mode programs passed live' "$LOG_DIR/$phase.log"
        fi
    done
done
phase=dsp-slot-save
python3 saturn_pending/test_scudsp_slot_save_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/dsp-slot-save" > "$LOG_DIR/dsp-slot-save.log" 2>&1
grep -q 'DSP pending slot save: wrapped slot restored and executed exactly' "$LOG_DIR/dsp-slot-save.log"
phase=scsp-timers
python3 saturn_pending/test_scsp_timers.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" > "$LOG_DIR/scsp-timers.log" 2>&1
grep -q '24 timer/divisor rates and three clear/reassert paths verified live' "$LOG_DIR/scsp-timers.log"
phase=smpc-multitap
python3 saturn_pending/test_smpc_multitap_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/smpc-multitap" > "$LOG_DIR/smpc-multitap.log" 2>&1
grep -q 'SMPC multitap: six live transport cases passed' "$LOG_DIR/smpc-multitap.log"
phase=smpc-sparse
python3 saturn_pending/test_smpc_multitap_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --empty-pad 1:2 --empty-pad 2:5 \
    --output "$LOG_DIR/smpc-sparse" > "$LOG_DIR/smpc-sparse.log" 2>&1
grep -q 'SMPC multitap: six live transport cases passed' "$LOG_DIR/smpc-sparse.log"
phase=smpc-segatap
python3 saturn_pending/test_smpc_multitap_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --adapter segatap \
    --output "$LOG_DIR/smpc-segatap" > "$LOG_DIR/smpc-segatap.log" 2>&1
grep -q 'SMPC multitap: six live transport cases passed' "$LOG_DIR/smpc-segatap.log"
phase=smpc-segatap-sparse
python3 saturn_pending/test_smpc_multitap_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --adapter segatap --empty-pad 1:2 --empty-pad 2:3 \
    --output "$LOG_DIR/smpc-segatap-sparse" > "$LOG_DIR/smpc-segatap-sparse.log" 2>&1
grep -q 'SMPC multitap: six live transport cases passed' "$LOG_DIR/smpc-segatap-sparse.log"
phase=smpc-empty-ports
python3 saturn_pending/test_smpc_multitap_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --adapter none \
    --output "$LOG_DIR/smpc-empty-ports" > "$LOG_DIR/smpc-empty-ports.log" 2>&1
grep -q 'SMPC multitap: six live transport cases passed' "$LOG_DIR/smpc-empty-ports.log"
phase=smpc-resb
python3 saturn_pending/test_smpc_resb_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/smpc-resb" > "$LOG_DIR/smpc-resb.log" 2>&1
grep -q 'SMPC_RESB PASS cases=7' "$LOG_DIR/smpc-resb/runtime.log"
phase=smpc-save
python3 saturn_pending/test_smpc_save_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/smpc-save" > "$LOG_DIR/smpc-save.log" 2>&1
grep -q 'SMPC save: partial report snapshot/cursor/mode restored' "$LOG_DIR/smpc-save.log"
phase=smpc-timeout
python3 saturn_pending/test_smpc_timeout_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/smpc-timeout" > "$LOG_DIR/smpc-timeout.log" 2>&1
grep -q 'SMPC timeout: four waiting/in-flight expiry cases passed live' "$LOG_DIR/smpc-timeout.log"
phase=sync-save
python3 saturn_pending/test_sync_save_runtime.py --executable "$ARTIFACT/saturn" \
    --rompath "$ROOT/regtests" --output "$LOG_DIR/sync-save" > "$LOG_DIR/sync-save.log" 2>&1
grep -q 'Sync save: H/V edge history and first restored SCU interrupt status passed live' "$LOG_DIR/sync-save.log"
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
echo 'PASS: CI-artifact configuration, CD/cart/backup, DSP wrapped control flow and read mirrors, DSP DMA B-bus addressing, program loaders and in-flight data/program save replay, three SCSP timers, full/sparse multitap transport, sampled RESB and snapshot save-load, timeout, H/V edge restore, and four BIOS/background replay configurations. Not full gameplay or hardware acceptance.' | tee "$LOG_DIR/status.txt"
