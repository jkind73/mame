# Game-by-game regression work

2026-10-08, local Saturn rewrite source. First pass covers the ten available
ST-V drivers below; it does not cover every Saturn disc or every ST-V set.
Each emulator runs alone at low priority, with independent configuration and
NVRAM, fixed RTC, no frame skipping, and video/audio output disabled.
Screenshots come from the emulated screen rather than the host video output.

| Game | Reproduced result | Status / next check |
|---|---|---|
| Radiant Silvergun (`rsgun`) | Visible story/attract screen at 60 seconds. | Older blanket blank-screen report does not reproduce. Gameplay, final boss and reverb remain unverified. |
| Elan-Doree (`elandore`) | Black at 30/60 seconds with DRC and interpreter. VDP2 display remains disabled. | OPEN. CPU polling PCs alone do not prove a dead CPU. Master still executes; initial VDP1 clear costs 175168 clocks, within a frame. Trace the startup transition rather than adding a display-enable hack. |
| Virtua Fighter Remix (`vfremix`) | Scripted coin/start/selection reaches fights with Akira, Wolf, Jeffry and Sarah. Selected fighter confirmed visually. | MT4445's three named character failures do not reproduce after existing rewrites. Remove stale NOT_WORKING flag; retain imperfect graphics/sound. Longer play and audio still need testing. |
| Golden Axe: The Duel (`gaxeduel`) | Visible title/attract at 60 seconds. | Attract reached; gameplay and sound regression cases remain open. |
| Die Hard Arcade (`diehard`) | Visible attract fight at 60 seconds. | Attract reached; quick-time-event slowdown and sound require gameplay checks. |
| Virtua Fighter Kids (`vfkids`) | Deterministic DRC fatal error around 42 seconds: `Overran maxinst in drcuml_block_append`. Fresh current and saved pre-register-fix builds reproduce. | OPEN, under investigation. The first invalid interrupt vector is at about 31.406 seconds: main CPU IRQ14/vector65 reads A5A5A5A5 at 06000104. Both interpreter and DRC lose valid execution; the compiler overflow is a later consequence. Increasing the UML buffer did not fix it and was reverted. This also occurs before the recent register fixes. Interpreter taps covering all WRAM-H mirrors identify the first vector overwrite: slave PC 0605B416 writes A5A5A5A5 at 06100104 (31.396616 s), in its linked-list traversal. ROM verification passes. A bounded interpreter trace shows the traversal starts from a bad head (060FFB00), follows 06000348 and then SEGA (53454741). The earlier producer of the bad head is still unidentified. Disabling the cache also stalled the diagnostic and was reverted. |
| Funky Head Boxers (`fhboxers`) | Visible attract animation at 60 seconds. | Attract reached; CN18 multicab serial support remains missing. |
| Batman Forever (`batmanfr`) | Visible attract animation at 60 seconds. | Attract reached; final-boss rotation and full gameplay remain unverified. |
| Cotton 2 (`cotton2`) | Visible title/attract at 60 seconds. | Attract reached; stage-one music/reverb needs sound-enabled testing. |
| Final Fight Revenge (`ffreveng`) | Visible attract fight at 60 seconds. | Attract reached; broader gameplay/audio not assessed. |

## Reproduction

Run `python3 scripts/saturn_game_survey.py --rompath /path/to/roms
--output /new/output/directory game1 game2 ...` from the workspace. The runner
refuses to overwrite an existing game output directory, runs sequentially,
records commands/exit codes/Lua errors in `results.json`, and retains logs and
fixed-frame PNGs. An exit code of zero is **not** a visual correctness verdict.
The timeout is per game; the subprocess is stopped before moving to another.

The VF Remix regressions use `tests/saturn/game_inputs/vfremix-{wolf,jeffry,sarah}.txt`:

```
python3 scripts/saturn_game_survey.py vfremix --rompath /path/to/roms \
  --output /new/vfremix-test --inputs tests/saturn/game_inputs/vfremix-jeffry.txt \
  --frames 2559,2800
```

Input files replay normal input fields (`frame port mask value`, hexadecimal
mask). They do not patch ROM/RAM or force emulated status flags. Fighter
selection timing is specific to this run configuration; verify the selection
capture before interpreting the fight capture. The harness can add capture
frames using `--frames` and extend runs using `--seconds`.

Current raw evidence is under `/private/tmp/saturn-game-survey/`, including
`regression-set/results.json`, Elan-Doree DRC/interpreter captures, and separate
VF Remix selection/fight captures. Source-level fixes must be described here
after their final build and game verification pass. No upstream issue was
changed, and no whole-game or whole-library accuracy claim is made.

Final normal SDL3 build passes after reverting every temporary CPU diagnostic and cache-disable experiment. The final scripted Sarah replay exits successfully, confirms Sarah at frame 2559, and shows Sarah versus Jacky at frame 3600. Python syntax, checklist consistency and whitespace checks pass. The only driver behavior classification changed by this batch is VF Remix; no new CPU/VDP hardware fix is claimed.
