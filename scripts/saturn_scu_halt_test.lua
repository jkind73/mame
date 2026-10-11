-- license:BSD-3-Clause
-- Direct C-bus DMA must release the SH-2 after its final beat.
local m=manager.machine
local cpu=m.devices[':maincpu'];local mem=cpu.spaces.program
local frame,stage,last=0,0,0
halt_release_subscription=emu.add_machine_frame_notifier(function()
 frame=frame+1
 local ok,err=pcall(function()
  if frame==1 then
   mem:write_u32(0x05fe00a0,0xffffffff)
   mem:write_u16(0x06008000,0x7701);mem:write_u16(0x06008002,0xaffd);mem:write_u16(0x06008004,0x0009)
   cpu.state.SR.value=0xf0;cpu.state.R7.value=0;cpu.state.CURPC.value=0x06008000
  elseif frame==2 then
   assert(cpu.state.R7.value>0,'counter guest did not run')
   mem:write_u32(0x05fe0000,0x06004000);mem:write_u32(0x05fe0004,0x05e00000)
   mem:write_u32(0x05fe0008,256);mem:write_u32(0x05fe000c,0x101)
   mem:write_u32(0x05fe0014,7);mem:write_u32(0x05fe0010,0x101)
  elseif frame==3 then
   assert(mem:read_u32(0x05fe007c)&0x30==0,'DMA still busy')
   last=cpu.state.R7.value
  elseif frame==4 then
   assert(cpu.state.R7.value>last,'CPU remained halted after C-bus DMA')
   -- A-to-B DMA leaves the CPUs running, but a B-bus mailbox write must wait.
   mem:write_u16(0x06009000,0x2101);mem:write_u16(0x06009002,0xaffe);mem:write_u16(0x06009004,0x0009)
   cpu.state.R0.value=0x55aa;cpu.state.R1.value=0x05a00000;cpu.state.CURPC.value=0x06009000
   mem:write_u32(0x05fe0000,0x02000000);mem:write_u32(0x05fe0004,0x05a00000)
   mem:write_u32(0x05fe0008,1024);mem:write_u32(0x05fe000c,0x101)
   mem:write_u32(0x05fe0014,7);mem:write_u32(0x05fe0010,0x101)
  elseif frame==5 then
   assert(mem:read_u32(0x05fe007c)&0x30==0,'A-to-B DMA still busy')
   assert(mem:read_u16(0x05a00000)==0x55aa,'DMA overwrote the master mailbox write')
   -- With caching enabled, a guest must poll SCU registers through the uncached alias.
   mem:write_u16(0x0600a000,0x6012);mem:write_u16(0x0600a002,0xc830)
   mem:write_u16(0x0600a004,0x8bfc);mem:write_u16(0x0600a006,0x7701)
   mem:write_u16(0x0600a008,0xaffe);mem:write_u16(0x0600a00a,0x0009)
   mem:write_u8(0xfffffe92,0x11)
   cpu.state.R7.value=0;cpu.state.R1.value=0x25fe007c;cpu.state.CURPC.value=0x0600a000
   mem:write_u32(0x05fe0000,0x06004000);mem:write_u32(0x05fe0004,0x05e00000)
   mem:write_u32(0x05fe0008,256);mem:write_u32(0x05fe000c,0x101)
   mem:write_u32(0x05fe0014,7);mem:write_u32(0x05fe0010,0x101)
  elseif frame==6 then
   assert(cpu.state.R7.value==1,'uncached SCU completion poll did not exit')
   print('SCU_HALT_RELEASE_PASS C-bus release, A-to-B mailbox ordering, uncached polling');m:exit()
  end
 end)
 if not ok then print('SCU_HALT_RELEASE_FAIL '..tostring(err));m:exit()end
end)
