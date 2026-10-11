-- license:BSD-3-Clause
-- Real SCU: zero counts wrap to 1 MiB at every indirect level; EC alone ends the chain.
local m=manager.machine
local cpu=m.devices[':maincpu']
local mem=cpu.spaces.program
local frame,case=0,0
local writes=0
local tap=mem:install_write_tap(0x05f00000,0x05f00003,'indirect-count',function(a,d,mask)
 if mask==0xffff0000 or mask==0x0000ffff then writes=writes+1 end
end)
local function start()
 local level=case%3
 local terminal=case<3 or case>=6
 writes=0
 mem:write_u32(0x06004000,0x11223344)
 mem:write_u32(0x06003000,case>=6 and case<9 and 0x40004 or 0)
 mem:write_u32(0x06003004,case>=9 and 0 or 0x05f00000)
 mem:write_u32(0x06003008,case>=9 and 0 or (0x06004000 | (terminal and 0x80000000 or 0)))
 mem:write_u32(0x0600300c,4)
 mem:write_u32(0x06003010,0x05f00010)
 mem:write_u32(0x06003014,0x86004000)
 mem:write_u32(0x05fe00a0,0xffffffff)
 mem:write_u32(0x05fe0004+level*0x20,0x06003000)
 mem:write_u32(0x05fe000c+level*0x20,0x00000100) -- read advances, fixed destination
 mem:write_u32(0x05fe0014+level*0x20,0x01000007)
 mem:write_u32(0x05fe0010+level*0x20,0x00000101)
end
scu_indirect_subscription=emu.add_machine_frame_notifier(function()
 frame=frame+1
 local ok,err=pcall(function()
  if frame==1 then cpu.state.SR.value=0xf0;start() end
  if frame>1 and mem:read_u32(0x05fe007c)&0x3330==0 then
   if case>=9 then
    assert(writes==0,'illegal descriptor moved data')
    assert(mem:read_u32(0x05fe00a4)&0x1000~=0,'illegal descriptor did not raise DMA illegal')
   else
   assert(writes==(case>=6 and 0x20002 or 0x80000),string.format('case %d: zero count transferred %d halfwords',case,writes))
   if case>=3 and case<6 then assert(mem:read_u16(0x05f00010)==0x3344,'next descriptor was not executed') end
   end
   print(string.format('SCU_INDIRECT_CASE_PASS level=%d terminal=%s words=%d',case%3,tostring(case<3 or case>=6),writes))
   case=case+1
   if case==12 then print('SCU_INDIRECT_PASS');m:exit() else start() end
  end
  assert(frame<300,'indirect chain failed to finish')
 end)
 if not ok then print('SCU_INDIRECT_FAIL '..tostring(err));m:exit() end
end)
