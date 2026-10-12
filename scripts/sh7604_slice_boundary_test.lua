-- license:BSD-3-Clause
-- A timer edge inside an ALU sequence must stop execution at an instruction boundary.
local m = manager.machine
local cpu = m.devices[':maincpu']
local mem = cpu.spaces.program
local function test()
 mem:write_u32(0x05fe00a0, 0xffffffff) -- isolate the CPU's FRT interrupt
 local handler, vectors = 0x26002000, 0x26001000
 -- Capture the number of foreground instructions, then park inside the handler.
 mem:write_u16(handler, 0x6983) -- MOV R8,R9
 mem:write_u16(handler + 2, 0xaffe)
 mem:write_u16(handler + 4, 9)
 mem:write_u32(vectors + 0x41 * 4, handler)
 for _, pc in ipairs({0x26004000, 0x06004000}) do
  cpu.state.SR.value = 0xf0
  mem:write_u8(0xfffffe10, 0)
  mem:write_u8(0xfffffe92, 0x10) -- purge, initially uncached
  for i = 0, 31 do mem:write_u16(pc + i * 2, 0x7801) end -- ADD #1,R8
  mem:write_u16(pc + 64, 0xafde) -- BRA back to first ADD
  mem:write_u16(pc + 66, 9)
  if pc < 0x20000000 then mem:write_u8(0xfffffe92, 0x11) end
  mem:write_u16(0xfffffe60, 0x0800)
  mem:write_u16(0xfffffe68, 0x4100)
  mem:write_u8(0xfffffe16, 0) -- FRT f/8
  mem:read_u8(0xfffffe11)
  mem:write_u8(0xfffffe11, 0)
  mem:write_u16(0xfffffe12, 0xffff) -- overflow after eight clocks
  mem:write_u8(0xfffffe10, 2)
  cpu.state.VBR.value = vectors
  cpu.state.R15.value = 0x26090000
  cpu.state.R8.value = 0
  cpu.state.R9.value = 0xffffffff
  cpu.state.CURPC.value = pc
  cpu.state.SR.value = 0
  emu.wait(0.00001)
  local count = cpu.state.R9.value
  print(string.format('SLICE_BOUNDARY pc=%08x count=%d', pc, count))
  assert(count ~= 0xffffffff, 'timer interrupt was not delivered')
  assert(count <= 8, 'executed ALU instructions beyond the eight-clock timer edge: ' .. count)
 end
 mem:write_u8(0xfffffe10, 0)
 cpu.state.SR.value = 0xf0
 print('SH7604_SLICE_BOUNDARY_PASS cached and uncached instruction budgets')
end
thread = coroutine.create(function()
 local ok, err = pcall(test)
 if not ok then print('SH7604_SLICE_BOUNDARY_FAIL ' .. tostring(err)) end
 m:exit()
end)
coroutine.resume(thread)
