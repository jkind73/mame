-- license:BSD-3-Clause
-- Real-device chapter-11 pin, clock, flag, interrupt and save-state checks.
local machine=manager.machine
local cpu=machine.devices[':maincpu']
local space=cpu.spaces.program
local function read(off) return space:read_u8(0xfffffe10+off) end
local function write(off,v) space:write_u8(0xfffffe10+off,v) end
local function counter(v)
    if v then space:write_u16(0xfffffe12,v) end
    return space:read_u16(0xfffffe12)
end
local function config(a,b,levels,clear,select)
    space:write_u8(0xfffffe91,2)
    cpu.state.FTCI.value=0;cpu.state.FTI.value=0
    write(6,select or 3)
    write(7,0x10|(levels or 0));space:write_u16(0xfffffe14,b)
    write(7,levels or 0);space:write_u16(0xfffffe14,a)
    counter(0);read(1);write(1,clear and 1 or 0)
    space:write_u8(0xfffffe91,0)
end
local function tick()
    cpu.state.FTCI.value=0;emu.wait(0.000001)
    cpu.state.FTCI.value=1;emu.wait(0.000001)
end
local function run()
    space:write_u32(0x05fe00a0,0xffffffff)
    local base=0x26003000
    space:write_u16(base,0xaffe);space:write_u16(base+2,9)
    cpu.state.CURPC.value=base;cpu.state.SR.value=0xf0
    config(2,3,3)
    tick();assert(counter()==1 and (read(1)&14)==0,'first external clock')
    tick();assert(counter()==2 and (read(1)&14)==0 and cpu.state.FTOA.value==0,'compare signalled on entering count')
    tick();assert(counter()==3 and (read(1)&14)==8 and cpu.state.FTOA.value==1 and cpu.state.FTOB.value==0,'compare A pin/flag')
    tick();assert(counter()==4 and (read(1)&14)==12 and cpu.state.FTOB.value==1,'compare B pin/flag')
    cpu.state.FTCI.value=1;emu.wait(0.000002);assert(counter()==4,'held clock counted twice')
    write(7,0);assert(cpu.state.FTOA.value==1 and cpu.state.FTOB.value==1,'OLVL changed pin before match')
    counter(2);tick();assert(cpu.state.FTOA.value==0 and (read(1)&8)~=0,'sticky OCFA blocked later output')
    counter(3);tick();assert(cpu.state.FTOB.value==0,'sticky OCFB blocked later output')
    config(1,1,3,true);tick();assert(counter()==1);tick()
    assert(counter()==0 and (read(1)&14)==12 and cpu.state.FTOA.value==1 and cpu.state.FTOB.value==1,'simultaneous compare/clear')
    write(7,0);tick();tick();assert(counter()==0 and cpu.state.FTOA.value==0 and cpu.state.FTOB.value==0,'sticky flag stopped periodic clear')
    config(0xffff,0xffff,3);counter(0xffff);tick()
    assert(counter()==0 and (read(1)&14)==14,'overflow simultaneous compare')
    config(0xffff,0xffff,3,true);counter(0xffff);tick()
    assert(counter()==0 and (read(1)&14)==12,'compare clear lost precedence over overflow')
    -- Capture pin independently latches the external-clock counter.
    config(20,30,0,false,0x83);tick();tick()
    cpu.state.FTI.value=1;emu.wait(0.000001)
    assert((read(1)&0x80)~=0 and space:read_u16(0xfffffe18)==2,'external-clock input capture')
    cpu.state.FTI.value=0;read(1);write(1,0)
    space:read_u8(0xfffffe18);cpu.state.FTI.value=1
    assert((read(1)&0x80)==0,'ICR contention did not defer capture')
    emu.wait(0.000001);assert((read(1)&0x80)~=0,'deferred input capture missing')
    -- Save while FTCI is high, then restore phase, flags and output levels.
    config(2,3,3);tick()
    local path=os.getenv('SH7604_FRT_STATE_PATH')
    machine:save(path);emu.wait(0.02);tick();tick();assert(cpu.state.FTOA.value==1)
    machine:load(path);emu.wait(0.02)
    assert(counter()==1 and cpu.state.FTCI.value==1 and cpu.state.FTOA.value==0 and (read(1)&14)==0,'external save state')
    cpu.state.FTCI.value=1;assert(counter()==1,'restored high clock manufactured an edge')
    tick();tick();assert(counter()==3 and cpu.state.FTOA.value==1,'restored pin progress')
    -- Dense guest counter reads cannot discard fractional prescaler clocks.
    local poll=0x26005000
    for i,op in ipairs({0xd103,0x6011,0xaffd,9}) do space:write_u16(poll+(i-1)*2,op) end
    space:write_u32(poll+16,0xfffffe12)
    config(0xffff,0xffff,0,false,2);local first=counter()
    cpu.state.CURPC.value=poll;emu.wait(0.010)
    local elapsed=counter()-first
    local phi=math.floor(14318181*1708/455/2)
    assert(math.abs(elapsed-math.floor(phi*0.010/128))<=2,string.format('dense polling lost clock phase: %d',elapsed))
    assert(math.abs(counter()-cpu.state.R0.value)<=2,'guest counter read not synchronized')
    cpu.state.CURPC.value=base
    -- An internal compare deadline and counter phase survive save/load.
    config(12000,0xffff,2,false,2)
    emu.wait(0.002);machine:save(path);emu.wait(0.065)
    assert(cpu.state.FTOA.value==1 and (read(1)&8)~=0,'internal pre-load compare')
    machine:load(path);emu.wait(0.002)
    assert(cpu.state.FTOA.value==0 and (read(1)&8)==0 and counter()<4000,'internal phase/deadline not restored')
    emu.wait(0.065);assert(cpu.state.FTOA.value==1 and (read(1)&8)~=0,'restored internal compare deadline')
    -- A zero compare period continues clearing without a timer-event storm.
    config(0,1,2,true,0);emu.wait(0.001)
    assert(counter()==0 and cpu.state.FTOA.value==1 and (read(1)&8)~=0,'zero-period internal clear')
    write(7,0);emu.wait(0.001);assert(counter()==0 and cpu.state.FTOA.value==0,'zero-period later output')
    -- Module stop cancels a deferred input capture.
    config(20,30,0,false,0x83)
    space:read_u8(0xfffffe18);cpu.state.FTI.value=1
    space:write_u8(0xfffffe91,2);emu.wait(0.000001)
    assert((read(1)&0x80)==0 and space:read_u16(0xfffffe18)==0,'stopped deferred capture fired')
    -- Stop/reset independently; physical clock transitions while stopped are retained.
    space:write_u8(0xfffffe91,2)
    assert(cpu.state.FTOA.value==0 and cpu.state.FTOB.value==0 and counter()==0,'module stop outputs/reset')
    tick();assert(counter()==0,'external clock counted during module stop')
    write(6,3);space:write_u8(0xfffffe91,0)
    cpu.state.FTCI.value=1;assert(counter()==0,'module restart manufactured a rising edge')
    tick();assert(counter()==1,'external clock did not restart')
    -- Actual internal clock compare IRQ/vector and exception stacking.
    local stack,vectors,handler=0x26090000,0x26001000,0x26002000
    space:write_u16(handler,0xaffe);space:write_u16(handler+2,9)
    space:write_u32(vectors+0x41*4,handler)
    cpu.state.VBR.value=vectors;cpu.state.R15.value=stack;cpu.state.SR.value=0xf0
    space:write_u16(0xfffffe60,0x0800);space:write_u16(0xfffffe66,0x4041)
    config(200,0xffff,2,false,2);write(0,9)
    emu.wait(0.002);assert((read(1)&8)~=0 and cpu.state.FTOA.value==1,'internal compare timer/pin')
    assert(cpu.state.R15.value==stack,'masked compare IRQ accepted')
    cpu.state.SR.value=0;emu.wait(0.001)
    assert(cpu.state.R15.value==stack-8 and (cpu.state.SR.value&0xf0)==0x80,'compare IRQ stack/priority')
    local pc=cpu.state.CURPC.value&0x07ffffff
    assert(pc>=0x06002000 and pc<=0x06002002,'compare IRQ vector')
    write(0,1);cpu.state.SR.value=0xf0;cpu.state.CURPC.value=base
    -- Manual reset initializes FRT and its outputs while retaining physical inputs.
    config(2,3,3);tick();tick();tick();tick()
    assert(cpu.state.FTOA.value==1 and cpu.state.FTOB.value==1)
    space:write_u16(0xfffffe82,0x5a60);space:write_u16(0xfffffe80,0x5aff);space:write_u16(0xfffffe80,0xa560)
    emu.wait(0.001)
    assert(cpu.state.FTOA.value==0 and cpu.state.FTOB.value==0 and cpu.state.FTCI.value==1,'reset output/input levels')
    assert(read(6)==0 and space:read_u16(0xfffffe14)==0xffff and (read(1)&12)==0,'reset OCRA/TCR/flags')
    write(7,0x10);assert(space:read_u16(0xfffffe14)==0xffff,'reset OCRB')
    print('SH7604_FRT_PASS external clock, compare pins/timing, recurring clear, overflow, capture/read contention, save/load, module stop, internal compare IRQ')
end
sh7604_frt_thread=coroutine.create(function()
    local ok,err=pcall(run)
    if not ok then print('SH7604_FRT_FAIL '..tostring(err)) end
    machine:exit()
end)
local ok,err=coroutine.resume(sh7604_frt_thread)
if not ok then print('SH7604_FRT_FAIL '..tostring(err));machine:exit() end
