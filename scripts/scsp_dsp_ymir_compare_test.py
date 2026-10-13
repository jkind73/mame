#!/usr/bin/env python3
# license:BSD-3-Clause
"""Compare actual MAME DSP instructions with an independently built Ymir DSP.

Supply a local Ymir checkout. No reference implementation is copied into MAME.
The generated test-only callback samples production state after each instruction.
This synthetic check does not replace a real BIOS/game audio trace.
"""
from pathlib import Path
import argparse
import subprocess
import tempfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--ymir',type=Path,required=True,help='Ymir repository root')
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
y=args.ymir.resolve()/'libs/ymir-core'

# Reuse the existing minimal MAME shim without executing its fixture.
s=(root/'scripts/scsp_dsp_bank_test.py').read_text();shim=s.split("shim=r'''",1)[1].split("'''",1)[0].replace('65536','262144').replace('65535','262143')
test=r'''
#include <ymir/hw/scsp/scsp_dsp.hpp>
#include <iostream>
static ymir::scsp::DSP *reference;
static unsigned stepIndex, trialIndex;
void compareStep(SCSPDSP &m, int acc,int frc,int yr,unsigned adr) {
 reference->Step();ymir::savestate::SCSPDSPSaveState st{};reference->SaveState(st);
 auto fail=[&](const char *field){std::cerr<<field<<" step mismatch trial "<<trialIndex<<" step "<<stepIndex<<"\n";std::exit(1);};
 for(unsigned i=0;i<128;++i)if(m.TEMP[i]!=st.TEMP[i])fail("TEMP");
 for(unsigned i=0;i<32;++i)if(m.MEMS[i]!=st.MEMS[i])fail("MEMS");
 for(unsigned i=0;i<16;++i)if(m.EFREG[i]!=st.EFREG[i])fail("EFREG");
 if((uint32_t(acc)&0x3ffffff)!=st.SFT_REG)fail("ACC");
 if((uint32_t(frc)&8191)!=st.FRC_REG)fail("FRC");
 if((uint32_t(yr)&0xffffff)!=st.Y_REG)fail("Y");
 if((adr&4095)!=st.ADRS_REG)fail("ADRS");
 if(m.ReadPending!=st.readPending || m.WritePending!=st.writePending || (uint32_t(m.ReadValue)&0xffffff)!=st.readValue)fail("PIPE");
 ++stepIndex;
}

#include <ymir/hw/scsp/scsp_dsp.hpp>
#include <random>
#include <iostream>
int main(){
 std::mt19937 random(0x292);
 auto sext24=[](uint32_t x){return int32_t(x<<8)>>8;};
 for(unsigned trial=0;trial<256;++trial){
  address_space mem; std::array<uint8_t,0x80000> ram{}; SCSPDSP m;m.Init();m.space=&mem;
  ymir::scsp::DSP y(ram.data()); ymir::savestate::SCSPDSPSaveState st{};st.PC=0;st.MIXSNull=0xffff; st.RBL=trial%4;st.RBP=trial%17;m.RBL=8192U<<st.RBL;m.RBP=st.RBP;
  for(unsigned i=0;i<262144;++i){auto w=random();mem.ram[i]=w;ram[i*2]=w>>8;ram[i*2+1]=w;}
  for(unsigned i=0;i<128;++i){ m.TEMP[i]=st.TEMP[i]=sext24(random()); }
  for(unsigned i=0;i<32;++i){m.MEMS[i]=st.MEMS[i]=sext24(random());m.MADRS[i]=st.MADRS[i]=random();}
  for(unsigned i=0;i<64;++i){auto c=random()&8191;st.COEF[i]=c;m.COEF[i]=c<<3;}
  for(unsigned i=0;i<16;++i){m.MIXSPrev[i]=st.MIXS[i+16]=sext24(random())>>4;}
  for(unsigned i=0;i<2;++i)m.EXTS[i]=st.EXTS[i]=random();
  for(unsigned i=0;i<128;++i){
   uint64_t p=(uint64_t(random())<<32)|random();
   if ((p>>29)&1) p &= ~(uint64_t(1)<<30);
   if(i==127)p &= ~(uint64_t(3)<<29);
   if(i>=1+trial%128)p=0;
   st.MPRO[i]=p;
   for(unsigned j=0;j<4;++j)m.MPRO[i*4+j]=p>>(48-j*16);
  }
  m.DecodeAll();m.Start();y.LoadState(st);reference=&y;trialIndex=trial;
  for(unsigned sample=0;sample<4;++sample){
   stepIndex=0;m.Step();for(unsigned i=m.LastStep;i<128;++i)y.Step();y.SaveState(st);
   for(unsigned i=0;i<262144;++i)if(mem.ram[i]!=((unsigned(ram[i*2])<<8)|ram[i*2+1])){std::cerr<<"RAM mismatch "<<trial<<" "<<sample<<" "<<i<<"\n";return 1;}
   for(unsigned i=0;i<128;++i)if(m.TEMP[i]!=st.TEMP[i]){std::cerr<<"TEMP mismatch "<<trial<<" "<<sample<<" "<<i<<" "<<m.TEMP[i]<<" "<<st.TEMP[i]<<"\n";return 1;}
   for(unsigned i=0;i<32;++i)if(m.MEMS[i]!=st.MEMS[i]){std::cerr<<"MEMS mismatch\n";return 1;}
   for(unsigned i=0;i<16;++i)if(m.EFREG[i]!=st.EFREG[i]){std::cerr<<"EFREG mismatch "<<trial<<" "<<sample<<" "<<i<<" "<<m.EFREG[i]<<" "<<st.EFREG[i]<<"\n";return 1;}
   if((uint32_t(m.AccReg)&0x3ffffff)!=st.SFT_REG || (uint32_t(m.FrcReg)&8191)!=st.FRC_REG || (uint32_t(m.YReg)&0xffffff)!=st.Y_REG || (m.AdrsReg&4095)!=st.ADRS_REG){std::cerr<<"register mismatch "<<trial<<" "<<sample<<" acc "<<(uint32_t(m.AccReg)&0x3ffffff)<<"/"<<st.SFT_REG<<" frc "<<(uint32_t(m.FrcReg)&8191)<<"/"<<st.FRC_REG<<" y "<<(uint32_t(m.YReg)&0xffffff)<<"/"<<st.Y_REG<<" addr "<<m.AdrsReg<<"/"<<st.ADRS_REG<<"\n";return 1;}
  }
 }
 std::cout<<"256 randomized DSP programs x 4 samples match Ymir at each step\n";
}
'''
with tempfile.TemporaryDirectory(prefix='scsp-ymir-compare-') as directory:
    out=Path(directory)
    (out/'emu.h').write_text(shim)
    code=(root/'src/devices/sound/scspdsp.cpp').read_text();assert code.count('\t}\n\n\tAccReg = ACC;')==1;code=code.replace('\t}\n\n\tAccReg = ACC;', '\t\tcompareStep(*this, ACC, FRC_REG, Y_REG, ADRS_REG);\n\t}\n\n\tAccReg = ACC;'); (out/'test.cpp').write_text('struct SCSPDSP; void compareStep(SCSPDSP&,int,int,int,unsigned);\n'+code+'\n'+test)
    subprocess.run(['clang++','-std=c++20','-O1','-g','-fsanitize=address,undefined','-I'+str(out),'-I'+str(root/'src/devices/sound'),'-I'+str(y/'include'),str(out/'test.cpp'),str(y/'src/ymir/hw/scsp/scsp_dsp.cpp'),'-o',str(out/'test')],check=True)
    subprocess.run([str(out/'test')],check=True)
