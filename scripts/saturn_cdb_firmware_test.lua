-- license:BSD-3-Clause
local m=manager.machine
local cpu=m.devices[':cdb:cdbcpu'];local sp=cpu.spaces.program
local host=m.devices[':maincpu'].spaces.program
local n=0
emu.register_frame_done(function()
 n=n+1
 if n%6==0 then
  print(string.format('CDB_BOOT t=%.3f PC=%08x SR=%08x SP=%08x err=%08x hw=%02x HIRQ=%04x RR=%04x/%04x/%04x/%04x SCI=%02x/%02x/%02x/%02x ITU=%02x/%02x/%02x',m.time:as_double(),cpu.state.PC.value,cpu.state.SR.value,cpu.state.R15.value,sp:read_u32(0x0f000000),sp:read_u8(0x0f00027d),host:read_u16(0x05890008),host:read_u16(0x05890018),host:read_u16(0x0589001c),host:read_u16(0x05890020),host:read_u16(0x05890024),sp:read_u8(0x05fffec0),sp:read_u8(0x05fffec2),sp:read_u8(0x05fffec4),sp:read_u8(0x05fffec5),sp:read_u8(0x05ffff00),sp:read_u8(0x05ffff23),sp:read_u8(0x05ffff24)))
 end
end)
