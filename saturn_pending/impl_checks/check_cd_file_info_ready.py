#!/usr/bin/env python3
"""File-info response/backing ready at notification; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_file_transfer_length.py')
scope={'__file__':str(fixture),'__name__':'file_ready_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
head=scope['head'].replace('// TYPES',scope['types'])
head=head.replace('void update_hirq(){++irqs;}', 'void (*observe)(saturn_cd_hle_device&)=nullptr;void update_hirq(){++irqs;if(observe)observe(*this);}')
functions=scope['functions']
tail=r'''
using D=saturn_cd_hle_device;
std::vector<u16> expected;unsigned at=0,cut=0,pending=0;bool all=false;
void observe(D &d){CHECK(d.irqs==1&&d.m_host_transfer_active&&d.xfercount==0&&d.xferdnum==0);
 CHECK(d.cr1==d.cd_stat&&d.cr2==expected.size()&&d.cr3==0&&d.cr4==0);
 CHECK(d.xfertype==(all?D::XFERTYPE_FILEINFO_254:D::XFERTYPE_FILEINFO_1));
 CHECK(d.hirqreg==(pending|CMOK|DRDY));
 for(;at<std::min<unsigned>(cut,expected.size());++at)CHECK(d.dataxfer_word_r()==expected[at]);
}
int main(){unsigned images=0;
 for(unsigned pattern:{0U,1U,7U,31U,127U,255U})for(bool bulk:{false,true})for(unsigned before:{0U,2U,0x41U,0xffffU})
 for(unsigned cursor:{0U,1U,5U,255U,1523U})for(unsigned read:{0U,1U,6U,65535U}){
  D d;d.curdir.resize(256);for(unsigned i=0;i<256;++i){auto &f=d.curdir[i];f.firstfad=150+pattern*10003+i*17;f.length=(i+1)*257+pattern*17;f.file_unit_size=pattern+i;f.interleave_gap_size=pattern+3*i;f.flags=i^pattern;}
  expected.clear();all=bulk;pending=before;cut=read;at=0;
  for(unsigned i=2;i<(bulk?256U:3U);++i){const auto &f=d.curdir[i];expected.push_back(f.firstfad>>16);expected.push_back(f.firstfad);expected.push_back(f.length>>16);expected.push_back(f.length);expected.push_back((f.file_unit_size<<8)|f.interleave_gap_size);expected.push_back((i<<8)|f.flags);}
  std::memset(d.finfbuf,0xa5,sizeof(d.finfbuf));d.xfercount=cursor;d.hirqreg=before;d.cr1=0x7300;d.cr2=0xdddd;d.cr3=bulk?0xff:0;d.cr4=bulk?0xffff:2;d.observe=observe;d.cmd_get_target_file_info();d.observe=nullptr;
  for(;at<expected.size();++at)CHECK(d.dataxfer_word_r()==expected[at]);
  CHECK(d.xfertype==D::XFERTYPE_INVALID&&d.xfercount==0&&d.xferdnum==expected.size()*2&&d.m_host_transfer_active);
  d.cmd_end_data_transfer();CHECK(d.cr2==expected.size()&&!d.m_host_transfer_active&&d.xferdnum==0);++images;
 }
 std::printf("method-level, unvalidated: %u single/table ready-notification images with 0/1/6/all immediate word reads, poisoned prior backing/cursor, exact continuation and DataEnd\n",images);
 std::puts("method-level, unvalidated: actual file command/word reader/End; callback observer is a publication-order diagnostic, not native IRQ timing, DMA reentrancy, held-table validity or padding qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-file-ready-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
