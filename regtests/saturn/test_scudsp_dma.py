#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Actual DSP DMA methods: B-bus beat addressing, reset and registered-state replay.

Recording bus/timer endpoints are not shared-bus timing or real save-manager
acceptance. ST-097 pp.134/136/138/140 define B-bus per-halfword additions.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
src = (ROOT/'src/devices/cpu/scudsp/scudsp.cpp').read_text()

def extract(signature):
    start = src.index(signature)
    end = src.index('{', start)+1
    depth = 1
    while depth:
        depth += (src[end] == '{')-(src[end] == '}')
        end += 1
    return src[start:end]

methods = '\n'.join(extract(s) for s in (
    'void scudsp_cpu_device::op_dma(', 'void scudsp_cpu_device::exec_dma()',
    'TIMER_CALLBACK_MEMBER(scudsp_cpu_device::dma_tick_cb)',
    'void scudsp_cpu_device::device_reset()',
    'void scudsp_cpu_device::set_dest_dma_mem(',
    'void scudsp_cpu_device::set_dest_mem_reg_2(',
    'uint32_t scudsp_cpu_device::get_mem_source_dma('))
fields = re.findall(r'save_item\(NAME\((m_dma\.[a-z_]+|m_dma_state)\)\)', src)
restore = '\n'.join(f' d.{field}=s.{field};' for field in fields)
mutant = os.environ.get('MUTATE_DSP_DMA', '')
if mutant == 'count-zero':
    methods = methods.replace('m_dma.size = 256;', 'm_dma.size = 0;')
if mutant == 'count-width':
    methods = methods.replace('get_source_mem_value( opcode & 0x7 ) & 0xff', 'get_source_mem_value( opcode & 0x7 ) & 0xffff')
if mutant == 'pram-alias':
    methods = methods.replace('(dir_from_D0 ? 0x300 : 0x700)', '0x300')
if mutant == 'pram-early-stall':
    methods = methods.replace('if (m_dma.dir || m_dma.dst != 4)', 'if (true)')
if mutant == 'pram-cursor':
    restore = restore.replace('d.m_dma.program_address=s.m_dma.program_address;', '')
if mutant == 'pram-resume':
    methods = methods.replace('m_pc = m_top;', 'm_pc = m_top + 1;')
if mutant == 'pram-flush':
    begin = methods.index('TIMER_CALLBACK_MEMBER')
    end = methods.index('void scudsp_cpu_device::device_reset()', begin)
    methods = methods[:begin]+methods[begin:end].replace('m_delay_pending = false;', '')+methods[end:]
if mutant == 'read-upper':
    methods = methods.replace('physical < 0x08000000', 'physical < 0x07000000')
if mutant == 'read-low-bits':
    methods = methods.replace('else if (physical >= 0x05900000 && physical < 0x06000000)', 'if ((m_dma.src & 0x00e00000) >= 0x00a00000)')
if mutant == 'read-cs2':
    methods = methods.replace('else if (physical >= 0x05900000', 'else if (physical >= 0x05800000')
if mutant == 'beat':
    methods = methods.replace('m_dma.dst + m_dma.write_stride', 'm_dma.dst + 2')
if mutant == 'count-source':
    methods = methods.replace('m_dma.add = 2 * m_dma.write_stride;', 'if (!(opcode & 0x2000)) m_dma.add = 2 * m_dma.write_stride;')
if mutant == 'save-state':
    restore = restore.replace('d.m_dma_state=s.m_dma_state;', '')
if mutant == 'save-count':
    restore = restore.replace('d.m_dma.count=s.m_dma.count;', '')
if mutant == 'reset-halt':
    methods = methods.replace('set_input_line(INPUT_LINE_HALT, CLEAR_LINE);', '', 2)

harness = r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <utility>
#include <vector>
#define TIMER_CALLBACK_MEMBER(n) void n(int param)
#define INPUT_LINE_HALT 1
#define ASSERT_LINE 1
#define CLEAR_LINE 0
#define scudsp_writeop(a,v) pram[(a)]=(v)
#define scudsp_writemem(a,b,v) ram[(a)|((b)<<6)]=(v)
#define scudsp_readmem(a,b) ram[(a)|((b)<<6)]
using emu_fatalerror=std::runtime_error;
struct attotime {static constexpr int never=-1;static int from_ticks(int n,int){return n;}};
struct timer {int delay=-1;void adjust(int n){delay=n;}};
struct scudsp_cpu_device {
 enum {DMA_STATE_IDLE,DMA_STATE_WAIT,DMA_STATE_MOVE,T0F=23};
 struct {uint32_t src=0,dst=0;uint8_t program_address=0;uint16_t add=0,write_stride=0,size=0,update=0,ex=0,dir=0,count=0;} m_dma;
 uint8_t m_pc=0,m_top=0;
 bool m_delay_pending=false;uint8_t m_delay=0;
 uint8_t m_dma_state=0,m_ct0=0,m_ct1=0,m_ct2=0,m_ct3=0;
 uint32_t m_ra0=0,m_wa0=0,m_flags=0,count_source=1;
 int m_icount=0;bool halt=false;int ddwt=0,ddmv=0;
 timer t;timer *m_dma_timer=&t;
 std::array<uint32_t,256> ram{},pram{};
 std::vector<std::pair<uint32_t,uint16_t>> writes;
 std::vector<uint32_t> reads;
 int clock(){return 1;}
 uint32_t get_source_mem_value(unsigned){return count_source;}
 void set_input_line(int line,int state){assert(line==INPUT_LINE_HALT);halt=state;}
 void m_out_ddwt_cb(int n){ddwt=n;}void m_out_ddmv_cb(int n){ddmv=n;}
 uint16_t m_in_dma_cb(uint32_t addr){reads.push_back(addr);return uint16_t(addr^0xabcd);}
 void m_out_dma_cb(uint32_t addr,uint16_t data){writes.emplace_back(addr,data);}
 void set_dest_mem_reg(uint32_t,uint32_t){assert(false);}
 void set_dest_mem_reg_2(uint32_t,uint32_t);
 void op_dma(uint32_t);void exec_dma();void dma_tick_cb(int);void device_reset();
 void set_dest_dma_mem(uint32_t,uint32_t);uint32_t get_mem_source_dma(uint32_t);
 void tick(){dma_tick_cb(0);}
 void finish(){unsigned bound=0;do{tick();assert(++bound<300);}while(m_dma.ex);}
};
// METHODS
void restore(scudsp_cpu_device &d,scudsp_cpu_device const &s){
 // The emulation framework owns timer/execution/memory state. Copy those
 // endpoints here; copy DMA state ONLY if registered by production source.
 d.t=s.t;d.halt=s.halt;d.ddwt=s.ddwt;d.ddmv=s.ddmv;
 d.pram=s.pram;d.m_pc=s.m_pc;d.m_top=s.m_top;d.m_delay=s.m_delay;d.m_delay_pending=s.m_delay_pending;
 d.ram=s.ram;d.m_flags=s.m_flags;d.m_ra0=s.m_ra0;d.m_wa0=s.m_wa0;
 d.m_ct0=s.m_ct0;d.m_ct1=s.m_ct1;d.m_ct2=s.m_ct2;d.m_ct3=s.m_ct3;
 // RESTORE
}
int main(){
 unsigned count_cases=0;
 for(unsigned raw=0;raw<256;++raw)for(unsigned bank=0;bank<4;++bank)
 for(unsigned dir=0;dir<2;++dir)for(unsigned hold=0;hold<2;++hold)
 for(unsigned indirect=0;indirect<2;++indirect)
 for(uint32_t upper:{0u,0x100u,0x5500u,0xffff0000u}){
  if(!indirect&&upper)continue;
  scudsp_cpu_device s;
  s.m_ra0=0x06010000/4;s.m_wa0=0x05e40000/4;s.count_source=upper|raw;
  uint32_t opcode=0xc0000000|((dir?1:2)<<15)|(hold<<14)|(indirect<<13)|(dir<<12)|(bank<<8)|(indirect?0:raw);
  unsigned expected=raw?raw:256;
  s.op_dma(opcode);assert(s.m_dma.size==expected);
  for(unsigned cut:{0u,1u,2u,expected/2+1,expected+1}){
   scudsp_cpu_device a=s;a.m_dma_timer=&a.t;
   for(unsigned i=0;i<cut;++i)a.tick();
   scudsp_cpu_device b;b.m_dma.size=7;b.m_dma.count=13;
   restore(b,a);a.writes.clear();a.reads.clear();a.finish();b.finish();
   assert(a.writes==b.writes&&a.reads==b.reads&&a.ram==b.ram);
   assert(a.m_dma.count==expected&&b.m_dma.count==expected);
  }
  s.finish();
  assert(s.reads.size()==(dir?0:expected*2)&&s.writes.size()==(dir?expected*2:0));
  assert(s.m_dma.count==expected&&!s.m_dma.ex&&!s.halt);
  assert((dir?s.m_wa0:s.m_ra0)==(dir?0x05e40000u/4:0x06010000u/4)+(hold?0:expected));
  ++count_cases;
 }
 assert(count_cases==20480);
 std::cout<<count_cases<<" count-width/zero/direction/bank/hold cases and five replay cuts passed\n";

 unsigned cases=0;
 for(unsigned bank=0;bank<4;++bank)for(unsigned mode=0;mode<8;++mode)
 for(unsigned hold=0;hold<2;++hold)for(unsigned indirect=0;indirect<2;++indirect)
 for(unsigned count:{1u,2u,63u,64u,65u,255u}){
  scudsp_cpu_device s;
  for(unsigned i=0;i<256;++i)s.ram[i]=0xa1230000u+i*0x103;
  auto original=s.ram;
  s.m_wa0=0x05a00000/4;s.count_source=count;
  uint32_t op=0xc0001000|(mode<<15)|(hold<<14)|(indirect<<13)|(bank<<8)|(indirect?0:count);
  s.op_dma(op);
  unsigned stride=mode?2u<<(mode-1):0;
  assert(s.m_dma.write_stride==stride&&s.m_dma.add==2*stride);
  assert(s.halt&&s.ddwt==1&&s.m_dma_state==s.DMA_STATE_WAIT);
  // Save in WAIT, first MOVE, midway, and the completion/IRQ-clear boundary.
  for(unsigned cut:{0u,1u,2u,count/2+1,count+1}){
   scudsp_cpu_device a=s;a.m_dma_timer=&a.t;
   for(unsigned i=0;i<cut;++i)a.tick();
   scudsp_cpu_device b;
   b.m_dma_state=b.DMA_STATE_IDLE;b.m_dma.count=37;b.m_dma.add=252;b.m_dma.dir=0;
   restore(b,a);
   a.writes.clear();a.reads.clear();a.finish();b.finish();
   assert(a.writes==b.writes&&a.reads==b.reads&&a.ram==b.ram);
   assert(a.m_wa0==b.m_wa0&&a.m_flags==b.m_flags&&!b.halt);
  }
  s.finish();
  assert(s.writes.size()==count*2&&s.reads.empty());
  for(unsigned i=0;i<count;++i){
   uint32_t value=original[bank*64+(i%64)];
   assert(s.writes[i*2]==std::make_pair(0x05a00000+i*2*stride,uint16_t(value>>16)));
   assert(s.writes[i*2+1]==std::make_pair(0x05a00000+(i*2+1)*stride,uint16_t(value)));
  }
  assert(!s.halt&&!(s.m_flags&(1<<s.T0F))&&!s.ddwt&&!s.ddmv);
  assert(s.m_wa0==0x05a00000/4+(hold?0:count*stride/2));
  for(unsigned cut:{0u,1u,2u}){
   scudsp_cpu_device r;r.m_wa0=0x05a00000/4;r.count_source=count;r.op_dma(op);
   for(unsigned i=0;i<cut;++i)r.tick();
   r.device_reset();
   assert(!r.halt&&!r.m_dma.ex&&!r.ddwt&&!r.ddmv&&r.t.delay==attotime::never);
   assert(r.m_dma_state==r.DMA_STATE_IDLE&&!(r.m_flags&(1<<r.T0F)));
  }
  ++cases;
 }
 // No B-bus classification for CS2 or C-bus; their existing pair layout stays.
 for(uint32_t addr:{0x02000000u,0x05800000u,0x06000000u}){
  scudsp_cpu_device s;s.m_wa0=addr/4;s.op_dma(0xc0001001|(2<<15));s.finish();
  assert(s.writes[0].first==addr&&s.writes[1].first==addr+2);
 }
 // Read direction still uses paired halfwords, all four CT banks wrap.
 for(unsigned bank=0;bank<4;++bank){
  scudsp_cpu_device s;s.m_ra0=0x06000000/4;s.op_dma(0xc0010000|(bank<<8)|65);s.finish();
  assert(s.reads.size()==130&&s.writes.empty());
  for(unsigned i=0;i<130;++i)assert(s.reads[i]==0x06000000+i*2);
 }
 unsigned program_cases=0;
 for(unsigned target=0;target<256;++target)for(unsigned hold=0;hold<2;++hold)
 for(unsigned indirect=0;indirect<2;++indirect)for(unsigned count:{1u,2u,63u,255u,256u}){
  scudsp_cpu_device s;s.m_ra0=0x06010000/4;s.count_source=count;s.m_pc=2;
  s.op_dma(0xc0010400|(hold<<14)|(indirect<<13)|(indirect?0:(count&255)));
  assert(s.m_dma.dst==4&&!s.halt);
  // Model the post-fetch PC of the required following MVI-to-PC instruction.
  s.m_pc=3;s.set_dest_mem_reg_2(12,target);
  assert(s.halt&&s.m_pc==target&&s.m_top==3);
  for(unsigned cut:{0u,1u,2u,count/2+1,count+1}){
   scudsp_cpu_device a=s;a.m_dma_timer=&a.t;
   for(unsigned i=0;i<cut;++i)a.tick();
   scudsp_cpu_device b;restore(b,a);
   a.reads.clear();a.finish();b.finish();
   assert(a.pram==b.pram&&a.ram==b.ram&&a.reads==b.reads);
   assert(a.m_pc==3&&b.m_pc==3&&!a.m_delay_pending&&!b.m_delay_pending&&!b.halt);
  }
  s.finish();
  std::array<uint32_t,256> expected{};
  for(unsigned i=0;i<count;++i){
   uint32_t addr=0x06010000+i*4;
   expected[(target+i)&255]=(uint32_t(uint16_t(addr^0xabcd))<<16)|uint16_t((addr+2)^0xabcd);
  }
  assert(s.pram==expected);
  for(auto word:s.ram)assert(word==0);
  assert(s.m_ra0==0x06010000/4+(hold?0:count));
  ++program_cases;
 }
 std::cout<<program_cases<<" program-RAM DMA target/wrap/count/hold cases and five replay cuts passed\n";
 unsigned read_cases=0;
 for(uint32_t alias:{0u,0x20000000u})for(unsigned mirror=0;mirror<32;++mirror)
 for(unsigned mode=0;mode<8;++mode)for(unsigned hold=0;hold<2;++hold)
 for(unsigned indirect=0;indirect<2;++indirect){
  scudsp_cpu_device s;uint32_t addr=alias+0x06010000+mirror*0x100000;
  s.m_ra0=addr/4;s.count_source=3;
  s.op_dma(0xc0000000|(mode<<15)|(hold<<14)|(indirect<<13)|(indirect?0:3));
  unsigned stride=(mode&2)?4:0;
  assert(s.m_dma.add==stride);s.finish();
  assert(s.reads.size()==6&&s.writes.empty());
  for(unsigned i=0;i<3;++i){
   assert(s.reads[i*2]==addr+i*stride&&s.reads[i*2+1]==addr+i*stride+2);
  }
  assert(s.m_ra0==addr/4+(hold?0:3*stride/4));
  ++read_cases;
 }
 // A-bus fixed-source reads must not inherit B-bus advancement from either
 // the 05 prefix (CS2) or low bits shared with sound/video addresses.
 for(uint32_t addr:{0x02010000u,0x02a10000u,0x02f10000u,0x05810000u}){
  scudsp_cpu_device s;s.m_ra0=addr/4;s.op_dma(0xc0000003);s.finish();
  for(unsigned i=0;i<3;++i)assert(s.reads[i*2]==addr&&s.reads[i*2+1]==addr+2);
 }
 for(uint32_t addr:{0x05910000u,0x05a10000u,0x05c10000u,0x05e10000u})
 for(unsigned mode=0;mode<8;++mode){
  scudsp_cpu_device s;s.m_ra0=addr/4;s.op_dma(0xc0000003|(mode<<15));s.finish();
  for(unsigned i=0;i<6;++i)assert(s.reads[i]==addr+i*2);
 }
 std::cout<<read_cases<<" DSP read DMA mirror/mode/hold/count cases plus A/B isolation passed\n";
 std::cout<<cases<<" DSP DMA B-bus mode/count/hold/bank cases, five replay cuts, reset and bus isolation passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='scudsp-dma-') as temp:
    d=Path(temp);cpp=d/'test.cpp';exe=d/'test'
    cpp.write_text(harness.replace('// METHODS',methods).replace('// RESTORE',restore))
    subprocess.run([os.environ.get('CXX','c++'),'-std=c++17','-O1','-g','-Wall','-Wextra',
                    '-Werror','-Wno-unused-parameter','-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
