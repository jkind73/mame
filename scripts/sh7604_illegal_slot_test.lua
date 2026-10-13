-- license:BSD-3-Clause
-- Real SH7604 general/slot illegal exceptions and a self-referential slot branch.
local m=manager.machine;local cpu=m.devices[':maincpu'];local h=cpu.spaces.program
local pc=0x26008000;local target=pc+0x100;local vbr=pc+0x1000;local stack=pc+0x2000
local function clear_delay()
 for name,id in pairs(cpu.items)do
  if name:match('m_delay$') or name:match('m_zero_delay_pending$')then emu.item(id):write(0,0)end
 end

end
local function run()
 emu.wait(0.02);h:write_u8(0xfffffe92,0x10)
 for vector=4,6,2 do
  local handler=vbr+0x200+vector*16
  h:write_u32(vbr+vector*4,handler);h:write_u32(handler,0xaffe0009)
 end
 local slots={0xaffe,0xbffe,0x000b,0x002b,0x0403,0x0423,0x440b,0x442b,0x8900,0x8b00,0x8d00,0x8f00,0xc310,0xffff,0x0000,0x4000|0x31,0x004b,0x012b,0x0443,0x44cb}
 for _,outer in ipairs({0xa07e,0x442b,0x440b,0xb07e})do
  for _,op in ipairs(slots)do
   clear_delay();h:write_u16(pc,outer);h:write_u16(pc+2,op);h:write_u32(target,0xaffe0009)
   h:write_u32(stack-8,0);h:write_u32(stack-4,0)
   cpu.state.VBR.value=vbr;cpu.state.SR.value=0xf0;cpu.state.R15.value=stack
   cpu.state.R4.value=target;cpu.state.PR.value=0x12345678;cpu.state.CURPC.value=pc
   emu.wait(0.0001)
   assert(cpu.state.CURPC.value==(vbr+0x260)&0x0fffffff or cpu.state.CURPC.value==(vbr+0x262)&0x0fffffff,string.format('vector 6 missing outer=%04x slot=%04x PC=%08x',outer,op,cpu.state.CURPC.value))
   assert(cpu.state.R15.value==stack-8,'slot stack depth')
   assert(h:read_u32(stack-8)==target,string.format('slot saved wrong jump address: %08x',h:read_u32(stack-8)))
   assert(h:read_u32(stack-4)==0xf0,'slot saved wrong SR')
   assert(cpu.state.PR.value==((outer==0x440b or outer==0xb07e)and pc+4 or 0x12345678),'illegal slot changed PR')
  end
 end
 -- Both named PC and CURPC debugger edits cancel the old pending slot.
 for _,alias in ipairs({'PC','CURPC'})do
  for name,id in pairs(cpu.items)do
   if name:match('m_delay$')then emu.item(id):write(0,target)end
   if name:match('m_zero_delay_pending$')then emu.item(id):write(0,1)end
  end
  cpu.state[alias].value=pc
  for name,id in pairs(cpu.items)do
   if name:match('m_delay$')or name:match('m_zero_delay_pending$')then
    assert(emu.item(id):read(0)==0,'PC alias retained a pending slot: '..alias)
   end
  end
 end
 -- Zero is a valid delayed destination, not an absent-delay marker.
 for _,outer in ipairs({0x442b,0x440b,0x000b,0x002b,0x0403,0x0423})do
  clear_delay();h:write_u16(pc,outer);h:write_u16(pc+2,0xffff)
  h:write_u32(stack,0);h:write_u32(stack+4,0xf0)
  cpu.state.VBR.value=vbr;cpu.state.SR.value=0xf0;cpu.state.R15.value=stack
  cpu.state.R4.value=(outer==0x0403 or outer==0x0423)and(-(pc+4)&0xffffffff)or 0;cpu.state.PR.value=0;cpu.state.CURPC.value=pc
  emu.wait(0.0001)
  local expected_stack=outer==0x002b and stack or stack-8
  assert(cpu.state.CURPC.value==(vbr+0x260)&0x0fffffff or cpu.state.CURPC.value==(vbr+0x262)&0x0fffffff,'zero-target slot vector missing')
  assert(cpu.state.R15.value==expected_stack and h:read_u32(expected_stack)==0,'zero-target slot saved wrong PC')
 end
 -- A legal slot must execute once before reaching address zero. The
 -- diagnostic ROM has an illegal word there, which then takes vector 4.
 for _,outer in ipairs({0x442b,0x440b,0x000b,0x002b,0x0403,0x0423})do
  clear_delay();h:write_u16(pc,outer);h:write_u16(pc+2,0xe72a)
  h:write_u32(stack,0);h:write_u32(stack+4,0xf0)
  cpu.state.VBR.value=vbr;cpu.state.SR.value=0xf0;cpu.state.R15.value=stack
  cpu.state.R4.value=(outer==0x0403 or outer==0x0423)and(-(pc+4)&0xffffffff)or 0;cpu.state.R7.value=0;cpu.state.PR.value=0;cpu.state.CURPC.value=pc
  emu.wait(0.0001)
  local expected_stack=outer==0x002b and stack or stack-8
  assert(cpu.state.R7.value==42,'legal zero-target slot skipped')
  assert(h:read_u32(expected_stack)==0,'legal zero-target branch failed')
 end
 -- Retain a pending zero-target slot through native save/load and a core
 -- timeslice while the CPU is disabled; resume must still take vector 6.
 local function field(suffix)
  for name,id in pairs(cpu.items)do
   if name:sub(-#suffix)==suffix then return emu.item(id)end
  end
  error('missing '..suffix)
 end
 clear_delay();h:write_u16(pc+2,0xffff)
 cpu.state.VBR.value=vbr;cpu.state.SR.value=0xf0;cpu.state.R15.value=stack;cpu.state.CURPC.value=pc+2
 field('m_cpu_off'):write(0,1);field('m_zero_delay_pending'):write(0,1)
 m:save('zero-delay');emu.wait(0.1)
 field('m_zero_delay_pending'):write(0,0);m:load('zero-delay');emu.wait(0.1)
 assert(field('m_zero_delay_pending'):read(0)==1,'pending zero slot lost on load')
 field('m_cpu_off'):write(0,0);emu.wait(0.0001)
 assert(cpu.state.R15.value==stack-8 and h:read_u32(stack-8)==0,'restored zero-target slot wrong PC')
 assert(cpu.state.CURPC.value==(vbr+0x260)&0x0fffffff or cpu.state.CURPC.value==(vbr+0x262)&0x0fffffff,'restored zero-target slot wrong vector')
 clear_delay();h:write_u16(pc,0xffff);cpu.state.VBR.value=vbr;cpu.state.SR.value=0xf0;cpu.state.R15.value=stack;cpu.state.CURPC.value=pc
 emu.wait(0.0001)
 assert(cpu.state.CURPC.value==(vbr+0x240)&0x0fffffff or cpu.state.CURPC.value==(vbr+0x242)&0x0fffffff,'general illegal vector')
 assert(cpu.state.R15.value==stack-8 and h:read_u32(stack-8)==pc,'general illegal saved PC')
 print('SH7604_ILLEGAL_SLOT_PASS 80 nonzero and 12 zero-target slots, self-loop decode, vector 6 jump PC/SR/PR and general vector 4');m:exit()
end
emu.register_frame_done(function()
 if ILLEGAL_SLOT_TEST_STARTED then return end;ILLEGAL_SLOT_TEST_STARTED=true
 coroutine.resume(coroutine.create(function()local ok,e=pcall(run);if not ok then print('SH7604_ILLEGAL_SLOT_FAIL '..tostring(e));m:exit()end end))
end)
