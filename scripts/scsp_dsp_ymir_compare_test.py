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
parser.add_argument('--snapshots',type=Path,help='Live BIOS state directory from saturn_bios_dsp_capture.py')
args=parser.parse_args()
root=Path(__file__).resolve().parent.parent
y=args.ymir.resolve()/'libs/ymir-core'

# Reuse the existing minimal MAME shim without executing its fixture.
s=(root/'scripts/scsp_dsp_bank_test.py').read_text();shim=s.split("shim=r'''",1)[1].split("'''",1)[0].replace('65536','262144').replace('65535','262143')
shim=shim.replace('return ram[(a/2)&262143];','a &= 0xfffff;return a<0x80000?ram[a/2]:0;').replace('ram[(a/2)&262143]=v;','a &= 0xfffff;if(a<0x80000)ram[a/2]=v;')
test=r'''
#include <ymir/hw/scsp/scsp_dsp.hpp>
#include <iostream>
#include <fstream>
#include <cassert>
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
 if((uint32_t(m.InputsReg)&0xffffff)!=(uint32_t(st.INPUTS)&0xffffff))fail("INPUTS");
 if(m.ReadNOFL!=st.readNOFL || m.WriteValue!=st.writeValue || ((m.ReadWriteAddr&0xfffff)>>1)!=st.readWriteAddr)fail("PIPE ADDRESS");
 ++stepIndex;
}

#include <ymir/hw/scsp/scsp_dsp.hpp>
#include <random>
#include <iostream>
int main(int argc,char **argv){
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
 for(int file=1;file<argc;++file){
  std::ifstream input(argv[file],std::ios::binary);assert(input);
  auto word=[&](){uint8_t b[4];input.read(reinterpret_cast<char*>(b),4);assert(input);return uint32_t(b[0])|(uint32_t(b[1])<<8)|(uint32_t(b[2])<<16)|(uint32_t(b[3])<<24);};
  assert(word()==0x44535031);unsigned frame=word();input.ignore(8);
  std::array<uint32_t,17> scalar{};for(auto &v:scalar)v=word();
  address_space mem;std::array<uint8_t,0x80000> ram{};SCSPDSP m;m.Init();m.space=&mem;
  ymir::scsp::DSP y(ram.data());ymir::savestate::SCSPDSPSaveState st{};st.PC=0;
  m.RBP=st.RBP=scalar[0];m.RBL=scalar[1];st.RBL=std::countr_zero(m.RBL)-13;
  m.DEC=scalar[2];st.MDEC_CT=m.DEC;
  m.AccReg=scalar[5];st.SFT_REG=scalar[5]&0x3ffffff;
  m.FrcReg=scalar[6];st.FRC_REG=scalar[6]&8191;
  m.YReg=scalar[7];st.Y_REG=scalar[7]&0xffffff;
  m.AdrsReg=scalar[8];st.ADRS_REG=scalar[8]&4095;
  m.InputsReg=st.INPUTS=scalar[9];
  m.ReadPending=st.readPending=scalar[10];m.ReadNOFL=st.readNOFL=scalar[11];m.WritePending=st.writePending=scalar[12];
  m.ReadValue=scalar[13];st.readValue=scalar[13]&0xffffff;
  m.WriteValue=st.writeValue=scalar[14];m.ReadWriteAddr=scalar[15];st.readWriteAddr=(scalar[15]&0xfffff)>>1;
  m.MixWritten=scalar[16];st.MIXSNull=~m.MixWritten;
  for(unsigned i=0;i<64;++i){m.COEF[i]=word();st.COEF[i]=(uint16_t(m.COEF[i])>>3)&8191;}
  for(unsigned i=0;i<32;++i)m.MADRS[i]=st.MADRS[i]=word();
  for(unsigned i=0;i<512;++i)m.MPRO[i]=word();
  for(unsigned i=0;i<128;++i)for(unsigned j=0;j<4;++j)st.MPRO[i]|=uint64_t(m.MPRO[i*4+j])<<(48-j*16);
  for(unsigned i=0;i<128;++i)m.TEMP[i]=st.TEMP[i]=word();
  for(unsigned i=0;i<32;++i)m.MEMS[i]=st.MEMS[i]=word();
  for(unsigned i=0;i<16;++i)m.MIXS[i]=st.MIXS[i]=word();
  for(unsigned i=0;i<16;++i)m.MIXSPrev[i]=st.MIXS[i+16]=word();
  for(unsigned i=0;i<2;++i)m.EXTS[i]=st.EXTS[i]=word();
  for(unsigned i=0;i<16;++i)m.EFREG[i]=st.EFREG[i]=word();
  input.read(reinterpret_cast<char*>(ram.data()),ram.size());assert(input);
  for(unsigned i=0;i<262144;++i)mem.ram[i]=(unsigned(ram[i*2])<<8)|ram[i*2+1];
  if(scalar[3])continue;
  m.DecodeAll();m.Start();assert(unsigned(m.LastStep)==scalar[4]);
  y.LoadState(st);reference=&y;trialIndex=frame;stepIndex=0;m.Step();
  for(unsigned i=m.LastStep;i<128;++i)y.Step();
  y.SaveState(st);
  for(unsigned i=0;i<262144;++i)if(mem.ram[i]!=((unsigned(ram[i*2])<<8)|ram[i*2+1])){std::cerr<<"BIOS RAM mismatch frame "<<frame<<"\n";return 1;}
  for(unsigned i=0;i<16;++i)if(m.EFREG[i]!=st.EFREG[i]){std::cerr<<"BIOS output mismatch frame "<<frame<<"\n";return 1;}
  std::cout<<"Live BIOS DSP state frame "<<frame<<": "<<stepIndex<<" instruction outputs and full RAM match\n";
 }
 std::cout<<"256 randomized DSP programs x 4 samples match Ymir at each step\n";
}
'''
with tempfile.TemporaryDirectory(prefix='scsp-ymir-compare-') as directory:
    out=Path(directory)
    (out/'emu.h').write_text(shim)
    code=(root/'src/devices/sound/scspdsp.cpp').read_text();assert code.count('\t}\n\n\tAccReg = ACC;')==1;code=code.replace('\t}\n\n\tAccReg = ACC;', '\t\tcompareStep(*this, ACC, FRC_REG, Y_REG, ADRS_REG);\n\t}\n\n\tAccReg = ACC;'); (out/'test.cpp').write_text('struct SCSPDSP; void compareStep(SCSPDSP&,int,int,int,unsigned);\n'+code+'\n'+test)
    subprocess.run(['clang++','-std=c++20','-O1','-g','-fsanitize=address,undefined','-I'+str(out),'-I'+str(root/'src/devices/sound'),'-I'+str(y/'include'),str(out/'test.cpp'),str(y/'src/ymir/hw/scsp/scsp_dsp.cpp'),'-o',str(out/'test')],check=True)
    snapshots=sorted(args.snapshots.resolve().glob('frame-*.bin')) if args.snapshots else []
    if args.snapshots and not snapshots:raise RuntimeError('No live DSP snapshots found')
    subprocess.run([str(out/'test'),*[str(p) for p in snapshots]],check=True)
