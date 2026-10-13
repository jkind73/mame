#!/usr/bin/env python3
# license:BSD-3-Clause
"""Compare current fetch code with the proposed NBG2/3 B-bank latency four.

The recorded Megamix B0/T1 PN + A0/T0 CP case is unchanged. B0/T5 is a
positive control: it changes, demonstrating the candidate is actually exercised.
This is a source-derived fetch trace, not a hardware oracle or full game test.
"""
from pathlib import Path
import subprocess
import tempfile

root=Path(__file__).resolve().parent.parent
source=(root/'src/mame/sega/saturn_vdp2_fetch.h').read_text()
candidate=source
changes={
    'unsigned cell;\n    pattern_name value;':'unsigned cell;\n    unsigned bank;\n    pattern_name value;',
    'history[index].slot + int(latency) <= slot':'history[index].slot + int(layer >= 2 && history[index].bank >= 2 ? 4 : latency) <= slot',
    'read{slot, cycle, cell, access.read_pn(address)}':'read{slot, cycle, cell, access.bank(address), access.read_pn(address)}',
}
for before,after in changes.items():
    assert candidate.count(before)==1,before
    candidate=candidate.replace(before,after)
fixture=r'''
#include "fetch.h"
#include <cstdio>
#include <cstdlib>
using namespace saturn_vdp2_fetch;
struct access {
 unsigned pn_bank=2;
 unsigned cycle_x(int cycle) const {return cycle*8;}
 unsigned cycle_y(int) const {return 0;}
 uint32_t pn_address(unsigned x,unsigned) const {return (pn_bank<<17)+x;}
 unsigned bank(uint32_t a) const {return (a>>17)&3;}
 pattern_name read_pn(uint32_t a) const {pattern_name p;p.character=(a&0x1ffff)/8+1;return p;}
 uint32_t read32(uint32_t a) const {std::printf("CP %u\n",a);return 0x11111111;}
};
int main(int argc,char**argv){
 unsigned slot=std::atoi(argv[1]),bank=std::atoi(argv[2]);
 schedule s;s.raw[bank][slot]=s.command[bank][slot]=2;
 s.raw[0][0]=s.command[0][0]=6;
 access a;a.pn_bank=bank;carry_state carry;
 fetch_line(s,2,0,false,{},bitmap_config{},8,a,carry,[](int,cycle_dots const&){});
}
'''
with tempfile.TemporaryDirectory(prefix='megamix-latency-') as directory:
    out=Path(directory)
    (out/'probe.cpp').write_text(fixture)
    binaries=[]
    for name,header in [('baseline',source),('candidate',candidate)]:
        path=out/name;path.mkdir();(path/'fetch.h').write_text(header)
        binary=path/'probe';binaries.append(binary)
        subprocess.run(['clang++','-std=c++20','-O1','-g','-fsanitize=address,undefined','-I'+str(path),str(out/'probe.cpp'),'-o',str(binary)],check=True)
    for bank,slot,different in [(2,1,False),(2,5,True),(0,5,False)]:
        traces=[subprocess.check_output([str(binary),str(slot),str(bank)]) for binary in binaries]
        assert (traces[0]!=traces[1])==different
        print(f'PN bank {bank} T{slot}, CP A0 T0: '+('changed (positive control)' if different else 'unchanged'))
