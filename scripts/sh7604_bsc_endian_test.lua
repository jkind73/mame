-- license:BSD-3-Clause
-- Actual guest reads/writes and DMA must obey CS2 data lanes (manual 7.3.2).
local m=manager.machine
local cpu=m.devices[':maincpu'];local mem=cpu.spaces.program
local function test()
 local pc,raw,through,dst=0x26008000,0x05a04000,0x25a04000,0x26009000
 cpu.state.SR.value=0xf0
 mem:write_u8(0xfffffe92,0)
 mem:write_u32(0x05fe00a0,0xffffffff)
 local function guest(op,address,value)
  mem:write_u16(pc,op);mem:write_u16(pc+2,0xaffe);mem:write_u16(pc+4,9)
  cpu.state.R1.value=address;cpu.state.R7.value=value or 0
  cpu.state.CURPC.value=pc
  emu.wait(0.0001)
  return cpu.state.R7.value&0xffffffff
 end
 local function sext(v,bits)
  if (v&(1<<(bits-1)))~=0 then return (v|(0xffffffff<<bits))&0xffffffff end
  return v
 end
 for _,mode in ipairs({0,4})do
 for _,width in ipairs(mode==0 and {1,2,4} or {2,4})do
  mem:write_u32(0xffffffec,0xa55a0000|(width==4 and 0x40 or 0))
  mem:write_u32(0xffffffe4,0xa55a0000|0xcc|((width==1 and 1 or width==2 and 2 or 3)<<4))
  for _,little in ipairs({false,true})do
   mem:write_u32(0xffffffe0,0xa55a03f0|mode|(little and 0x1000 or 0))
   mem:write_u32(raw,0x8122ee44)
   local active=little and width>1
   assert(guest(0x6710,through)==0xffffff81,'byte lane was converted')
   assert(guest(0x6711,through)==sext(active and 0x2281 or 0x8122,16),'word lane mismatch')
   local long=active and (width==2 and 0x228144ee or 0x44ee2281) or 0x8122ee44
   assert(guest(0x6712,through)==long,'longword lane mismatch')
   guest(0x2172,through,0x12345678)
   local physical=active and (width==2 and 0x34127856 or 0x78563412) or 0x12345678
   assert(mem:read_u32(raw)==physical,'CPU write lane mismatch')
   guest(0x2171,through,0x1234)
   assert(mem:read_u16(raw)==(active and 0x3412 or 0x1234),'CPU word write lane mismatch')
   guest(0x2170,through,0x5a)
   assert(mem:read_u8(raw)==0x5a,'CPU byte write lane mismatch')
   -- The identical logical access on CS3 is never converted.
   mem:write_u32(dst,0x8122ee44)
   assert(guest(0x6712,dst)==0x8122ee44,'CS3 was converted')
   -- DMAC reads and writes use the physical width, including split 16-bit beats.
   mem:write_u32(raw,0x8122ee44);mem:write_u32(dst,0)
   mem:write_u32(0xffffffb0,0);mem:read_u32(0xffffff8c);mem:write_u32(0xffffff8c,0)
   mem:write_u32(0xffffff80,through);mem:write_u32(0xffffff84,dst)
   mem:write_u32(0xffffff88,1);mem:write_u32(0xffffff8c,0x5a01);mem:write_u32(0xffffffb0,1)
   emu.wait(0.001)
   assert((mem:read_u32(0xffffff8c)&2)~=0,'DMA read did not complete')
   assert(mem:read_u32(dst)==long,string.format('DMA read lane mismatch width=%d little=%s actual=%08x expected=%08x',width,tostring(little),mem:read_u32(dst),long))
   mem:write_u32(dst,0x12345678);mem:write_u32(raw,0)
   mem:write_u32(0xffffffb0,0);mem:read_u32(0xffffff8c);mem:write_u32(0xffffff8c,0)
   mem:write_u32(0xffffff80,dst);mem:write_u32(0xffffff84,through)
   mem:write_u32(0xffffff88,1);mem:write_u32(0xffffff8c,0x5a01);mem:write_u32(0xffffffb0,1)
   emu.wait(0.001)
   assert(mem:read_u32(raw)==physical,'DMA write lane mismatch')
  end
 end
 end
 -- Cache fills and write-through stores use converted physical data.
 mem:write_u32(0xffffffe0,0xa55a13f0);mem:write_u32(0xffffffe4,0xa55a00fc)
 mem:write_u32(raw,0x8122ee44);mem:write_u8(0xfffffe92,0x11)
 assert(guest(0x6712,raw)==0x44ee2281,'cache fill did not convert CS2')
 guest(0x2172,raw,0x12345678)
 assert(mem:read_u32(raw)==0x78563412,'cached write-through did not convert CS2')
 mem:write_u8(0xfffffe92,0)
 local state=m.options.entries['state_directory']:value()..'/bsc-endian.sta'
 m:save(state);emu.wait(0.02)
 mem:write_u32(0xffffffe0,0xa55a03f0)
 assert(guest(0x6712,through)==0x78563412,'conversion did not switch off')
 m:load(state);if not emu.wait(0.02)then emu.wait(0.02)end
 assert(guest(0x6712,through)==0x12345678,'saved BSC conversion was not restored')
 -- Converted cache-through instruction reads use word lanes, not raw decode.
 local code=0x05a05000
 mem:write_u16(code,0x07e7);mem:write_u16(code+2,0xfeaf);mem:write_u16(code+4,0x0900)
 cpu.state.R7.value=0;cpu.state.CURPC.value=code|0x20000000;emu.wait(0.0001)
 assert(cpu.state.R7.value==7,'CS2 instruction fetch used raw endian lanes')
 print('SH7604_BSC_ENDIAN_PASS CPU and DMA data lanes')
end
thread=coroutine.create(function()
 local ok,err=pcall(test)
 if not ok then print('SH7604_BSC_ENDIAN_FAIL '..tostring(err))end
 m:exit()
end)
coroutine.resume(thread)
