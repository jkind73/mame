#!/usr/bin/env python3
# license:BSD-3-Clause
"""Exhaustively compare the real sprite decoder with its pre-optimization reference."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent


def decoder(text, owner):
    start = text.index('renderer::sprite_dot renderer::decode_sprite')
    opening = text.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end].replace('renderer::', owner + '::')


fixture = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
struct decoded { unsigned sp_type; bool sp_clmd, sp_winen, tpsdsl; };
struct sprite_dot {
    bool palette=false, tp=true, wn=false, sd=false;
    unsigned pr=0, cc=0; uint32_t dc=0;
    bool operator==(sprite_dot const&) const = default;
};
unsigned bits(unsigned data, unsigned hi, unsigned lo) {
    return (data >> lo) & ((1U << (hi-lo+1))-1);
}
struct reference {
    using sprite_dot=::sprite_dot;
    sprite_dot decode_sprite(decoded const&, uint16_t) const;
};
struct current {
    using sprite_dot=::sprite_dot;
    sprite_dot decode_sprite(decoded const&, uint16_t) const;
};
// METHODS
int main() {
    reference r; current c;
    for (unsigned type=0; type<16; ++type)
        for (unsigned flags=0; flags<8; ++flags) {
            decoded d{type, bool(flags&1), bool(flags&2), bool(flags&4)};
            for (unsigned word=0; word<65536; ++word)
                assert(r.decode_sprite(d, word)==c.decode_sprite(d, word));
        }
    std::cout << "8388608 sprite decoder comparisons PASS\n";
}
'''
old = (ROOT / 'tests/saturn/vdp2_sprite_decode_reference.cpp').read_text()
new = (ROOT / 'src/mame/sega/saturn_vdp2_render.cpp').read_text()
with tempfile.TemporaryDirectory(prefix='saturn-sprite-equivalence-') as directory:
    source = Path(directory) / 'test.cpp'
    source.write_text(fixture.replace('// METHODS', decoder(old, 'reference') + '\n' + decoder(new, 'current')))
    binary = source.with_suffix('')
    subprocess.run(['clang++', '-std=c++20', '-O1', '-fsanitize=address,undefined', str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
