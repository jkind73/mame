#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Compile production timeout bodies with recording timers/IRQs, not live MAME.

An optional --source-root can point to a separate candidate copy.
Save registration assertions are source checks, not live save-manager evidence.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[2])
p.add_argument('--mutant', choices=('pending', 'continue', 'sf', 'status', 'stv', 'hook', 'edge', 'irq'))
a = p.parse_args()


def extract(text, signature):
    begin = text.index(signature)
    end = text.index('{', begin) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[begin:end]


smpc = (a.source_root/'src/mame/sega/smpc.cpp').read_text()
host = (a.source_root/'src/mame/sega/saturn.cpp').read_text()
header = (a.source_root/'src/mame/sega/saturn.h').read_text()
# Registration/init checks are source checks, not a real save-manager roundtrip.
for field in ('m_prev_hint', 'm_prev_vint'):
    assert 'save_item(NAME('+field+'));' in extract(host, 'void saturn_state::machine_start()')
assert 'm_prev_hint = m_prev_vint = 0;' in extract(host, 'void saturn_state::machine_reset()')
assert 'int m_prev_hint = 0, m_prev_vint = 0;' in header
functions = '\n'.join((extract(smpc, 'void smpc_hle_device::vblank_in()'),
                       extract(smpc, 'inline void smpc_hle_device::sf_ack('),
                       extract(host, 'void saturn_state::vint_callback(')))
mutations = {
    'pending': ('bool const pending = m_command_in_progress', 'bool const pending = false && m_command_in_progress'),
    'continue': ('m_intback_timer->reset();', '(void)0;'),
    'sf': ('if (!m_command_in_progress)', 'if (true)'),
    'status': ('m_sr &= ~0x60;', 'm_sr = 0;'),
    'stv': ('if (!m_has_ctrl_ports)', 'if (false)'),
    'hook': ('m_smpc_hle->vblank_in();', '(void)0;'),
    'edge': ('if (state) {', 'if (!state) {'),
    'irq': ('m_intback_timer->reset();', 'm_intback_timer->reset(); irq_request();'),
}
if a.mutant:
    before, after = mutations[a.mutant]
    assert functions.count(before) == 1
    functions = functions.replace(before, after)

HARNESS = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
struct timer {
 bool pending=false; unsigned resets=0;
 void reset(){pending=false;++resets;}
};
struct smpc_hle_device {
 bool m_resb=false,m_has_ctrl_ports=true,m_command_in_progress=false,m_sf=false,m_cd_sf=false;
 uint8_t m_comreg=0,m_intback_buf[3]{},m_sr=0;
 unsigned m_intback_stage=0,m_peripheral_size=38,m_peripheral_pos=32,irqs=0;
 timer command,continuation;
 timer *m_cmd_timer=&command,*m_intback_timer=&continuation;
 int m_reset_button_read(){return 0;}
 void sf_ack(bool);void vblank_in();void irq_request(){++irqs;}
};
struct scu {
 unsigned in=0,out=0;
 smpc_hle_device *s=nullptr;
 void vblank_in_w(int n){assert(n==1);if(s)assert(s->m_intback_stage==0);++in;}
 void vblank_out_w(int n){assert(n==1);++out;}
};
struct cpu {
 unsigned calls=0;int last=0;
 void set_input_line(int line,int state){assert(state==1);last=line;++calls;}
};
constexpr int ASSERT_LINE=1;
struct saturn_state {
 bool m_prev_vint=false;
 smpc_hle_device *m_smpc_hle;scu *m_scu;cpu *m_slave;
 void vint_callback(int);
};
// FUNCTIONS
int main(){
 unsigned cases=0;
 for(bool ports:{false,true}) for(unsigned stage=0;stage<3;++stage)
 for(bool active:{false,true}) for(unsigned command:{0u,0x10u,0x18u})
 for(unsigned pen:{0u,8u}) for(unsigned sr=0;sr<256;++sr)
 for(bool sf:{false,true}) for(bool cd:{false,true}) {
  smpc_hle_device s;
  s.m_has_ctrl_ports=ports;s.m_intback_stage=stage;s.m_command_in_progress=active;
  s.command.pending=active;s.continuation.pending=stage!=0;
  s.m_comreg=command;s.m_intback_buf[1]=pen;s.m_sr=sr;s.m_sf=sf;s.m_cd_sf=cd;
  bool pending=active&&command==0x10&&pen;
  bool cancel=ports&&(stage||pending);
  bool command_after=active&&!(cancel&&pending);
  s.vblank_in();
  assert(s.m_intback_stage==(cancel?0:stage));
  assert(s.m_peripheral_size==(cancel?0u:38u)&&s.m_peripheral_pos==(cancel?0u:32u));
  assert(s.command.pending==command_after&&s.m_command_in_progress==command_after);
  assert(s.command.resets==unsigned(cancel&&pending));
  assert(s.continuation.pending==(!cancel&&stage!=0));
  assert(s.continuation.resets==unsigned(cancel));
  assert(s.m_sr==(cancel?(sr&0x9f):sr));
  assert(s.m_sf==((cancel&&!command_after)?false:sf));
  assert(s.m_cd_sf==((cancel&&!command_after)?false:cd));
  assert(s.irqs==0);
  ++cases;
 }
 // Real driver callback: rising edge cancels before SCU IRQ; repeated high
 // and falling edges cannot cancel a new report. Its previous-level field
 // is now explicitly initialized/reset and save-registered by the candidate.
 smpc_hle_device s;scu u;cpu c;saturn_state host{false,&s,&u,&c};
 s.m_intback_stage=2;u.s=&s;
 host.vint_callback(1);
 assert(s.m_intback_stage==0&&u.in==1&&u.out==0&&c.last==6&&c.calls==1);
 s.m_intback_stage=2;u.s=nullptr;host.vint_callback(1);
 assert(s.m_intback_stage==2&&u.in==1&&c.calls==1);
 host.vint_callback(0);
 assert(s.m_intback_stage==2&&u.out==1&&c.last==4&&c.calls==2);
 host.vint_callback(0);
 assert(s.m_intback_stage==2&&u.out==1&&c.calls==2);
 assert(cases==73728);
 std::cout<<cases<<" timeout state combinations and four VBlank edge/order checks passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='smpc-timeout-') as temp:
    root = Path(temp)
    cpp = root/'test.cpp'
    exe = root/'test'
    cpp.write_text(HARNESS.replace('// FUNCTIONS', functions))
    subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O1', '-g',
                    '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
