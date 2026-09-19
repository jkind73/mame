#!/usr/bin/env python3
"""CD condition initialization must preserve unselected connectors; method-level, unvalidated."""
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
 void cd_free_block(blockT*){CHECK(false);}
 void cmd_set_filter_mode();void cmd_reset_selector();void cd_reset_filter_conditions(filterT&);
};
#define LOGCMD(...) ((void)0)
#define BIT(v,b) (((v)>>(b))&1)
constexpr unsigned CMOK=1,ESEL=0x40,CD_STAT_REJECT=0xff00;
'''
functions='\n'.join(extract(source,s) for s in ('void saturn_cd_hle_device::cmd_set_filter_mode()', 'void saturn_cd_hle_device::cmd_reset_selector()'))
if 'void saturn_cd_hle_device::cd_reset_filter_conditions(' in source:
    functions+='\n'+extract(source,'void saturn_cd_hle_device::cd_reset_filter_conditions(')
tail=r'''
using D=saturn_cd_hle_device;
void poison(D &d,unsigned value){for(unsigned i=0;i<24;++i){auto &f=d.filters[i];f.mode=0x4f;f.fad=150+value;f.range=300+value;f.chan=f.fid=value;f.smmask=0x7f;f.smval=value;f.cimask=0xf;f.cival=value;f.condtrue=(i+7)%24;f.condfalse=0xff;}}
void zero(const D::filterT &f){CHECK(!f.mode&&!f.fad&&!f.range&&!f.chan&&!f.fid&&!f.smmask&&!f.smval&&!f.cimask&&!f.cival);}
int main(){
 auto d=std::make_unique<D>();unsigned single=0,ordinary=0,bulk=0;
 for(unsigned target=0;target<24;++target)for(unsigned t=0;t<=24;++t)
 for(unsigned f:{0U,7U,23U,255U})for(unsigned mode:{0x80U,0xdfU}){
  poison(*d,37);d->filters[target].condtrue=t==24?0xff:t;d->filters[target].condfalse=f;
  d->cr1=0x4400|mode;d->cr3=target<<8;d->cmd_set_filter_mode();
  zero(d->filters[target]);CHECK(d->filters[target].condtrue==(t==24?0xff:t)&&d->filters[target].condfalse==f);
  for(unsigned i=0;i<24;++i)if(i!=target)CHECK(d->filters[i].mode==0x4f&&d->filters[i].fad==187&&d->filters[i].range==337&&d->filters[i].condtrue==(i+7)%24&&d->filters[i].condfalse==0xff);
  CHECK(d->cr1==d->cd_stat&&(d->hirqreg&(CMOK|ESEL))==(CMOK|ESEL));++single;
 }
 for(unsigned target=0;target<24;++target)for(unsigned mode=0;mode<128;++mode){
  if(mode&0x20)continue;poison(*d,53);d->cr1=0x4400|mode;d->cr3=target<<8;d->cmd_set_filter_mode();
  const auto &f=d->filters[target];CHECK(f.mode==mode&&f.fad==203&&f.range==353&&f.fid==53&&f.chan==53&&f.smmask==0x7f&&f.smval==53&&f.cimask==0xf&&f.cival==53&&f.condtrue==(target+7)%24&&f.condfalse==0xff);++ordinary;
 }
 for(unsigned value=0;value<256;++value)for(unsigned flags:{0x10U,0x50U,0x90U,0xd0U}){
  poison(*d,value);for(unsigned i=0;i<24;++i)d->filters[i].condfalse=(i+1)%24;
  d->cr1=0x4800|flags;d->cmd_reset_selector();
  for(unsigned i=0;i<24;++i){const auto &f=d->filters[i];zero(f);CHECK(f.condtrue==((flags&0x40)?i:(i+7)%24));CHECK(f.condfalse==((flags&0x80)?0xff:(i+1)%24));}
  CHECK(d->freeblocks==200&&d->cr1==d->cd_stat);++bulk;
 }
 std::printf("method-level, unvalidated: %u selected-filter initialize cases; %u ordinary mode-write controls; %u bulk condition/connector-mask cases\n",single,ordinary,bulk);
 std::puts("method-level, unvalidated: actual commands/helper, recording IRQ/response; connector storage diagnostics do not qualify cycles, timing or native gameplay/save behavior");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-conditions-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
