#!/usr/bin/env python3
# license:BSD-3-Clause
"""Execute the actual VDP2 reset method with deliberately dirty register state."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

root=Path(__file__).resolve().parent.parent
source=(Path(sys.argv[1]) if len(sys.argv)>1 else root/'src/mame/sega/saturn_vdp2.cpp').read_text()
method=source[source.index('void saturn_vdp2_device::device_reset()'):source.index('void saturn_vdp2_device::init_vcounter_table()')]
fields=set(re.findall(r'\bm_[a-zA-Z_]+',method))|{'m_vramsz'}
fixture='#include <cassert>\n#include <cstdint>\nstruct saturn_vdp2_device {\n'
fixture+='\n'.join('uint32_t '+f+'=0xffffffff;' for f in sorted(fields))
fixture+='\nunsigned reconfigured=0; void reconfigure_crtc(){++reconfigured;} void device_reset();};\n'+method
fixture+='\nint main(){saturn_vdp2_device d;d.device_reset();assert(d.m_vramsz==0);assert(d.m_tvmd==0 && d.m_exten==0);assert(d.m_hcounter_latch==0 && d.m_vcounter_latch==0);assert(d.reconfigured==1);}\n'
with tempfile.TemporaryDirectory(prefix='saturn-vdp2-reset-unit-') as directory:
    out=Path(directory);(out/'test.cpp').write_text(fixture)
    subprocess.run(['clang++','-std=c++17','-O1','-g','-fsanitize=address,undefined',str(out/'test.cpp'),'-o',str(out/'test')],check=True)
    subprocess.run([str(out/'test')],check=True)
print('Actual VDP2 TVMD/EXTEN/VRSIZE/latch reset PASS')
