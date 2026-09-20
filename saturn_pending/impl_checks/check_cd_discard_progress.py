#!/usr/bin/env python3
"""Discard advances the CD stream without becoming storage success or buffer wait."""
from pathlib import Path
import re
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_directory_clear.py')
scope={'__file__':str(fixture),'__name__':'discard_progress_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
source,head,functions,extract,helpers,reserve=(scope[k] for k in ('source','head','functions','extract','helpers','reserve'))
head=('#define HAS_DISCARD_RESULT '+str(int('bool *p_consumed' in source))+'\n')+head
dev=extract(head,'struct saturn_cd_hle_device');head=head.replace(dev,dev[:-1]+'void cmd_play_disc();\n}',1)
functions+='\n'+extract(source,'void saturn_cd_hle_device::cmd_play_disc()')
start=extract(source,'void saturn_cd_hle_device::device_start()');reg=extract(functions,'void saturn_cd_hle_device::register_state()')
fields={'m_play_start_fad','m_play_end_fad','m_play_range_valid'}
extra=[m[0] for m in re.finditer(r'save_item\(NAME\((\w+)\)\);',start) if m[1] in fields and m[0] not in reg]
functions=functions.replace(reg,reg[:-1]+'\n'+'\n'.join(extra)+'\n}',1)
tail=r'''
void settle(D &d,unsigned state){unsigned n=0;while((d.cd_stat&0xf00)!=state){CHECK(++n<64);d.cd_playdata();}}
void route(D &d,unsigned input,unsigned mode,unsigned pos){const unsigned dest=(input+1)%24;
 if(mode==4||(mode==5&&pos<3)){d.cd_connect_cddevice(255);return;}
 d.cd_connect_cddevice(input);auto &f=d.filters[input];f={};f.condtrue=dest;f.condfalse=255;
 if(mode==0){f.mode=0x40;f.fad=1236;f.range=2;}
 if(mode==1){f.mode=1;f.fid=7;}
 if(mode==2)f.condtrue=255;
 if(mode==3){f.mode=1;f.fid=6;f.condfalse=(input+2)%24;auto &g=d.filters[(input+2)%24];g={};g.mode=1;g.fid=7;g.condtrue=dest;g.condfalse=255;}
}
bool stores(unsigned mode,unsigned pos){return mode==0?(pos==2||pos==3):mode==1?(pos%2==0):mode==3?(pos%3!=2):mode==5?pos>=3:false;}
void arm(D &d,unsigned input,bool file){d.media.type=cdrom_file::CD_TRACK_MODE2_RAW;d.media.bytes[15]=2;
 if(file){d.curdir[2].length=6*2048;d.cr1=0x7400;d.cr2=0;d.cr3=input<<8;d.cr4=2;d.cmd_read_file();}
 else{d.cr1=0x1080;d.cr2=1234;d.cr3=0x80;d.cr4=6;d.cmd_play_disc();}
 settle(d,CD_STAT_PLAY);d.hirqreg=0;d.sectorstore=0;d.lastbuf=23;
}
void frame(D &d,unsigned input,unsigned mode,unsigned pos,unsigned hostkind){route(d,input,mode,pos);d.media.bytes[16]=mode==3?6+pos%3:pos%2?8:7;
 const unsigned dest=(input+1)%24;const auto count=d.partitions[dest].numblks,previous=d.lastbuf;const auto free=d.freeblocks;const auto bytes=d.xferdnum;const auto *owner=d.transpart;const auto type=d.xfertype32;const auto reads=d.media.reads;
 d.hirqreg&=~(CSCT|PEND|EFLS);d.cd_playdata();const bool keep=stores(mode,pos);
 CHECK(d.cd_curfad==1235+pos&&d.fadstoplay==5-pos&&(d.hirqreg&CSCT)&&d.sectorstore&&!d.buffull_temp_pause);
 CHECK(d.freeblocks==free-int(keep)&&d.partitions[dest].numblks==count+keep&&d.lastbuf==(keep?dest:previous));
 if(keep)CHECK(d.partitions[dest].blocks[count]->FAD==int(1234+pos));
 CHECK(d.media.reads==reads+int(mode!=4&&!(mode==5&&pos<3)));
 CHECK(d.m_host_transfer_active==bool(hostkind)&&d.transpart==owner&&d.xfertype32==type&&d.xferdnum==bytes);
 if(pos==5)CHECK(d.cd_next_stat==CD_STAT_PAUSE&&(d.hirqreg&PEND)&&bool(d.hirqreg&EFLS)==bool(d.playtype));else CHECK(!(d.hirqreg&(PEND|EFLS)));
}
void end(D &d,unsigned input,unsigned mode,unsigned cut,unsigned hostkind){for(unsigned pos=cut;pos<6;++pos)frame(d,input,mode,pos,hostkind);settle(d,CD_STAT_PAUSE);CHECK(d.cd_curfad==1240&&!d.fadstoplay);
 if(hostkind){if(hostkind==1)d.dataxfer_long_w(0xdeadbeef);else CHECK(d.dataxfer_long_r()==word(4));CHECK(d.xferdnum==8);d.cmd_end_data_transfer();CHECK(!d.m_host_transfer_active);}
}
int main(){unsigned images=0,replays=0,full=0,results=0,repeats=0;
 for(unsigned input=0;input<24;++input)for(unsigned mode=0;mode<6;++mode)for(bool file:{false,true})for(unsigned hostkind=0;hostkind<4;++hostkind)for(unsigned cut:{0U,1U,3U,5U}){
  auto p=std::make_unique<D>();auto &d=*p;seed(d,hostkind==3?(input+3)%24:input,hostkind,hostkind==3?2:hostkind?17:0);arm(d,input,file);route(d,input,mode,0);
  for(unsigned pos=0;pos<cut;++pos)frame(d,input,mode,pos,hostkind);d.register_state();d.capture();end(d,input,mode,cut,hostkind);
  d.cddevice=nullptr;d.cddevicenum=255;d.cd_curfad=42;d.fadstoplay=0;d.lastbuf=255;d.m_host_transfer_active=false;d.transpart=nullptr;d.freeblocks=0;d.restore();end(d,input,mode,cut,hostkind);++images;++replays;
 }
 for(unsigned input:{0U,7U,23U})for(unsigned mode:{2U,4U}){
  auto p=std::make_unique<D>();auto &d=*p;d.curdir.resize(3);for(unsigned i=0;i<200;++i)append(d,input,true,0);arm(d,input,false);route(d,input,mode,0);
  const auto reads=d.media.reads;d.cd_playdata();CHECK(d.cd_curfad==1234&&d.fadstoplay==6&&d.buffull_temp_pause&&!(d.hirqreg&CSCT)&&d.media.reads==reads);settle(d,CD_STAT_PAUSE);
  d.cr1=0x6200;d.cr2=0;d.cr3=input<<8;d.cr4=1;d.cmd_delete_sector_data();CHECK(d.freeblocks==1&&!d.buffull);settle(d,CD_STAT_PLAY);
  end(d,input,mode,0,0);CHECK(d.freeblocks==1);++full;
 }

 for(unsigned input:{0U,7U,23U})for(unsigned mode:{2U,4U}){
  auto p=std::make_unique<D>();auto &d=*p;d.media.type=cdrom_file::CD_TRACK_MODE2_RAW;d.media.bytes[15]=2;d.lastbuf=23;route(d,input,mode,0);
#if HAS_DISCARD_RESULT
  uint8_t stored=99;bool consumed=false;CHECK(!d.cd_read_filtered_sector(1234,&stored,&consumed)&&!stored&&consumed&&d.freeblocks==200&&d.lastbuf==23);++results;
#endif
  d.cr1=0x1080;d.cr2=1234;d.cr3=0x0280;d.cr4=2;d.cmd_play_disc();
  for(unsigned iteration=0;iteration<3;++iteration){settle(d,CD_STAT_PLAY);CHECK(d.cd_curfad==1234&&d.fadstoplay==2&&d.cdda_repeat_count==iteration);
   for(unsigned frame=0;frame<2;++frame){d.hirqreg&=~CSCT;d.cd_playdata();CHECK(d.cd_curfad==1235+frame&&(d.hirqreg&CSCT)&&d.freeblocks==200&&d.lastbuf==23);}
  }settle(d,CD_STAT_PAUSE);CHECK(!d.fadstoplay&&d.cdda_repeat_count==2);++repeats;
 }
 std::printf("method-level, unvalidated: %u discard/route/host/producer/cut images; %u registered continuations; %u full-pool pause/release controls; %u stored-versus-consumed and %u repeat controls\n",images,replays,full,results,repeats);
 std::puts("method-level, unvalidated: actual Play/Read File/drive/read/filter/pool/host/End/save methods; authored Mode2 sectors, mock image/audio/IRQ/serializer, held metadata outside replay; no native FIFO, selector activation latency, media errors, XA interleaving or save-file qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-discard-progress-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+helpers+reserve+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
