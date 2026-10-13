#!/usr/bin/env python3
# license:BSD-3-Clause
"""Exercise real SMPC collection and tap routing with every sparse connection mask."""
from pathlib import Path
import subprocess
import sys
import tempfile

root=Path(__file__).resolve().parent.parent
bus=root/'src/devices/bus/sat_ctrl'
def method(path,signature):
    s=path.read_text();a=s.index(signature);b=s.index('{',a);depth=1;i=b+1
    while depth:
        depth+=(s[i]=='{')-(s[i]=='}');i+=1
    return s[a:i]
code='\n'.join(method(bus/'ctrl.cpp','uint8_t saturn_control_port_device::'+f) for f in ('read_status()','read_id(int idx)','read_ctrl_at(int idx, uint8_t offset)'))
for name in ('multitap','segatap'):
    for f in ('read_id(int idx)','read_ctrl_at(int idx, uint8_t offset)'):
        code+='\n'+method(bus/(name+'.cpp'),'uint8_t saturn_'+name+'_device::'+f)
code+='\n'+method(Path(sys.argv[1]) if len(sys.argv)>1 else root/'src/mame/sega/smpc.cpp','void smpc_hle_device::read_saturn_ports()')
fixture=r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <vector>
struct peripheral {
 virtual uint8_t read_status(){return 0xf1;}
 virtual uint8_t read_id(int){return 0x02;}
 virtual uint8_t read_ctrl(uint8_t){return 0xff;}
 virtual uint8_t read_ctrl_at(int,uint8_t offset){return read_ctrl(offset);}
 virtual ~peripheral()=default;
};
struct saturn_control_port_device {
 peripheral *m_device=nullptr;
 uint8_t read_status();uint8_t read_id(int);uint8_t read_ctrl_at(int,uint8_t);
 uint8_t read_ctrl(uint8_t offset){return m_device?m_device->read_ctrl(offset):0xff;}
};
struct saturn_multitap_device:peripheral {
 std::array<saturn_control_port_device*,6> m_subctrl_port;
 uint8_t read_status() override{return 0x16;}
 uint8_t read_id(int) override;uint8_t read_ctrl_at(int,uint8_t) override;
};
struct saturn_segatap_device:peripheral {
 std::array<saturn_control_port_device*,4> m_subctrl_port;
 uint8_t read_status() override{return 0x04;}
 uint8_t read_id(int) override;uint8_t read_ctrl_at(int,uint8_t) override;
};
struct smpc_hle_device {
 saturn_control_port_device *m_ctrl1,*m_ctrl2;unsigned m_pmode=0;std::vector<uint8_t> m_periph_report;
 void read_saturn_ports();
};
METHODS
struct leaf:peripheral {
 unsigned connector=0,length=2;
 uint8_t read_id(int) override{return length;}
 uint8_t read_ctrl(uint8_t offset) override{assert(offset<length);return connector*16+offset;}
};
int main(){
 saturn_control_port_device empty;assert(empty.read_status()==0xf0 && empty.read_id(0)==0xff);
 std::array<saturn_control_port_device,6> ports;
 std::array<leaf,6> leaves;
 saturn_multitap_device multi; saturn_segatap_device sega;
 for(unsigned i=0;i<6;++i){leaves[i].connector=i+1;multi.m_subctrl_port[i]=&ports[i];if(i<4)sega.m_subctrl_port[i]=&ports[i];}
 for(unsigned count : {4U,6U}) for(unsigned mask=0;mask<(1U<<count);++mask) for(unsigned pmode=0;pmode<16;++pmode){
  for(unsigned i=0;i<count;++i){ports[i].m_device=(mask&(1U<<i))?&leaves[i]:nullptr;leaves[i].length=count==6?2:1+i%3;}
  saturn_control_port_device tap;tap.m_device=count==6?static_cast<peripheral*>(&multi):static_cast<peripheral*>(&sega);
  smpc_hle_device s{&tap,&empty,pmode,{}};s.read_saturn_ports();std::vector<uint8_t> expected;
  if((pmode&3)!=3){
   expected.push_back(count==6?0x16:0x04);
   for(unsigned i=0;i<count;++i){
    expected.push_back((mask&(1U<<i))?leaves[i].length:0xff);
    if(mask&(1U<<i))for(unsigned j=0;j<leaves[i].length;++j)expected.push_back((i+1)*16+j);
   }
  }
  if(((pmode>>2)&3)!=3)expected.push_back(0xf0);
  assert(s.m_periph_report==expected);
 }
 assert(multi.read_ctrl_at(-1,0)==0xff && multi.read_ctrl_at(6,0)==0xff);
 assert(sega.read_ctrl_at(-1,0)==0xff && sega.read_ctrl_at(4,0)==0xff);
}
'''.replace('METHODS',code)
with tempfile.TemporaryDirectory(prefix='saturn-multitap-') as directory:
    out=Path(directory);(out/'test.cpp').write_text(fixture)
    subprocess.run(['clang++','-std=c++17','-O1','-g','-fsanitize=address,undefined',str(out/'test.cpp'),'-o',str(out/'test')],check=True)
    subprocess.run([str(out/'test')],check=True)
print('SMPC sparse 6/4-port taps, mixed lengths, empty ports and all port modes PASS')
