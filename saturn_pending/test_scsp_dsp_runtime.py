#!/usr/bin/env python3
# license:BSD-3-Clause
"""Mapped SCSP microprograms: zero tails, live writes and signed addresses; not audio QA."""
import re
import test_scudsp_dma_runtime as runner
from test_smpc_multitap_runtime import COMMON_LUA
runner.LUA=COMMON_LUA+r'''
local frames,started=0,false
local base=0x05b00000
local function blank()
    local code={};for i=1,512 do code[i]=0 end;return code
end
local function upload(code)
    for i=1,512 do sp:write_u16(base+0x800+(i-1)*2,code[i]) end
    sp:write_u16(base+0xbf0,code[505])
end
local function code_for(last)
    local code=blank();code[3]=0x1002;code[6]=0x20;code[7]=2
    code[last*4+2]=0xa000;code[last*4+3]=0xa002;code[last*4+4]=0x100
    return code
end
local function scaled(word)
    local v=word>=0x8000 and word-0x10000 or word
    return ((v*256*4095//4096)//256)&0xffff
end
local function test()
    park()
    local snd=m.devices[':audiocpu']
    if snd then
        snd.spaces['program']:write_u16(0x70000,0x60fe)
        snd.state['SR'].value=0x2700;snd.state['PC'].value=0x70000
    end
    sp:write_u16(base+0x400,0);sp:write_u16(base+0x402,0)
    sp:write_u16(base+0x700,0x7ff8);sp:write_u16(base+0x702,0)
    sp:write_u16(base+0x780,0x4000)
    -- Clear TEMP through actual microinstructions, not private DSP injection.
    local clear=blank()
    for i=0,127 do clear[i*4+1]=0x80|i;clear[i*4+2]=0x2000;clear[i*4+3]=2;clear[i*4+4]=0x200 end
    upload(clear);emu.wait(emu.attotime.from_msec(2))
    sp:write_u16(0x05a08000,0x1234)
    local seed=code_for(3);seed[19]=0x1100;upload(seed);emu.wait(emu.attotime.from_usec(500))
    check('seed_effect1',sp:read_u16(base+0xec2),scaled(0x1234))
    local case=0
    for _,last in ipairs({3,5,31,63,125,127}) do
      for _,word in ipairs({0,0x1234,0x7fff,0x8000,0xffff}) do
        case=case+1;local before=#fails
        sp:write_u16(0x05a08000,word);upload(code_for(last))
        emu.wait(emu.attotime.from_usec(500))
        check('memory_control'..case,sp:read_u32(base+0xe00)&0xffffff,word<<8)
        check('zero_tail_effect'..case,sp:read_u16(base+0xec0),last==127 and scaled(word) or 0)
        if #fails==before then print('SCSP_DSP case='..case..' PASS') end
      end
    end
    case=case+1;local before=#fails
    sp:write_u16(0x05a08000,0x1234);upload(code_for(3));emu.wait(emu.attotime.from_usec(500))
    check('unwritten_effect_persists',sp:read_u16(base+0xec2),scaled(0x1234))
    -- Step127 word2 is not the legacy Start trigger at step126 word0.
    sp:write_u16(base+0xbfc,0x1100);emu.wait(emu.attotime.from_usec(500))
    check('live_tail_extension',sp:read_u16(base+0xec2),0)
    if #fails==before then print('SCSP_DSP case='..case..' PASS') end
    -- Both ADRL sources, signed displacements, NXADR, TABLE/ring and ADREB gates.
    sp:write_u16(base+0x700,0x8000)
    sp:write_u16(base+0x780,0x3000);sp:write_u16(base+0x784,0x3001)
    local function address_code(form,tablemode,add,nx,write,reference)
        local c=blank()
        c[7]=0xa000;c[8]=0x100
        c[14]=0x20;c[15]=2;c[18]=0xa000;c[19]=2
        c[23]=0x80|(form==12 and 0x30 or 0)
        local bits=0x104|(add and 2 or 0)|nx
        if write then
            c[31]=0xa000;c[32]=0x108;c[38]=0x21
            c[42]=0xa040;c[43]=2
            c[47]=(tablemode and 0x8000 or 0)|0x4000;c[48]=bits
        elseif reference then
            c[31]=0x2000;c[32]=0x104;c[38]=0x21
            c[47]=0x2000;c[48]=bits;c[54]=0x22
        else
            c[31]=(tablemode and 0x8000 or 0)|0x2000;c[32]=bits;c[38]=0x22
        end
        return c
    end
    local function table_case(form,raw,madr,nx,add,write)
        case=case+1;local before=#fails
        local delta=raw>=(1<<(form-1)) and raw-(1<<form) or raw
        local seedword=form==12 and (-delta*16)&0xffff or raw<<8
        local index=(madr+(add and delta or 0)+nx)&0xffff
        local oldindex=(madr+(add and (delta&0xfff) or 0)+nx)&0xffff
        sp:write_u16(base+0x402,0);sp:write_u16(base+0x782,madr)
        sp:write_u16(0x05a06000,seedword);sp:write_u16(0x05a06002,0xa988)
        sp:write_u16(0x05a00000+index*2,write and 0xdead or 0x1234)
        if oldindex~=index then sp:write_u16(0x05a00000+oldindex*2,write and 0xdead or 0xbeef) end
        upload(address_code(form,true,add,nx,write,false));emu.wait(emu.attotime.from_usec(500))
        check('address_seed'..case,sp:read_u32(base+0xe00)&0xffffff,seedword<<8)
        if write then
            check('signed_table_write'..case,sp:read_u16(0x05a00000+index*2),0x5678)
            if oldindex~=index then check('unsigned_write_guard'..case,sp:read_u16(0x05a00000+oldindex*2),0xdead) end
        else check('signed_table_read'..case,(sp:read_u32(base+0xe08)>>8)&0xffff,0x1234) end
        if #fails==before then print('SCSP_DSP case='..case..' PASS') end
    end
    for _,madr in ipairs({0,0x4000,0xffff}) do for _,raw in ipairs({0,1,0x7ff,0x800,0xfff}) do
      for nx=0,1 do for _,add in ipairs({false,true}) do for _,write in ipairs({false,true}) do
        table_case(12,raw,madr,nx,add,write)
      end end end
    end end
    for _,raw in ipairs({0,0x7f,0x80,0xff}) do for nx=0,1 do for _,write in ipairs({false,true}) do
        table_case(8,raw,0x4000,nx,true,write)
    end end end
    -- Address-coded RAM lets the guest report its moving ring reference address;
    -- no private MDEC_CT value or assumed sample phase is used.
    upload(blank());sp:read_u16(base+0xec0)
    for i=0,65535 do sp:write_u16(0x05a00000+i*2,i~0x5a5a) end
    sp:write_u16(base+0x782,0x4000)
    for rb=0,3 do for _,raw in ipairs({0,1,0x7ff,0x800,0xfff}) do for nx=0,1 do for _,add in ipairs({false,true}) do
        case=case+1;local before=#fails
        local delta=raw>=0x800 and raw-4096 or raw
        local seedword=(-delta*16)&0xffff
        sp:write_u16(base+0x402,rb<<7);sp:write_u16(0x05a06000,seedword)
        upload(address_code(12,false,add,nx,false,true));emu.wait(emu.attotime.from_usec(500))
        local ref=(sp:read_u32(base+0xe04)>>8)&0xffff
        for retry=1,3 do
            if ref~=seedword then break end
            emu.wait(emu.attotime.from_usec(50));ref=(sp:read_u32(base+0xe04)>>8)&0xffff
        end
        assert(ref~=seedword,'ambiguous source-hole ring reference')
        local anchor=ref~0x5a5a;local mask=(8192<<rb)-1
        assert(anchor<=mask,string.format('ring reference outside selected size case=%d ref=%x seed=%x anchor=%x rb=%x mem0=%x',case,ref,seedword,anchor,sp:read_u16(base+0x402),sp:read_u32(base+0xe00)))
        local wantindex=(anchor+(add and delta or 0)+nx)&mask
        local want=wantindex==0x3000 and seedword or wantindex~0x5a5a
        check('signed_ring_read'..case,(sp:read_u32(base+0xe08)>>8)&0xffff,want)
        if #fails==before then print('SCSP_DSP case='..case..' PASS') end
    end end end end
    -- IWT commits MEMS after this instruction has captured its input operand.
    sp:write_u16(base+0x402,0);sp:write_u16(base+0x700,0x7ff8)
    sp:write_u16(base+0x780,0x4000);sp:write_u16(base+0x782,0x4001)
    for iwa=0,31 do for _,same in ipairs({false,true}) do for _,enabled in ipairs({false,true}) do
      for _,pair in ipairs({{0x1234,0x5678},{0x8000,0x7fff},{0xffff,0},{0,0x8000}}) do
        case=case+1;local before=#fails;local ira=same and iwa or (iwa+1)&31
        local c=blank()
        c[7]=0xa000;c[8]=0x100;c[14]=0x20|ira
        c[23]=0xa000;c[24]=0x104
        c[30]=0xa000|(ira<<6)|(enabled and 0x20 or 0)|iwa;c[31]=2
        c[35]=0x1002;c[38]=0xa000|(ira<<6);c[39]=2;c[43]=0x1102
        sp:write_u16(0x05a08000,pair[1]);sp:write_u16(0x05a08002,pair[2])
        upload(c);emu.wait(emu.attotime.from_usec(500))
        check('entry_input'..case,sp:read_u16(base+0xec0),scaled(pair[1]))
        local after=enabled and same and pair[2] or pair[1]
        check('subsequent_input'..case,sp:read_u16(base+0xec2),scaled(after))
        check('input_commit'..case,sp:read_u32(base+0xe00+ira*4)&0xffffff,after<<8)
        if enabled then check('destination_commit'..case,sp:read_u32(base+0xe00+iwa*4)&0xffffff,pair[2]<<8) end
        if #fails==before then print('SCSP_DSP case='..case..' PASS') end
      end
    end end end
    if #fails==0 then print('SCSP_DSP PASS cases=759')
    else for _,f in ipairs(fails) do print('SCSP_DSP FAIL '..f) end end
    m:exit()
end
emu.register_frame_done(function()
    frames=frames+1;if started or frames<180 then return end;started=true
    coroutine.wrap(function()
        local ok,err=pcall(test)
        if not ok then print('SCSP_DSP FAIL '..tostring(err));m:exit() end
    end)()
end)
print('SCSP_DSP armed')
'''
def validate_output(text,returncode):
    if (returncode or 'SCSP_DSP FAIL' in text or 'LUA ERROR' in text or
        re.findall(r'^SCSP_DSP case=(\d+) PASS$',text,re.M)!=[str(i) for i in range(1,760)] or
        len(re.findall(r'^SCSP_DSP PASS cases=759$',text,re.M))!=1):
        raise RuntimeError('SCSP DSP fixture failed:\n'+text[-12000:])
runner.validate_output=validate_output
if __name__=='__main__':runner.main('SCSP DSP: 759 zero-tail/live-program/signed-address/input-order cases passed live')
