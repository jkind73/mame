# Production 79f36021 local checks

`python3 regtests/saturn/run_all.py` exited zero: 56 scripts, including the new
9,216 physical-socket/mode report cases. Three optional live scripts skipped
because the default repository-root binary is absent; these are not accepted
native passes. The full output is retained in regressions.log.

Additional focused RESB extraction: 6,144 cases plus ST-V isolation pass.
Full-TU C++20 syntax passes for SMPC, sat_console, ctrl, multitap and segatap.
An initial C++17 full-TU invocation was rejected because current MAME requires
C++20; the successful syntax invocation used that required language version.

Native source 79f36021 remains pending CI 35303949227. All native negatives and
positives under 2781-live belong to the older, explicitly identified binary.
