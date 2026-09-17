#!/bin/sh
# ---------------------------------------------------------------------------
# build_satdev.sh - reproducible Saturn/ST-V-only MAME build for this project
#
# Why this exists: a full `make` builds every MAME driver (~10k translation
# units).  On the 2-core sandbox used for the device work that is many hours
# per clean build, which makes device iteration impractical.  MAME already
# supports driver-filtered subtargets through `src/mame/<subtarget>.flt` plus
# `scripts/build/makedep.py filterproject`, which computes the full device
# dependency closure automatically.
#
# The filter file is generated on demand below and deliberately kept OUT of
# git (it is a local build accelerator, not a shipped target).  Add the line
#     /src/mame/satdev.flt
# to .git/info/exclude if you regenerate the checkout.
#
# Sandbox note: the default image has no SDL2/X11/fontconfig development files
# and no package network.  See regtests/saturn/handoff/devices.md, section
# "Build environment", for the vendored toolchain that this script expects.
# ---------------------------------------------------------------------------
set -e

MAME_DIR=${MAME_DIR:-/home/user/mame}
SDK=${MAME_SDK:-/home/user/sdk}
JOBS=${JOBS:-2}

cd "$MAME_DIR"

cat > src/mame/satdev.flt <<'EOF'
sega/sat_console.cpp
sega/stv.cpp
sega/stvdev.cpp
EOF

export PATH="$SDK/bin:$PATH"

# NOWERROR=1 : gcc-12 emits a false-positive -Wrestrict/-Warray-bounds inside
#              libstdc++ basic_string on src/emu/device.cpp; upstream tolerates
#              this via NOWERROR.  It is not a code defect in this fork.
# OPTIMIZE=1 : default.  The src/emu/emumem_he* template instantiations take
#              >12 min each at -O2 on this 2-core host; -O1 keeps the whole
#              subtarget build inside ~1 h.  Override with OPTIMIZE=2 for
#              performance runs (QA-05).  Object files are shared, so only
#              files built after the change pick up the new level.
# OPT_FLAGS  : -DUSE_OZONE stops bgfx' bundled EGL/eglplatform.h from pulling
#              in X11/Xlib.h; the ggc params cap cc1plus peak RSS so two
#              parallel jobs survive on a 3 GB machine.
exec make SUBTARGET=satdev -j"$JOBS" "$@" \
	REGENIE=1 \
	NOWERROR=1 \
	USE_QTDEBUG=0 \
	NO_OPENGL=1 \
	NO_X11=1 \
	OPTIMIZE="${OPTIMIZE:-1}" \
	OPT_FLAGS="-DUSE_OZONE --param=ggc-min-expand=10 --param=ggc-min-heapsize=65536" \
	NO_USE_MIDI=1 \
	NO_USE_PORTAUDIO=1 \
	NO_USE_PULSEAUDIO=1 \
	NO_USE_PIPEWIRE=1
