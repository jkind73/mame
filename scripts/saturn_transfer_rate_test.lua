-- license:BSD-3-Clause
-- Real guest loops/DMAC/SCU-DMA; time a completion marker using machine time.
local m=manager.machine
local cpu=m.devices[':maincpu']
local mem=cpu.spaces.program
local frame,case=0,0
local start,finish,active=0,0,false
local marker=0x05fe0090 -- device port: DRC fast RAM bypasses Lua write taps
local tap=mem:install_write_tap(marker,marker+3,'rate-completion',function(a,d,mask)
 if active and case<6 then finish=m.time:as_double();active=false end
end)
local payload_taps={}
for i,dest in ipairs({0x05c00000,0x05e00000,0x05a00000}) do
 payload_taps[i]=mem:install_write_tap(dest+252,dest+255,'scu-last-word-'..i,function(a,d,mask)
  if active and case>=6 and case%3==i-1 and mask~=0 then
   finish=m.time:as_double();active=false
  end
 end)
end
local function setup()
 local kind=math.floor(case/3)
 local dests={0x05c00000,0x05e00000,0x05a00000}
 local dest=dests[case%3+1]
 local code=0x06002000+case*0x100
 cpu.state.SR.value=0xf0
 mem:write_u32(0x05fe00a0,0xffffffff)
 mem:write_u8(0xfffffe92,0x11) -- enable CPU cache for the guest loop
 for i=0,63 do mem:write_u32(0x06004000+i*4,0x12340000+i) end
 mem:write_u16(0x05f80000,0) -- blank VDP2; VDP1 drawing and 68000/DSP stay stopped
 cpu.state.R4.value=1;cpu.state.R5.value=marker
 if kind==0 then
  local words={0x6016,0x2202,0x7204,0x4310,0x8bfa,0x2542,0xaffe,0x0009}
  for i,v in ipairs(words)do mem:write_u16(code+(i-1)*2,v)end
  cpu.state.R1.value=0x06004000;cpu.state.R2.value=dest;cpu.state.R3.value=64
 else
  local words={0x6012,0xc802,0x89fc,0x2542,0xaffe,0x0009}
  if kind==2 then -- while SCU owns C-bus the guest is halted; after release emit marker
   words={0xaffe,0x0009} -- park; SCU completion is captured at its final payload write
  end
  for i,v in ipairs(words)do mem:write_u16(code+(i-1)*2,v)end
  cpu.state.R1.value=kind==2 and 0x05fe007c or 0xffffff8c
 end
 cpu.state.CURPC.value=code
 start=m.time:as_double();finish=0;active=true
 if kind==1 then
  mem:write_u32(0xffffffb0,0)
  mem:write_u32(0xffffff80,0x06004000)
  mem:write_u32(0xffffff84,dest)
  mem:write_u32(0xffffff88,64)
  mem:write_u32(0xffffff8c,0x5e01)
  mem:write_u32(0xffffffb0,1)
 elseif kind==2 then
  mem:write_u32(0x05fe0000,0x06004000)
  mem:write_u32(0x05fe0004,dest)
  mem:write_u32(0x05fe0008,256)
  mem:write_u32(0x05fe000c,0x101)
  mem:write_u32(0x05fe0014,7)
  mem:write_u32(0x05fe0010,0x101)
 end
end
rate_subscription=emu.add_machine_frame_notifier(function()
 frame=frame+1
 local ok,err=pcall(function()
  if frame==1 then setup() end
  if frame>1 and not active then
   assert(finish>start,'no positive transfer interval')
   local dest=({0x05c00000,0x05e00000,0x05a00000})[case%3+1]
   for i=0,63 do assert(mem:read_u32(dest+i*4)==0x12340000+i,'transfer payload mismatch') end
   if case>=6 then assert(mem:read_u32(0x05fe007c)&0x30==0,'SCU did not release DMA') end
   print(string.format('TRANSFER_RATE kind=%d dest=%d clocks_per_4B=%.4f',math.floor(case/3),case%3,(finish-start)*(14318181*1708/455/2)/64))
   case=case+1
   if case==9 then print('TRANSFER_RATE_PASS');m:exit()else setup()end
  end
  assert(frame<180,string.format('transfer timed out case=%d PC=%08x SCU=%08x',case,cpu.state.CURPC.value,mem:read_u32(0x05fe007c)))
 end)
 if not ok then print('TRANSFER_RATE_FAIL '..tostring(err));m:exit()end
end)
