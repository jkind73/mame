#!/usr/bin/env python3
# license:BSD-3-Clause
"""Compare fixed-frame VDP captures from two builds, one game at a time."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--rompath", required=True)
    parser.add_argument("--vf2-disc", type=Path, required=True)
    parser.add_argument("--nvram", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--games", nargs="+", choices=["diehard", "vfkids", "vf2"], default=["diehard", "vfkids", "vf2"])
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for game, machine, extra in [
        ("diehard", "diehard", []),
        ("vfkids", "vfkids", []),
        ("vf2", "saturneu", ["-cdrom", str(args.vf2_disc.resolve())]),
    ]:
        if game not in args.games:
            continue
        for label, binary in [("baseline", args.baseline), ("current", args.current)]:
            run = output / label / game
            # Refuse to mix new captures with a previous run.
            run.mkdir(parents=True, exist_ok=False)
            for directory in ["cfg", "nvram", "diff", "sta"]:
                (run / directory).mkdir()
            seed = args.nvram / machine
            if machine == "saturneu" and not seed.exists():
                seed = args.nvram / "saturn"
            if machine == "saturneu" and not seed.is_dir():
                raise RuntimeError(f"Missing initialized NVRAM seed: {seed}")
            if seed.is_dir():
                shutil.copytree(seed, run / "nvram" / machine)
            if machine == "saturneu" and seed.name == "saturn":
                # The PAL SMPC seed must be valid and use English. Otherwise the
                # BIOS language menu makes a VF2 comparison meaningless.
                (run / "nvram" / machine / "smpc_smem").write_bytes(bytes([0, 0, 0, 0, 255]))
            command = [
                str(binary.resolve()), machine, *extra,
                "-noreadconfig", "-rompath", args.rompath,
                "-hashpath", str(root / "hash"),
                "-video", "none", "-sound", "none", "-nothrottle", "-frameskip", "0",
                # 1800 frames takes 36 seconds on PAL, 30 seconds on NTSC.
                "-seconds_to_run", "37", "-rtc", "20000101000000", "-skip_gameinfo",
                "-autoboot_delay", "0", "-autoboot_script", str(root / "scripts/saturn_vdp_capture.lua"),
                "-snapshot_directory", str(run), "-cfg_directory", str(run / "cfg"),
                "-nvram_directory", str(run / "nvram"), "-diff_directory", str(run / "diff"),
                "-state_directory", str(run / "sta"),
            ]
            print(f"Capturing {game}: {label}", flush=True)
            with (run / "run.log").open("w") as log:
                subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT,
                               timeout=180, check=True)
            for frame in [60, 300, 600, 1200, 1800]:
                for suffix in ["pixels", "png", "sta"]:
                    if not (run / f"frame-{frame:04d}.{suffix}").is_file():
                        raise RuntimeError(f"Missing capture: {run}/frame-{frame:04d}.{suffix}")
        for frame in [60, 300, 600, 1200, 1800]:
            entry = {"game": game, "frame": frame}
            for suffix in ["pixels", "sta"]:
                hashes = [hashlib.sha256((output / label / game / f"frame-{frame:04d}.{suffix}").read_bytes()).hexdigest()
                          for label in ["baseline", "current"]]
                entry[suffix] = {"equal": hashes[0] == hashes[1], "baseline": hashes[0], "current": hashes[1]}
            results.append(entry)
            print(f"{game} frame {frame}: pixels={entry['pixels']['equal']} state={entry['sta']['equal']}", flush=True)
        (output / "comparison.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
