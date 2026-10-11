-- license:BSD-3-Clause
-- Guest MINIT/SINIT stores must yield to synchronized FRT capture without freezing.
local m=manager.machine
local master=m.devices[':maincpu'];local slave=m.devices[':slave']
local mem=master.spaces.program
local function run()
 mem:write_u8(0x0010001f,2);emu.wait(0.0002)
 local code=0x26004000
 local handler,vectors=0x26002000,0x26001000
 for i,op in ipairs({0xd103,0x6010,0xe000,0x2100,0x7801,0x002b,9})do mem:write_u16(handler+2*(i-1),op)end
 mem:write_u32(handler+16,0xfffffe11);mem:write_u32(vectors+0x40*4,handler)
 for _,interrupts in ipairs({false,true})do
 for _,width in ipairs({1,2})do
  for i,op in ipairs({0x2100|width,0x7701,0xaffc,9})do mem:write_u16(code+2*(i-1),op)end
  for _,cpu in ipairs({master,slave})do
   local other=cpu==master and slave or master
   local addr=cpu==master and 0x01000000 or 0x01800000
   local space=other.spaces.program
   space:write_u8(0xfffffe10,interrupts and 0x81 or 1);space:write_u8(0xfffffe16,0)
   space:write_u16(0xfffffe60,0x0800);space:write_u16(0xfffffe66,0x4041)
   other.state.VBR.value=vectors;other.state.R15.value=0x26090000;other.state.R8.value=0;other.state.SR.value=interrupts and 0 or 0xf0
   space:read_u8(0xfffffe11);space:write_u8(0xfffffe11,0)
   cpu.state.SR.value=0xf0;cpu.state.R0.value=0;cpu.state.R1.value=addr;cpu.state.R7.value=0;cpu.state.CURPC.value=code
   emu.wait(0.0001)
   assert(cpu.state.R7.value>0,'guest MINIT/SINIT store froze CPU')
   if interrupts then assert(other.state.R8.value>0,'MINIT/SINIT capture IRQ/return missing')else assert(space:read_u8(0xfffffe11)&0x80~=0,'MINIT/SINIT capture missing')end
   other.state.SR.value=0xf0;other.state.CURPC.value=0x100
   cpu.state.CURPC.value=0x100
  end
 end
 end
 print('SATURN_MINIT_PASS 16/32-bit guest MINIT/SINIT synchronization and FRT capture')
end
thread=coroutine.create(function()local ok,err=pcall(run);if not ok then print('SATURN_MINIT_FAIL '..tostring(err))end;m:exit()end)
coroutine.resume(thread)
