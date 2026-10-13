-- license:BSD-3-Clause
-- Protected-port driver latches must accompany the cipher's saved stream state.
local m=manager.machine;local cpu=m.devices[':maincpu'];local h=cpu.spaces.program
local frame=0
local function item(suffix)
 for name,id in pairs(m.devices[':'].items)do
  if name:sub(-#suffix)==suffix then return emu.item(id)end
 end
 error('missing saved protected-port latch '..suffix)
end
STV_CRYPT_STATE_SUBSCRIPTION=emu.add_machine_frame_notifier(function()
 frame=frame+1
 local ok,e=pcall(function()
  if frame==60 then
   cpu.state.SR.value=0xf0;h:write_u32(0x05fe00a0,0xbfff)
   h:write_u32(0x26006000,0xaffe0009);cpu.state.CURPC.value=0x26006000
   h:write_u32(0x04fffff0,0x10000)
   h:write_u32(0x04fffffc,0x12345678)
   assert(item('m_abus_protenable'):read(0)==0x10000,'enable latch write failed')
   assert(item('m_abus_protkey'):read(0)==0x12345678,'key latch write failed')
   m:save('crypt-latches')
  elseif frame==62 then
   h:write_u32(0x04fffff0,0);h:write_u32(0x04fffffc,0xabcd9876)
   assert(item('m_abus_protenable'):read(0)==0 and item('m_abus_protkey'):read(0)==0xabcd9876,'latch mutation failed')
   m:load('crypt-latches')
  elseif frame==64 then
   assert(item('m_abus_protenable'):read(0)==0x10000,'enable latch not restored')
   assert(item('m_abus_protkey'):read(0)==0x12345678,'key latch not restored')
   print('STV_CRYPT_STATE_PASS enable/key latches and native save/load');m:exit()
  end
 end)
 if not ok then print('STV_CRYPT_STATE_FAIL '..tostring(e));m:exit()end
end)
