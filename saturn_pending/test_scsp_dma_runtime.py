#!/usr/bin/env python3
# license:BSD-3-Clause
"""Mapped SCSP DMA controls and forbidden self-target host-safety policy.

SCSP_DMA_SELF_EXECUTE=1 opts into recursive-execute payloads, for fixed binaries
only. The default safe negative control does not submit DEXE in DMA payloads.
"""
import os
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
CASES=48 if os.getenv('SCSP_DMA_SELF_EXECUTE')=='1' else 40
runner.LUA=COMMON_LUA+r'''
local frames,started=0,false
local base=0x05b00000
local function test()
    park();local snd=assert(m.devices[':audiocpu']);local ss=snd.spaces['program']
    ss:write_u16(0x70000,0x60fe);snd.state['SR'].value=0x2700;snd.state['PC'].value=0x70000
    sp:write_u16(base+0x41e,0);sp:write_u16(base+0x42a,0)
    for i=0,511 do sp:write_u16(base+0x800+i*2,0) end
    for i=0,3 do sp:write_u16(0x05a00000+i*2,0);sp:write_u16(0x05a09000+i*2,0) end
    local case=0
    local payloads={0,0x2000}
    if os.getenv('SCSP_DMA_SELF_EXECUTE')=='1' then payloads={0,0x2000,0x1008,0x7008} end
    for _,bus in ipairs({{space=sp,base=base},{space=ss,base=0x100000}}) do
      for _,dir in ipairs({false,true}) do for _,gate in ipairs({false,true}) do
        for _,length in ipairs({0,2,32,128}) do
          case=case+1;local before=#fails
          for i=0,63 do sp:write_u16(0x05a08000+i*2,0x4000~(i*24));sp:write_u16(base+0x700+i*2,0x8000~(i*24)) end
          sp:write_u16(base+0x422,0x10);sp:write_u16(base+0x42e,0x10)
          bus.space:write_u16(bus.base+0x412,0x8000);bus.space:write_u16(bus.base+0x414,0x700)
          bus.space:write_u16(bus.base+0x416,0x1000|(dir and 0x2000 or 0)|(gate and 0x4000 or 0)|length)
          for i=0,63 do
            local transferred=i<length//2
            local want_mem=0x4000~(i*24);local want_reg=0x8000~(i*24)
            if transferred then
              if dir then want_mem=gate and 0 or want_reg else want_reg=gate and 0 or want_mem end
            end
            check('memory'..case..'_'..i,sp:read_u16(0x05a08000+i*2),want_mem)
            check('coefficient'..case..'_'..i,sp:read_u16(base+0x700+i*2),want_reg)
          end
          check('execute_done'..case,sp:read_u16(base+0x416)&0x1000,0)
          check('sound_done'..case,sp:read_u16(base+0x420)&0x10,0x10)
          check('main_done'..case,sp:read_u16(base+0x42c)&0x10,0x10)
          if #fails==before then print('SCSP_DMA case='..case..' PASS') end
        end
      end end
      for _,gate in ipairs({false,true}) do for _,payload in ipairs(payloads) do
        case=case+1;local before=#fails
        sp:write_u16(0x05a08000,0x9000);sp:write_u16(0x05a08002,0x700)
        sp:write_u16(0x05a08004,payload);sp:write_u16(0x05a08006,0x300)
        bus.space:write_u16(bus.base+0x412,0x8000);bus.space:write_u16(bus.base+0x414,0x412)
        bus.space:write_u16(bus.base+0x416,0x1008|(gate and 0x4000 or 0))
        check('following_register'..case,sp:read_u16(base+0x418)&0x700,gate and 0 or 0x300)
        sp:write_u16(0x05a08006,0x100)
        -- Re-use the programmed addresses, without writing DMEA/DRGA again.
        bus.space:write_u16(bus.base+0x416,0x1008)
        check('cached_parameters'..case,sp:read_u16(base+0x418)&0x700,0x100)
        check('self_execute_done'..case,sp:read_u16(base+0x416)&0x1000,0)
        if #fails==before then print('SCSP_DMA case='..case..' PASS') end
      end end
    end
    if #fails==0 then print('SCSP_DMA PASS cases='..case)
    else for _,f in ipairs(fails) do print('SCSP_DMA FAIL '..f) end end
    m:exit()
end
emu.register_frame_done(function()
    frames=frames+1;if started or frames<180 then return end;started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('SCSP_DMA FAIL '..tostring(err));m:exit() end
    end)()
end)
print('SCSP_DMA armed')
'''
def validate_output(text,returncode):
    if (returncode or 'SCSP_DMA FAIL' in text or 'LUA ERROR' in text or
        re.findall(r'^SCSP_DMA case=(\d+) PASS$',text,re.M)!=[str(i) for i in range(1,CASES+1)] or
        len(re.findall(rf'^SCSP_DMA PASS cases={CASES}$',text,re.M))!=1):
        raise RuntimeError('SCSP DMA fixture failed:\n'+text[-16000:])
runner.validate_output=validate_output
if __name__=='__main__':runner.main(f'SCSP DMA: {CASES} transfer/self-target cases passed live')
