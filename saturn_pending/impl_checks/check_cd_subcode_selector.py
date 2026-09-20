#!/usr/bin/env python3
"""Unsupported subcode selectors cannot acquire a phantom transfer; method-level, unvalidated."""
from pathlib import Path
import subprocess
import tempfile
fixture=Path(__file__).with_name('check_cd_host_transfer_lifecycle.py')
scope={'__file__':str(fixture),'__name__':'subcode_selector_scaffold'}
exec(compile(fixture.read_text().split("\ntail=r'''",1)[0],str(fixture),'exec'),scope)
head,functions=(scope[k] for k in ('head','functions'))
tail=r'''
using D=saturn_cd_hle_device;
void issue(D &d,unsigned type){d.cr1=0x2000|type;d.cr2=0xabcd;d.cr3=0x1234;d.cr4=0x5678;d.cmd_get_subcode_q_rw_channel();}
int main(){auto d=std::make_unique<D>();unsigned refused=0,busy=0,starts=0;d->cd_stat=0x100;
 for(unsigned type=2;type<256;++type)for(unsigned pending=0;pending<65536;++pending){
  d->hirqreg=pending;d->xfercount=17;d->xferdnum=42;d->subqbuf[0]=0xa5;d->subrwbuf[0]=0x5a;const auto irqs=d->irqs;issue(*d,type);
  CHECK(d->cr1==CD_STAT_REJECT&&d->hirqreg==(pending|CMOK)&&d->irqs==irqs+1&&!d->m_host_transfer_active&&d->cd_stat==0x100);
  CHECK(d->xfertype==D::XFERTYPE_INVALID&&d->xfertype32==D::XFERTYPE32_INVALID&&d->xfercount==17&&d->xferdnum==42&&d->subqbuf[0]==0xa5&&d->subrwbuf[0]==0x5a&&d->m_put_filter==0xff);
  CHECK(d->seen[0]==CD_STAT_REJECT&&!d->seen_active);++refused;
 }
 d->xfercount=d->xferdnum=0;
 for(unsigned accepted:{0U,1U}){issue(*d,255);issue(*d,accepted);const unsigned words=accepted?12:5;CHECK(d->cr2==words&&d->m_host_transfer_active&&(d->hirqreg&DRDY));
  for(unsigned i=0;i<words;++i)d->dataxfer_word_r();CHECK(d->xfertype==D::XFERTYPE_INVALID&&d->m_host_transfer_active);
  for(unsigned type=0;type<256;++type)for(unsigned pending:{0U,2U,0x201U,0xffffU}){d->hirqreg=pending;issue(*d,type);
   CHECK(d->cr1==(d->cd_stat|CD_STAT_WAIT)&&d->hirqreg==(pending|CMOK)&&d->m_host_transfer_active&&d->xfertype==D::XFERTYPE_INVALID&&d->xferdnum==words*2);++busy;}
  d->cmd_end_data_transfer();CHECK(d->cr2==words&&!d->m_host_transfer_active);++starts;
 }
 std::printf("method-level, unvalidated: %u unsupported-selector/pending-HIRQ images; %u EOF-owner WAIT precedence images; %u legal-start/End controls\n",refused,busy,starts);
 std::puts("method-level, unvalidated: actual selector/WAIT/word/End methods with mock report/media/IRQ; cursor poison is diagnostic; Q geometry, RW packet availability, status formatting and native timing excluded");
}
'''
with tempfile.TemporaryDirectory(prefix='impl-cd-subcode-selector-') as directory:
    cpp=Path(directory)/'check.cpp';exe=Path(directory)/'check';cpp.write_text(head+functions+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
