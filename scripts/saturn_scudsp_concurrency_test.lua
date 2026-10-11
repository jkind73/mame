-- license:BSD-3-Clause
-- Exercise real DSP instruction execution while another SCU DMA owns the bus.
local m=manager.machine
local mem=m.devices[':maincpu'].spaces.program
local dsp=m.devices[':scu:scudsp']
local frame=0
local queued_writes=0
local priority_tap=mem:install_write_tap(0x05c10000,0x05c100ff,'dsp priority',function(offset,data,mask)
 queued_writes=queued_writes+1
 assert(dsp.state.SR.value&0x800000==0,'ordinary queued channel ran before DSP acknowledgement')
end)
local function start(conflict)
 mem:write_u32(0x05fe0080,0x8000)
 -- RA0, DMA32 to MC0, independent RX write, false conditional MC0 write,
 -- then either a conflicting MC0 write or a T0 polling loop (with delay NOP).
 local program={0x99801000,0xc0010020,0x90000001,0x83080001}
 if conflict then
  program[#program+1]=0x80000077
  program[#program+1]=0xf8000000
 else
  program[#program+1]=0xd1400004
  program[#program+1]=0x00000000
  program[#program+1]=0xf8000000
 end
 for _,op in ipairs(program)do mem:write_u32(0x05fe0084,op)end
 dsp.state.RX.value=0;dsp.state.CT0.value=0
 for i=0,31 do mem:write_u32(0x06004000+4*i,0x12340000+i)end
 mem:write_u32(0x05fe0000,0x02000000);mem:write_u32(0x05fe0004,0x05a00000)
 mem:write_u32(0x05fe0008,0x40000);mem:write_u32(0x05fe000c,0x101)
 mem:write_u32(0x05fe0014,7);mem:write_u32(0x05fe0010,0x101)
end
local function waiting(conflict)
 local status=mem:read_u32(0x05fe007c)
 print(string.format('DSP PC=%x SR=%x RX=%x CT=%x',dsp.state.PC.value,dsp.state.SR.value,dsp.state.RX.value,dsp.state.CT0.value))
 assert(status&3==2,string.format('DSP preempted owner: %08x',status))
 assert(dsp.state.RX.value==1,'independent instruction did not execute')
 assert(dsp.state.CT0.value==0,'DMA used RAM before grant')
 assert(dsp.state.SR.value&0x800000~=0,'T0 cleared before acknowledgement')
 if conflict then assert(dsp.state.PC.value==4,'conflicting instruction was not held')end
end
local function completed(conflict)
 assert(mem:read_u32(0x05fe007c)&0x33==0,'DMA did not finish')
 assert(dsp.state.SR.value&0x810000==0,'DSP did not end after DMA')
 mem:write_u32(0x05fe0088,0)
 for i=0,31 do
  local expected=0x12340000+i
  assert(mem:read_u32(0x05fe008c)==expected,'DSP payload differs at '..i)
 end
 if conflict then assert(mem:read_u32(0x05fe008c)==0x77,'conflicting write did not resume after DMA')end
end
dsp_concurrency_subscription=emu.add_machine_frame_notifier(function()
 frame=frame+1
 local ok,err=pcall(function()
  if frame==1 then start(false)
  elseif frame==2 then mem:write_u32(0x05fe0080,0x18000)
  elseif frame==3 then waiting(false)
  elseif frame==8 then completed(false);start(true)
  elseif frame==9 then mem:write_u32(0x05fe0080,0x18000)
  elseif frame==10 then waiting(true)
  elseif frame==16 then completed(true);start(false)
  elseif frame==17 then
   mem:write_u32(0x05fe0080,0x18000)
   mem:write_u32(0x05fe0020,0x02000000);mem:write_u32(0x05fe0024,0x05c10000)
   mem:write_u32(0x05fe0028,256);mem:write_u32(0x05fe002c,0x101)
   mem:write_u32(0x05fe0034,7);mem:write_u32(0x05fe0030,0x101)
  elseif frame==18 then waiting(false)
  elseif frame==24 then completed(false);assert(queued_writes==128,'queued channel did not resume');print('DSP_CONCURRENCY_PASS grant, independent execution, conditional write, RAM conflict, payload, queued priority');m:exit()end
 end)
 if not ok then print('DSP_CONCURRENCY_FAIL '..tostring(err));m:exit()end
end)
