-- license:BSD-3-Clause
-- Real SYSRES command must reset connected devices and retain battery storage.
if SATURN_SYSTEM_RESET_ACTIVE then return end
SATURN_SYSTEM_RESET_ACTIVE=true
local m=manager.machine;local cpu=m.devices[':maincpu'];local h=cpu.spaces.program
local phase=0;local started=0;local rounds=0
local memory={0x00201000,0x06001000,0x05a01000,0x05c01000,0x05c81000,0x05e01000,0x05f01000}
local function start_command(code)
 h:write_u8(0x00100063,1);h:write_u8(0x0010001f,code)
end
emu.register_frame_done(function()
 local ok,e=pcall(function()
  if phase==0 then
   for i,v in ipairs({0x11,0x22,0x33,0x44})do h:write_u8(0x00100001+2*(i-1),v)end
   start_command(0x17);h:write_u8(0x00180001,0x5a);phase=1
  elseif phase==1 then
   assert((h:read_u8(0x00100063)&1)==0,'SETSMEM not finished')
   -- Run the real clock-change sequence first, with a safe NMI return.
   h:write_u32(0x0600802c,0x06008100)
   h:write_u16(0x06008100,0x002b);h:write_u16(0x06008102,9)
   cpu.state.VBR.value=0x06008000;cpu.state.R15.value=0x2600b000
   start_command(0x0e);phase=4
  elseif phase==4 and (h:read_u8(0x00100063)&1)==0 then
   for _,a in ipairs(memory)do h:write_u32(a,0x11223344)end
   h:write_u16(0x05f80000,0x81e3);h:write_u16(0x05f80002,0x303)
   h:write_u16(0x05b00008,0x1234)
   h:write_u16(0x0589000c,0x0fff)
   h:write_u32(0x05fe00a0,0x0123)
   h:write_u16(0x06008000,0xaffe);h:write_u16(0x06008002,9)
   cpu.state.CURPC.value=0x06008000
   started=m.time:as_double();start_command(0x0d);phase=2
  elseif phase==2 and m.time:as_double()-started>0.13 then
   assert(h:read_u8(0x0010005f)==0x0d,'SYSRES result lost during board reset')
   assert(h:read_u16(0x05b00008)==0,'SCSP registers not reset')
   assert(h:read_u16(0x0589000c)==0,'CD block interrupt mask not reset')
   assert(h:read_u16(0x05f80000)==0 and h:read_u16(0x05f80002)==0,'VDP2 not reset')
   local expected=8/math.floor(14318181*1708/455)
   assert(math.abs(m.screens[':screen'].pixel_period-expected)<1e-12,'reset retained 352-mode oscillator')
   assert(h:read_u32(0x05fe00a0)==0xbfff,'SCU not reset')
   for _,a in ipairs(memory)do assert(h:read_u32(a)==0,string.format('volatile memory retained at %08x',a))end
   assert(h:read_u8(0x00180001)==0x5a,'battery backup RAM cleared')
   assert(cpu.state.PC.value>=0x100 and cpu.state.PC.value<=0x104,'master did not restart at power-on vector')
   h:write_u8(0x00100001,1);h:write_u8(0x00100003,0);start_command(0x10);phase=3
  elseif phase==3 then
   for i,v in ipairs({0x11,0x22,0x33,0x44})do assert(h:read_u8(0x00100039+2*(i-1))==v,'SMPC battery settings cleared')end
   rounds=rounds+1
   if rounds==2 then print('SATURN_SYSTEM_RESET_PASS repeated SYSRES, power-on vector, SCU/SCSP/VDP2/CD and volatile/battery memory');m:exit()
   else phase=1 end
  end
 end)
 if not ok then print('SATURN_SYSTEM_RESET_FAIL '..tostring(e));m:exit()end
end)
