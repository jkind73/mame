#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production MPOFN/MPOFR three-bit decoding (ST-058 pp.85–86).

Actual macros, not injected pre-decoded map offsets. Address arithmetic does not
replace linked renderer qualification.
"""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--mutation',choices=('N0','N1','N2','N3','RA','RB'));a=p.parse_args()
src=(ROOT/'src/mame/sega/saturn.cpp').read_text()
names=('VDP2_MPOFN_','VDP2_MPOFR_')+tuple('VDP2_'+n+'MP_' for n in ('N0','N1','N2','N3','RA','RB'))
macros='\n'.join(re.search(r'^#define '+n+r' .*$',src,re.M)[0] for n in names)
if a.mutation:
 line=re.search(r'^#define VDP2_'+a.mutation+r'MP_ .*$',macros,re.M)[0]
 macros=macros.replace(line,line.replace('0x0007','0x0003').replace('0x0070','0x0030').replace('0x0700','0x0300').replace('0x7000','0x3000'))
code=r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
// MACROS
int main(){uint16_t m_vdp2_regs[256]{};unsigned cases=0;
 for(unsigned raw=0;raw<65536;++raw){
  m_vdp2_regs[0x3c/2]=raw;m_vdp2_regs[0x3e/2]=raw;
  std::array<unsigned,6> actual={unsigned(VDP2_N0MP_),unsigned(VDP2_N1MP_),unsigned(VDP2_N2MP_),unsigned(VDP2_N3MP_),unsigned(VDP2_RAMP_),unsigned(VDP2_RBMP_)};
  for(unsigned layer=0;layer<6;++layer){
   unsigned expected=(raw/(1u<<((layer%4)*4)))%8;
   assert(actual[layer]==expected);
   for(unsigned capacity:{524288u,1048576u}){
    assert(((actual[layer]*0x20000)&(capacity-1))==(expected*131072)%capacity);
    for(unsigned low:{0u,31u,63u})assert((((actual[layer]<<6)|low)*2048&(capacity-1))==((expected*64+low)*2048)%capacity);
   }
   ++cases;
  }
 }
 std::cout<<cases<<" map-offset register-field/bank/address cases passed\n";
}
'''.replace('// MACROS',macros)
with tempfile.TemporaryDirectory(prefix='saturn-map-offset-regs-') as d:
 cpp=Path(d)/'test.cpp';exe=Path(d)/'test';cpp.write_text(code)
 subprocess.run([os.environ.get('CXX','c++'),'-std=c++20','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
