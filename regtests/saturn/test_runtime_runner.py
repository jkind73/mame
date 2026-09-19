#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Linked-runner failure protocol with a fake executable, NOT renderer evidence."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
HERE=Path(__file__).resolve().parent
fake=r'''#!/usr/bin/env python3
import os,sys
mode=os.environ['SATURN_FAKE_RESULT']
bios='bios_runtime.lua' in sys.argv[sys.argv.index('-autoboot_script')+1]
assert ('-drc' in sys.argv) == (os.environ['SATURN_FAKE_DRC']=='yes')
assert os.environ['SDL_VIDEODRIVER']=='dummy'
assert os.environ['SDL_AUDIODRIVER']=='dummy'
assert os.environ['SATURN_BIOS_FRAMES']=='900'
assert os.path.isabs(os.environ['SATURN_RUNTIME_OUTPUT'])
assert '-noreadconfig' in sys.argv
if mode=='none':sys.exit(0)
marker='BIOS_RUNTIME' if bios else 'VDP2_RUNTIME'
if not bios:
    count=1042 if os.environ['SATURN_RUNTIME_COMPOSITION']=='1' else 46
    ids=list(range(1,count+1))
    if mode=='missing':ids.pop(20)
    if mode=='duplicate':ids[20]=20
    if mode=='reordered':ids[0],ids[1]=ids[1],ids[0]
    for i in ids:print(f'VDP2_RUNTIME case={i} layer=NBG0 depth=0 cell=false rotation=false large=false pixels/save/load PASS')
    print('VDP2_RUNTIME PASS cases='+(str(count)+'0' if mode=='substring' else str(count)))
else:
    system='stvbios' if mode=='wrong-system' else sys.argv[1]
    print(f'BIOS_RUNTIME PASS system={system} time=15.560998664 pc=06040226 full-image replay identical'+(' extra' if mode=='substring' else ''))
if mode=='fail':print(marker+' FAIL deliberate negative test')
if mode=='nonzero':sys.exit(7)
'''
with tempfile.TemporaryDirectory(prefix='saturn-runtime-runner-') as temp:
    d=Path(temp);exe=d/'fake';exe.write_text(fake);exe.chmod(0o755)
    count=0
    for suite in ('backgrounds','composition','bios'):
        bios=suite=='bios'
        modes=['good','none','substring','fail','nonzero']+(['wrong-system'] if bios else ['missing','duplicate','reordered'])
        for drc in (False,True):
            for mode in modes:
                command=[sys.executable,str(HERE/'run_vdp2_runtime.py'),'--executable',str(exe),'--rompath',str(d),'--output',str(d/'output')]
                if bios:command+=['--bios']
                if suite=='composition':command+=['--composition']
                if drc:command+=['--drc']
                env=os.environ.copy();env.update(SATURN_FAKE_RESULT=mode,SATURN_FAKE_DRC='yes' if drc else 'no')
                result=subprocess.run(command,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=10)
                assert (result.returncode==0)==(mode=='good'),(bios,drc,mode,result.stdout)
                assert (d/'output/runtime.log').exists()
                count+=1
print(f'{count} fake-executable runner protocol cases passed (not linked MAME execution)')

# Validate the supplied CD/cart runners without pretending to emulate hardware.
device_fake=r'''#!/usr/bin/env python3
import os,sys
mode=os.environ['SATURN_DEVICE_FAKE_RESULT']
if 'SATURN_BRMODE' in os.environ:
 marker='BACKUP_RAM';message=marker+' OK '+os.environ['SATURN_BRMODE']
elif '-cart' in sys.argv:
 cart=sys.argv[sys.argv.index('-cart')+1]
 marker='CART_RUNTIME'
 message=marker+' PASS '+('dram (ram8)' if cart=='ram8' else 'bram (bram4)')
else:
 marker='CD_HIRQ_RUNTIME';message=marker+' PASS'
if mode=='empty':sys.exit(0)
print(message+(' extra' if mode=='substring' else ''))
if mode=='fail':print(marker+' FAIL deliberate')
if mode=='lua':print('LUA ERROR deliberate')
if mode=='nonzero':sys.exit(7)
'''
with tempfile.TemporaryDirectory(prefix='saturn-device-protocol-') as temp:
    d=Path(temp);exe=d/'fake';exe.write_text(device_fake);exe.chmod(0o755)
    (d/'saturnjp.zip').touch();(d/'sat_cart.xml').touch()
    count=0
    for name in ('test_cd_hirq.py','test_cart_runtime.py','test_backup_ram.py'):
        for mode in ('good','empty','substring','fail','lua','nonzero'):
            command=[sys.executable,str(HERE/name),'--executable',str(exe),'--rompath',str(d)]
            if name=='test_cart_runtime.py':command+=['--hashpath',str(d)]
            env=os.environ.copy();env['SATURN_DEVICE_FAKE_RESULT']=mode
            result=subprocess.run(command,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=10)
            assert (result.returncode==0)==(mode=='good'),(name,mode,result.stdout)
            count+=1
    print(f'{count} fake-executable CD/cart/backup failure-protocol cases passed (not hardware evidence)')
