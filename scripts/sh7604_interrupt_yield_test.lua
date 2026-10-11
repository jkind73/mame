-- license:BSD-3-Clause
-- A persistent FRT IRQ must not prevent the DRC returning to the scheduler.
local m=manager.machine
local cpu=m.devices[':maincpu'];local mem=cpu.spaces.program
local function run()
 local pc,handler,vectors=0x26004000,0x26002000,0x26001000
 mem:write_u32(pc,0xaffe0009)
 -- ADD #1,R8; RTE; NOP: deliberately leave the level request asserted.
 mem:write_u16(handler,0x7801);mem:write_u16(handler+2,0x002b);mem:write_u16(handler+4,9)
 mem:write_u32(vectors+0x41*4,handler)
 mem:write_u16(0xfffffe60,0x0800);mem:write_u16(0xfffffe66,0x4041)
 mem:write_u8(0xfffffe16,0);mem:write_u8(0xfffffe17,0)
 mem:write_u16(0xfffffe14,0xffff);mem:write_u16(0xfffffe12,0xfffe)
 mem:write_u8(0xfffffe10,0x09)
 cpu.state.VBR.value=vectors;cpu.state.R15.value=0x26090000
 cpu.state.R8.value=0;cpu.state.SR.value=0;cpu.state.CURPC.value=pc
 emu.wait(0.001)
 assert(cpu.state.R8.value>10,'persistent interrupt was not delivered repeatedly')
 assert(cpu.state.R15.value>=0x2608fff0,'interrupt stack grew without returns')
 mem:write_u8(0xfffffe10,1);cpu.state.SR.value=0xf0
 print('SH7604_INTERRUPT_YIELD_PASS persistent interrupt returns control to scheduler')
end
thread=coroutine.create(function()local ok,err=pcall(run);if not ok then print('SH7604_INTERRUPT_YIELD_FAIL '..tostring(err))end;m:exit()end)
coroutine.resume(thread)
