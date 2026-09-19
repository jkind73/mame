#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Execute production SCSP LFO reset/step code and check its UpdateSlot wiring.

ST-077-R2-052594 p.89 makes LFORE=1 hold the slot LFO in reset and p.37 exempts
the noise waveform. LFO state is not readable through any register, so this is
extracted-method evidence plus source-structure checks on the per-sample path,
not a native or audio-capture qualification.

SCSP_LFO_MUTANT selects a compiled negative control; each must fail.
"""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
source = Path(os.environ.get('SCSP_LFO_SOURCE', ROOT/'src/devices/sound/scsp.cpp')).read_text()
# The pre-LFORE source has no hold helper and its step functions take no flag.
OLD = 'bool scsp_device::LFO_ResetHold(' not in source

def extract(signature):
    a = source.index(signature); b = source.index('{', a)+1; depth = 1
    while depth:
        depth += (source[b] == '{') - (source[b] == '}'); b += 1
    return source[a:b]

# The static LFOFreq/ASCALE/PSCALE tables and LFO_Init sit between these marks.
a = source.index('#define LFIX(v)')
b = source.index('void scsp_device::LFO_Init()')
b = source.index('{', b)+1
depth = 1
while depth:
    depth += (source[b] == '{') - (source[b] == '}'); b += 1
tables = source[a:b]

macros = '\n'.join(line for line in source.splitlines()
                   if line.startswith('#define') and line.split('(')[0].replace('#define', '').strip()
                   in ('LFORE', 'LFOF', 'PLFOWS', 'PLFOS', 'ALFOWS', 'ALFOS'))
assert len(macros.splitlines()) == 6, macros

methods = '\n\n'.join((tables, macros,
                       extract('void scsp_device::Compute_LFO('),
                       extract('void scsp_device::LFO_ComputeStep('),
                       extract('s32 scsp_device::PLFO_Step('),
                       extract('s32 scsp_device::ALFO_Step(')))
if OLD:
    methods = methods.replace('s32 scsp_device::PLFO_Step(SCSP_LFO_t *LFO) {',
                              's32 scsp_device::PLFO_Step(SCSP_LFO_t *LFO, bool) {')
    methods = methods.replace('s32 scsp_device::ALFO_Step(SCSP_LFO_t *LFO) {',
                              's32 scsp_device::ALFO_Step(SCSP_LFO_t *LFO, bool) {')
    methods += '\nbool scsp_device::LFO_ResetHold(SCSP_SLOT *) { return false; }'
else:
    methods += '\n\n' + extract('bool scsp_device::LFO_ResetHold(')

# Per-sample wiring: the hold must be evaluated once, before either step call,
# and both step calls must receive it.
update_slot = extract('inline s32 scsp_device::UpdateSlot(') if not OLD else ''
if OLD:
    hold_at = p_at = a_at = 0
else:
    hold_at = update_slot.index('bool const lfo_hold = LFO_ResetHold(slot);')
    p_at = update_slot.index('PLFO_Step(&(slot->PLFO), lfo_hold)')
    a_at = update_slot.index('ALFO_Step(&(slot->ALFO), lfo_hold)')
    assert update_slot.count('LFO_ResetHold(') == 1, 'hold must be evaluated once per sample'
    assert hold_at < p_at < a_at, 'hold must precede both LFO step calls'
    assert 'PLFO_Step(&(slot->PLFO))' not in update_slot
    assert 'ALFO_Step(&(slot->ALFO))' not in update_slot

mutant = os.environ.get('SCSP_LFO_MUTANT', '')
original = methods
if mutant == 'lfore-ignored':
    methods = methods.replace('  if (!LFORE(slot))\n    return false;', '  return false;')
if mutant == 'lfore-always':
    methods = methods.replace('  if (!LFORE(slot))\n    return false;', '')
if mutant == 'lfore-hold-noise':
    methods = methods.replace('''  if (!slot->PLFO.noise)
    slot->PLFO.phase = 0;
  if (!slot->ALFO.noise)
    slot->ALFO.phase = 0;''', '''  slot->PLFO.phase = 0;
  slot->ALFO.phase = 0;''')
if mutant == 'lfore-step-noise':
    methods = methods.replace('if (hold && !LFO->noise)', 'if (hold)')
if mutant == 'lfore-step-advance':
    methods = methods.replace('''  if (hold && !LFO->noise)
    LFO->phase = 0;
  else
    LFO->phase += LFO->phase_step; // wraps at 2^32 == one cycle''',
'''  LFO->phase += LFO->phase_step; // wraps at 2^32 == one cycle''')
if mutant == 'lfore-return-inverted':
    methods = methods.replace('    slot->ALFO.phase = 0;\n  return true;', '    slot->ALFO.phase = 0;\n  return false;')
if mutant == 'lfo-saw-square-swap':
    methods = methods.replace('''    case 0:
      LFO->table = m_PLFO_SAW;
      break;
    case 1:
      LFO->table = m_PLFO_SQR;''', '''    case 0:
      LFO->table = m_PLFO_SQR;
      break;
    case 1:
      LFO->table = m_PLFO_SAW;''')
if mutant == 'lfo-scale-swap':
    methods = methods.replace('LFO->scale = m_PSCALES[LFOS];', 'LFO->scale = m_ASCALES[LFOS];')
if mutant == 'lfo-noise-flag':
    methods = methods.replace('LFO->noise = (LFOWS == 3);', 'LFO->noise = (LFOWS == 2);')
if mutant == 'lfo-lowfreq-truncate':
    methods = methods.replace('''  double const rate = double(clock()) / SAMPLE_CLOCKS;
  LFO->phase_step = (u32)std::llround(
      double(LFOFreq[LFOF]) * 4294967296.0 / rate);''',
'''  float step = (float)LFOFreq[LFOF] * 256.0f / (float)(clock() / SAMPLE_CLOCKS);
  LFO->phase_step = (u32)((float)(1 << LFO_SHIFT) * step);''')
if mutant == 'lfo-truncate-not-round':
    methods = methods.replace('std::llround(double(LFOFreq[LFOF])', 'std::trunc(double(LFOFreq[LFOF])')
if mutant == 'lfo-depth-zero-refresh':
    methods = methods.replace('  if (PLFOS(slot) != 0)\n', '')
if mutant:
    assert methods != original, 'unknown or no-op mutation: '+mutant

cpp = r'''
#include <cassert>
#include <cmath>
#include <cstdlib>
#include <cstdint>
#include <iostream>
using u8=uint8_t;using u16=uint16_t;using u32=uint32_t;using s8=int8_t;using s16=int16_t;using s32=int32_t;
constexpr int SHIFT=12,LFO_SHIFT=8,SAMPLE_CLOCKS=512;
constexpr int LFO_PHASE_SHIFT=24;
struct SCSP_LFO_t {u32 phase=0;u32 phase_step=0;int *table=nullptr;int *scale=nullptr;bool noise=false;};
struct SCSP_SLOT {
 union {u16 data[0x10];u8 datab[0x20];} udata;
 SCSP_LFO_t PLFO,ALFO;int slot=0;
};
struct scsp_device {
 int m_PLFO_TRI[256]{},m_PLFO_SQR[256]{},m_PLFO_SAW[256]{};
 int m_ALFO_TRI[256]{},m_ALFO_SQR[256]{},m_ALFO_SAW[256]{};
 int m_PSCALES[8][256]{},m_ASCALES[8][256]{};
 u32 m_lfsr=1;u32 m_clock=22579200;
 unsigned clock(){return m_clock;}
 template<class...T>void logerror(T...){}
 void LFO_Init();void Compute_LFO(SCSP_SLOT *slot);
 void LFO_ComputeStep(SCSP_LFO_t *LFO,u32 LFOF,u32 LFOWS,u32 LFOS,int ALFO);
 bool LFO_ResetHold(SCSP_SLOT *slot);
 s32 PLFO_Step(SCSP_LFO_t *LFO,bool hold);s32 ALFO_Step(SCSP_LFO_t *LFO,bool hold);
};
// METHODS
int main(){
 scsp_device d;d.LFO_Init();
 unsigned cases=0;
 // Table sanity: saw/square/triangle shapes and the noise exemption.
 for(int i=0;i<256;++i){
  assert(d.m_PLFO_SAW[i]==(i<128?i:i-256));
  assert(d.m_ALFO_SAW[i]==255-i);
  assert(d.m_PLFO_SQR[i]==(i<128?127:-128));
  assert(d.m_ALFO_SQR[i]==(i<128?255:0));
 }
 // Table 4.21 (printed p.89) oscillation frequencies, straight from the manual.
 {
  static const float manual[32]={0.17f,0.19f,0.23f,0.27f,0.34f,0.39f,0.45f,0.55f,
   0.68f,0.78f,0.92f,1.10f,1.39f,1.60f,1.87f,2.27f,2.87f,3.31f,3.92f,4.79f,
   6.15f,7.18f,8.60f,10.8f,14.4f,17.2f,21.5f,28.7f,43.1f,57.4f,86.1f,172.3f};
  for(unsigned i=0;i<32;++i)assert(LFOFreq[i]==manual[i]);
  ++cases;
 }
 assert(d.m_PSCALES[0][0]==d.m_PSCALES[0][255]);   // depth 0 is flat
 assert(d.m_ASCALES[0][0]==d.m_ASCALES[0][255]);
 assert(d.m_PSCALES[7][0]!=d.m_PSCALES[7][255]);   // depth 7 is not
 ++cases;
 // Every legal LFO register word: waveform/scale/noise mapping and the
 // documented "no depth, no recomputation" behaviour.
 for(unsigned reg=0;reg<0x10000;++reg){
  SCSP_SLOT s;s.udata.data[9]=u16(reg);
  s.PLFO.phase=0x1234abcd;s.PLFO.phase_step=0xdeadbeef;s.PLFO.table=&d.m_PLFO_TRI[0];
  s.PLFO.scale=&d.m_PSCALES[0][0];s.PLFO.noise=false;
  s.ALFO=s.PLFO;s.ALFO.table=&d.m_ALFO_TRI[0];s.ALFO.scale=&d.m_ASCALES[0][0];
  d.Compute_LFO(&s);
  unsigned const lf=(reg>>10)&0x1f,pws=(reg>>8)&3,pls=(reg>>5)&7,aws=(reg>>3)&3,als=reg&7;
  if(pls){
   assert(s.PLFO.noise==(pws==3));
   assert(s.PLFO.table==(pws==0?&d.m_PLFO_SAW[0]:pws==1?&d.m_PLFO_SQR[0]:pws==2?&d.m_PLFO_TRI[0]:nullptr));
   assert(s.PLFO.scale==&d.m_PSCALES[pls][0]);
   // Every Table 4.21 setting must actually oscillate: the slow end (0.17 Hz)
   // used to truncate to a zero increment, i.e. no modulation at all.
   assert(s.PLFO.phase_step>0);
   {
    double const rate=double(d.clock())/SAMPLE_CLOCKS;
    double const want=(LFOFreq[lf]*4294967296.0)/rate;
    double const err=std::fabs(double(s.PLFO.phase_step)-want)/want;
    assert(err<0.01);                        // within 1% of the manual rate
    assert(double(s.PLFO.phase_step)>=want-0.5&&double(s.PLFO.phase_step)<=want+0.5);
   }
   assert(s.PLFO.phase==0x1234abcd);      // Compute_LFO must not touch phase
  }else{
   assert(s.PLFO.phase_step==0xdeadbeef&&s.PLFO.table==&d.m_PLFO_TRI[0]&&s.PLFO.scale==&d.m_PSCALES[0][0]&&!s.PLFO.noise);
  }
  if(als){
   assert(s.ALFO.noise==(aws==3));
   assert(s.ALFO.table==(aws==0?&d.m_ALFO_SAW[0]:aws==1?&d.m_ALFO_SQR[0]:aws==2?&d.m_ALFO_TRI[0]:nullptr));
   assert(s.ALFO.scale==&d.m_ASCALES[als][0]);
   // Both LFOs share LFOF, so a programmed pair must compute one increment.
   assert(s.ALFO.phase_step>0&&(pls?s.ALFO.phase_step==s.PLFO.phase_step:true));
  }else{
   assert(s.ALFO.phase_step==0xdeadbeef&&s.ALFO.table==&d.m_ALFO_TRI[0]&&s.ALFO.scale==&d.m_ASCALES[0][0]&&!s.ALFO.noise);
  }
  // LFOF must raise the rate monotonically for a programmed depth.
  if(pls>0&&lf<31){
   SCSP_SLOT t=s;t.udata.data[9]=u16((reg&0x83ff)|((lf+1)<<10));
   d.Compute_LFO(&t);
   assert(t.PLFO.phase_step>=s.PLFO.phase_step);
  }
  ++cases;
 }
 // LFO_ResetHold: LFORE level, noise exemption, no other state disturbed.
 for(unsigned reg=0;reg<0x10000;++reg)for(bool pnoise:{false,true})for(bool anoise:{false,true}){
  SCSP_SLOT s;s.udata.data[9]=u16(reg);
  s.PLFO.phase=0xbeef0000;s.PLFO.phase_step=77;s.PLFO.table=&d.m_PLFO_SAW[0];
  s.PLFO.scale=&d.m_PSCALES[3][0];s.PLFO.noise=pnoise;
  s.ALFO.phase=0xf00d0000;s.ALFO.phase_step=88;s.ALFO.table=&d.m_ALFO_SQR[0];
  s.ALFO.scale=&d.m_ASCALES[5][0];s.ALFO.noise=anoise;
  bool const want=reg&0x8000;
  assert(d.LFO_ResetHold(&s)==want);
  assert(s.PLFO.phase==((want&&!pnoise)?0u:0xbeef0000u));
  assert(s.ALFO.phase==((want&&!anoise)?0u:0xf00d0000u));
  assert(s.PLFO.phase_step==77&&s.ALFO.phase_step==88);
  assert(s.PLFO.table==&d.m_PLFO_SAW[0]&&s.ALFO.table==&d.m_ALFO_SQR[0]);
  assert(s.PLFO.scale==&d.m_PSCALES[3][0]&&s.ALFO.scale==&d.m_ASCALES[5][0]);
  assert(s.PLFO.noise==pnoise&&s.ALFO.noise==anoise);
  ++cases;
 }
 // Step behaviour: held phase reports the reset-phase output and never runs;
 // released phase starts from zero; noise ignores the reset entirely.
 for(unsigned lf=0;lf<32;++lf)for(unsigned ws=0;ws<4;++ws)for(unsigned depth=1;depth<8;++depth){
  SCSP_SLOT s;s.udata.data[9]=u16(0x8000|(lf<<10)|(ws<<8)|(depth<<5)|(ws<<3)|depth);
  d.Compute_LFO(&s);
  bool const noise=(ws==3);
  // held: constant output, zero phase
  s.PLFO.phase=0x4321;s.ALFO.phase=0x4321;
  s32 held_p=d.PLFO_Step(&s.PLFO,true),held_a=d.ALFO_Step(&s.ALFO,true);
  assert(s.PLFO.phase==(noise?0x4321u+s.PLFO.phase_step:0u));
  assert(s.ALFO.phase==(noise?0x4321u+s.ALFO.phase_step:0u));
  if(!noise){
   assert(held_p==d.m_PSCALES[depth][d.m_PLFO_SAW==nullptr?0:(ws==0?d.m_PLFO_SAW[0]:ws==1?d.m_PLFO_SQR[0]:d.m_PLFO_TRI[0])+128]<<(SHIFT-LFO_SHIFT));
   assert(held_a==d.m_ASCALES[depth][(ws==0?d.m_ALFO_SAW[0]:ws==1?d.m_ALFO_SQR[0]:d.m_ALFO_TRI[0])]<<(SHIFT-LFO_SHIFT));
   for(int i=0;i<8;++i){
    assert(d.PLFO_Step(&s.PLFO,true)==held_p);
    assert(d.ALFO_Step(&s.ALFO,true)==held_a);
    assert(!s.PLFO.phase&&!s.ALFO.phase);
   }
   // Releasing LFORE starts the oscillator from the reset phase, and one full
   // cycle takes the manual's period: 2^24 accumulator units.
   u32 pp=0,pa=0;
   for(unsigned k=1;k<=6;++k){
    d.PLFO_Step(&s.PLFO,false);d.ALFO_Step(&s.ALFO,false);
    pp+=s.PLFO.phase_step;pa+=s.ALFO.phase_step;
    assert(s.PLFO.phase==pp&&s.ALFO.phase==pa);
    assert(s.PLFO.phase==k*s.PLFO.phase_step);
    assert((s.PLFO.phase>>LFO_PHASE_SHIFT)<256);
   }
   // Wrap: the accumulator must return to index 0 after exactly one cycle.
   s.PLFO.phase=0xffffffffu-s.PLFO.phase_step+1;
   d.PLFO_Step(&s.PLFO,false);
   assert(s.PLFO.phase==0&&(s.PLFO.phase>>LFO_PHASE_SHIFT)==0);
  }else{
   // p.37: with noise selected the LFORE reset does not function, the output
   // keeps following the LFSR and the phase keeps running.
   s.PLFO.phase=0x4321;
   d.m_lfsr=0x12345;
   s32 const np=d.PLFO_Step(&s.PLFO,true);
   assert(s.PLFO.phase==0x4321u+s.PLFO.phase_step);
   assert(np==(d.m_PSCALES[depth][(int)(s8)(0x12345&~1)+128]<<(SHIFT-LFO_SHIFT)));
   d.m_lfsr=0x12301;
   s32 const nq=d.PLFO_Step(&s.PLFO,true);
   assert(nq==(d.m_PSCALES[depth][(int)(s8)(0x12301&~1)+128]<<(SHIFT-LFO_SHIFT)));
   if(depth==7)assert(nq!=np);   // a different LFSR byte must be audible
   assert(s.PLFO.phase==u32(0x4321)+2*s.PLFO.phase_step);
   s.ALFO.phase=0x4321;d.m_lfsr=0x12345;
   assert(d.ALFO_Step(&s.ALFO,true)==(d.m_ASCALES[depth][(unsigned)(u8)(0x12345&~1)]<<(SHIFT-LFO_SHIFT)));
  }
  ++cases;
 }
 std::cout<<cases<<" actual SCSP LFO reset/step/waveform cases passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='scsp-lfo-') as tmp:
    p = Path(tmp); (p/'test.cpp').write_text(cpp.replace('// METHODS', methods))
    subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++20', '-O1',
                    '-fsanitize=undefined', '-fno-sanitize-recover=all',
                    str(p/'test.cpp'), '-o', str(p/'test')], check=True)
    subprocess.run([str(p/'test')], check=True)
