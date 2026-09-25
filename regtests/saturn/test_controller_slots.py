#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Exercise actual controller/tap dispatch and SMPC packing with recording pads.

Unlike a flattened fake report, empty sockets retain physical positions here.
No serial timing or real save-manager qualification follows from this test.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[2])
p.add_argument('--mutant', choices=('compressed', 'alias', 'empty-data', 'child-index'))
a = p.parse_args()


def extract(path, signature):
    source = (a.source_root/path).read_text()
    begin = source.index(signature)
    end = source.index('{', begin)+1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[begin:end]


base = 'src/devices/bus/sat_ctrl/'
method = (extract(base+'ctrl.h', 'virtual uint8_t read_ctrl_slot(') + '\n' +
          extract(base+'ctrl.h', 'virtual uint8_t read_ext_size('))
functions = '\n'.join(extract(base+'ctrl.cpp', 'uint8_t saturn_control_port_device::'+name)
                      for name in ('read_ctrl(', 'read_ctrl_slot(', 'read_status(', 'read_id(', 'read_ext_size('))
for device in ('multitap', 'segatap'):
    functions += '\n'+'\n'.join(extract(base+device+'.cpp', 'uint8_t saturn_'+device+'_device::'+name)
                               for name in ('read_ctrl(', 'read_ctrl_slot(', 'read_id('))
functions += '\n'+extract('src/mame/sega/smpc.cpp', 'void smpc_hle_device::read_saturn_ports()')
if a.mutant == 'compressed':
    functions = functions.replace('    for (unsigned i = 0;', '    unsigned offset = 0;\n    for (unsigned i = 0;')
    functions = functions.replace('ctrl->read_ctrl_slot(i, j);', 'ctrl->read_ctrl(offset + j);\n      offset += size;')
if a.mutant == 'alias':
    functions = functions.replace('m_subctrl_port[index]', 'm_subctrl_port[0]')
if a.mutant == 'empty-data':
    functions = functions.replace('id == 0xff ? 0 : (id & 0xf)', '(id & 0xf)')
if a.mutant == 'child-index':
    functions = functions.replace('->read_ctrl_slot(0, offset)', '->read_ctrl_slot(index, offset)')

harness = r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>
struct device_saturn_control_port_interface {
 virtual ~device_saturn_control_port_interface()=default;
 virtual uint8_t read_ctrl(uint8_t){return 0;}
 virtual uint8_t read_status(){return 0xf0;}
 virtual uint8_t read_id(int){return 0xff;}
 // DEFAULT_METHOD
};
struct saturn_control_port_device {
 device_saturn_control_port_interface *m_device=nullptr;
 uint8_t read_ctrl(uint8_t);uint8_t read_ctrl_slot(unsigned,uint8_t);
 uint8_t read_status();uint8_t read_id(int);uint8_t read_ext_size(unsigned);
};
struct joy:device_saturn_control_port_interface {
 uint16_t value=0;unsigned reads=0;
 uint8_t read_ctrl(uint8_t off)override{++reads;return off<2?uint8_t(value>>(off?0:8)):0xff;}
 uint8_t read_id(int)override{return 2;}
 uint8_t read_status()override{return 0xf1;}
};
struct saturn_multitap_device:device_saturn_control_port_interface {
 std::array<saturn_control_port_device*,6> m_subctrl_port;
 uint8_t read_ctrl(uint8_t)override;uint8_t read_ctrl_slot(unsigned,uint8_t)override;
 uint8_t read_id(int)override;uint8_t read_status()override{return 0x16;}
};
struct saturn_segatap_device:device_saturn_control_port_interface {
 std::array<saturn_control_port_device*,4> m_subctrl_port;
 uint8_t read_ctrl(uint8_t)override;uint8_t read_ctrl_slot(unsigned,uint8_t)override;
 uint8_t read_id(int)override;uint8_t read_status()override{return 4;}
};
struct smpc_hle_device {
 saturn_control_port_device *m_ctrl1=nullptr,*m_ctrl2=nullptr;
 uint8_t m_peripheral_data[512]{};unsigned m_peripheral_size=0,m_peripheral_pos=0,m_pmode=0;
 void read_saturn_ports();
};
// FUNCTIONS
int main(){
 unsigned cases=0;
 for(unsigned mask1=0;mask1<64;++mask1)for(unsigned mask2=0;mask2<16;++mask2)
 for(unsigned mode1:{0u,1u,3u})for(unsigned mode2:{0u,1u,3u}) {
  std::array<joy,10> pads;std::array<saturn_control_port_device,10> slots;
  saturn_multitap_device tap1;saturn_segatap_device tap2;
  for(unsigned i=0;i<10;++i){
   pads[i].value=0xa100+i*0x103;
   bool connected=i<6?bool(mask1&(1<<i)):bool(mask2&(1<<(i-6)));
   slots[i].m_device=connected?&pads[i]:nullptr;
   if(i<6)tap1.m_subctrl_port[i]=&slots[i];else tap2.m_subctrl_port[i-6]=&slots[i];
  }
  saturn_control_port_device ports[2];ports[0].m_device=&tap1;ports[1].m_device=&tap2;
  smpc_hle_device s;s.m_ctrl1=&ports[0];s.m_ctrl2=&ports[1];s.m_pmode=mode1|(mode2<<2);
  std::vector<uint8_t> want;
  for(unsigned port=0;port<2;++port){
   if((port?mode2:mode1)==3)continue;
   unsigned count=port?4:6,base=port?6:0,mask=port?mask2:mask1;
   want.push_back(port?4:0x16);
   for(unsigned i=0;i<count;++i){
    if(!(mask&(1<<i))){want.push_back(0xff);continue;}
    want.push_back(2);want.push_back(pads[base+i].value>>8);want.push_back(pads[base+i].value&255);
   }
  }
  s.read_saturn_ports();
  assert(s.m_peripheral_size==want.size());
  assert(std::vector<uint8_t>(s.m_peripheral_data,s.m_peripheral_data+s.m_peripheral_size)==want);
  for(unsigned i=0;i<10;++i){
   bool enabled=(i<6?mode1:mode2)!=3;
   assert(pads[i].reads==(enabled&&slots[i].m_device?2u:0u));
  }
  assert(tap1.read_ctrl_slot(6,0)==0xff&&tap1.read_ctrl_slot(1000,0)==0xff);
  assert(tap2.read_ctrl_slot(4,0)==0xff&&tap2.read_ctrl_slot(1000,0)==0xff);
  ++cases;
 }
 joy direct;direct.value=0xabcd;saturn_control_port_device p;p.m_device=&direct;
 assert(p.read_ctrl_slot(0,0)==0xab&&p.read_ctrl_slot(0,1)==0xcd);
 assert(p.read_ctrl_slot(1,0)==0xff&&direct.reads==2);
 p.m_device=nullptr;assert(p.read_ctrl_slot(0,0)==0xff);
 assert(p.read_id(0)==0xff&&p.read_status()==0xf0);
 assert(cases==9216);
 std::cout<<cases<<" physical tap topology/mode reports plus direct/empty/bounds checks passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='saturn-slots-') as tmp:
    d = Path(tmp)
    cpp = d/'test.cpp'
    exe = d/'test'
    cpp.write_text(harness.replace('// DEFAULT_METHOD', method).replace('// FUNCTIONS', functions))
    subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O1', '-g',
                    '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
