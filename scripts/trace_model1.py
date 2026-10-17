#!/usr/bin/env python3
"""
scripts/trace_model1.py: Automated Headless Attract-Mode Trace Runner for Sega Model 1

Executes non-interactive headless runs (-str <seconds> -nothrottle -video none -sound none)
across all six Sega Model 1 arcade systems:
- vr (Virtua Racing)
- vformula (Virtua Formula)
- vf (Virtua Fighter)
- swa (Star Wars Arcade)
- wingwar (Wing War)
- netmerc (Sega NetMerc)

Verifies runtime stability, absence of hangs/crashes, and records execution metrics.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Dict, List, Optional, Sequence

DEFAULT_GAMES = ["vr", "vformula", "vf", "swa", "swaj", "wingwar", "wingwaru", "wingwarj", "wingwar360", "netmerc"]


def run_headless_trace(
    mame_exe: Path,
    rom_paths: Sequence[str],
    game: str,
    seconds: int,
    out_dir: Path,
    extra_args: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    """Runs a single headless MAME trace and captures status and timing."""
    log_file = out_dir / f"{game}_trace.log"
    rompath_arg = ";".join(rom_paths)

    cmd = [
        str(mame_exe),
        game,
        "-str",
        str(seconds),
        "-nothrottle",
        "-video",
        "none",
        "-sound",
        "none",
        "-rompath",
        rompath_arg,
    ]
    if extra_args:
        cmd.extend(extra_args)

    print(f"[*] Running headless trace: {game} for {seconds}s...")
    t0 = time.time()
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    elapsed = time.time() - t0

    log_content = (
        f"; Command: {' '.join(cmd)}\n"
        f"; Exit code: {res.returncode}\n"
        f"; Wallclock: {elapsed:.2f}s\n"
        f"; ================= STDOUT ================\n"
        f"{res.stdout}\n"
        f"; ================= STDERR ================\n"
        f"{res.stderr}\n"
    )
    log_file.write_text(log_content, encoding="utf-8")

    status = "ok" if res.returncode == 0 else f"failed (code {res.returncode})"
    print(f"    [+] {game}: {status} in {elapsed:.2f}s wallclock")

    return {
        "game": game,
        "seconds_requested": seconds,
        "wallclock_elapsed": round(elapsed, 2),
        "returncode": res.returncode,
        "status": "passed" if res.returncode == 0 else "failed",
        "log_file": str(log_file),
        "stdout_tail": res.stdout.strip().splitlines()[-10:] if res.stdout else [],
        "stderr_tail": res.stderr.strip().splitlines()[-10:] if res.stderr else [],
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Headless Attract-Mode Trace Runner for Sega Model 1")
    parser.add_argument(
        "--mame",
        type=Path,
        default=Path("mame1.exe"),
        help="Path to MAME executable (default: ./mame1.exe)",
    )
    parser.add_argument(
        "--roms",
        nargs="+",
        default=["roms", r"Z:\mame\roms"],
        help="Directories containing ROMs (default: roms Z:\\mame\\roms)",
    )
    parser.add_argument(
        "--seconds",
        "-s",
        type=int,
        default=60,
        help="Seconds of emulation to run per game (default: 60)",
    )
    parser.add_argument(
        "--games",
        nargs="+",
        default=DEFAULT_GAMES,
        help=f"Target games to trace (default: {' '.join(DEFAULT_GAMES)})",
    )
    parser.add_argument(
        "--out-dir",
        "-o",
        type=Path,
        default=Path("build/model1_traces"),
        help="Output directory for trace logs and JSON report",
    )
    args = parser.parse_args(argv)

    if not args.mame.is_file():
        print(f"[!] MAME executable not found at {args.mame}")
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report: Dict[str, object] = {
        "timestamp": datetime.now().isoformat(),
        "mame_binary": str(args.mame),
        "seconds_per_game": args.seconds,
        "rom_paths": args.roms,
        "results": {},
    }

    all_passed = True
    for game in args.games:
        res = run_headless_trace(
            mame_exe=args.mame,
            rom_paths=args.roms,
            game=game,
            seconds=args.seconds,
            out_dir=args.out_dir,
        )
        report["results"][game] = res
        if res["status"] != "passed":
            all_passed = False

    report_path = args.out_dir / "trace_summary.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n[+] Wrote trace summary to {report_path}")
    return 0 if all_passed else 2


if __name__ == "__main__":
    sys.exit(main())
