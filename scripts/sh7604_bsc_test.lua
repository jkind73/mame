-- license:BSD-3-Clause
-- Real CPU BSC timer/IRQ/width tests, followed by a scheduled pending save/load.
local machine=manager.machine
local cpu=machine.devices[':maincpu']
local space=cpu.spaces.program
local base,handler,vectors,stack,marker=0x26004000,0x26004100,0x26005000,0x26090000,0x26006000
local phi=math.floor(14318181*1708/455/2)
local path=assert(os.getenv('SH7604_BSC_STATE_PATH'))
local function key(a,v) space:write_u32(a,0xa55a0000|v) end
local function stop() key(0xfffffff0,0); space:read_u32(0xfffffff0); key(0xfffffff0,0) end
local function assert_flag(expected,label)
    assert((space:read_u32(0xfffffff0)&0x80)==expected,label)
end
local phase=0
local function run()
    space:write_u32(0x05fe00a0,0xffffffff)
    space:write_u16(base,0xaffe);space:write_u16(base+2,0x0009)
    cpu.state.SR.value=0xf0;cpu.state.CURPC.value=base
    assert((space:read_u32(0xffffffe0)&0x8000)==0,'master BCR1 identity')
    assert((machine.devices[':slave'].spaces.program:read_u32(0xffffffe0)&0x8000)~=0,'slave BCR1 identity')
    stop();key(0xffffffec,0);key(0xfffffff8,200);key(0xfffffff4,0)
    for select,div in ipairs({4,16,64,256,1024,2048,4096}) do
        stop();key(0xfffffff4,0);key(0xfffffff0,select*8)
        emu.wait(20*div/phi)
        local count=space:read_u16(0xfffffff6)
        assert(count>=18 and count<=23,string.format('clock /%d: count=%d',div,count))
        assert_flag(0,'early match')
    end
    stop();key(0xfffffff4,17);emu.wait(0.001)
    assert(space:read_u32(0xfffffff4)==17,'disabled counter progressed')
    -- RTCOR=0 matches after 256 increments, including normal counter wrap.
    key(0xfffffff8,0);key(0xfffffff4,250);key(0xfffffff0,0x38)
    emu.wait(8*4096/phi);assert_flag(0x80,'zero constant/wrap failed')
    assert(space:read_u32(0xfffffff4)<=4,'wrap count')
    stop();key(0xfffffff8,3);key(0xfffffff4,250);key(0xfffffff0,0x38)
    emu.wait(12*4096/phi);assert_flag(0x80,'compare beyond wrap failed')
    stop();key(0xfffffff4,0);key(0xfffffff8,1);key(0xfffffff0,0x38)
    emu.wait(3*4096/phi)
    -- Ordinary writes cannot clear a flag without a prior status read.
    key(0xfffffff0,0);assert_flag(0x80,'unqualified CMF clear')
    key(0xfffffff0,0);assert_flag(0,'qualified CMF clear')
    space:write_u16(0xfffffff2,0xffff);space:write_u8(0xfffffff3,0xff)
    assert(space:read_u32(0xfffffff0)==0,'unkeyed/partial writes accepted')
    -- Illegal CPU accesses take vector 9 before modifying operands or registers.
    space:write_u16(handler,0xaffe);space:write_u16(handler+2,0x0009)
    space:write_u32(vectors+9*4,handler)
    cpu.state.VBR.value=vectors
    local cases={
        {0x6010,0xffffff03,0,0}, -- MOV.B @R1,R0
        {0x6014,0xffffff03,0,0}, -- MOV.B @R1+,R0
        {0x2100,0xffffff03,0,0}, -- MOV.B R0,@R1
        {0x2104,0xffffff04,0,0}, -- MOV.B R0,@-R1
        {0x001c,0xffffff02,1,0}, -- MOV.B @(R0,R1),R0
        {0x0104,0xffffff02,1,0}, -- MOV.B R0,@(R0,R1)
        {0x8413,0xffffff00,0,0}, -- MOV.B @(3,R1),R0
        {0x8013,0xffffff00,0,0}, -- MOV.B R0,@(3,R1)
        {0xc400,0,0,0xffffff03}, -- MOV.B @(0,GBR),R0
        {0xcd00,0,0,0xffffff03}, -- AND.B #0,@(R0,GBR)
        {0x411b,0xffffff03,0,0}, -- TAS.B @R1
        {0x6012,0xfffffe00,0,0}, -- MOV.L @R1,R0
        {0x2106,0xfffffe04,0,0}, -- MOV.L R0,@-R1
        {0x4106,0xfffffe00,0,0}, -- LDS.L @R1+,MACH
    }
    for i,c in ipairs(cases) do
        base=0x26010000+i*0x100
        space:write_u16(base,c[1]);space:write_u16(base+2,0xaffe);space:write_u16(base+4,0x0009)
        cpu.state.R0.value=c[3];cpu.state.R1.value=c[2];cpu.state.GBR.value=c[4]
        cpu.state.R15.value=stack;cpu.state.SR.value=0xf0;cpu.state.CURPC.value=base
        emu.wait(0.001)
        assert((cpu.state.PC.value&0x1fffffff)==(handler&0x1fffffff) or (cpu.state.PC.value&0x1fffffff)==((handler+2)&0x1fffffff),string.format('address error handler case %d PC=%08x SP=%08x R1=%08x stacked=%08x',i,cpu.state.PC.value,cpu.state.R15.value,cpu.state.R1.value,space:read_u32(stack-8)))
        assert(cpu.state.R15.value==stack-8,'address error stack case '..i)
        assert(space:read_u32(stack-8)==base,'address error fault PC case '..i)
        assert(space:read_u32(stack-4)==0xf0 and cpu.state.SR.value==0xf0,'address error SR case '..i)
        assert(cpu.state.R1.value==c[2] and cpu.state.R0.value==c[3],'faulting instruction side effects case '..i)
    end
    base=0x26020000
    space:write_u16(base,0xa006);space:write_u16(base+2,0x6014)
    cpu.state.R1.value=0xffffff03;cpu.state.R15.value=stack;cpu.state.CURPC.value=base
    emu.wait(0.001)
    assert(space:read_u32(stack-8)==base and cpu.state.R1.value==0xffffff03,'delay slot fault PC/side effects')
    -- Valid keyed longword writes and word reads still execute on the CPU.
    base=0x26021000
    space:write_u16(base,0xaffe);space:write_u16(base+2,0x0009)
    cpu.state.CURPC.value=base;cpu.state.R15.value=stack
    -- Actual CMI delivery: the handler reads and clears CMF, disables counting,
    -- writes its marker and returns. No poll is needed to generate the interrupt.
    handler=0x26004200
    local code={0xd007,0x6102,0xd107,0x2012,0xd007,0xe101,0x2012,0x002b,0x0009}
    for i,op in ipairs(code) do space:write_u16(handler+(i-1)*2,op) end
    space:write_u32(handler+32,0xfffffff0);space:write_u32(handler+36,0xa55a0000);space:write_u32(handler+40,marker)
    space:write_u32(vectors+0x52*4,handler);space:write_u16(0xfffffee4,0x0052)
    space:write_u16(0xfffffee2,0x0070);space:write_u32(marker,0)
    stop();key(0xfffffff8,20);key(0xfffffff4,0)
    cpu.state.SR.value=0;key(0xfffffff0,0x78)
    emu.wait(0.006)
    assert(space:read_u32(marker)==1,'CMI interrupt not delivered')
    assert(cpu.state.R15.value==stack,'CMI RTE stack')
    assert_flag(0,'CMI handler did not clear source')
    cpu.state.SR.value=0xf0
    phase=1
end
sh7604_bsc_thread=coroutine.create(run)
local ok,err=coroutine.resume(sh7604_bsc_thread)
if not ok then print('SH7604_BSC_FAIL '..tostring(err));machine:exit() end
sh7604_bsc_frames=emu.add_machine_frame_notifier(function()
    if phase==0 then return end
    local ok,err=pcall(function()
        if phase==1 then
            stop();key(0xfffffff8,250);key(0xfffffff4,0);key(0xfffffff0,0x78);phase=2
        elseif phase==2 then
            local count=space:read_u32(0xfffffff4)
            assert(count>50 and count<150,'save counter phase')
            machine:save(path);phase=3
        elseif phase==3 then assert_flag(0,'match too early');phase=4
        elseif phase==4 then assert_flag(0x80,'saved pending timer did not fire');machine:load(path);phase=5
        elseif phase==5 then assert_flag(0,'load did not restore pending flag/timer');phase=6
        elseif phase==6 then assert_flag(0x80,'restored pending timer did not fire');stop()
            print('SH7604_BSC_PASS seven clocks, disabled/wrap/compare, qualified clears, CPU widths/address errors, CMI and scheduled pending save/load')
            machine:exit()
        end
    end)
    if not ok then print('SH7604_BSC_FAIL '..tostring(err));machine:exit() end
end)
