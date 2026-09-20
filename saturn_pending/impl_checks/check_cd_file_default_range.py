#!/usr/bin/env python3
"""Filesystem defaults replace programmed Play range, not active file progress/host owner."""
from pathlib import Path
import re
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_directory_clear.py')
scope={'__file__':str(fixture),'__name__':'file_default_range_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract,helpers,builders,reserve=(scope[k] for k in ('source','head','functions','extract','helpers','builders','reserve'))
head=head.replace('unsigned get_track_start(unsigned t){return 150+t*10000;}', 'unsigned get_track_start(unsigned t){return t==0xaa?10000:t*3000;}')
dev=extract(head,'struct saturn_cd_hle_device');head=head.replace(dev,dev[:-1]+'\nvoid cmd_play_disc();\n}',1)
functions+='\n'+extract(source,'void saturn_cd_hle_device::cmd_play_disc()')
fields={'m_play_start_fad','m_play_end_fad','m_play_range_valid'}
start=extract(source,'void saturn_cd_hle_device::device_start()');reg=extract(functions,'void saturn_cd_hle_device::register_state()')
extra=[m[0] for m in re.finditer(r'save_item\(NAME\((\w+)\)\);',start) if m[1] in fields and m[0] not in reg]
functions=functions.replace(reg,reg[:-1]+'\n'+'\n'.join(extra)+'\n}',1)
tail=r'''
void play(D &d,unsigned start,unsigned end,unsigned mode){d.cr1=0x1000|(start>>16);d.cr2=start;d.cr3=(mode<<8)|(end>>16);d.cr4=end;d.cmd_play_disc();}
void settle(D &d){unsigned n=0;while((d.cd_stat&0xf00)!=CD_STAT_PLAY){CHECK(++n<96);d.cd_playdata();}}
void setup(D &d,unsigned work,unsigned kind,bool defaults){seed(d,work,kind,kind==3?2:kind?17:0);root(d,2048);child(d,3,6144,2048);record(&d.media.directory[1000][102],4000,4096,false,'F');d.read_new_dir(0xffffff);
 play(d,defaults?0:0x8001b8,defaults?0:0x800028,15);settle(d);d.cdda_repeat_count=7;d.media.reads=0;
}
void access(D &d,unsigned work,unsigned action,unsigned fid){d.cr1=action==0?0x7400:action==1?0x7000:0x7100;d.cr2=0;d.cr3=(work<<8)|(fid>>16);d.cr4=fid;
 if(action==0)d.cmd_read_file();else if(action==1)d.cmd_change_directory();else d.cmd_read_directory();
}
void check(D &d,unsigned counter){CHECK(d.m_play_range_valid&&d.m_play_start_fad==150&&d.m_play_end_fad==10150&&d.cdda_repeat_count==counter&&d.cdda_maxrepeat==15);}
void finish_host(D &d,unsigned kind){if(!kind)return;
 if(kind==1){d.dataxfer_long_w(0xdeadbeef);CHECK(get_u32be(d.m_put_partition.blocks[0]->data)==0xcafebabe);}
 else CHECK(d.dataxfer_long_r()==word(4));CHECK(d.xferdnum==8);d.cmd_end_data_transfer();CHECK(!d.m_host_transfer_active);
}
int main(){unsigned cases=0,replays=0,controls=0;
 for(unsigned work=0;work<24;++work)for(unsigned kind=0;kind<4;++kind)for(bool defaults:{false,true})for(unsigned action=0;action<3;++action){
  auto p=std::make_unique<D>();auto &d=*p;setup(d,work,kind,defaults);
  const auto owner=d.transpart;const auto type=d.xfertype32;const auto cursor=d.xferdnum;
  const auto reservation=kind==1?partition_image(d.m_put_partition):kind==2?partition_image(d.m_get_partition):0;
  access(d,work,action,action==0?3:2);check(d,defaults?7:0);
  CHECK(d.m_host_transfer_active==bool(kind)&&d.transpart==owner&&d.xfertype32==type&&d.xferdnum==cursor);
  if(kind==1)CHECK(partition_image(d.m_put_partition)==reservation);if(kind==2)CHECK(partition_image(d.m_get_partition)==reservation);
  // The ordinary file's two-sector active extent is not replaced with the
  // default disc length by the programmed-range helper.
  if(action==0)CHECK(d.cd_curfad==4000&&d.fadstoplay==2&&d.playtype==1);
  const auto position=d.cd_curfad;d.register_state();d.capture();finish_host(d,kind);
  play(d,0xffffff,0xffffff,0xff);settle(d);CHECK(d.cd_curfad==position&&d.fadstoplay==10150-position);check(d,defaults?7:0);
  d.m_play_start_fad=42;d.m_play_end_fad=43;d.m_play_range_valid=false;d.cdda_repeat_count=13;d.fadstoplay=0;d.transpart=nullptr;d.m_host_transfer_active=false;
  d.restore();check(d,defaults?7:0);finish_host(d,kind);play(d,0xffffff,0xffffff,0xff);settle(d);CHECK(d.cd_curfad==position&&d.fadstoplay==10150-position);++cases;++replays;
 }
 for(unsigned action=0;action<3;++action)for(unsigned reason=0;reason<4;++reason){auto p=std::make_unique<D>();auto &d=*p;setup(d,7,2,false);
  if(reason==2)d.m_file_info_invalidated=true;if(reason==3){if(action==1)d.curdir[2].flags=0;else d.curdir.clear();}
  access(d,reason==0?24:7,action,reason==1?99:2);
  CHECK(d.m_play_range_valid&&d.m_play_start_fad==440&&d.m_play_end_fad==480&&d.cdda_repeat_count==7&&d.cdda_maxrepeat==15&&d.m_host_transfer_active&&d.xferdnum==4);++controls;
 }
 {auto p=std::make_unique<D>();auto &d=*p;setup(d,7,0,false);access(d,7,1,0);CHECK(d.m_play_start_fad==440&&d.m_play_end_fad==480&&d.cdda_repeat_count==7);d.read_new_dir(0xffffff);CHECK(d.m_play_start_fad==440&&d.m_play_end_fad==480&&d.cdda_repeat_count==7);controls+=2;}
 std::printf("method-level, unvalidated: %u filesystem/default-range/host images; %u registered range/pool/host replays; %u rejection/self/passive controls\n",cases,replays,controls);
 std::puts("method-level, unvalidated: actual filesystem/Play/parser/ports/allocator/drive/save methods, authored ISO and mock image/IRQ/audio/serializer; no native FLS/timing/save-file qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-file-default-range-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+helpers+reserve+builders+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
