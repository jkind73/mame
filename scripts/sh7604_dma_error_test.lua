-- license:BSD-3-Clause
-- Actual mapped DMAC: address errors must not touch an aligned neighbour.
local m=manager.machine;local cpu=m.devices[':maincpu'];local h=cpu.spaces.program
local function reset()
 h:write_u32(0xffffffb0,0);h:write_u32(0xffffff8c,0);h:write_u32(0xffffff9c,0)
 h:read_u32(0xffffffb0);h:write_u32(0xffffffb0,0)
end
local function run()
 for _,v in ipairs({{0x06004001,0x06005000,1},{0x06004000,0x06005001,1},{0x06004002,0x06005000,2},{0x06004000,0x06005002,2},{0xffffff00,0x06005000,0},{0xfffffe00,0x06005000,2}})do
  reset();h:write_u32(0x06005000,0xa55a1234)
  h:write_u32(0xffffff80,v[1]);h:write_u32(0xffffff84,v[2]);h:write_u32(0xffffff88,1);h:write_u32(0xffffff8c,0x0201|(v[3]<<10));h:write_u32(0xffffffb0,1)
  emu.wait(0.00001)
  assert((h:read_u32(0xffffffb0)&4)~=0,'AE absent')
  assert(h:read_u32(0x06005000)==0xa55a1234,'error transfer wrote memory')
  assert(h:read_u32(0xffffff88)==1 and (h:read_u32(0xffffff8c)&2)==0,'error completed transfer')
 end
 reset();h:write_u32(0xffffff80,0x06004000);h:write_u32(0xffffff84,0x06005000);h:write_u32(0xffffff88,0x100000);h:write_u32(0xffffff8c,0x0a01);h:write_u32(0xffffffb0,1)
 h:write_u8(0x00100063,1);h:write_u8(0x0010001f,0x18);emu.wait(0.001)
 assert((h:read_u32(0xffffffb0)&2)~=0,'NMI did not inhibit DMAC')
 local left=h:read_u32(0xffffff88);assert(left>0 and left<0x100000,'NMI test did not interrupt active transfer');emu.wait(0.001)
 assert(h:read_u32(0xffffff88)==left and (h:read_u32(0xffffff8c)&2)==0,'DMA continued after NMI')
 reset();print('SH7604_DMA_ERROR_PASS')
end
coroutine.resume(coroutine.create(function()local ok,e=pcall(run);if not ok then print('SH7604_DMA_ERROR_FAIL '..tostring(e))end;m:exit()end))
