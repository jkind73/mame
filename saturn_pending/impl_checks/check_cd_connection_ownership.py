#!/usr/bin/env python3
"""Single-producer filter inputs and atomic connector validation; method-level, unvalidated."""
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
head=next(ast.literal_eval(n.value) for n in ast.parse(Path(__file__).with_name('check_cd_filter_routing.py').read_text()).body
          if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='head' for t in n.targets))
head=head.replace('// TYPES','\n'.join(extract(header,'struct '+s)+';' for s in ('filterT','blockT','partitionT')))
head=head[:head.rfind('};')]+r'''
 uint16_t cr1=0,cr2=0,cr3=0,cr4=0,cd_stat=0x100,hirqreg=0;
 unsigned irqs=0;int sectorstore=0,cddevicenum=0xff;bool buffull_temp_pause=false;
 void update_hirq(){++irqs;}void cr_standard_return(uint16_t status){cr1=status;cr2=cr3=cr4=0;}
 void cd_free_block(blockT*){CHECK(false);}void popmessage(const char*,unsigned){}
 void cmd_set_cddevice_connection();void cmd_get_cddevice_connection();void cmd_set_filter_connection();
 void cmd_reset_selector();void cd_reset_filter_conditions(filterT&);void cd_disconnect_filter_input(uint8_t);
};
#define LOGCMD(...) ((void)0)
#define LOGWARN(...) ((void)0)
#define BIT(v,b) (((v)>>(b))&1)
constexpr unsigned CMOK=1,ESEL=0x40,CD_STAT_REJECT=0xff00;
'''
head='#include <array>\n'+head
names=['cmd_set_cddevice_connection','cmd_get_cddevice_connection','cmd_set_filter_connection','cmd_reset_selector','cd_reset_filter_conditions']
if 'void saturn_cd_hle_device::cd_disconnect_filter_input(' in source:names+=['cd_disconnect_filter_input']
functions='\n'.join(extract(source,'void saturn_cd_hle_device::'+s+'(') for s in names)
tail=r'''
using D=saturn_cd_hle_device;using Image=std::array<D::filterT,24>;
unsigned endpoint(unsigned value){return value==24?0xff:value;}
void seed(D &d,unsigned cd,unsigned producer,unsigned destination){
 for(unsigned i=0;i<24;++i){auto &f=d.filters[i];f={};f.condtrue=7;f.condfalse=0xff;f.mode=0x4f;f.fad=150+i;f.range=200+i;f.fid=f.chan=i;}
 if(producer<24)d.filters[producer].condfalse=destination;
 d.cddevicenum=cd;d.cddevice=cd<24?&d.filters[cd]:nullptr;d.hirqreg=0;
}
Image image(const D &d){Image a;std::memcpy(a.data(),d.filters,sizeof(d.filters));return a;}
void expect(const D &d,const Image &a,unsigned cd){CHECK(!std::memcmp(a.data(),d.filters,sizeof(d.filters)));CHECK(d.cddevicenum==int(cd)&&d.cddevice==(cd<24?&d.filters[cd]:nullptr));CHECK(d.freeblocks==200);}
void write(D &d,unsigned source,unsigned flags,unsigned t,unsigned f){d.cr1=0x4600|flags;d.cr2=t<<8|f;d.cr3=source<<8;d.cmd_set_filter_connection();}
void expected(Image &a,unsigned source,unsigned flags,unsigned t,unsigned f){
 if(flags&1)a[source].condtrue=t;
 if(flags&2){if(f<24)for(auto &row:a)if(row.condfalse==f)row.condfalse=0xff;a[source].condfalse=f;}
}
int main(){auto d=std::make_unique<D>();unsigned cd_cases=0,false_cases=0,validation=0;
 for(unsigned input=0;input<=24;++input)for(unsigned cd=0;cd<=24;++cd)for(unsigned rival=0;rival<=24;++rival){
  const unsigned dest=endpoint(input);seed(*d,endpoint(cd),rival,dest);auto want=image(*d);
  if(dest<24)for(auto &f:want)if(f.condfalse==dest)f.condfalse=0xff;
  d->cr3=dest<<8;d->cmd_set_cddevice_connection();expect(*d,want,dest);CHECK(d->cr1==d->cd_stat&&d->hirqreg==(CMOK|ESEL));
  d->cmd_get_cddevice_connection();CHECK(d->cr3==(dest<<8));++cd_cases;
 }
 for(unsigned source=0;source<24;++source)for(unsigned input=0;input<=24;++input)
 for(unsigned cd:{input,(input+1)%24,24U})for(unsigned rival:{source,(source+1)%24,24U})for(unsigned flags:{2U,3U}){
  const unsigned dest=endpoint(input),old_cd=endpoint(cd);seed(*d,old_cd,rival,dest);auto want=image(*d);
  expected(want,source,flags,7,dest);write(*d,source,flags,7,dest);
  expect(*d,want,(dest<24&&old_cd==dest)?0xff:old_cd);CHECK(d->cr1==d->cd_stat);++false_cases;
 }
 for(unsigned source:{0U,23U,24U,255U})for(unsigned flags=0;flags<4;++flags)
 for(bool vary_true:{false,true})for(unsigned value=0;value<256;++value){
  const unsigned t=vary_true?value:7,f=vary_true?3:value;
  const bool reject=source>=24||((flags&1)&&t>=24&&t!=0xff)||((flags&2)&&f>=24&&f!=0xff);
  seed(*d,3,1,2);auto want=image(*d);unsigned cd=3;
  if(!reject){expected(want,source,flags,t,f);if((flags&2)&&f==cd)cd=0xff;}
  write(*d,source,flags,t,f);expect(*d,want,cd);CHECK(d->cr1==(reject?CD_STAT_REJECT:d->cd_stat));++validation;
 }
 for(unsigned input=24;input<255;++input){seed(*d,3,1,2);auto want=image(*d);d->cr3=input<<8;d->cmd_set_cddevice_connection();expect(*d,want,3);CHECK(d->cr1==CD_STAT_REJECT);++validation;}
 for(unsigned input=0;input<24;++input){seed(*d,input,(input+1)%24,input);auto want=image(*d);for(auto &f:want)f.condfalse=0xff;d->cr1=0x4820;d->cmd_reset_selector();expect(*d,want,0xff);d->cmd_get_cddevice_connection();CHECK(d->cr3==0xff00);}
 // Legacy file commands can set the pointer without changing the visible number.
 seed(*d,3,1,2);d->cddevicenum=2;write(*d,0,2,0,3);CHECK(!d->cddevice&&d->cddevicenum==0xff);
 seed(*d,3,1,2);d->cddevicenum=2;write(*d,0,2,0,2);CHECK(d->cddevice==&d->filters[3]);
 std::printf("method-level, unvalidated: %u CD connector cases; %u false-output ownership cases; %u selected-byte/bounds controls; 24 input resets; actual-pointer legacy controls\n",cd_cases,false_cases,validation);
 std::puts("method-level, unvalidated: actual commands/helpers; includes duplicate-producer and cyclic-storage diagnostics, not native stream/scheduler/IRQ qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-connections-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
