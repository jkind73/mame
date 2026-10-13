#!/usr/bin/env python3
# license:BSD-3-Clause
"""Capture games sequentially with isolated settings; screenshots require human review."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("games", nargs="+")
    parser.add_argument("--binary", type=Path, default=Path("saturn"))
    parser.add_argument("--rompath", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=62)
    parser.add_argument("--inputs", type=Path, help="Frame/port/mask/value replay; one game only")
    parser.add_argument("--frames", default="")
    parser.add_argument("--machine", help="Console driver for software-list games, e.g. saturnjp")
    parser.add_argument("--nvram-source", type=Path, help="Copy initialized NVRAM into each isolated run")
    parser.add_argument("--audio", action="store_true", help="Record internal audio at 48kHz")
    args = parser.parse_args()
    if args.inputs and len(args.games) != 1:
        parser.error("--inputs requires exactly one game")
    root = Path(__file__).resolve().parent.parent
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # A build during a long survey must not switch later games to another binary.
    binary = output/"survey-binary"
    if binary.exists():
        parser.error("output already contains a survey binary; use a new output directory")
    shutil.copy2(args.binary.resolve(), binary)
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True)
    changes = subprocess.run(["git", "diff", "--name-only"], cwd=root, text=True, capture_output=True)
    manifest = {"binary_sha256":digest, "binary_source":str(args.binary.resolve()),
                "checkout_head":head.stdout.strip(), "checkout_modified_files":changes.stdout.splitlines(),
                "machine":args.machine, "games":args.games, "seconds":args.seconds, "audio":args.audio}
    (output/"manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    results = []
    for game in args.games:
        run = output/game
        run.mkdir(exist_ok=False)
        if args.nvram_source:
            shutil.copytree(args.nvram_source.resolve(), run/"nvram")
        command = ["nice", "-n", "10", str(binary)]
        if args.machine:
            command.append(args.machine)
        command += [game,
                   "-noreadconfig", "-rompath", args.rompath,
                   "-video", "none", "-sound", "none", "-nothrottle", "-frameskip", "0",
                   "-seconds_to_run", str(args.seconds), "-rtc", "20000101000000",
                   "-skip_gameinfo", "-autoboot_delay", "0", "-autoboot_script",
                   str(root/"scripts"/("saturn_game_inputs.lua" if args.inputs else "saturn_game_survey.lua")),
                   "-snapshot_directory", str(run), "-cfg_directory", str(run/"cfg"),
                   "-nvram_directory", str(run/"nvram"), "-diff_directory", str(run/"diff")]
        if args.audio:
            command += ["-samplerate", "48000", "-wavwrite", str(run/"audio.wav")]
        env = os.environ.copy()
        env.pop("SATURN_SURVEY_INPUTS", None)
        env["SATURN_SURVEY_CAPTURE_FRAMES"] = args.frames
        if args.inputs:
            env["SATURN_SURVEY_INPUTS"] = str(args.inputs.resolve())
        print("Surveying " + game, flush=True)
        with (run/"run.log").open("w") as log:
            try:
                process = subprocess.run(command, cwd=root, env=env, stdout=log,
                                         stderr=subprocess.STDOUT, timeout=240)
                status = process.returncode
            except subprocess.TimeoutExpired:
                status = "timeout"
        text = (run/"run.log").read_text(errors="replace")
        result = {"game":game, "exit":status, "command":command,
                  "lua_errors":"[LUA ERROR]" in text,
                  "captures":[str(p) for p in sorted(run.glob("frame-*.png"))],
                  "observations":[line for line in text.splitlines() if line.startswith(("SURVEY ","INPUT "))]}
        results.append(result)
        (output/"results.json").write_text(json.dumps(results, indent=2)+"\n")
        print(f"{game}: exit={status}, {len(result['captures'])} captures; review required", flush=True)


if __name__ == "__main__":
    main()
