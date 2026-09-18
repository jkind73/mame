#!/usr/bin/env python3
# license:BSD-3-Clause
"""Public-port parallel operations, full RAM images, counter markers and registers."""
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local frames,done=0,false
local control,program,addr,data=0x05fe0080,0x05fe0084,0x05fe0088,0x05fe008c
local function execute(code)
    sp:write_u32(control,0x8000)
    for _,op in ipairs(code) do sp:write_u32(program,op) end
    sp:write_u32(control,0x18000);emu.wait(emu.attotime.from_usec(10))
    assert((sp:read_u32(control)&0x10000)==0,'program did not end')
end
local function test()
    park();local case=0
    for bank=0,3 do for _,pos in ipairs({0,1,63}) do for kind=0,11 do
        case=case+1;local before=#fails
        local ram,ct,reads,inc={},{},{},{}
        for b=0,3 do
            ct[b]=pos;reads[b]=false;inc[b]=false
            for i=0,63 do ram[b*64+i]=0x51000000|(b<<16)|(i<<8)|(i~b) end
        end
        ram[254]=0 -- stopped-program setup supplies zero to RX/RY
        sp:write_u32(control,0x8000);sp:write_u32(addr,0)
        for i=0,255 do sp:write_u32(data,ram[i]) end
        local other,third=(bank+1)%4,(bank+2)%4
        local xs,ys,source,dest,imm=nil,nil,nil,nil,nil
        local both=false
        if kind==0 or kind==1 then xs=bank;ys=bank;source=bank+(kind==1 and 4 or 0);dest=5
        elseif kind==2 then xs=bank;ys=other;source=bank+4;dest=third
        elseif kind==3 or kind==4 then source=bank+(kind==4 and 4 or 0);dest=bank
        elseif kind==5 then xs=bank;ys=other;source=third+4;dest=bank
        elseif kind==6 then xs=bank;ys=bank;source=bank+4;dest=12+bank
        elseif kind==7 then xs=bank;ys=bank;imm=-59;dest=bank
        elseif kind==8 then source=bank+4;dest=other
        elseif kind==9 then xs=bank;ys=bank;both=true
        elseif kind==10 then xs=bank;ys=other;imm=63;dest=12+bank
        elseif kind==11 then xs=bank;ys=other;source=9;dest=bank end
        local op,rx,ry,pl,ac=0,0,0,0,0
        if xs then
            op=op|((both and 7 or 4)<<23)|((xs+4)<<20)
            rx=ram[xs*64+pos];reads[xs]=true;inc[xs]=true;if both then pl=rx end
        end
        if ys then
            op=op|((both and 7 or 4)<<17)|((ys+4)<<14)
            ry=ram[ys*64+pos];reads[ys]=true;inc[ys]=true;if both then ac=ry end
        end
        if dest then
            local value=imm and (imm&0xffffffff) or 0
            if imm then op=op|0x1000|(imm&255)
            else
                op=op|0x3000|source
                if source<8 then
                    local b=source%4;reads[b]=true;value=ram[b*64+pos]
                    if source>=4 and dest~=b then inc[b]=true end
                end -- ALL is zero from setup XOR
            end
            op=op|(dest<<8)
            if dest<4 then
                if not reads[dest] then ram[dest*64+pos]=value;inc[dest]=true end
            elseif dest==5 then pl=value
            elseif dest>=12 then ct[dest-12]=value&63;inc[dest-12]=false end
        end
        for b=0,3 do if inc[b] then ct[b]=(ct[b]+1)&63 end end
        local code={0x1f3e,0x238c000,0x20000,0x1500,3<<26,
                    0x1c00|pos,0x1d00|pos,0x1e00|pos,0x1f00|pos,op}
        for b=0,3 do
            code[#code+1]=0x1000|(b<<8)|(0x70+b)
            ram[b*64+ct[b]]=0x70+b
        end
        code[#code+1]=0xf0000000;execute(code)
        sp:write_u32(addr,0)
        for i=0,255 do check('ram'..case..'_'..i,sp:read_u32(data),ram[i]) end
        -- Separate stopped phase: observe P+A and RX*RY without hiding markers.
        execute({0x1f00,4<<26,0x3309,0x20000,0x1000000,6<<26,0x3309,0x330a,0xf0000000})
        sp:write_u32(addr,192)
        check('sum'..case,sp:read_u32(data),(ac+pl)&0xffffffff)
        local product=(rx*ry)&0xffffffffffff
        check('product_low'..case,sp:read_u32(data),product&0xffffffff)
        check('product_high'..case,sp:read_u32(data),(product>>16)&0xffffffff)
        if #fails==before then print('DSP_PARALLEL case='..case..' PASS') end
    end end end
    if #fails==0 then print('DSP_PARALLEL PASS cases=144')
    else for _,f in ipairs(fails) do print('DSP_PARALLEL FAIL '..f) end end
    m:exit()
end
emu.register_frame_done(function()
    frames=frames+1;if done or frames<180 then return end;done=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('DSP_PARALLEL FAIL '..tostring(err));m:exit() end
    end)()
end)
print('DSP_PARALLEL armed')
'''
def validate_output(text,returncode):
    if (returncode or 'DSP_PARALLEL FAIL' in text or 'LUA ERROR' in text or
            re.findall(r'^DSP_PARALLEL case=(\d+) PASS$',text,re.M)!=[str(i) for i in range(1,145)] or
            len(re.findall(r'^DSP_PARALLEL PASS cases=144$',text,re.M))!=1):
        raise RuntimeError('DSP parallel fixture failed:\n'+text[-16000:])
runner.validate_output=validate_output
if __name__=='__main__':
    runner.main('DSP parallel buses: 144 RAM/register/counter programs passed live')
