#!/usr/bin/env python3
"""Registered 16-bit transfer payload replay; method-level, unvalidated."""
import ast
from pathlib import Path
import re
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[2]
source=(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'src/mame/sega/saturn_cd_hle.cpp').read_text()
header=(ROOT/'src/mame/sega/saturn_cd_hle.h').read_text()
def extract(text,signature):
    start=text.index(signature);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
head=next(ast.literal_eval(n.value) for n in ast.parse(Path(__file__).with_name('check_cd_file_transfer_length.py').read_text()).body
          if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='head' for t in n.targets))
head=head.replace('// TYPES','\n'.join(extract(header,s)+';' for s in ('struct direntryT','enum transT','enum trans32T')))
head=head[:head.rfind('};')]+r'''
 struct Entry{void *address;size_t bytes;std::vector<u8>image;};std::vector<Entry> entries;
 template<class T>void save_item(T &value,const char*){entries.push_back({&value,sizeof(value),{}});}
 void register_state();
 void capture(){for(auto &e:entries){e.image.resize(e.bytes);std::memcpy(e.image.data(),e.address,e.bytes);}}
 void restore(){for(auto &e:entries)std::memcpy(e.address,e.image.data(),e.bytes);}
};
#define NAME(x) x,#x
'''
selected={'m_host_transfer_active','tocbuf','subqbuf','subrwbuf','finfbuf','xfertype','xfertype32','xfercount','xferdnum','cr1','cr2','cr3','cr4','hirqreg','cd_stat','playtype','cdda_repeat_count'}
start=extract(source,'void saturn_cd_hle_device::device_start()')
regs=[m[0] for m in re.finditer(r'save_item\(NAME\((\w+)\)\);',start) if m[1] in selected]
functions='void saturn_cd_hle_device::register_state(){\n'+'\n'.join(regs)+'\n}\n'
functions+='\n'.join(extract(source,s) for s in ('inline u16 saturn_cd_hle_device::dataxfer_word_r()', 'void saturn_cd_hle_device::cmd_end_data_transfer()'))
import runpy
head,functions=runpy.run_path(str(Path(__file__).with_name('cd_file_scope_scaffold.py')))['extend'](head,functions,source)

tail=r'''
using D=saturn_cd_hle_device;
std::vector<u16> finish(D &d,unsigned words,unsigned cut){std::vector<u16> data;for(unsigned i=cut;i<words;++i)data.push_back(d.dataxfer_word_r());CHECK(d.xfertype==D::XFERTYPE_INVALID&&d.xfercount==0&&d.xferdnum==words*2);d.cmd_end_data_transfer();CHECK(d.cr2==words);return data;}
int main(){unsigned replays=0;
 for(auto mode:{D::XFERTYPE_TOC,D::XFERTYPE_SUBQ,D::XFERTYPE_SUBRW,D::XFERTYPE_FILEINFO_1}){
  const unsigned words=mode==D::XFERTYPE_TOC?204:mode==D::XFERTYPE_SUBQ?5:mode==D::XFERTYPE_SUBRW?12:6;
  for(unsigned pattern=0;pattern<256;++pattern)for(unsigned cut=0;cut<=words;++cut){
   D d;unsigned byte=0;
   auto seed=[&](auto &a){for(auto &v:a)v=u8((byte++*17)^(pattern*7));};
   seed(d.tocbuf);seed(d.subqbuf);seed(d.subrwbuf);seed(d.finfbuf);
   std::array<u8,698> payload;unsigned pos=0;auto copy=[&](const auto &a){for(auto v:a)payload[pos++]=v;};copy(d.tocbuf);copy(d.subqbuf);copy(d.subrwbuf);copy(d.finfbuf);CHECK(pos==payload.size());
   d.xfertype=mode;d.cd_stat=0x4100;d.hirqreg=DRDY;
   for(unsigned i=0;i<cut;++i)d.dataxfer_word_r();d.register_state();d.capture();
   const auto expected=finish(d,words,cut);const auto expected_cr=std::array<u16,5>{d.cr1,d.cr2,d.cr3,d.cr4,d.hirqreg};
   auto poison=[](auto &a){std::fill(std::begin(a),std::end(a),0xe5);};poison(d.tocbuf);poison(d.subqbuf);poison(d.subrwbuf);poison(d.finfbuf);
   d.xfertype=D::XFERTYPE_INVALID;d.xfertype32=D::XFERTYPE32_GETDELETESECTOR;d.xfercount=d.xferdnum=0;d.cd_stat=d.cr1=d.cr2=d.cr3=d.cr4=d.hirqreg=0;
   const auto irqs=d.irqs;d.restore();CHECK(d.irqs==irqs);
   CHECK(finish(d,words,cut)==expected);CHECK((std::array<u16,5>{d.cr1,d.cr2,d.cr3,d.cr4,d.hirqreg})==expected_cr);
   pos=0;auto unchanged=[&](const auto &a){for(auto v:a)CHECK(v==payload[pos++]);};unchanged(d.tocbuf);unchanged(d.subqbuf);unchanged(d.subrwbuf);unchanged(d.finfbuf);++replays;
  }
 }
 std::printf("method-level, unvalidated: %u registered-image TOC/subQ/subRW/single-file replays at every word cut across 256 payload patterns; exact remaining words, backing bytes and DataEnd responses\n",replays);
 std::puts("method-level, unvalidated: production registrations and readers, mocked byte serializer/IRQ; not native file save/load or full-directory serialization");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-word-save-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
