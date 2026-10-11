-- license:BSD-3-Clause
-- Integrated Saturn CD LLE boot trace and FIFO error check.
local m=manager.machine;local n=0;local h=m.devices[':maincpu'].spaces.program
emu.register_frame_done(function()
 n=n+1;if n%300==0 then
 local sp=m.devices[':saturn_cdb:cdbcpu'].spaces.program
 print(string.format('LLE_CONSOLE %.1f PC=%x CD=%04x/%04x/%04x/%04x HIRQ=%04x SH1=%x auth=%04x',m.time:as_double(),m.devices[':maincpu'].state.PC.value,h:read_u16(0x05890018),h:read_u16(0x0589001c),h:read_u16(0x05890020),h:read_u16(0x05890024),h:read_u16(0x05890008),m.devices[':saturn_cdb:cdbcpu'].state.PC.value,sp:read_u16(0x0f000786)))
 for name,id in pairs(m.devices[':saturn_cdb'].items)do if name:find('m_host_')then local v=emu.item(id):read(0);print(name,v);assert(v==0,'integrated host FIFO error '..name)end end
 m.video:snapshot()
 end
end)
