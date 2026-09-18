#!/usr/bin/env python3
# license:BSD-3-Clause
"""Real MAME debugger dump of stopped DSP program RAM uploaded via host ports."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from test_smpc_multitap_runtime import COMMON_LUA
ROOT=Path(__file__).resolve().parents[1]
def vectors():
    result=[]
    mvi=['MC0','MC1','MC2','MC3','RX','PL','RA0','WA0','???','???','LOP','???','PC','???','???','???']
    d1=['MC0','MC1','MC2','MC3','RX','PL','RA0','WA0','???','???','LOP','TOP','CT0','CT1','CT2','CT3']
    for dest in range(16):
        for cond in (False,True):
            result.append((0x80000000|(dest<<26)|0x12345|(0x03080000 if cond else 0),f'MVI #$12345,{mvi[dest]}'+(',Z' if cond else '')))
        result.append((0x1031|(dest<<8),f'MOV #$31,{d1[dest]}'))
    for x in range(8):
        for y in range(8):
            for bus in (0,1,3):
                op=(4<<26)|(x<<23)|(y<<17)|(1<<14)|(bus<<12)|(3<<8)|(0x31 if bus==1 else 2)
                text=['ADD']
                if x&4:text.append('MOV M0,X')
                if x&3==2:text.append('MOV MUL,P')
                if x&3==3:text.append('MOV M0,P')
                if y&4:text.append('MOV M1,Y')
                if y&3==1:text.append('CLR A')
                if y&3==2:text.append('MOV ALU,A')
                if y&3==3:text.append('MOV M1,A')
                if bus==1:text.append('MOV #$31,MC3')
                if bus==3:text.append('MOV M2,MC3')
                result.append((op,' '.join(text)))
    return result+[(0,'NOP')]
VECTORS=vectors()
LUA=COMMON_LUA+'\nlocal code={'+','.join(hex(op) for op,_ in VECTORS)+r'''}
local frames,done=0,false
emu.register_frame_done(function()
    frames=frames+1;if done or frames<180 then return end;done=true
    local ok,err=pcall(function()
        park();sp:write_u32(0x05fe0080,0x8000)
        for _,op in ipairs(code) do sp:write_u32(0x05fe0084,op) end
        assert(m.debugger,'debugger not enabled')
        m.debugger:command('dasm "'..assert(os.getenv('DSP_DASM_FILE'))..'",0,f1,0,:scu:scudsp')
        print('DSP_DASM dumped words=241')
    end)
    if not ok then print('DSP_DASM FAIL '..tostring(err)) end
    m:exit()
end)
print('DSP_DASM armed')
'''
def validate_output(log,dump,returncode):
    if returncode or 'DSP_DASM FAIL' in log or 'LUA ERROR' in log or len(re.findall(r'^DSP_DASM dumped words=241$',log,re.M))!=1:
        raise RuntimeError('Debugger fixture failed:\n'+log[-6000:])
    rows=re.findall(r'^([0-9a-fA-F]+):\s*(.*?)\s*$',dump,re.M)
    if len(rows)!=len(VECTORS):raise RuntimeError(f'Missing debugger rows: {len(rows)} of {len(VECTORS)}')
    errors=[]
    for i,((address,text),(_,expected)) in enumerate(zip(rows,VECTORS)):
        if int(address,16)!=i or ' '.join(text.split())!=expected:
            errors.append(f'row{i}: {text!r} != {expected!r}')
    if errors:raise RuntimeError(f'{len(errors)} disassembly mismatches:\n'+'\n'.join(errors))
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--executable',type=Path,required=True);p.add_argument('--rompath',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();exe=a.executable.resolve();rom=a.rompath.resolve();output=a.output.resolve();output.mkdir(parents=True,exist_ok=True)
    if not exe.is_file() or not (rom/'saturnjp.zip').is_file():raise RuntimeError('Native binary and JP BIOS required')
    (output/'invocation.json').write_text(json.dumps({'binary_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'bios_sha256':hashlib.sha256((rom/'saturnjp.zip').read_bytes()).hexdigest(),'lua_sha256':hashlib.sha256(LUA.encode()).hexdigest(),'engine':'interpreter','debugger':'none'},indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='dsp-dasm-live-') as tmp:
        d=Path(tmp);(d/'test.lua').write_text(LUA)
        command=[str(exe),'saturnjp','-rompath',str(rom),'-noreadconfig','-skip_gameinfo','-nodrc','-debug','-debugger','none','-video','none','-sound','none','-nothrottle','-seconds_to_run','30','-autoboot_delay','0','-autoboot_script',str(d/'test.lua')]
        for option in ('nvram','cfg','state','snapshot'):command+=['-'+option+'_directory',str(d/option)]
        env={**os.environ,'SDL_VIDEODRIVER':'dummy','SDL_AUDIODRIVER':'dummy','DSP_DASM_FILE':str(d/'dasm.txt')}
        with (output/'runtime.log').open('w') as log:run=subprocess.run(command,cwd=d,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
        dump=(d/'dasm.txt').read_text() if (d/'dasm.txt').is_file() else ''
        (output/'disassembly.txt').write_text(dump)
        validate_output((output/'runtime.log').read_text(),dump,run.returncode)
    print('DSP disassembler: 241 real debugger destination/parallel-command rows passed')
if __name__=='__main__':main()
