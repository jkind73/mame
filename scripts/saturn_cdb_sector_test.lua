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
 emu.wait(0.9)
 cmd(0x0400,0,0,0);emu.wait(0.2)
 cmd(0xe000,0,0,0);emu.wait(2);local auth=cmd(0xe100,0,0,0);assert(auth[2]==4 and auth[3]==0,'firmware disc authentication')
 cmd(0x4603,0x00ff,0,0);emu.wait(0.01);cmd(0x4700,0,0,0)
 cmd(0x3000,0,0,0);emu.wait(0.01);cmd(0x3100,0,0,0)
 cmd(0x1080,150,0x0080,160);emu.wait(0.5)
 cmd(0x5000,0,0,0);local count=cmd(0x5100,0,0,0);assert(count[4]>0,'sector partition count');local transfer=cmd(0x6100,0,0,1);assert((transfer[1]&0x4000)~=0,'sector transfer accepted')
 local out={}
 for i=1,1024 do
  for j=1,100 do if (h:read_u16(0x05890004)&1)==0 then break end;emu.wait(0.000001)end
  local v=h:read_u16(0x05818000);out[#out+1]=string.char(v>>8,v&255)
  emu.wait(0.000001)
 end
 local data=table.concat(out);assert(#data==2048 and data:sub(1,16)=='SEGA SEGASATURN ','sector bytes/header');for i=1,2048 do assert(data:byte(i)==h:read_u8(0x05900000+i-1),'sector mismatch at byte '..i)end;print('SECTOR_PASS '..#data)
 cmd(0x0600,0,0,0)
 local dst=0x06001000
 local function check_ram(name)
  for i=0,2047 do assert(h:read_u8(dst+i)==h:read_u8(0x05900000+i),string.format('%s byte %d got=%02x want=%02x',name,i,h:read_u8(dst+i),h:read_u8(0x05900000+i)))end
  print('AWAIT_PASS '..name)
 end
 for _,tag in ipairs({':maincpu',':slave'})do
  local cpu=m.devices[tag];local mem=cpu.spaces.program
  cmd(0x6100,0,0,1)
  local base=0x06008000
  local code={0xd10f,0xd210,0xd310,0x6012,0x2202,0x7204,0x4310,0x8ffa,0xe001,0xd410,0x2402,0xaffe,0x0009}
  for i,v in ipairs(code)do h:write_u16(base+2*(i-1),v)end
  h:write_u32(base+0x40,0x25818000);h:write_u32(base+0x44,dst);h:write_u32(base+0x48,512);h:write_u32(base+0x54,0x06007800)
  h:write_u32(0x06007800,0);cpu.state.SR.value=0xf0;cpu.state.CURPC.value=base
  for i=1,10000 do emu.wait(0.00001);if h:read_u32(0x06007800)==1 then break end end
  assert(h:read_u32(0x06007800)==1,'CPU FIFO wait did not finish '..tag)
  check_ram('CPU '..tag);cpu.state.CURPC.value=0x100;cmd(0x0600,0,0,0)
  cmd(0x6100,0,0,1)
  mem:write_u32(0xffffffb0,0);mem:write_u32(0xffffff8c,0)
  mem:write_u32(0xffffff80,0x25818000);mem:write_u32(0xffffff84,dst)
  mem:write_u32(0xffffff88,512);mem:write_u32(0xffffff8c,0x4a01);mem:write_u32(0xffffffb0,1)
  for i=1,10000 do emu.wait(0.00001);if (mem:read_u32(0xffffff8c)&2)~=0 then break end end
  assert((mem:read_u32(0xffffff8c)&2)~=0,'SH2 DMA FIFO wait did not finish '..tag)
  check_ram('DMAC '..tag);mem:write_u32(0xffffffb0,0);mem:write_u32(0xffffff8c,0);cmd(0x0600,0,0,0)
 end
 for step=1,2 do
 dst=step==1 and 0x06001000 or 0x05c01000
 for level=0,2 do
  cmd(0x6100,0,0,1)
  local b=0x05fe0000+level*0x20
  h:write_u32(b,0x05818000);h:write_u32(b+4,dst);h:write_u32(b+8,2048);h:write_u32(b+12,step)
  h:write_u32(b+20,7);h:write_u32(b+16,0x101)
  if step==2 and level==0 then
   local pending={};for name,id in pairs(m.devices[':scu'].items)do if name:find('cd_second_pending')then pending[#pending+1]=emu.item(id)end end
   local half=false
   for i=1,10000 do
    emu.wait(0.00000001);for _,v in ipairs(pending)do if v:read(0)~=0 then half=true end end
    if half then break end
   end
   assert(half,'eight-byte transfer half-phase not reached')
   local state=m:buffer_save();emu.wait(0.002);check_ram('SCU paired before load')
   assert(m:buffer_load(state),'SCU half-phase reload');print('SCU_HALF_SAVE_PASS')
  end
  for i=1,10000 do emu.wait(0.00001);if (h:read_u32(0x05fe007c)&(0x30<<(level*4)))==0 then break end end
  assert((h:read_u32(0x05fe007c)&(0x30<<(level*4)))==0,'SCU DMA FIFO wait did not finish')
  check_ram('SCU '..level..' stride '..step);cmd(0x0600,0,0,0)
 end
 end
 dst=0x06001000
 local dsp=m.devices[':scu:scudsp']
 cmd(0x6100,0,0,1)
 h:write_u32(0x05fe0080,0x8000)
 h:write_u32(0x05fe0084,0xc0000020);h:write_u32(0x05fe0084,0xf0000000)
 dsp.state.CT0.value=0;dsp.state.RA0.value=0x05818000>>2
 h:write_u32(0x05fe0080,0x18000)
 for i=1,10000 do emu.wait(0.00001);if (dsp.state.SR.value&0x810000)==0 then break end end
 assert((dsp.state.SR.value&0x810000)==0,'DSP DMA FIFO wait did not finish')
 for i=0,31 do assert(dsp.spaces.data:read_u32(i)==h:read_u32(0x05900000+4*i),'DSP FIFO data '..i)end
 print('AWAIT_PASS DSP');cmd(0x0600,0,0,0)

 local function item(device,field)
  for name,id in pairs(m.devices[device].items)do if name:match('/'..field..'$')then return emu.item(id):read(0)end end
  error('missing saved field '..field)
 end
 -- Put Sector Data into a separate partition, then read the exact payload back.
 for pass,tag in ipairs({':maincpu',':slave'})do
  local cpu=m.devices[tag]
  local source=0x06004000
  for i=0,511 do h:write_u32(source+4*i,0x51370000|((i+pass*0x100)&0xffff))end
  if pass==1 then
   for i=1,20000 do if item(':cdb','m_link_active')~=0 and item(':cdb','m_link_byte')<8 and item(':cdb','m_link_bit')>0 then break end;emu.wait(0.00001)end
  end
  local r=cmd(0x6400,0,0x0100,1);assert((r[1]&0xc000)==0x4000,'put sector rejected')
  local base=0x06008000
  local code={0xd10f,0xd210,0xd310,0x6016,0x2202,0x0009,0x4310,0x8ffa,0xe001,0xd410,0x2402,0xaffe,0x0009}
  for i,v in ipairs(code)do h:write_u16(base+2*(i-1),v)end
  h:write_u32(base+0x40,source);h:write_u32(base+0x44,0x25818000);h:write_u32(base+0x48,512);h:write_u32(base+0x54,0x06007800)
  h:write_u32(0x06007800,0);cpu.state.SR.value=0xf0;cpu.state.CURPC.value=base
  emu.wait(0.00002)
  if pass==1 then
   assert(h:read_u32(0x06007800)==0,'write already complete before live-save test')
   assert(item(':cdb','m_link_active')~=0,'SCI link was not active at save')
   print(string.format('SAVE PC=%x R0=%x R1=%x R2=%x R3=%x FIFO=%d',cpu.state.PC.value,cpu.state.R0.value,cpu.state.R1.value,cpu.state.R2.value,cpu.state.R3.value,item(':cdb','m_fifo_count')));local saved=m:buffer_save();emu.wait(0.002)
   assert(h:read_u32(0x06007800)==1,'first write did not finish')
   assert(m:buffer_load(saved),'live FIFO/SCI state load')
   assert(h:read_u32(0x06007800)==0,'CPU write cursor was not restored');print(string.format('LOAD PC=%x R0=%x R1=%x R2=%x R3=%x FIFO=%d',cpu.state.PC.value,cpu.state.R0.value,cpu.state.R1.value,cpu.state.R2.value,cpu.state.R3.value,item(':cdb','m_fifo_count')))
  end
  emu.wait(0.002);assert(h:read_u32(0x06007800)==1,'CPU FIFO write did not finish')
  cpu.state.CURPC.value=0x100;cmd(0x0600,0,0,0);emu.wait(0.001)
  cmd(0x6100,0,0x0100,1)
  for i=0,511 do
   for j=1,10000 do if (h:read_u16(0x05890004)&1)==0 then break end;emu.wait(0.000001)end
   local hi=h:read_u16(0x05818000)
   for j=1,10000 do if (h:read_u16(0x05890004)&1)==0 then break end;emu.wait(0.000001)end
   local lo=h:read_u16(0x05818000)
   assert(((hi<<16)|lo)==h:read_u32(source+4*i),string.format('put/get sector payload %d got=%08x want=%08x',i,(hi<<16)|lo,h:read_u32(source+4*i)))
  end
  cmd(0x0600,0,0,0);print('AWAIT_WRITE_PASS '..tag)
  cmd(0x6200,0,0x0100,1);emu.wait(0.001)
 end
 -- Every DMA writer must obey the same full-FIFO wait as native MOV stores.
 for _,engine in ipairs({'DMAC main','DMAC slave','SCU 0','SCU 1','SCU 2','DSP'})do
  local source=0x06004000
  for i=0,511 do h:write_u32(source+4*i,0x725a0000|(i&63));dsp.spaces.data:write_u32(i&63,0x725a0000|(i&63))end
  cmd(0x6400,0,0x0100,1)
  if engine:match('DMAC')then
   local mem=m.devices[engine=='DMAC main' and ':maincpu' or ':slave'].spaces.program
   mem:write_u32(0xffffffb0,0);mem:write_u32(0xffffff8c,0)
   mem:write_u32(0xffffff80,source);mem:write_u32(0xffffff84,0x25818000);mem:write_u32(0xffffff88,512)
   mem:write_u32(0xffffff8c,0x1a01);mem:write_u32(0xffffffb0,1)
   for i=1,10000 do emu.wait(0.00001);if (mem:read_u32(0xffffff8c)&2)~=0 then break end end
   assert((mem:read_u32(0xffffff8c)&2)~=0,engine..' write stalled')
   mem:write_u32(0xffffffb0,0);mem:write_u32(0xffffff8c,0)
  elseif engine:match('SCU')then
   local level=tonumber(engine:sub(-1));local b=0x05fe0000+level*0x20
   h:write_u32(b,source);h:write_u32(b+4,0x05818000);h:write_u32(b+8,2048);h:write_u32(b+12,0x100)
   h:write_u32(b+20,7);h:write_u32(b+16,0x101)
   for i=1,10000 do emu.wait(0.00001);if (h:read_u32(0x05fe007c)&(0x30<<(level*4)))==0 then break end end
   assert((h:read_u32(0x05fe007c)&(0x30<<(level*4)))==0,engine..' write stalled')
  else
   for block=1,2 do
    h:write_u32(0x05fe0080,0x8000);h:write_u32(0x05fe0084,0xc0005000);h:write_u32(0x05fe0084,0xf0000000)
    dsp.state.CT0.value=0;dsp.state.WA0.value=0x05818000>>2;h:write_u32(0x05fe0080,0x18000)
    for i=1,10000 do emu.wait(0.00001);if (dsp.state.SR.value&0x810000)==0 then break end end
    assert((dsp.state.SR.value&0x810000)==0,'DSP write stalled')
   end
  end
  cmd(0x0600,0,0,0);emu.wait(0.001);cmd(0x6100,0,0x0100,1)
  for i=0,1023 do
   for j=1,10000 do if (h:read_u16(0x05890004)&1)==0 then break end;emu.wait(0.000001)end
   assert(h:read_u16(0x05818000)==h:read_u16(source+2*i),engine..' write payload halfword '..i)
  end
  cmd(0x0600,0,0,0);cmd(0x6200,0,0x0100,1);emu.wait(0.001);print('AWAIT_WRITE_PASS '..engine)
 end
 print('LIVE_FIFO_SAVE_PASS')
 for name,id in pairs(m.devices[':cdb'].items)do
  if name:find('m_host_underflow')or name:find('m_host_overflow')then assert(emu.item(id):read(0)==0,name..' was nonzero')end
 end
 print('SATURN_CDB_FIRMWARE_PASS')
end
emu.register_frame_done(function()end)
coroutine.resume(coroutine.create(function()local ok,e=pcall(test);if not ok then print('SATURN_CDB_FIRMWARE_FAIL '..tostring(e))end;m:exit()end))
