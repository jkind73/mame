-- license:BSD-3-Clause
-- Native debugger stops and single steps, driven by wall-clock Lua callbacks.
local m=manager.machine
local dsp=m.devices[':scu:scudsp']
local mem=m.devices[':maincpu'].spaces.program
local dbg=assert(m.debugger)
local phase=0
local bp
local function finish(ok,err)
 print(ok and 'SCUDSP_DEBUG_STEP_PASS breakpoint, branch delay and single-step scheduling' or 'SCUDSP_DEBUG_STEP_FAIL '..tostring(err))
 dbg.execution_state='run'
 m:exit()
 phase=99
end
emu.register_periodic(function()
 if phase==99 then return end
 local ok,err=pcall(function()
  if phase==0 then
   mem:write_u32(0x05fe0080,0x8000)
   for _,word in ipairs({0x90000011,0xd0000007,0x9000002a,0,0,0,0,0x90000055,0xf0000000})do mem:write_u32(0x05fe0084,word)end
   mem:write_u32(0x05fe0080,0x8000)
   dsp.state.RX.value=0
   dbg.visible_cpu=dsp
   bp=dsp.debug:bpset(0)
   phase=1
   mem:write_u32(0x05fe0080,0x18000)
   dbg.execution_state='run'
  elseif dbg.execution_state=='stop' and dbg.visible_cpu==dsp then
   local expected_pc=({0,1,2,7,8})[phase]
   local expected_rx=({0,17,17,42,85})[phase]
   assert(dsp.state.CURPC.value==expected_pc,string.format('phase %d stopped at %x expected %x',phase,dsp.state.CURPC.value,expected_pc))
   assert(dsp.state.RX.value==expected_rx,'single-step data differs')
   if phase==1 then dsp.debug:bpclear(bp)end
   if phase==5 then finish(true)else phase=phase+1;dsp.debug:step(1)end
  end
 end)
 if not ok then finish(false,err)end
end)
