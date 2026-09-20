#!/usr/bin/env python3
"""Current-position Q track/control lookup; extracted method, not native validation."""
from pathlib import Path
import argparse
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[2]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--mutate', choices=['fad', 'control'])
a = p.parse_args()
s = (ROOT / 'src/mame/sega/saturn_cd_hle.cpp').read_text()
start = s.index('void saturn_cd_hle_device::cmd_get_subcode_q_rw_channel()')
end = s.index('\n// Filter inputs', start)
method = s[start:end]
if a.mutate == 'fad':
    method = method.replace('get_track(cd_curfad - 150)', 'get_track(cd_curfad)')
if a.mutate == 'control':
    method = method.replace('get_track_type(track)', 'get_track_type(m_cdrom_image->get_track(track + 1))')
head = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <vector>
#define LOG(...) ((void)0)
constexpr unsigned CD_STAT_TRANS=0x4000,CD_STAT_REJECT=0xff00,CMOK=1,DRDY=2;
unsigned dec_2_bcd(unsigned n){return (n/10)*16+n%10;}
namespace cdrom_file {
constexpr unsigned CD_TRACK_AUDIO=0;
unsigned lba_to_msf_alt(unsigned lba){return ((lba/4500)<<16)|((lba/75%60)<<8)|(lba%75);}
}
struct Media {
 unsigned mask=0; std::vector<unsigned> lookups,types;
 static constexpr unsigned starts[]={0,100,210,600};
 unsigned get_track(unsigned lba){lookups.push_back(lba);assert(lba<600);return lba<100?0:lba<210?1:2;}
 unsigned get_track_start(unsigned t){assert(t<3);return starts[t];}
 unsigned get_track_type(unsigned t){assert(t<3);types.push_back(t);return (mask>>t)&1?0:1;}
};
struct saturn_cd_hle_device {
 Media media;Media *m_cdrom_image=&media;
 unsigned cr1=0,cr2=0,cr3=0,cr4=0,cd_stat=0x300,cd_curfad=150,hirqreg=0,xfercount=7,xfertype=0;
 uint8_t subqbuf[10]{},subrwbuf[24]{};
 enum {XFERTYPE_SUBQ=1,XFERTYPE_SUBRW=2};bool m_host_transfer_active=false,wait=false;
 bool cd_transfer_wait(){return wait;}void cr_standard_return(unsigned s){cr1=s;}
 unsigned get_track_index(unsigned){return 1;}void update_hirq(){}
 void cmd_get_subcode_q_rw_channel();
};
'''
tail = r'''
int main(){unsigned cases=0;
 for(unsigned mask=0;mask<8;++mask)for(unsigned lba=0;lba<440;++lba){
  saturn_cd_hle_device d;d.media.mask=mask;d.cd_curfad=lba+150;d.cmd_get_subcode_q_rw_channel();
  unsigned t=lba<100?0:lba<210?1:2;
  assert(d.media.lookups==std::vector<unsigned>{lba});
  assert(d.media.types==std::vector<unsigned>{t});
  assert(d.subqbuf[1]==dec_2_bcd(t+1));assert(d.subqbuf[0]==(((mask>>t)&1)?1:0x41));
  assert(d.subqbuf[2]==1&&d.cr2==5&&d.xfercount==0&&d.xfertype==d.XFERTYPE_SUBQ);
  assert(d.m_host_transfer_active&&(d.hirqreg&(CMOK|DRDY))==(CMOK|DRDY));++cases;
 }
 saturn_cd_hle_device w;w.wait=true;w.cmd_get_subcode_q_rw_channel();assert(w.media.lookups.empty()&&!w.m_host_transfer_active);
 saturn_cd_hle_device r;r.cr1=2;r.cmd_get_subcode_q_rw_channel();assert(r.cr1==CD_STAT_REJECT&&r.media.lookups.empty()&&!r.m_host_transfer_active);
 std::printf("method-level, unvalidated: %u Q current-position track/control images; 2 admission controls\n",cases);
}
'''
with tempfile.TemporaryDirectory(prefix='subq-position-') as tmp:
    cpp=Path(tmp)/'probe.cpp';exe=Path(tmp)/'probe';cpp.write_text(head+method+tail)
    subprocess.run(['g++','-std=c++20','-O2','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
