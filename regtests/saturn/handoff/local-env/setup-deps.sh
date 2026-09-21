#!/usr/bin/env bash
# One-time dependency install for a native Saturn/ST-V build of this tree.
#
# The package list in tier 1 is copied verbatim from this repository's own CI
# (.github/workflows/ci-linux.yml, "Install dependencies" step), so it is what the
# project actually tests against -- not a guess.  Tier 2 is only needed for the
# full-features build (bgfx renderer, sound, CHD) and the script installs those
# after asking, because they are not what CI proves.
#
# Debian/Ubuntu only.  On other platforms use your package manager for the same
# development packages, or run the CI container.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
  SUDO=sudo
else
  SUDO=
fi

TIER1=(
  build-essential
  git
  python3
  libsdl2-dev
  libsdl2-ttf-dev
  libfontconfig-dev
  libasound2-dev
  libxinerama-dev
  libxi-dev
)

# Needed by the full emulator (bgfx/text/sound/CHD paths) that CI trims by
# building a smaller subtarget.  Missing one of these shows up as a missing
# header or -l<library> at link time, which is exactly the failure a headless
# sandbox papered over with stubs; install the real package instead.
TIER2=(
  libfreetype-dev
  libpng-dev
  libjpeg-dev
  zlib1g-dev
  libflac-dev
  libogg-dev
  libvorbis-dev
  libopus-dev
  libgl1-mesa-dev
  libglew-dev
  libsqlite3-dev
  libpulse-dev
  libudev-dev
)

apt_update() { $SUDO apt-get update -qq; }

install_pkgs() {
  local missing=() p
  for p in "$@"; do
    dpkg -s "$p" >/dev/null 2>&1 || missing+=("$p")
  done
  if [ ${#missing[@]} -eq 0 ]; then
    echo "already installed: $*"
    return
  fi
  echo "installing: ${missing[*]}"
  DEBIAN_FRONTEND=noninteractive apt_install "${missing[@]}"
}

apt_install() { $SUDO apt-get install -y --no-install-recommends "$@"; }

apt_update
install_pkgs "${TIER1[@]}"

if [ "${ASSUME_YES:-0}" = "1" ]; then
  install_tier2=1
elif [ ! -t 0 ]; then
  install_tier2=0
else
  echo
  echo "Install the full-features set too? (bgfx renderer, sound codecs, CHD, OpenGL)"
  read -r -p "[Y/n] " answer || answer=n
  case "${answer:-y}" in [Nn]*) install_tier2=0 ;; *) install_tier2=1 ;; esac
fi

if [ "$install_tier2" = 1 ]; then
  install_pkgs "${TIER2[@]}"
else
  echo "tier 2 not installed: ${TIER2[*]}"
  echo "if the build then reports a missing header or -l<library>, install what it names,"
  echo "or run: sudo apt-get install -y ${TIER2[*]}"
fi

echo
echo "Dependencies ready.  Next: ./build.sh"
