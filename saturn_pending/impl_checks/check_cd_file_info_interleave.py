#!/usr/bin/env python3
"""File-info word4 unit/gap byte order; method-level, unvalidated."""
import ast
from pathlib import Path
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
functions='\n'.join(extract(source,s) for s in ('void saturn_cd_hle_device::cmd_get_target_file_info()', 'inline u16 saturn_cd_hle_device::dataxfer_word_r()', 'void saturn_cd_hle_device::cmd_end_data_transfer()'))
tail=r'''
int main(){saturn_cd_hle_device d;d.curdir.resize(3);auto &f=d.curdir[2];f.firstfad=150;f.length=0x12345;f.flags=2;unsigned words=0;
 for(unsigned unit=0;unit<256;++unit)for(unsigned gap=0;gap<256;++gap)for(bool all:{false,true}){
  f.file_unit_size=unit;f.interleave_gap_size=gap;
  d.cr1=0x7300;d.cr3=all?0xff:0;d.cr4=all?0xffff:2;d.cmd_get_target_file_info();
  CHECK(d.dataxfer_word_r()==0&&d.dataxfer_word_r()==150&&d.dataxfer_word_r()==1&&d.dataxfer_word_r()==0x2345);
  CHECK(d.dataxfer_word_r()==((unit<<8)|gap));CHECK((d.dataxfer_word_r()&0xff)==2);
  d.cmd_end_data_transfer();CHECK(d.cr2==6&&d.xferdnum==0);++words;
 }
 std::printf("method-level, unvalidated: %u single/all-table first-record word4 images, all unit/gap byte pairs; FAD/length/attribute retention and six-word DataEnd controls\n",words);
 std::puts("method-level, unvalidated: actual command/word-reader; byte storage diagnostics, not ISO/XA parser, file-number, streaming or native bus qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-file-interleave-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
