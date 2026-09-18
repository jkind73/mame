# Integrated SMPC source checks — 234c7abc

The full 54-script regression batch completed successfully on the integrated
production source. Three live-device runners skipped because their default
`./saturn` executable is absent; those skips are not live acceptance of this
revision. The old CI executable is kept separately to prevent accidental
attribution of pre-fix results to the new source.

The new transport fixture and adapted handshake fixture passed in this batch.
Six focused compiled transport mutants were separately rejected, and the SMPC
translation unit passed C++20 syntax checking before commit.

Native rebuild: https://github.com/jkind73/mame/actions/runs/35291979814
Source: `234c7abcfc9a222978a7545a8491e568cf1781cf`.
It is compiling at this checkpoint. Positive live multitap acceptance and repeat
whole-machine checks still require that newly built executable.
