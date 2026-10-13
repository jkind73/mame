#!/usr/bin/env python3
# license:BSD-3-Clause
"""Exercise the actual SCSP master attenuation before output saturation."""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parent.parent
source = (root / 'src/devices/sound/scsp.cpp').read_text()
start = source.index('s32 scsp_device::apply_master_volume(')
end = source.index('\nvoid scsp_device::device_post_load()', start)
method = source[start:end]
fixture = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
using s32=int32_t; using s64=int64_t;
struct scsp_device {
 unsigned volume=15;
 unsigned MVOL() const { return volume; }
 s32 apply_master_volume(s32 sample) const;
};
'''
tests = r'''
int main() {
 scsp_device d;
 for(unsigned volume=0;volume<16;++volume) {
  d.volume=volume;
  for(s32 sample: {INT32_MIN, -262144, -65536, -32769, -1, 0, 1, 32767, 65536, 262144, INT32_MAX}) {
   // Independent rational oracle, rounding negative results toward minus infinity.
   s64 numerator=s64(sample)*(volume&1 ? 4 : 3);
   s64 denominator=s64(4)<<( (volume^15)>>1 );
   s64 expected=volume ? numerator/denominator : 0;
   if(volume && numerator<0 && numerator%denominator) --expected;
   assert(d.apply_master_volume(sample)==expected);
  }
 }
 // A loud mix at half volume remains loud, rather than clipping then halving.
 d.volume=13;
 assert(std::clamp(d.apply_master_volume(65536), -32768, 32767)==32767);
 assert(std::clamp(65536, -32768, 32767)/2==16383);
 // Both DAC paths attenuate before clipping, and mute suppresses any mix.
 assert(std::clamp(d.apply_master_volume(262144)>>2,-32768,32767)==32767);
 d.volume=0; assert(d.apply_master_volume(INT32_MAX)==0);
}
'''
with tempfile.TemporaryDirectory(prefix='scsp-master-volume-') as directory:
    out=Path(directory)
    (out/'test.cpp').write_text(fixture+method+tests)
    subprocess.run(['clang++','-std=c++20','-O1','-g','-fsanitize=address,undefined',str(out/'test.cpp'),'-o',str(out/'test')],check=True)
    subprocess.run([str(out/'test')],check=True)
assert 'set_output_gain(0, master_gain())' not in source
assert source.index('smpl = apply_master_volume(smpl)') < source.index('stream.put_int_clamp(0, s, smpl, 32768)')
print('SCSP master attenuation/clipping ASan/UBSan checks passed')
