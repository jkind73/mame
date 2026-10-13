#!/usr/bin/env python3
# license:BSD-3-Clause
"""Check the actual SCSP send/pan lookup construction against binary gains."""
from pathlib import Path
import argparse
import subprocess
import tempfile
root=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,default=root/'src/devices/sound/scsp.cpp')
args=parser.parse_args()
source=args.source.read_text()
start=source.index('\tfor (i = 0; i < 0x10000; ++i)')
end=source.index('\n\tLFO_Init();',start)
fixture=r'''
#include <cmath>
#include <cstdint>
#include <cassert>
#define SHIFT 12
#define FIX(v) ((uint32_t)(float(1<<SHIFT)*(v)))
int main() {
 int i; int m_LPANTABLE[65536],m_RPANTABLE[65536];
'''
tests=r'''
 for(unsigned send=0;send<8;++send)for(unsigned pan=0;pan<32;++pan) {
  unsigned index=(send<<13)|(pan<<8);
  unsigned level=send ? 16384U>>(send^7) : 0;
  unsigned muted=level>>( (pan&15)>>1 );
  if(pan&1)muted-=muted/4;
  if((pan&15)==15)muted=0;
  assert(m_LPANTABLE[index]==int(pan&16 ? level : muted));
  assert(m_RPANTABLE[index]==int(pan&16 ? muted : level));
  for(unsigned tl=0;tl<256;++tl) {
   assert(m_LPANTABLE[index|tl]>=0 && m_LPANTABLE[index|tl]<=m_LPANTABLE[index]);
   assert(m_RPANTABLE[index|tl]>=0 && m_RPANTABLE[index|tl]<=m_RPANTABLE[index]);
  }
 }
 assert(m_LPANTABLE[(7<<13)|(1<<8)]==12288); // quarter subtraction
 assert(m_RPANTABLE[1<<13]==256); // six exact halving steps
}
'''
with tempfile.TemporaryDirectory(prefix='scsp-mix-level-') as directory:
 out=Path(directory);(out/'test.cpp').write_text(fixture+('static const float SDLT[8]={-1000000,-36,-30,-24,-18,-12,-6,0};\n' if 'SDLT[iSDL]' in source[start:end] else '')+source[start:end]+tests)
 subprocess.run(['clang++','-std=c++20','-O1','-g','-fsanitize=address,undefined',str(out/'test.cpp'),'-o',str(out/'test')],check=True)
 subprocess.run([str(out/'test')],check=True)
print('SCSP send/pan lookup ASan/UBSan checks passed: all 65536 entries')
