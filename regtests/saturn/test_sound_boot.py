#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Production SCSP/68000 reset-line wiring and side-effect-free boot diagnostics.

This tests signal delivery, not execution of the sound driver or game boot.
MUTATE_DROP_RESET_IRQ=1 restores the former gate and must fail.
"""
from pathlib import Path
import os, subprocess, tempfile
ROOT = Path(__file__).resolve().parents[2]
source = (ROOT/'src/mame/sega/saturn.cpp').read_text()
scsp = (ROOT/'src/devices/sound/scsp.cpp').read_text()
def extract(text, signature):
    start=text.index(signature);end=text.index('{', start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
functions='\n'.join(extract(source,s) for s in (
    'void saturn_state::scsp_irq(', 'void saturn_state::sound_68k_reset_w(',
    'bool saturn_state::boot_trace_word(', 'void saturn_state::trace_boot_cpu()'))
functions+='\n'+extract(scsp,'void scsp_device::CheckPendingIRQ()')
if os.environ.get('MUTATE_DROP_RESET_IRQ') == '1':
    functions=functions.replace('void saturn_state::scsp_irq(offs_t offset, uint8_t data) {',
                               'void saturn_state::scsp_irq(offs_t offset, uint8_t data) { if (!m_en_68k) return;')
harness=r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <string>
#include <iostream>
using u32=uint32_t;using u16=uint16_t;using offs_t=uint32_t;
constexpr int ASSERT_LINE=1,CLEAR_LINE=0,INPUT_LINE_RESET=8;
constexpr int SUSPEND_REASON_RESET=1,SUSPEND_REASON_HALT=2;
constexpr int SH_SR=1,SH4_PR=2,SH4_R0=16,M68K_SR=1,M68K_SP=2;
struct cpu {
 std::array<bool,9> lines{};std::array<u32,32> state{};u32 pc_=0;bool halt=false;
 void set_input_line(int n,int v){assert(n>=0&&n<9);lines[n]=v;}
 u32 pc(){return pc_;}u32 state_int(int n){return state.at(n);}
 uint64_t total_cycles(){return 123456;}
 bool suspended(int why){return why==SUSPEND_REASON_RESET?lines[INPUT_LINE_RESET]:halt;}
 unsigned level(){for(unsigned i=7;i;i--)if(lines[i])return i;return 0;}
};
struct saturn_state {
 cpu main,sound;cpu *m_maincpu=&main,*m_audiocpu=&sound;
 int m_en_68k=0,m_scsp_last_line=0;bool m_system_halt=false,m_sound_dma_halt=false;
 int64_t m_boot_trace_second=-1;
 std::array<u32,0x40000> m_workram_h{},m_workram_l{};std::array<u16,0x40000> m_sound_ram{};
 struct opts {bool enabled=false;bool verbose(){return enabled;}} opts_;
 struct clock {int64_t second=0;int64_t seconds(){return second;}const char *as_string(){return "test-time";}} clock_;
 auto &machine(){return *this;}auto &options(){return opts_;}auto &time(){return clock_;}
 std::string logs;
 template<class... T>void logerror(const char *fmt,T... args){char buf[2048];std::snprintf(buf,sizeof(buf),fmt,args...);logs+=buf;}
 void scsp_irq(offs_t,uint8_t);void sound_68k_reset_w(int);
 bool boot_trace_word(u32,bool,u16&);void trace_boot_cpu();
};
struct scsp_device {
 struct {std::array<u16,64> data{};} m_udata;
 u32 m_MidiW=0,m_MidiR=0,m_current_level=0;std::array<u32,3> levels{};
 u32 SCILV0(){return levels[0];}u32 SCILV1(){return levels[1];}u32 SCILV2(){return levels[2];}
 struct callback {saturn_state *owner;void operator()(offs_t n,uint8_t v){owner->scsp_irq(n,v);}} m_irq_cb;
 void CheckPendingIRQ();
 void request(unsigned level){
  for(unsigned i=0;i<3;i++)levels[i]=(level&(1<<i))?0x40:0;
  m_udata.data[0x1e/2]=0x40;m_udata.data[0x20/2]=level?0x40:0;CheckPendingIRQ();
 }
};
// FUNCTIONS
int main(){
 unsigned cases=0;
 for(unsigned before=0;before<8;++before)for(unsigned during=0;during<8;++during){
  auto s=std::make_unique<saturn_state>();scsp_device sc;sc.m_irq_cb.owner=s.get();
  s->sound_68k_reset_w(0);sc.request(before);assert(s->sound.level()==before);
  s->sound_68k_reset_w(1);assert(s->sound.lines[INPUT_LINE_RESET]&&!s->m_en_68k);
  sc.request(during);assert(s->sound.level()==during); // IRQ still driven during RESET
  s->sound_68k_reset_w(0);assert(!s->sound.lines[INPUT_LINE_RESET]&&s->m_en_68k);
  sc.CheckPendingIRQ();assert(s->sound.level()==during); // no new level-change callback
  sc.request(0);assert(!s->sound.level());++cases;
 }
 auto s=std::make_unique<saturn_state>();u16 word=0;
 s->m_workram_h[0]=0x12345678;s->m_workram_l[0]=0x9abcdef0;s->m_sound_ram[0]=0x1357;
 for(auto a:{0x06000000u,0x26000000u,0x07f00000u}){
  assert(s->boot_trace_word(a,false,word)&&word==0x1234);
  assert(s->boot_trace_word(a+2,false,word)&&word==0x5678);
 }
 assert(s->boot_trace_word(0x20200000,false,word)&&word==0x9abc);
 assert(s->boot_trace_word(0x00200002,false,word)&&word==0xdef0);
 for(auto a:{0x05a00000u,0x25a00000u,0x05a80000u})assert(s->boot_trace_word(a,false,word)&&word==0x1357);
 for(auto a:{0u})assert(s->boot_trace_word(a,true,word)&&word==0x1357);
 for(auto a:{0u,0x05800000u,0x05b00000u,0x08000000u,0x66000000u,0xc6000000u,0xffffffffu})assert(!s->boot_trace_word(a,false,word));
 for(auto a:{0x80000u,0xffffeu,0x100000u,0xffffffffu})assert(!s->boot_trace_word(a,true,word));
 s->m_workram_h.back()=0x2468ace0;s->m_sound_ram.back()=0xace0;
 assert(s->boot_trace_word(0x07fffffe,false,word)&&word==0xace0);
 assert(s->boot_trace_word(0x7fffe,true,word)&&word==0xace0);
 s->trace_boot_cpu();assert(s->logs.empty()&&s->m_boot_trace_second==-1);
 s->opts_.enabled=true;s->main.pc_=0x06000002;s->sound.pc_=0x7fffe;
 s->main.state[SH4_R0]=0x05a00000;s->trace_boot_cpu();
 assert(s->logs.find("mainpc=06000002")!=std::string::npos);
 assert(s->logs.find("main code @06000000: 1234 5678")!=std::string::npos);
 assert(s->logs.find("R0=05a00000 ram @05a00000: 1357")!=std::string::npos);
 assert(s->logs.find("----")!=std::string::npos);
 auto size=s->logs.size();s->trace_boot_cpu();assert(s->logs.size()==size);
 s->clock_.second=1;s->trace_boot_cpu();assert(s->logs.size()==2*size);
 assert(s->m_sound_ram[0]==0x1357&&s->m_workram_h[0]==0x12345678&&!s->sound.level());
 std::cout<<"Sound boot: "<<cases<<" SCSP/reset IRQ transitions and RAM/trace checks passed\n";
}
'''.replace('// FUNCTIONS',functions)
with tempfile.TemporaryDirectory(prefix='saturn-sound-boot-') as tmp:
    src=Path(tmp)/'test.cpp';exe=Path(tmp)/'test';src.write_text(harness)
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie',str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
