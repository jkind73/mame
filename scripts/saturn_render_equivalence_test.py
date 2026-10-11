#!/usr/bin/env python3
# license:BSD-3-Clause
"""Compare a saved pre-change renderer with the current renderer on 4096 varied lines."""
import argparse
from pathlib import Path
import subprocess
import tempfile
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reference',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='saturn-render-equivalence-') as tmp:
    values=[]
    for name,source in [('reference',a.reference.resolve()),('current',root/'src/mame/sega/saturn_vdp2_render.cpp')]:
        binary=Path(tmp)/name
        subprocess.run(['clang++','-std=c++17','-O1','-fsanitize=address,undefined',
                        '-I',str(root/'src/mame/sega'),str(root/'tests/saturn/vdp2_render_digest_test.cpp'),
                        str(source),'-o',str(binary)],check=True)
        values.append(subprocess.check_output([str(binary)],text=True).strip())
    assert values[0]==values[1],values
    print('VDP2 renderer equivalence PASS: 4096 varied lines, digest',values[0])
