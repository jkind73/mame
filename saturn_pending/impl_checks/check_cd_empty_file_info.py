#!/usr/bin/env python3
"""Empty-file information is a record, not missing data; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_file_transfer_length.py')
scope={'__file__':str(fixture),'__name__':'empty_file_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
head=scope['head'].replace('// TYPES',scope['types']);functions=scope['functions']
tail=r'''
using D=saturn_cd_hle_device;
int main(){unsigned records=0,replays=0;
 for(unsigned fid=2;fid<256;++fid)for(unsigned size:{0U,1U,2048U,65536U,0xffffffffU}){
  D d;d.curdir.resize(256);for(unsigned i=0;i<256;++i){auto &f=d.curdir[i];f.firstfad=0x10000+i;f.length=1234;f.flags=0;f.file_unit_size=0;f.interleave_gap_size=0;}
  d.curdir[fid].length=size;d.cr1=0x7300;d.cr3=0;d.cr4=fid;d.cmd_get_target_file_info();
  CHECK(d.cr2==6&&d.m_host_transfer_active&&(d.hirqreg&DRDY));
  std::array<u16,6> single{};D prefix=d;
  for(unsigned i=0;i<6;++i)single[i]=d.dataxfer_word_r();
  CHECK(single[0]==1&&single[1]==fid&&single[2]==(size>>16)&&single[3]==(size&65535)&&single[4]==0&&(single[5]&255)==0);
  d.cmd_end_data_transfer();CHECK(d.cr2==6&&!d.m_host_transfer_active);
  for(unsigned cut=0;cut<=6;++cut){D replay=prefix;for(unsigned i=cut;i<6;++i)CHECK(replay.dataxfer_word_r()==single[i]);replay.cmd_end_data_transfer();CHECK(replay.cr2==6&&!replay.m_host_transfer_active);if(cut<6)prefix.dataxfer_word_r();++replays;}
  d.cr1=0x7300;d.cr3=0xff;d.cr4=0xffff;d.cmd_get_target_file_info();for(unsigned i=0;i<(fid-2)*6;++i)d.dataxfer_word_r();for(auto word:single)CHECK(d.dataxfer_word_r()==word);d.cmd_end_data_transfer();++records;
 }
 std::printf("method-level, unvalidated: %u single/table empty/nonempty record comparisons; %u every-word state-copy continuations\n",records,replays);
 std::puts("method-level, unvalidated: actual File Info/word/End methods; 32-bit-size extremes are storage diagnostics; zero-FAD/invalid-ID policy, ISO parsing, XA number, held-window and native save/timing excluded");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-empty-info-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
