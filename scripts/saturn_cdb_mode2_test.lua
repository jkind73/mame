-- license:BSD-3-Clause
-- Real cdb106 firmware authentication and VF2 PAL sector FIFO regression.
local m=manager.machine;local h=m.devices[':maincpu'].spaces.program
local function cmd(a,b,c,d)
 h:write_u16(0x05890008,0xfffe)
 for i,v in ipairs({a,b,c,d})do h:write_u16(0x05890018+4*(i-1),v)end
 for i=1,2000 do
  emu.wait(0.00001)
  if (h:read_u16(0x05890008)&1)~=0 then
   local r={};for j=1,4 do r[j]=h:read_u16(0x05890018+4*(j-1))end
   print(string.format('RESPONSE %04x %04x/%04x/%04x/%04x HIRQ=%04x',a,r[1],r[2],r[3],r[4],h:read_u16(0x05890008)))
   emu.wait(0.00005) -- Lua register accesses do not consume the physical host bus cycles.
   return r
  end
 end
 error('command timeout')
end
local function test()
 emu.wait(0.9);cmd(0x0400,0,0,0);emu.wait(0.2);cmd(0x1080,150,0x0080,160)
 local id
 for name,n in pairs(m.devices[':cdb'].items)do if name:match('/m_sector$')then id=n end end
 assert(id,'sector save item');local sector=emu.item(id)
 local found=false
 for i=1,100000 do
  emu.wait(0.00001)
  if sector:read(12)==0 and sector:read(13)==2 and sector:read(14)==0 and sector:read(15)==2 then found=true;break end
 end
 assert(found,'mode-2 sector never reached drive output')
 local size=h:read_u32(0x05901000);assert(size==2048 or size==2324,'reference size')
 assert(sector:read(18)==(size==2324 and 0x20 or 0),'form bit')
 for i=16,19 do assert(sector:read(i)==sector:read(i+4),'duplicated subheader')end
 for i=0,size-1 do assert(sector:read(24+i)==h:read_u8(0x05900000+i),'mode-2 payload byte '..i)end
 local edc=size==2324 and 2348 or 2072;local crc=0
 for i=16,edc-1 do
  crc=crc~sector:read(i)
  for bit=1,8 do crc=(crc>>1)~((crc&1)~=0 and 0xd8018001 or 0)end
 end
 for i=0,3 do assert(sector:read(edc+i)==((crc>>(8*i))&255),'mode-2 EDC byte '..i)end
 print('SATURN_CDB_MODE2_PASS payload='..size)
end
emu.register_frame_done(function()end)
coroutine.resume(coroutine.create(function()local ok,e=pcall(test);if not ok then print('SATURN_CDB_FIRMWARE_FAIL '..tostring(e))end;m:exit()end))
