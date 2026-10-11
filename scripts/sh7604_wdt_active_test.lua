-- license:BSD-3-Clause
-- Exercise the active WDT map, clock, interval IRQ and both chip reset modes.
local machine=manager.machine
local cpu=machine.devices[':maincpu']
local space=cpu.spaces.program
local base,handler,vector,stack,marker=0x26003000,0x26003200,0x26001000,0x26090000,0x26003500
local function run()
    space:write_u32(0x05fe00a0,0xffffffff)
    space:write_u16(base,0xaffe);space:write_u16(base+2,0x0009)
    cpu.state.CURPC.value=base;cpu.state.SR.value=0xf0
    space:write_u16(0xfffffe80,0xa500)
    space:write_u16(0xfffffe80,0x5a55)
    assert(space:read_u8(0xfffffe81)==0x55,'counter key/address')
    space:write_u8(0xfffffe81,0x66);space:write_u16(0xfffffe80,0x1255)
    assert(space:read_u8(0xfffffe81)==0x55,'partial/invalid key modified counter')
    space:write_u16(0xfffffe80,0xa527)
    emu.wait(0.002)
    local count=space:read_u8(0xfffffe81)
    assert(count>0x55 and count<0x65,'WDT clock did not advance')
    space:write_u16(0xfffffe80,0xa500)
    assert(space:read_u8(0xfffffe81)==0,'TME clear did not reset counter')
    -- ITI actual delivery and qualified OVF clear.
    local code={0xd007,0x6101,0xd107,0x2011,0xd007,0xe101,0x2012,0x002b,0x0009}
    for i,op in ipairs(code) do space:write_u16(handler+(i-1)*2,op) end
    space:write_u32(handler+32,0xfffffe80);space:write_u32(handler+36,0xa500);space:write_u32(handler+40,marker)
    space:write_u32(vector+0x53*4,handler)
    space:write_u16(0xfffffee2,0x70);space:write_u16(0xfffffee4,0x5300)
    cpu.state.VBR.value=vector;cpu.state.R15.value=stack;cpu.state.SR.value=0
    space:write_u32(marker,0);space:write_u16(0xfffffe80,0x5afa);space:write_u16(0xfffffe80,0xa527)
    emu.wait(0.004)
    assert(space:read_u32(marker)==1,'ITI not delivered')
    assert(cpu.state.R15.value==stack,'ITI RTE stack')
    assert((space:read_u8(0xfffffe80)&0xa0)==0,'handler failed to clear/disable ITI')
    cpu.state.SR.value=0xf0
    -- RSTE=0: overflow updates WOVF and resets only the watchdog, not the CPU.
    space:write_u16(0xfffffe82,0x5a00);space:write_u16(0xfffffe80,0x5afa);space:write_u16(0xfffffe80,0xa567)
    emu.wait(0.004)
    assert((space:read_u8(0xfffffe83)&0x80)~=0,'watchdog WOVF')
    assert((space:read_u8(0xfffffe80)&0x7f)==0x18 and space:read_u8(0xfffffe81)==0,'watchdog local reset')
    assert((cpu.state.PC.value&0x1fffffff)==(base&0x1fffffff) or (cpu.state.PC.value&0x1fffffff)==((base+2)&0x1fffffff),'RSTE=0 reset CPU')
    space:write_u16(0xfffffe82,0xa500);assert((space:read_u8(0xfffffe83)&0x80)==0,'qualified WOVF clear')
    -- RSTS selects a manual vs power-on chip reset; BSC retention proves which.
    for _,control in ipairs({0x60,0x40}) do
        space:write_u32(0xffffffe8,0xa55a1234)
        space:write_u16(0xfffffe82,0x5a00|control)
        space:write_u16(0xfffffe80,0x5afa);space:write_u16(0xfffffe80,0xa567)
        emu.wait(0.004)
        assert(space:read_u32(0xffffffe8)==(control==0x60 and 0x1234 or 0xaaff),'WDT reset selected wrong BSC initialization')
        assert((space:read_u8(0xfffffe83)&0xe0)==(0x80|control),'RSTCSR must survive watchdog reset')
        assert(cpu.state.PC.value==0x100 or cpu.state.PC.value==0x102,'WDT failed to release reset into ROM vector')
        space:read_u8(0xfffffe83);space:write_u16(0xfffffe82,0xa500)
    end
    print('SH7604_WDT_PASS map/keys, clock, interval IRQ/qualified clear, local overflow, manual/power-on reset retention')
    machine:exit()
end
sh7604_wdt_active_thread=coroutine.create(run)
local ok,err=coroutine.resume(sh7604_wdt_active_thread)
if not ok then print('SH7604_WDT_FAIL '..tostring(err));machine:exit() end
