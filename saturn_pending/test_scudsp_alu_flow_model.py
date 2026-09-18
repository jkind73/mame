#!/usr/bin/env python3
# license:BSD-3-Clause
"""Actual ALU method: entry-A bypass, upper bits and same-cycle Y writeback."""
import ast
import os
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
src=Path(os.environ.get('SCUDSP_ALU_FLOW_SOURCE',ROOT/'src/devices/cpu/scudsp/scudsp.cpp')).read_text()
def extract(signature):
    start=src.index(signature);end=src.index('{',start)+1;depth=1
    while depth:
        depth+=(src[end]=='{')-(src[end]=='}');end+=1
    return src[start:end]
methods='\n'.join(extract(s) for s in ['void scudsp_cpu_device::op_alu(', 'uint32_t scudsp_cpu_device::program_control_r()'])
mutant=os.environ.get('SCUDSP_ALU_FLOW_MUTANT','')
if mutant=='no-bypass': methods=methods.replace('m_alu = concat_64(m_ach.ui, m_acl.ui);', '')
if mutant=='stale-high': methods=methods.replace('m_alu = concat_64(m_ach.ui, m_acl.ui);', 'm_alu = (m_alu & 0xffff00000000) | m_acl.ui;')
if mutant=='late-bypass':
    methods=methods.replace('m_alu = concat_64(m_ach.ui, m_acl.ui);', '')
    methods=methods.replace('/* D1-Bus */', 'm_alu = concat_64(m_ach.ui, m_acl.ui); /* D1-Bus */')
macros='\n'.join(re.findall(r'^#define (?:SET_[CSZV]\b|FLAGS_MASK\b).*$',src,re.M))
tree=ast.parse((ROOT/'regtests/saturn/test_scudsp_alu.py').read_text())
h=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='cpp' for t in n.targets))
h=h[:h.index('void check(')]+r'''
int main(){
 unsigned cases=0;uint64_t random=0x1234abcd5678;
 for(unsigned i=0;i<4096;++i){
  random=random*6364136223846793005ull+1442695040888963407ull;uint64_t a=random&0xffffffffffff;
  random=random*6364136223846793005ull+1442695040888963407ull;uint64_t p=random&0xffffffffffff;
  for(unsigned op:{0u,1u,2u,3u,4u,5u,6u,8u,9u,10u,11u,15u})for(unsigned y=0;y<3;++y){
   scudsp_cpu_device d;d.m_acl.ui=a;d.m_ach.ui=a>>32;d.m_pl.ui=p;d.m_ph.ui=p>>32;
   d.m_alu=(~a)&0xffffffffffff;d.m_flags=0x00781234;auto flags=d.m_flags;
   uint32_t lo=a,b=p;
   switch(op){
    case 1:lo&=b;break;case 2:lo|=b;break;case 3:lo^=b;break;
    case 4:lo+=b;break;case 5:lo-=b;break;
    case 8:lo=(lo>>1)|(lo&0x80000000);break;
    case 9:lo=std::rotr(lo,1);break;case 10:lo<<=1;break;
    case 11:lo=std::rotl(lo,1);break;case 15:lo=std::rotl(lo,8);break;
   }
   uint64_t result=op==6?(a+p)&0xffffffffffff:((a&0xffff00000000)|lo);
   d.op_alu((op<<26)|(y<<17));
   assert(uint64_t(d.m_alu)==result);
   if(op==0)assert(d.m_flags==flags);
   uint64_t next=y==1?0:y==2?result:a;
   assert(concat_64(d.m_ach.ui,d.m_acl.ui)==next);
   flags=d.m_flags;d.op_alu(0);
   assert(uint64_t(d.m_alu)==next&&d.m_flags==flags);++cases;
  }
 }
 std::cout<<cases<<" actual entry-A/bypass/high-half/Y-writeback transitions passed under UBSan\n";
}
'''
with tempfile.TemporaryDirectory(prefix='scudsp-flow-') as folder:
    p=Path(folder);(p/'test.cpp').write_text(h.replace('// MACROS',macros).replace('// METHODS',methods))
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-g','-fsanitize=undefined',
                    '-fno-sanitize-recover=all',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
    subprocess.run([str(p/'test')],check=True)
