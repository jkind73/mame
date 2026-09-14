#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Execute shared HALT callbacks/reset; copied latches are not MAME save-manager proof."""
from pathlib import Path
import os, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[2]
source=(ROOT/'src/mame/sega/saturn.cpp').read_text()
def extract(signature):
    start=source.index(signature);end=source.index('{',start)+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]
functions='\n'.join(extract('void saturn_state::'+s) for s in ('update_halt_lines()', 'system_halt_w(', 'main_dma_halt_w(', 'sound_dma_halt_w(', 'reset_halt_state()'))
start=extract('void saturn_state::machine_start()')
for field in ('m_system_halt','m_main_dma_halt','m_sound_dma_halt'):
    assert f'save_item(NAME({field}))' in start
assert 'register_postload' in start and 'FUNC(saturn_state::update_halt_lines)' in start
assert 'reset_halt_state();' in extract('void saturn_state::machine_reset()')
for name,cls in [('sat_console','sat_console_state'),('stv','stv_state')]:
    config=(ROOT/f'src/mame/sega/{name}.cpp').read_text()
    for bus in ('main','sound'):
        assert f'{bus}_dtack_cb().set(FUNC({cls}::{bus}_dma_halt_w))' in config
harness=r'''
#include <cassert>
#include <iostream>
constexpr int INPUT_LINE_HALT=1, ASSERT_LINE=1, CLEAR_LINE=0;
struct cpu {bool halt=false;void set_input_line(int line,int value){assert(line==INPUT_LINE_HALT);halt=value;}};
struct saturn_state {
 bool m_system_halt=false,m_main_dma_halt=false,m_sound_dma_halt=false;
 cpu main,slave,sound;cpu *m_maincpu=&main,*m_slave=&slave,*m_audiocpu=&sound;
 void update_halt_lines();void reset_halt_state();void system_halt_w(int);void main_dma_halt_w(int);void sound_dma_halt_w(int);
};
// FUNCTIONS
int main(){
 unsigned cases=0;
 for(unsigned sequence=0;sequence<1296;++sequence){
  saturn_state s;bool expected[3]{};unsigned code=sequence;
  for(unsigned step=0;step<4;++step){
   unsigned event=code%6;code/=6;expected[event/2]=event&1;
   switch(event/2){case 0:s.system_halt_w(event&1);break;case 1:s.main_dma_halt_w(event&1);break;case 2:s.sound_dma_halt_w(event&1);break;}
   assert(s.main.halt==(expected[0]||expected[1])&&s.slave.halt==s.main.halt);
   assert(s.sound.halt==(expected[0]||expected[2]));
   saturn_state restored;restored.m_system_halt=s.m_system_halt;restored.m_main_dma_halt=s.m_main_dma_halt;restored.m_sound_dma_halt=s.m_sound_dma_halt;
   restored.update_halt_lines();assert(restored.main.halt==s.main.halt&&restored.sound.halt==s.sound.halt);
  }
  s.reset_halt_state();assert(!s.main.halt&&!s.slave.halt&&!s.sound.halt);
  assert(!s.m_system_halt&&!s.m_main_dma_halt&&!s.m_sound_dma_halt);++cases;
 }
 std::cout<<"Shared HALT: "<<cases<<" event sequences passed\n";
}
'''.replace('// FUNCTIONS',functions)
with tempfile.TemporaryDirectory(prefix='saturn-halt-') as tmp:
    src=Path(tmp)/'test.cpp';exe=Path(tmp)/'test';src.write_text(harness)
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-pie','-no-pie',str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
