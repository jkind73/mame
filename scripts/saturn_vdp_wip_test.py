#!/usr/bin/env python3
# license:BSD-3-Clause
"""Run the real renderer and isolated VDP1 erase methods with ASan/UBSan."""
import argparse
from pathlib import Path
import subprocess
import tempfile


def method(source, name):
    start = source.index("void saturn_vdp1_device::" + name + "(")
    brace = source.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


ERASE_FIXTURE = r"""
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
constexpr unsigned TVMR_8BPP = 1, TVMR_ROTATE = 2, TVMR_HDTV = 4;
struct saturn_vdp1_device {
    uint16_t m_tvmr = 0, m_ewlr = 0, m_ewrr = 0, m_ewdr = 0;
    struct { bool rot8; unsigned x_mask, y_start, x_start, y_end, x_bound, data; } m_erase{};
    std::array<uint16_t, 512 * 256> buffer;
    uint16_t *display_buffer() { return buffer.data(); }
    void latch_erase_params();
    void erase_row(unsigned y);
    void erase_limited(int64_t budget);
};
// ACTUAL_METHODS
int main() {
    for (unsigned mode : {0U, 1U, 2U, 3U, 4U}) {
        for (unsigned condition : {0U, 1U, 2U, 3U}) {
            for (bool limited : {false, true}) {
                saturn_vdp1_device d;
                d.buffer.fill(0xa55a);
                d.m_tvmr = mode;
                d.m_ewdr = 0x1234;
                d.m_ewlr = (1 << 9) | 3; // start word 8, row 3
                // Valid interval, equal X, backwards X, backwards Y.
                d.m_ewrr = ((condition == 1 ? 1 : condition == 2 ? 0 : 3) << 9) |
                    (condition == 3 ? 2 : 4);
                d.latch_erase_params();
                if (limited) d.erase_limited(1000);
                else for (unsigned y = d.m_erase.y_start; y <= d.m_erase.y_end; ++y) d.erase_row(y);
                unsigned const words = condition == 0 ? 16 : mode & 6 ? 8 : 1;
                unsigned const rows = condition == 0 ? 2 : 1;
                for (unsigned y = 0; y < 256; ++y)
                    for (unsigned x = 0; x < 512; ++x) {
                        bool const erased = y >= 3 && y < 3 + rows && x >= 8 && x < 8 + words;
                        assert(d.buffer[y * 512 + x] == (erased ? 0x1234 : 0xa55a));
                    }
            }
        }
    }
    std::cout << "erase passed (framebuffer words, including packed 8-bit modes)\n";
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="clang++")
    parser.add_argument("--revision", help="Test source from a Git revision instead of the working tree")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    sega = root / "src/mame/sega"
    with tempfile.TemporaryDirectory(prefix="saturn-vdp-tests-") as directory:
        out = Path(directory)
        def source(name):
            if args.revision:
                return subprocess.check_output(["git", "show", f"{args.revision}:src/mame/sega/{name}"], cwd=root).decode()
            return (sega / name).read_text()
        renderer = out / "renderer.cpp"
        renderer.write_text(source("saturn_vdp2_render.cpp"))
        erase = out / "erase.cpp"
        vdp1 = source("saturn_vdp1.cpp")
        erase.write_text(ERASE_FIXTURE.replace("// ACTUAL_METHODS", "\n".join(
            method(vdp1, name) for name in ["latch_erase_params", "erase_row", "erase_limited"])))
        flags = [args.cxx, "-std=c++20", "-O1", "-g", "-fsanitize=address,undefined", "-I" + str(sega)]
        subprocess.run([*flags, str(root / "tests/saturn/vdp_wip_test.cpp"), str(renderer), "-o", str(out / "renderer")], check=True)
        subprocess.run([*flags, str(erase), "-o", str(out / "erase")], check=True)
        failures = []
        for command in [[str(out / "renderer"), "windows"], [str(out / "renderer"), "rotation"], [str(out / "erase")]]:
            if subprocess.run(command).returncode:
                failures.append(command[-1])
        if failures:
            raise SystemExit("Failed fixtures: " + ", ".join(failures))


if __name__ == "__main__":
    main()
