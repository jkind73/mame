#!/usr/bin/env python3
# license:BSD-3-Clause
"""Check actual VDP1 vertical/horizontal edge methods against the FBCR access window."""
import argparse
from pathlib import Path
import subprocess
import tempfile
from saturn_vdp_wip_test import method

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=ROOT / 'src/mame/sega/saturn_vdp1.cpp')
args = parser.parse_args()
fixture = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
struct attotime {
    int64_t ticks=0;
    static attotime from_usec(int64_t n) { return {n}; }
    static const attotime never;
    attotime operator-(attotime b)const { return {ticks-b.ticks}; }
    int64_t as_ticks(unsigned hz)const { return ticks; }
};
const attotime attotime::never{INT64_MAX};
struct timer { attotime expiry; void adjust(attotime t) { expiry=t; } };
struct machine_stub { attotime now; attotime time()const { return now; } };
struct saturn_vdp1_device {
    static constexpr int VBE_SAMPLE_DELAY_US=63;
    bool m_vblank=false, m_hblank=false, m_frame_change_pending=false;
    bool m_vb_erase_active=false;
    attotime m_vblank_start;
    timer t, *m_vbe_timer=&t;
    machine_stub m;
    unsigned changes=0, m_edsr=3, m_fbcr=0, sampled_fbcr=0;
    int64_t erase_budget=-1;
    machine_stub& machine() { return m; }
    unsigned clock()const { return 1; }
    void erase_limited(int64_t budget) {
        // Erase finishes against the old display buffer before a swap.
        assert(changes==0); erase_budget=budget;
    }
    void frame_change() { ++changes; m_edsr >>= 1; sampled_fbcr=m_fbcr; }
    void vblank_w(int);
    void hblank_w(int);
};
// METHODS
int main() {
    saturn_vdp1_device d;
    d.m.now={100}; d.vblank_w(1); d.m_vb_erase_active=true;
    d.hblank_w(1); assert(d.changes==0);
    d.m.now={200}; d.vblank_w(0);
    assert(d.changes==0 && d.m_edsr==3);
    assert(d.erase_budget==100 && !d.m_vb_erase_active);
    // Software can still request a manual change after VBLANK-OUT.
    d.m_fbcr=3;
    d.hblank_w(1); assert(d.changes==0); // repeated level is not an edge
    d.hblank_w(0); assert(d.changes==0);
    d.m.now={230}; d.hblank_w(1);
    assert(d.changes==1 && d.sampled_fbcr==3 && d.m_edsr==1);
    assert(!d.m_frame_change_pending && d.erase_budget==100);
    d.hblank_w(1); d.hblank_w(0); d.hblank_w(1);
    assert(d.changes==1);
    d.vblank_w(0); d.hblank_w(0); d.hblank_w(1);
    assert(d.changes==1); // repeated vertical level cannot re-arm
    d.vblank_w(1); d.hblank_w(0); d.hblank_w(1);
    assert(d.changes==1); // no frame change during vertical blank
    d.vblank_w(0); d.hblank_w(0); d.hblank_w(1);
    assert(d.changes==2);
    std::cout << "VDP1 FBCR access-window and erase-end timing PASS\n";
}
'''
source = args.source.read_text()
methods = '\n'.join(method(source, name) for name in ('vblank_w', 'hblank_w'))
with tempfile.TemporaryDirectory(prefix='saturn-vdp1-frame-edge-') as directory:
    cpp = Path(directory) / 'test.cpp'
    cpp.write_text(fixture.replace('// METHODS', methods))
    binary = cpp.with_suffix('')
    subprocess.run(['clang++', '-std=c++17', '-O1', '-fsanitize=address,undefined', str(cpp), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
