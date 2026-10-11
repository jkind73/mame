-- license:BSD-3-Clause
-- Exercise command dispatch and real register responses, without disc content.
local m=manager.machine
local sp=m.devices[':maincpu'].spaces.program
local HIRQ,CR1,CR2,CR3,CR4=0x05890008,0x05890018,0x0589001c,0x05890020,0x05890024
local function cmd(a,b,c,d)
 sp:write_u16(HIRQ,0xffbe)
 sp:write_u16(CR1,a);sp:write_u16(CR2,b);sp:write_u16(CR3,c);sp:write_u16(CR4,d)
 for i=1,100 do
  emu.wait(emu.attotime.from_msec(1))
  if (sp:read_u16(HIRQ)&1)~=0 then
   return {sp:read_u16(CR1),sp:read_u16(CR2),sp:read_u16(CR3),sp:read_u16(CR4)},sp:read_u16(HIRQ)
  end
 end
 error('CD command timeout')
end
local function test()
 for _,tag in ipairs({':maincpu',':slave'}) do m.devices[tag].state.SR.value=0xf0;m.devices[tag].state.PC.value=0x06000000 end
 sp:write_u32(0x06000000,0xaffe0009)
 cmd(0x4012,0x3456,0x170a,0xbcde)
 local r,h=cmd(0x4100,0,0x1700,0)
 assert((r[1]&255)==0x12 and r[2]==0x3456 and r[3]==0x170a and r[4]==0xbcde and (h&0x40)==0,'range readback/flags')
 cmd(0x4603,0x05ff,0x1700,0);cmd(0x4480,0,0x1700,0)
 r,h=cmd(0x4700,0,0x1700,0)
 assert(r[2]==0x05ff and r[3]==0x1700 and r[4]==0 and (h&0x40)==0,'connection dispatch/readback/reset')
 for _,opcode in ipairs({0x30,0x40,0x41,0x42,0x43,0x44,0x45,0x46,0x47,0x54}) do
  r,h=cmd(opcode<<8,0,0x1800,0)
  assert((r[1]&0xff00)==0xff00 and (h&0x40)==0,'invalid selector '..opcode)
 end
 print('SATURN_CD_SELECTOR_RUNTIME_PASS')
 m:exit()
end
local co=coroutine.create(test)
local ok,err=coroutine.resume(co);if not ok then error(err) end
