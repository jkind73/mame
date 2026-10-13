-- license:BSD-3-Clause
-- Real SH-2 and 68000 maps must agree on the 512KiB SCSP RAM boundary.
local m=manager.machine
emu.register_frame_done(function()
 if SOUND_RAM_BOUNDARY_TEST_STARTED then return end
 SOUND_RAM_BOUNDARY_TEST_STARTED=true
 local ok,e=pcall(function()
  local h=m.devices[':maincpu'].spaces.program
  local s=m.devices[':slave'].spaces.program
  local a=m.devices[':audiocpu'].spaces.program
  local unmapped=h:read_u16(0x05800000)
  h:write_u16(0x05a00000,0x1234);h:write_u16(0x05a7fffe,0x5678)
  assert(a:read_u16(0)==0x1234 and a:read_u16(0x7fffe)==0x5678,'CPU sound RAM views disagree')
  assert(s:read_u16(0x05a00000)==0x1234 and s:read_u16(0x05a7fffe)==0x5678,'slave sound RAM view disagrees')
  -- Exercise the entire formerly mapped expansion region, including its end.
  for addr=0x05a80000,0x05affffe,2 do
   h:write_u16(addr,0xa5a5)
   assert(h:read_u16(addr)==unmapped,'expansion incorrectly backed by RAM')
  end
  assert(h:read_u16(0x05a00000)==0x1234 and h:read_u16(0x05a7fffe)==0x5678,'expansion changed physical RAM')
  print('SATURN_SOUND_RAM_BOUNDARY_PASS 512KiB shared views and 512KiB absent expansion');m:exit()
 end)
 if not ok then print('SATURN_SOUND_RAM_BOUNDARY_FAIL '..tostring(e));m:exit()end
end)
