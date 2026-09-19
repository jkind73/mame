#!/usr/bin/env python3
"""Sector metadata query range/END/response behavior; method-level, unvalidated."""
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
 unsigned irqs=0;
 void update_hirq(){++irqs;}void cr_standard_return(uint16_t status){cr1=status;cr2=cr3=cr4=0;}
 void cmd_get_sector_information();
};
#define LOGWARN(...) ((void)0)
constexpr unsigned CMOK=1,ESEL=0x40,CD_STAT_REJECT=0xff00;
'''
method=extract(source,'void saturn_cd_hle_device::cmd_get_sector_information()')
tail=r'''
int main(){auto d=std::make_unique<saturn_cd_hle_device>();unsigned queries=0,rejections=0;
 for(unsigned p=0;p<24;++p)for(unsigned count:{0U,1U,3U,199U,200U}){
  auto &part=d->partitions[p];part.numblks=count;part.size=count*2048;
  // Poison unused pointers with real allocated storage. Count, not merely
  // non-null pointers, defines the accessible sector positions.
  for(unsigned i=0;i<200;++i){auto &b=d->blocks[(i*67)%200];part.blocks[i]=&b;part.bnum[i]=(i*67)%200;
   b.size=2048;b.FAD=(0x123456^(p*0x10001+i*0x101))&0xffffff;b.fnum=i;b.chan=i^0xa5;b.subm=i^0x5a;b.cinf=i^0xff;
  }
  for(unsigned position=0;position<65536;++position){
   const unsigned effective=position==0xffff&&count?count-1:position;const bool valid=effective<count;
   const unsigned pending=(position&1)?0x8040:0;d->hirqreg=pending;d->cr1=0x5400;d->cr2=position;d->cr3=p<<8;d->cr4=0xbeef;const unsigned old_irq=d->irqs;
   d->cmd_get_sector_information();CHECK(d->hirqreg==(pending|CMOK)&&d->irqs==old_irq+1&&part.numblks==count&&part.size==int(count*2048));
   if(valid){const auto &b=*part.blocks[effective];CHECK(d->cr1==(0x100|(b.FAD>>16))&&d->cr2==(b.FAD&0xffff)&&d->cr3==((unsigned(b.fnum)<<8)|b.chan)&&d->cr4==((unsigned(b.subm)<<8)|b.cinf));++queries;}
   else{CHECK(d->cr1==CD_STAT_REJECT);++rejections;}
  }
 }
 for(unsigned p=24;p<256;++p){d->cr1=0x5400;d->cr2=0xffff;d->cr3=p<<8;d->hirqreg=0;d->cmd_get_sector_information();CHECK(d->cr1==CD_STAT_REJECT&&d->hirqreg==CMOK);++rejections;}
 d->partitions[0].numblks=1;d->partitions[0].blocks[0]=nullptr;d->cr3=0;d->cr2=0;d->cmd_get_sector_information();CHECK(d->cr1==CD_STAT_REJECT);
 std::printf("method-level, unvalidated: %u metadata/END responses; %u unavailable/invalid-index controls across all 16-bit positions, 24 partitions and five lengths; null-pointer control\n",queries,rejections);
 std::puts("method-level, unvalidated: actual command; poisoned unused-slot diagnostics; mocked standard response/IRQ, not native transport/timing/empty-media qualification");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-sectorinfo-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check'
    cpp.write_text(head+method+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
