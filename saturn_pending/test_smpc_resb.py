#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Compile RESB candidate methods against a recording input/timer endpoint.

This checks VBlank sampling, command independence and NMI-enable independence,
not physical switch debounce or MAME's actual save manager.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-root', type=Path, required=True)
p.add_argument('--mutant', choices=('idle', 'disable', 'immediate', 'overwrite'))
a = p.parse_args()
source = (a.source_root/'src/mame/sega/smpc.cpp').read_text()
header = (a.source_root/'src/mame/sega/smpc.h').read_text()
console = (a.source_root/'src/mame/sega/sat_console.cpp').read_text()


def extract(signature):
    begin = source.index(signature)
    end = source.index('{', begin)+1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[begin:end]


assert 'save_item(NAME(m_resb));' in extract('void smpc_hle_device::device_start()')
assert 'm_resb = false;' in extract('void smpc_hle_device::device_reset()')
assert 'bool m_resb = false;' in header
assert 'reset_button_in_handler().set_ioport(":RESET").bit(0);' in console
functions = '\n'.join(extract(s) for s in (
    'uint8_t smpc_hle_device::status_register_r()',
    'void smpc_hle_device::vblank_in()',
    'inline void smpc_hle_device::sr_ack()',
    'inline void smpc_hle_device::sr_set(',
    'inline void smpc_hle_device::sf_ack('))
mutations = {
    'idle': ('m_resb = bool(m_reset_button_read());',
             'if (m_intback_stage) m_resb = bool(m_reset_button_read());'),
    'disable': ('m_resb = bool(m_reset_button_read());',
                'if (m_NMI_reset) m_resb = bool(m_reset_button_read());'),
    'immediate': ('(m_resb ? 0x10 : 0)', '(m_reset_button_read() ? 0x10 : 0)'),
    'overwrite': ('return (m_sr & ~0x10) | (m_resb ? 0x10 : 0);', 'return m_sr;'),
}
if a.mutant:
    old, new = mutations[a.mutant]
    assert functions.count(old) == 1
    functions = functions.replace(old, new)

harness = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
struct timer{void reset(){}};
struct smpc_hle_device {
 bool m_has_ctrl_ports=true,m_command_in_progress=false,m_resb=false,m_NMI_reset=false;
 bool m_sf=false,m_cd_sf=false,button=false;
 uint8_t m_sr=0,m_comreg=0,m_intback_buf[3]{};
 unsigned m_intback_stage=0,m_peripheral_size=38,m_peripheral_pos=32,reads=0;
 timer cmd,cont;timer *m_cmd_timer=&cmd,*m_intback_timer=&cont;
 int m_reset_button_read(){++reads;return button;}
 uint8_t status_register_r();void vblank_in();void sr_ack();void sr_set(uint8_t);void sf_ack(bool);
};
// FUNCTIONS
int main(){
 unsigned cases=0;
 for(unsigned sr=0;sr<256;++sr)for(bool initial:{false,true})
 for(bool button:{false,true})for(bool enable:{false,true})
 for(unsigned stage=0;stage<3;++stage){
  smpc_hle_device s;s.m_sr=sr;s.m_resb=initial;s.button=button;s.m_NMI_reset=enable;s.m_intback_stage=stage;
  assert(s.status_register_r()==((sr&~0x10)|(initial?0x10:0))&&s.reads==0);
  s.vblank_in();unsigned after=stage?(sr&~0x60):sr;
  assert(s.reads==1&&s.m_resb==button&&s.m_NMI_reset==enable);
  assert(s.status_register_r()==((after&~0x10)|(button?0x10:0)));
  s.button=!button;
  assert(s.status_register_r()==((after&~0x10)|(button?0x10:0))&&s.reads==1);
  s.sr_set(uint8_t(~sr));
  assert(s.status_register_r()==(((~sr)&0xef)|(button?0x10:0)));
  s.sr_ack();
  assert(s.status_register_r()==(((~sr)&0x0f)|(button?0x10:0)));
  s.vblank_in();
  assert(s.m_resb==!button&&s.reads==2);
  assert((s.status_register_r()&0x10)==(!button?0x10:0));
  ++cases;
 }
 smpc_hle_device stv;stv.m_has_ctrl_ports=false;stv.button=true;stv.m_sr=0xc0;
 stv.vblank_in();assert(stv.reads==0&&!stv.m_resb&&stv.status_register_r()==0xc0);
 assert(cases==6144);
 std::cout<<cases<<" RESB latch/read/command/enable combinations and ST-V isolation passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='smpc-resb-') as tmp:
    d = Path(tmp)
    cpp = d/'test.cpp'
    exe = d/'test'
    cpp.write_text(harness.replace('// FUNCTIONS', functions))
    subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O1', '-g',
                    '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
