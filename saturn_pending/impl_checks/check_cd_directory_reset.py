#!/usr/bin/env python3
"""Hard reset clears root/scope before optional directory reload; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_selector_reset.py')
scope={'__file__':str(fixture),'__name__':'directory_reset_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
head,functions=(scope[k] for k in ('head','functions'))
head=head.replace('void read_new_dir(unsigned){++dir_reads;}',r'''bool reload=false;
 bool empty_root() const {return !curroot.record_size&&!curroot.xa_record_size&&!curroot.file_number&&!curroot.firstfad&&!curroot.length&&!curroot.year&&!curroot.month&&!curroot.day&&!curroot.hour&&!curroot.minute&&!curroot.second&&!curroot.gmt_offset&&!curroot.flags&&!curroot.file_unit_size&&!curroot.interleave_gap_size&&!curroot.volume_sequencer_number&&std::all_of(std::begin(curroot.name),std::end(curroot.name),[](auto c){return c==0;});}
 void read_new_dir(unsigned id){CHECK(id==0xffffff&&empty_root()&&!numfiles&&!firstfile&&curdir.empty());++dir_reads;if(reload){curroot.firstfad=1000;curroot.length=2048;curroot.flags=2;numfiles=3;firstfile=2;curdir={1,2,3};}}
''')
tail=r'''
int main(){unsigned images=0;
 for(unsigned poison=0;poison<256;++poison)for(bool inserted:{false,true})for(bool reload:{false,true}){
  auto d=std::make_unique<saturn_cd_hle_device>();std::memset(&d->curroot,poison,sizeof(d->curroot));d->numfiles=1000+poison;d->firstfile=17+poison;d->curdir={4,5,6};d->media.inserted=inserted;d->reload=reload;
  d->device_reset();CHECK(d->dir_reads==unsigned(inserted)&&d->irqs==1);
  if(inserted&&reload)CHECK(d->curroot.firstfad==1000&&d->curroot.length==2048&&d->curroot.flags==2&&d->curdir.size()==3&&d->numfiles==3&&d->firstfile==2);
  else CHECK(d->empty_root()&&d->curdir.empty()&&!d->numfiles&&!d->firstfile);
  ++images;
 }
 std::printf("method-level, unvalidated: %u poisoned directory/root/scope hard-reset images, media absent/present and failed/successful mock reload\n",images);
 std::puts("method-level, unvalidated: actual device_reset, mock media/reload/timers; no native reset notification timing, software Init-CD, scope-validity or game qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-dir-reset-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
