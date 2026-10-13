#!/usr/bin/env python3
# license:BSD-3-Clause
"""Check the actual Mission Stick read/reset methods against Sega Table 3.19."""
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parent.parent
source = (Path(sys.argv[1]) if len(sys.argv)>1 else root/'src/devices/bus/sat_ctrl/analog.cpp').read_text()
reset = source[source.index('void saturn_analog_device::device_reset()'):source.index('//-------------------------------------------------\n//  read_ctrl')]
read = source[source.index('uint8_t saturn_analog_device::read_ctrl'):]
fixture = r'''
#include <cstdint>
#include <cassert>
struct input { uint16_t value=0xffff; input *operator->(){return this;} uint16_t read(){return value;} };
struct saturn_analog_device {
 input m_joy,m_anx,m_any,m_anz;
 uint8_t m_directions=0xf0;
 void device_reset();uint8_t read_ctrl(uint8_t);
};
METHODS
int main(){
 saturn_analog_device d;d.m_anx.value=d.m_any.value=128;d.m_anz.value=0;
 d.device_reset();assert(d.read_ctrl(0)==0xff);
 // Independent one-axis sweeps: upper/lower inclusive release thresholds
 // differ from assertion thresholds. Exercise every ADC code both ways.
 for(unsigned axis=0;axis<2;++axis){
  auto &a=axis?d.m_any:d.m_anx;unsigned high=axis?0x20:0x80,low=axis?0x10:0x40;
  d.m_anx.value=d.m_any.value=128;d.device_reset();
  for(unsigned v=0;v<256;++v){a.value=v;auto r=d.read_ctrl(0);assert(bool(r&high)==(v<170));assert(bool(r&low)==(v>=107));}
  for(int v=255;v>=0;--v){a.value=v;auto r=d.read_ctrl(0);assert(bool(r&high)==(v<=149));assert(bool(r&low)==(v>86));}
  // Neutral deadband has different results depending on approach.
  a.value=170;assert(!(d.read_ctrl(0)&high));a.value=160;assert(!(d.read_ctrl(0)&high));
  auto saved=d.m_directions;d.device_reset();assert(d.read_ctrl(0)&high);
  d.m_directions=saved;assert(!(d.read_ctrl(0)&high));a.value=149;assert(d.read_ctrl(0)&high);
  a.value=86;assert(!(d.read_ctrl(0)&low));a.value=96;assert(!(d.read_ctrl(0)&low));
  a.value=107;assert(d.read_ctrl(0)&low);
 }
 d.m_anx.value=d.m_any.value=128;d.device_reset();
 // Preserve all nine active-low buttons and the three fixed high bits.
 for(unsigned b=3;b<12;++b){d.m_joy.value=uint16_t(~(1U<<b));assert(d.read_ctrl(0)==uint8_t(0xff&~((1U<<b)>>8)));assert(d.read_ctrl(1)==uint8_t(~(1U<<b)));}
 d.m_joy.value=0xffff;
 for(unsigned v=0;v<256;++v){d.m_anx.value=v;d.m_any.value=255-v;d.m_anz.value=v;assert(d.read_ctrl(2)==v);assert(d.read_ctrl(3)==255-v);assert(d.read_ctrl(4)==v);}
}
'''.replace('METHODS',reset+'\n'+read)
with tempfile.TemporaryDirectory(prefix='saturn-mission-stick-') as directory:
    out=Path(directory);(out/'test.cpp').write_text(fixture)
    subprocess.run(['clang++','-std=c++17','-O1','-g','-fsanitize=address,undefined',str(out/'test.cpp'),'-o',str(out/'test')],check=True)
    subprocess.run([str(out/'test')],check=True)
print('Mission Stick ADC hysteresis, buttons and analog bytes PASS')
