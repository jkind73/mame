-- license:BSD-3-Clause
-- Periodic subcode status must keep arriving while sector storage is full.
local m = manager.machine
local sp = m.devices[':maincpu'].spaces.program
local function item(field)
 for name, id in pairs(m.devices[':saturn_cd_hle'].items) do
  if name:match('/' .. field .. '$') then return emu.item(id) end
 end
 error('missing CD field ' .. field)
end
local function test()
 local full, hirq = item('buffull'), item('hirqreg')
 for _, value in ipairs({0, 1, 0}) do
  full:write(0, value)
  hirq:write(0, 0x0080) -- existing host-transfer completion must stay latched
  emu.wait(0.05)
  local flags = sp:read_u16(0x05890008)
  assert((flags & 0x0400) ~= 0, 'SCDQ suppressed with buffull=' .. value)
  assert((flags & 0x0080) ~= 0, 'periodic update lost host-transfer completion')
  assert(((flags & 0x0008) ~= 0) == (value == 1), 'buffer-full indication changed')
  sp:write_u16(0x05890008, 0xfbff) -- host acknowledges only SCDQ
  assert((sp:read_u16(0x05890008) & 0x0400) == 0, 'SCDQ acknowledgement failed')
  emu.wait(0.05)
  assert((sp:read_u16(0x05890008) & 0x0400) ~= 0, 'SCDQ did not recur after acknowledgement')
 end
 print('SATURN_CD_FULL_BUFFER_PASS periodic SCDQ, acknowledgement and other latched flags')
end
thread = coroutine.create(function()
 local ok, err = pcall(test)
 if not ok then print('SATURN_CD_FULL_BUFFER_FAIL ' .. tostring(err)) end
 m:exit()
end)
coroutine.resume(thread)
