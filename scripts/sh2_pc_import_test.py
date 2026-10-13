#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual SH2 state import: PC edits cancel pending delay slots through every alias."""
from pathlib import Path
import subprocess
import sys
import tempfile
root=Path(__file__).resolve().parent.parent
source=(Path(sys.argv[1]) if len(sys.argv)>1 else root/'src/devices/cpu/sh/sh2.cpp').read_text()
a=source.index('void sh2_device::state_import(');b=source.index('\nvoid sh2_device::execute_set_input(',a)
code=r'''
#include <cassert>
#include <cstdint>
using uint32_t=std::uint32_t;
enum {STATE_GENPC=-1,STATE_GENPCBASE=-2,SH4_PC=1,SH_SR=2};
struct device_state_entry {int value;int index() const {return value;}};
struct sh2_device {
 struct state {uint32_t m_delay=0x100;} storage,*m_sh2_state=&storage;
 bool m_zero_delay_pending=true;unsigned checks=0;
 void check_pending_irq(const char*){++checks;}
 void state_import(const device_state_entry&);
};
METHOD
int main(){
 sh2_device d;
 for(int entry:{SH4_PC,STATE_GENPC,STATE_GENPCBASE}){
  d.storage.m_delay=0x100;d.m_zero_delay_pending=true;
  d.state_import({entry});assert(d.storage.m_delay==0&&!d.m_zero_delay_pending);
 }
 d.storage.m_delay=0x100;d.m_zero_delay_pending=true;
 d.state_import({SH_SR});assert(d.checks==1&&d.storage.m_delay==0x100&&d.m_zero_delay_pending);
}
'''.replace('METHOD',source[a:b]).replace('#include <cassert>','#include <cassert>\n#include <initializer_list>')
with tempfile.TemporaryDirectory(prefix='sh2-pc-import-') as directory:
 out=Path(directory);(out/'test.cpp').write_text(code)
 subprocess.run(['clang++','-std=c++20','-O1','-g','-fsanitize=address,undefined',str(out/'test.cpp'),'-o',str(out/'test')],check=True)
 subprocess.run([str(out/'test')],check=True)
print('SH2 PC aliases/delay state ASan/UBSan PASS')
