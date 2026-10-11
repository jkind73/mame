-- license:BSD-3-Clause
-- Real-device UBC register, instruction/data/DMA and exception regressions.
local machine=manager.machine
local cpu=machine.devices[':maincpu']
local space=cpu.spaces.program
local stack,vectors,handler=0x26090000,0x26001000,0x26001200
local serial=0
local function reg(off,v) if v~=nil then space:write_u16(0xffffff40+off,v) end;return space:read_u16(0xffffff40+off) end
local function clear()
    reg(8,0);reg(0x28,0);reg(0x38,0x1000)
    for _,off in ipairs({0,2,4,6,0x20,0x22,0x24,0x26,0x30,0x32,0x34,0x36}) do reg(off,0) end
end
local function start(code,mask)
    serial=serial+1;local base=0x26010000+serial*0x100
    for i,op in ipairs(code) do space:write_u16(base+(i-1)*2,op) end
    cpu.state.R0.value=0;cpu.state.R15.value=stack;cpu.state.VBR.value=vectors
    cpu.state.SR.value=mask or 0;cpu.state.CURPC.value=base
    return base
end
local function address(off,v) reg(off,v>>16);reg(off+2,v&0xffff) end
local function caught(pc,flags,value)
    emu.wait(0.001)
    assert(cpu.state.R15.value==stack-8,'UBC did not stack an exception')
    assert(space:read_u32(stack-8)==pc,string.format('saved PC expected=%08x actual=%08x',pc,space:read_u32(stack-8)))
    assert((reg(0x38)&0xc0c0)==flags,'UBC match flags')
    assert((cpu.state.SR.value&0xf0)==0xf0,'UBC exception priority')
    if value then assert(cpu.state.R0.value==value,'instruction before/after behavior') end
end
local function run()
    if os.getenv('SH7604_TEST_IDEAL_BUS')=='1' then assert((machine.ioport.ports[':CONFIG']:read()&1)==0,'ideal bus config not applied') end
    space:write_u32(0x05fe00a0,0xffffffff)
    space:write_u16(handler,0xaffe);space:write_u16(handler+2,9)
    space:write_u32(vectors+12*4,handler)
    -- All fifteen halfword mappings, longword pairs and prohibited byte writes.
    clear()
    for _,off in ipairs({0,2,4,6,8,0x20,0x22,0x24,0x26,0x28,0x30,0x32,0x34,0x36,0x38}) do
        local expected=(off==8 or off==0x28) and 0xff or off==0x38 and 0xf4dc or 0xffff
        assert(reg(off,0xffff)==expected,'register mapping/mask')
        space:write_u8(0xffffff40+off,0);assert(reg(off)==expected,'prohibited byte write')
    end
    space:write_u32(0xffffff40,0x12345678);assert(space:read_u32(0xffffff40)==0x12345678,'paired longword register access')
    for _,channel in ipairs({0,1}) do
        for _,after in ipairs({false,true}) do
            clear();local base=start({0xe001,0xaffe,9})
            address(channel*0x20,base);reg(8+channel*0x20,0x56)
            reg(0x38,0x1000|(after and (channel==0 and 0x400 or 4) or 0))
            caught(base+(after and 2 or 0),channel==0 and 0x8000 or 0x80,after and 1 or 0)
        end
    end
    clear();local base=start({0xe001,0xe002,0xaffe,9})
    address(0,base);address(0x20,base+2);reg(8,0x56);reg(0x28,0x56);reg(0x38,0x1010)
    caught(base+2,0x8080,1)
    -- Simultaneous A/B cannot satisfy sequential matching.
    clear();base=start({0xe001,0xaffe,9})
    address(0,base);address(0x20,base);reg(8,0x56);reg(0x28,0x56);reg(0x38,0x1010)
    emu.wait(0.001);assert(cpu.state.R15.value==stack and (reg(0x38)&0xc0c0)==0x8000,'simultaneous sequence break')
    clear();base=start({0xe001,0xaffe,9})
    address(0,base);address(0x20,base);reg(8,0x56);reg(0x28,0x56);reg(0x38,0x1014)
    emu.wait(0.001);assert(cpu.state.R15.value==stack and (reg(0x38)&0xc0c0)==0x8000,'same fetch counted twice in sequence')
    -- Delay-slot break must defer until the branch destination.
    clear();base=start({0xa002,0xe003,9,9,0xaffe,9})
    address(0,base+2);reg(8,0x56)
    caught(base+8,0x8000,3)
    -- LDC inhibits the following instruction, even when that instruction matches.
    clear();base=start({0x410e,0xe004,0xaffe,9});cpu.state.R1.value=0
    address(0,base+2);reg(8,0x56)
    caught(base+4,0x8000,4)
    -- Masked requests remain pending after the matching instruction has passed.
    clear();base=start({0xe005,0xaffe,9},0xf0);address(0,base);reg(8,0x56)
    emu.wait(0.001);assert(cpu.state.R15.value==stack and (reg(0x38)&0x8000)~=0,'masked request lost')
    reg(8,0);cpu.state.SR.value=0;emu.wait(0.001)
    assert(cpu.state.R15.value==stack-8,string.format('pending unmask SP=%08x PC=%08x SR=%x flags=%x',cpu.state.R15.value,cpu.state.CURPC.value,cpu.state.SR.value,reg(0x38)))
    -- SH7000 compatibility: channel A only, no flags.
    clear();base=start({0xe006,0xaffe,9});address(0,base);reg(8,0x56);reg(0x38,0)
    caught(base,0,0)
    -- Compatible mode includes a fetched but unexecuted branch fall-through.
    clear();base=start({0x8902,0xe009,9,9,0xaffe,9});cpu.state.SR.value=1
    address(0,base+2);reg(8,0x56);reg(0x38,0)
    caught(base,0,0)
    clear();base=start({0x8902,0xe009,9,9,0xaffe,9});cpu.state.SR.value=1
    address(0,base+2);reg(8,0x56)
    emu.wait(0.001);assert(cpu.state.R15.value==stack and (reg(0x38)&0xc0c0)==0,'modern overrun fetch broke')
    -- CPU operand address alignment, size qualification, and data masks.
    for _,size in ipairs({1,2,4}) do
        clear();base=start({0xe007,0x2100+(size==1 and 0 or size==2 and 1 or 2),0xaffe,9})
        cpu.state.R1.value=0x26008000
        address(0x20,0x26008000+size-1);reg(0x28,0x68|(size==4 and 3 or size))
        address(0x30,size==1 and 0x0707 or 7);address(0x34,0);reg(0x38,0x1008)
        caught(base+4,0x80,7)
        assert(space:read_u8(0x26008000+size-1)==7,'CPU write data')
    end
    -- Save/load preserves a partially matched sequence and a masked request.
    clear();base=start({0xe008,0xaffe,9},0xf0)
    local target=base+0x40;space:write_u16(target,0xe00a);space:write_u16(target+2,0xaffe);space:write_u16(target+4,9)
    address(0,base);address(0x20,target);reg(8,0x56);reg(0x28,0x56);reg(0x38,0x1010)
    emu.wait(0.001);assert((reg(0x38)&0xc0c0)==0x8000,'sequence did not arm')
    local statepath=os.getenv('SH7604_UBC_STATE_PATH')
    machine:save(statepath);emu.wait(0.02)
    cpu.state.CURPC.value=target;emu.wait(0.001);assert((reg(0x38)&0xc0c0)==0x8080,'sequence completion')
    machine:load(statepath);emu.wait(0.02)
    assert((reg(0x38)&0xc0c0)==0x8000,'sequence state not restored')
    cpu.state.CURPC.value=target;emu.wait(0.001)
    machine:save(statepath);emu.wait(0.02)
    cpu.state.SR.value=0;emu.wait(0.001);assert(cpu.state.R15.value==stack-8,'sequence interrupt unmask')
    machine:load(statepath);emu.wait(0.02)
    assert(cpu.state.R15.value==stack and (cpu.state.SR.value&0xf0)==0xf0,'pending state not restored')
    reg(8,0);reg(0x28,0);cpu.state.SR.value=0;emu.wait(0.001)
    assert(cpu.state.R15.value==stack-8,string.format('restored pending SP=%08x PC=%08x SR=%x flags=%x',cpu.state.R15.value,cpu.state.CURPC.value,cpu.state.SR.value,reg(0x38)))
    -- CPU arms UBC inside existing compiled code; the next fetch must observe it.
    clear();base=start({0xaffe,9},0)
    local guest=base+0x40
    local code={0xd103,0xe056,0x2101,0x6211,0xe009,0xaffe,9}
    for i,op in ipairs(code) do space:write_u16(guest+(i-1)*2,op) end
    space:write_u32(guest+16,0xffffff48)
    address(0,guest+8);emu.wait(0.001)
    cpu.state.CURPC.value=guest
    caught(guest+8,0x8000,0x56)
    -- Both DMAC channels and every operand size, including source-line bursts.
    for channel=0,1 do
        for mode=0,3 do
            clear();base=start({0xaffe,9},0xf0)
            local src,dst=0x06009000,0x0600a000
            for n=0,3 do space:write_u32(src+n*4,0x71727374+n);space:write_u32(dst+n*4,0) end
            address(0x20,dst);reg(0x28,0xa8|(mode==0 and 1 or mode==1 and 2 or 3));reg(0x38,0x1000)
            local off=channel*16
            space:read_u32(0xffffff8c+off);space:write_u32(0xffffff8c+off,0)
            space:write_u32(0xffffffb0,0);space:write_u8(0xfffffe71+channel,0)
            space:write_u32(0xffffff80+off,src);space:write_u32(0xffffff84+off,dst)
            space:write_u32(0xffffff88+off,mode==3 and 4 or 1)
            space:write_u32(0xffffff8c+off,0x5201+mode*0x400);space:write_u32(0xffffffb0,1)
            emu.wait(0.001)
            assert((reg(0x38)&0xc0c0)==0x40,'DMA peripheral match')
            assert(cpu.state.R15.value==stack,'masked DMA break accepted')
            space:read_u32(0xffffff8c+off);space:write_u32(0xffffff8c+off,0)
        end
    end
    -- Peer SH-2 bus cycles are external peripheral cycles, with size/data ignored.
    local peer=machine.devices[':slave'].spaces.program
    local function preg(off,value)
        if value~=nil then peer:write_u16(0xffffff40+off,value) end
        return peer:read_u16(0xffffff40+off)
    end
    clear();base=start({0xe007,0x2100,0xaffe,9},0xf0);cpu.state.R1.value=0x26008000
    preg(8,0);preg(0x20,0x0600);preg(0x22,0x8000);preg(0x24,0);preg(0x26,0)
    preg(0x28,0xab);preg(0x30,0);preg(0x32,0);preg(0x34,0);preg(0x36,0);preg(0x38,0x1008)
    emu.wait(0.001);assert((preg(0x38)&0xc0c0)==0,'disabled external bus break')
    preg(0x38,0x3008);base=start({0xe007,0x2100,0xaffe,9},0xf0);cpu.state.R1.value=0x26008000
    emu.wait(0.001);assert((preg(0x38)&0xc0c0)==0x40,'peer external bus break')
    -- SCU C-Bus DMA is an external master for both SH-2 UBCs.
    clear();start({0xaffe,9},0xf0)
    address(0x20,0x0600b000);reg(0x28,0xa9);reg(0x38,0x3008)
    preg(0x22,0xb000);preg(0x38,0x3008)
    space:write_u32(0x05a00000,0x12345678);space:write_u32(0x0600b000,0)
    space:write_u32(0x05fe0000,0x05a00000);space:write_u32(0x05fe0004,0x0600b000)
    space:write_u32(0x05fe0008,4);space:write_u32(0x05fe000c,0x102)
    space:write_u32(0x05fe0014,7);space:write_u32(0x05fe0010,0x101)
    emu.wait(0.002)
    assert(space:read_u32(0x0600b000)==0x12345678,'SCU external payload')
    assert((reg(0x38)&0xc0c0)==0x40 and (preg(0x38)&0xc0c0)==0x40,'SCU external master break')
    preg(0x28,0);preg(0x38,0)
    -- WDT manual reset retains UBC storage; power-on reset initializes it.
    clear();start({0xaffe,9},0xf0);address(0,0x12345678);address(0x30,0x87654321)
    space:write_u16(0xfffffe82,0x5a60);space:write_u16(0xfffffe80,0x5aff);space:write_u16(0xfffffe80,0xa560)
    emu.wait(0.002)
    assert(space:read_u32(0xffffff40)==0x12345678 and space:read_u32(0xffffff70)==0x87654321,'manual reset lost UBC')
    space:write_u16(0xfffffe82,0x5a40);space:write_u16(0xfffffe80,0x5aff);space:write_u16(0xfffffe80,0xa560)
    emu.wait(0.002)
    assert(space:read_u32(0xffffff40)==0 and space:read_u32(0xffffff70)==0 and reg(0x38)==0,'power reset did not initialize UBC')
    clear();print('SH7604_UBC_PASS registers, masks, before/after, sequence, delay/LDC, pending, compatible, CPU data, both DMA channels')
end
sh7604_ubc_thread=coroutine.create(function()
    local ok,err=pcall(run)
    if not ok then print('SH7604_UBC_FAIL '..tostring(err)) end
    machine:exit()
end)
local ok,err=coroutine.resume(sh7604_ubc_thread)
if not ok then print('SH7604_UBC_FAIL '..tostring(err));machine:exit() end
