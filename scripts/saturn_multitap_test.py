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
code='\n'.join(method(bus/'ctrl.cpp','uint8_t saturn_control_port_device::'+f) for f in ('read_status()','read_id(int idx)','read_ctrl_at(int idx, uint8_t offset)','max_data_size() const'))
for name in ('multitap','segatap'):
    for f in ('read_id(int idx)','read_ctrl_at(int idx, uint8_t offset)'):
        code+='\n'+method(bus/(name+'.cpp'),'uint8_t saturn_'+name+'_device::'+f)
source=Path(sys.argv[1]) if len(sys.argv)>1 else root/'src/mame/sega/smpc.cpp'
collector=method(source,'void smpc_hle_device::read_saturn_ports()')
legacy='push_back' in collector
code+='\n'+collector
code+='\n'+method(source,'void smpc_hle_device::write_periph_report()')
fixture=r'''
#include <array>
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <vector>
struct peripheral {
 virtual uint8_t read_status(){return 0xf1;}
 virtual uint8_t read_id(int){return 0x02;}
 virtual uint8_t read_ctrl(uint8_t){return 0xff;}
 virtual uint8_t read_ctrl_at(int,uint8_t offset){return read_ctrl(offset);}
 virtual uint8_t max_data_size() const{return 255;}
 virtual ~peripheral()=default;
};
struct saturn_control_port_device {
 peripheral *m_device=nullptr;
 uint8_t read_status();uint8_t read_id(int);uint8_t read_ctrl_at(int,uint8_t);
 uint8_t max_data_size() const;
 uint8_t read_ctrl(uint8_t offset){return m_device?m_device->read_ctrl(offset):0xff;}
};
struct saturn_multitap_device:peripheral {
 std::array<saturn_control_port_device*,6> m_subctrl_port;
 uint8_t read_status() override{return 0x16;}
 uint8_t read_id(int) override;uint8_t read_ctrl_at(int,uint8_t) override;
 uint8_t max_data_size() const override{return 15;}
};
struct saturn_segatap_device:peripheral {
 std::array<saturn_control_port_device*,4> m_subctrl_port;
 uint8_t read_status() override{return 0x04;}
 uint8_t read_id(int) override;uint8_t read_ctrl_at(int,uint8_t) override;
 uint8_t max_data_size() const override{return 15;}
};
struct smpc_hle_device {
 saturn_control_port_device *m_ctrl1,*m_ctrl2;unsigned m_pmode=0;REPORT_STORAGE m_periph_report{};
 uint32_t m_periph_size=0,m_periph_offset=0;uint8_t m_oreg[32]{};bool m_resb=false;int m_intback_stage=0;unsigned status=0;
 void sr_set(unsigned value){status=value;}
 void read_saturn_ports();void write_periph_report();
};
METHODS
std::vector<uint8_t> report_bytes(smpc_hle_device const &s){REPORT_BYTES}
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
  assert(report_bytes(s)==expected);
 }
 assert(multi.read_ctrl_at(-1,0)==0xff && multi.read_ctrl_at(6,0)==0xff);
 assert(sega.read_ctrl_at(-1,0)==0xff && sega.read_ctrl_at(4,0)==0xff);
 struct extended:peripheral{
  unsigned length=0;
  uint8_t read_id(int) override{return 0x10;}
  uint8_t read_ctrl(uint8_t offset) override{if(!offset)return length;assert(offset<=length);return offset-1;}
 } ext;
 saturn_control_port_device direct;direct.m_device=&ext;
 for(unsigned length=0;length<256;++length) for(unsigned mode=0;mode<4;++mode){
  ext.length=length;smpc_hle_device s{&direct,&empty,mode|12,{}};s.read_saturn_ports();std::vector<uint8_t> expected;
  if(mode!=3){unsigned n=std::min(length,mode==1?255U:15U);expected={0xf1,0x10,uint8_t(n)};for(unsigned j=0;j<n;++j)expected.push_back(j);}
  assert(report_bytes(s)==expected);
  ports[0].m_device=&ext;for(unsigned i=1;i<6;++i)ports[i].m_device=nullptr;
  saturn_control_port_device tap;tap.m_device=&multi;smpc_hle_device t{&tap,&empty,mode|12,{}};t.read_saturn_ports();expected.clear();
  if(mode!=3){unsigned n=std::min(length,15U);expected={0x16,0x10,uint8_t(n)};for(unsigned j=0;j<n;++j)expected.push_back(j);for(unsigned i=1;i<6;++i)expected.push_back(0xff);}
  assert(report_bytes(t)==expected);
 }
 struct unknown:peripheral{
  uint8_t id=0xf0;uint8_t read_id(int)override{return id;}
  uint8_t read_ctrl(uint8_t)override{assert(false && "UNKNOWN must not be read");return 0;}
 } unk;
 direct.m_device=&unk;
 for(unsigned id=0xf0;id<=0xff;++id){unk.id=id;smpc_hle_device s{&direct,&empty,12,{}};s.read_saturn_ports();assert(report_bytes(s)==std::vector<uint8_t>({0xf1,uint8_t(id)}));}
 direct.m_device=&ext;ext.length=255;smpc_hle_device s{&direct,&direct,5,{}};s.read_saturn_ports();auto expected=report_bytes(s);assert(expected.size()==516);
 unsigned cursor=0;while(cursor<expected.size()){
  s.write_periph_report();unsigned n=std::min<unsigned>(32,expected.size()-cursor);
  for(unsigned j=0;j<n;++j)assert(s.m_oreg[j]==expected[cursor+j]);
  assert(bool(s.status&0x40)==(cursor==0));cursor+=n;assert(bool(s.status&0x20)==(cursor<expected.size()));
 }
 assert(!s.m_periph_offset && !s.m_periph_size && report_bytes(s).empty());
 struct bulk:peripheral{
  uint8_t read_status()override{return 0x0f;}
  uint8_t read_id(int)override{return 0x10;}
  uint8_t read_ctrl_at(int index,uint8_t offset)override{return offset?uint8_t(index+offset):255;}
 } full;
 direct.m_device=&full;smpc_hle_device maximum{&direct,&direct,5,{}};maximum.read_saturn_ports();
 auto bytes=report_bytes(maximum);assert(bytes.size()==7712);
 unsigned index=0;for(unsigned port=0;port<2;++port){
  assert(bytes[index++]==0x0f);
  for(unsigned connector=0;connector<15;++connector){
   assert(bytes[index++]==0x10 && bytes[index++]==255);
   for(unsigned offset=1;offset<=255;++offset)assert(bytes[index++]==uint8_t(connector+offset));
  }
 }
}
'''.replace('METHODS',code).replace('REPORT_STORAGE','std::vector<uint8_t>' if legacy else 'std::array<uint8_t,7712>').replace('REPORT_BYTES','return s.m_periph_report;' if legacy else 'return {s.m_periph_report.begin(),s.m_periph_report.begin()+s.m_periph_size};')
with tempfile.TemporaryDirectory(prefix='saturn-multitap-') as directory:
    out=Path(directory);(out/'test.cpp').write_text(fixture)
    subprocess.run(['clang++','-std=c++17','-O1','-g','-fsanitize=address,undefined',str(out/'test.cpp'),'-o',str(out/'test')],check=True)
    subprocess.run([str(out/'test')],check=True)
print('SMPC sparse taps, all extended sizes, limits, UNKNOWN IDs and 516-byte continuation PASS')
