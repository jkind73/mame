#!/bin/sh
# ---------------------------------------------------------------------------
# bootstrap_toolchain.sh - recreate the vendored build toolchain from scratch
#
# Why this exists: the sandbox has no SDL2/X11/fontconfig development files and
# no package network (deb.debian.org is unreachable; github.com,
# codeload.github.com and pypi.org are). Everything this script produces lives
# OUTSIDE the repository under $MAME_SDK, so it is wiped whenever the sandbox is
# recycled and is not recoverable from git. This script is the part that does
# survive - run it, then build_satdev.sh.
#
# Idempotent: safe to re-run. Skips the SDL2 build if libSDL2.a already exists.
#
# Takes roughly a minute for SDL2 plus a few seconds for the headers and stubs.
# ---------------------------------------------------------------------------
set -e

SDK=${MAME_SDK:-/home/user/sdk}
SDL_TAG=${SDL_TAG:-release-2.30.11}
FC_TAG=${FC_TAG:-2.13.1}
FT_TAG=${FT_TAG:-VER-2-13-2}
WORK=${TMPDIR:-/tmp}/mame-toolchain-bootstrap

mkdir -p "$SDK/bin" "$SDK/inc" "$SDK/lib" "$WORK"

# --- 1. SDL2, built static with every optional backend disabled -------------
# Each --disable-* below removes a dependency the sandbox does not have. The
# resulting library still provides the dummy/offscreen video and disk/dummy
# audio drivers MAME's headless regression runs need.
if [ ! -f "$SDK/sdl2/lib/libSDL2.a" ]; then
	echo "==> building SDL2 $SDL_TAG (static)"
	rm -rf "$WORK/sdl"
	mkdir -p "$WORK/sdl"
	curl -sSL -o "$WORK/sdl.tar.gz" \
		"https://codeload.github.com/libsdl-org/SDL/tar.gz/refs/tags/$SDL_TAG"
	tar xzf "$WORK/sdl.tar.gz" -C "$WORK/sdl" --strip-components=1
	cd "$WORK/sdl"
	./configure --prefix="$SDK/sdl2" \
		--enable-static --disable-shared \
		--disable-video-x11 --disable-video-wayland \
		--disable-video-opengl --disable-video-opengles \
		--disable-video-kmsdrm --disable-video-vivante --disable-video-cocoa \
		--disable-render-d3d --disable-audio-pipewire \
		--disable-libudev --disable-dbus --disable-ibus --disable-fcitx \
		--disable-sdl2-config --disable-oss --disable-alsa \
		--disable-pulseaudio --disable-jack --disable-esd --disable-nas \
		--disable-sndio > "$WORK/sdl-configure.log" 2>&1
	make -j"${JOBS:-3}" > "$WORK/sdl-make.log" 2>&1
	make install > "$WORK/sdl-install.log" 2>&1
	cd - > /dev/null
else
	echo "==> SDL2 already present, skipping build"
fi

# --- 2. include-root symlink ------------------------------------------------
# MAME sources include both <SDL.h> and <SDL2/SDL.h>. The shim emits
# -I$SDK/sdl2/include/SDL2 (satisfies the first) and -I$SDK/inc (satisfies the
# second only through this symlink). Created here, before the SDL_ttf stub,
# because the stub is compiled against -I$SDK/inc.
ln -sfn "$SDK/sdl2/include/SDL2" "$SDK/inc/SDL2"

# --- 3. fontconfig + FreeType headers ---------------------------------------
# Headers only; both link against the image's runtime .so.1/.so.6 via the
# symlinks in step 4. The header versions differ from the runtime (2.13.1 vs
# 2.14.x, 2.13.2 vs system) but the Fc*/FT_* entry points MAME uses are
# unchanged across those releases.
if [ ! -f "$SDK/inc/fontconfig/fontconfig.h" ]; then
	echo "==> fetching fontconfig $FC_TAG headers"
	rm -rf "$WORK/fc"; mkdir -p "$WORK/fc"
	curl -sSL -o "$WORK/fc.tar.gz" \
		"https://codeload.github.com/fontconfig/fontconfig/tar.gz/refs/tags/$FC_TAG"
	tar xzf "$WORK/fc.tar.gz" -C "$WORK/fc" --strip-components=1
	mkdir -p "$SDK/inc/fontconfig"
	# In the fontconfig source tree the public headers live in a fontconfig/
	# subdirectory, not at the top level.
	cp "$WORK/fc/fontconfig/fontconfig.h" "$WORK/fc/fontconfig/fcfreetype.h" \
		"$WORK/fc/fontconfig/fcprivate.h" "$SDK/inc/fontconfig/"
fi

if [ ! -f "$SDK/inc/freetype2/ft2build.h" ]; then
	echo "==> fetching FreeType $FT_TAG headers"
	rm -rf "$WORK/ft"; mkdir -p "$WORK/ft"
	curl -sSL -o "$WORK/ft.tar.gz" \
		"https://codeload.github.com/freetype/freetype/tar.gz/refs/tags/$FT_TAG"
	tar xzf "$WORK/ft.tar.gz" -C "$WORK/ft" --strip-components=1
	# NOTE: the release tarball has include/freetype/, NOT include/freetype2/.
	# The freetype2 wrapper directory is created by `make install`, so taking
	# headers straight from the archive means building that level by hand.
	mkdir -p "$SDK/inc/freetype2"
	cp -r "$WORK/ft/include/freetype" "$SDK/inc/freetype2/"
	cp "$WORK/ft/include/ft2build.h" "$SDK/inc/freetype2/"
fi

# --- 4. SDL_ttf stub --------------------------------------------------------
# MAME's scripts/src/osd/sdl.lua links SDL2_ttf unconditionally and
# src/osd/modules/font/font_sdl.cpp calls eight TTF_* entry points (grep -rn
# "TTF_" src/osd/ returns 54 hits, all in that file). An empty archive fails the
# link, so the archive must define them. Returning "no font available" is safe:
# font_sdl.cpp:165 guards on `if (drawsurf)` and a null TTF_OpenFontIndex is
# handled. CONSEQUENCE: a binary built this way renders no UI text. It is a test
# vehicle for -validate / headless regression / Lua probes, NOT shippable.
cat > "$SDK/sdl2/include/SDL2/SDL_ttf.h" <<'TTF_H'
/* SDL2/SDL_ttf.h -- API subset stub. NOT SDL_ttf. See
   regtests/saturn/handoff/bootstrap_toolchain.sh for why this exists and what
   it costs (no UI text rendering). */
#ifndef SDL_TTF_STUB_H
#define SDL_TTF_STUB_H

#include <SDL.h>

#define TTF_MAJOR_VERSION 2
#define TTF_MINOR_VERSION 20
#define TTF_PATCHLEVEL 2

#define TTF_STYLE_NORMAL         0x00
#define TTF_STYLE_BOLD           0x01
#define TTF_STYLE_ITALIC         0x02
#define TTF_STYLE_UNDERLINE      0x04
#define TTF_STYLE_STRIKETHROUGH  0x08

typedef struct _TTF_Font TTF_Font;

#ifdef __cplusplus
extern "C" {
#endif

int TTF_Init(void);
void TTF_Quit(void);
const char *TTF_GetError(void);

TTF_Font *TTF_OpenFontIndex(const char *file, int ptsize, long index);
void TTF_CloseFont(TTF_Font *font);
void TTF_SetFontStyle(TTF_Font *font, int style);
int TTF_FontLineSkip(const TTF_Font *font);
SDL_Surface *TTF_RenderUTF8_Solid(TTF_Font *font, const char *text, SDL_Color fg);

#ifdef __cplusplus
}
#endif

#endif /* SDL_TTF_STUB_H */
TTF_H

cat > "$WORK/sdl_ttf_stub.c" <<'TTF_C'
#include <SDL2/SDL_ttf.h>
#include <stddef.h>
int TTF_Init(void) { return 0; }
void TTF_Quit(void) { }
const char *TTF_GetError(void)
{ return "SDL_ttf stub: font rendering unavailable in this sandbox build"; }
TTF_Font *TTF_OpenFontIndex(const char *file, int ptsize, long index)
{ (void)file; (void)ptsize; (void)index; return NULL; }
void TTF_CloseFont(TTF_Font *font) { (void)font; }
void TTF_SetFontStyle(TTF_Font *font, int style) { (void)font; (void)style; }
int TTF_FontLineSkip(const TTF_Font *font) { (void)font; return 0; }
SDL_Surface *TTF_RenderUTF8_Solid(TTF_Font *font, const char *text, SDL_Color fg)
{ (void)font; (void)text; (void)fg; return NULL; }
TTF_C
gcc -c -O1 -I"$SDK/inc" -I"$SDK/sdl2/include/SDL2" \
	-o "$WORK/sdl_ttf_stub.o" "$WORK/sdl_ttf_stub.c"
ar rcs "$SDK/lib/libSDL2_ttf.a" "$WORK/sdl_ttf_stub.o"

# --- 5. link satisfiers for backends that were compiled out -----------------
# Empty on purpose: SDL2 was configured without these, so no symbol is
# referenced. This is independent of MAME's own src/osd/modules/input/
# input_x11.cpp, which is gated on the generated USE_XINPUT define and needs
# NO_USE_XINPUT=1 at make time - see build_satdev.sh.
for lib in EGL X11 Xinerama Xext Xi; do
	[ -f "$SDK/lib/lib$lib.a" ] || : | ar rcs "$SDK/lib/lib$lib.a"
done
ln -sf /usr/lib/x86_64-linux-gnu/libfontconfig.so.1 "$SDK/lib/libfontconfig.so"
ln -sf /usr/lib/x86_64-linux-gnu/libfreetype.so.6   "$SDK/lib/libfreetype.so"

# --- 6. pkg-config shim -----------------------------------------------------
# Both include roots and both -L paths are required; libSDL2.a installs under
# $SDK/sdl2/lib, not $SDK/lib, and omitting either produced a distinct link
# failure during development.
cat > "$SDK/bin/pkg-config" <<SHIM
#!/bin/sh
# Generated by regtests/saturn/handoff/bootstrap_toolchain.sh
INC=$SDK/inc
SDL=$SDK/sdl2
LIBS=$SDK/lib
case " \$* " in
  *" sdl2 "*)
    for a in "\$@"; do
      case "\$a" in
        --cflags) echo "-I\$SDL/include/SDL2 -I\$INC" ;;
        --libs)   echo "-L\$LIBS -L\$SDL/lib -lSDL2 -lpthread -ldl -lm" ;;
        --modversion) echo "2.30.11" ;;
        --exists) exit 0 ;;
      esac
    done
    exit 0 ;;
esac
for a in "\$@"; do
  case "\$a" in
    --cflags) echo "-I\$INC" ;;
    --libs)   echo "-L\$LIBS -lfontconfig" ;;
    --modversion) echo "2.13.1" ;;
    --exists) exit 0 ;;
  esac
done
exit 0
SHIM
chmod +x "$SDK/bin/pkg-config"

# --- 7. smoke test ----------------------------------------------------------
# Compile AND link, against the real flags MAME will use, so a broken shim or a
# missing stub is caught here rather than 30 minutes into a MAME build.
#
# The include set deliberately matches what MAME actually pulls in - <SDL2/SDL.h>
# and <SDL2/SDL_ttf.h> from src/osd/modules/font/font_sdl.cpp and
# <fontconfig/fontconfig.h> from there plus src/osd/sdl/sdlmain.cpp. MAME never
# includes <ft2build.h> itself, so asserting that here would fail the bootstrap
# for a reason that does not affect the build.
cat > "$WORK/smoke.cpp" <<'SMOKE'
#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>
#include <fontconfig/fontconfig.h>
int main()
{
	TTF_Font *f = nullptr;
	TTF_CloseFont(f);
	if (FC_MAJOR < 2)
		return 1;
	return TTF_STYLE_STRIKETHROUGH;
}
SMOKE
FLAGS=$("$SDK/bin/pkg-config" --cflags --libs sdl2)
# MAME's scripts/src/osd/sdl.lua links SDL2_ttf separately from the sdl2
# pkg-config module, so the smoke test has to as well or it would pass while the
# real link fails.
#
# The source file must come first: ld searches archives in command-line order
# and only pulls members that resolve symbols already undefined at that point,
# so putting -lSDL2_ttf before smoke.cpp fails with "undefined reference to
# TTF_CloseFont" even though the archive defines it.
# shellcheck disable=SC2086
if g++ -std=c++20 "$WORK/smoke.cpp" $FLAGS -L"$SDK/lib" -lSDL2_ttf \
		-o "$WORK/smoke"; then
	echo "==> smoke test linked OK"
else
	echo "bootstrap_toolchain.sh: smoke test FAILED to link" >&2
	exit 1
fi

echo "Toolchain ready under $SDK"
echo "Next: PATH=$SDK/bin:\$PATH regtests/saturn/handoff/build_satdev.sh"
