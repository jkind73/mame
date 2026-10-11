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
local function item(tag,suffix)
 for name,n in pairs(m.devices[tag].items)do if name:match('/'..suffix..'$')then return emu.item(n)end end
 error('missing '..suffix)
end
local function test()
 emu.wait(0.9);cmd(0x0400,0,0,0);emu.wait(0.2)
 local fad=h:read_u32(0x05901004);assert(fad>150)
 cmd(0x1080|((fad>>16)&255),fad&65535,0x0080,300);emu.wait(0.4)
 local playing=item(':cdda','m_audio_playing');local paused=item(':cdda','m_audio_pause');local lba=item(':cdda','m_audio_lba')
 assert(playing:read(0)~=0 and paused:read(0)==0,'CDDA did not start')
 local save=m:buffer_save();local pos=lba:read(0);emu.wait(0.15);assert(lba:read(0)>pos,'audio position stuck')
 m:buffer_load(save);assert(lba:read(0)==pos and playing:read(0)~=0,'audio restore')
 cmd(0x11ff,0xffff,0,0);emu.wait(0.2);assert(paused:read(0)~=0,'pause');pos=lba:read(0);emu.wait(0.1);assert(lba:read(0)==pos,'paused audio advances')
 cmd(0x10ff,0xffff,0x0080,300);emu.wait(0.3);assert(playing:read(0)~=0 and paused:read(0)==0,'resume')
 cmd(0x1100,0,0,0);emu.wait(0.2);assert(playing:read(0)==0,'stop')
 h:write_u32(0x05901010,1);emu.wait(0.2);assert(item(':cdb','m_tray_open'):read(0)~=0,'tray open');assert(playing:read(0)==0,'tray audio')
 h:write_u32(0x05901010,0);emu.wait(1);assert(item(':cdb','m_tray_open'):read(0)==0,'tray close');local r=cmd(0x0000,0,0,0);assert(r[2]~=0xffff,'firmware still reports open tray')
 print('SATURN_CDB_AUDIO_PASS')
end
coroutine.resume(coroutine.create(function()local ok,e=pcall(test);if not ok then print('SATURN_CDB_FIRMWARE_FAIL '..tostring(e))end;m:exit()end))
