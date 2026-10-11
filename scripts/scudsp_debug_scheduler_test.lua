-- license:BSD-3-Clause
-- Exercise debugger breakpoints/stepping during scheduled DSP execution.
local m=manager.machine
local mem=m.devices[':maincpu'].spaces.program
local dsp=m.devices[':scu:scudsp']
local dbg=assert(m.debugger)
local function upload(words)
 mem:write_u32(0x05fe0080,0x8000)
 for _,word in ipairs(words)do mem:write_u32(0x05fe0084,word)end
 mem:write_u32(0x05fe0080,0x8000)
end
local function run()
 dbg.visible_cpu=dsp
 dbg:command('temp0=0')
 -- LPS executes the move 100 times, each at the same debugger address.
 upload({0xa8000063,0xe8000000,0x00001007,0xf0000000})
 dsp.state.CT0.value=0
 local bp=dsp.debug:bpset(2,nil,'temp0=temp0+1;go')
 mem:write_u32(0x05fe0080,0x18000)
 emu.wait(0.001)
 assert(dsp.state.PC.value==4 and dsp.state.CT0.value==36,'breakpoint loop changed execution')
 dsp.debug:bpclear(bp)
 dbg:command('printf "DSP_BREAK_COUNT=%d",temp0')
 local count=false
 for i=1,#dbg.consolelog do
  local line=dbg.consolelog[i]
  if line and line:match('^DSP_BREAK_COUNT=100%s*$')then count=true end
 end
 assert(count,'debugger did not observe all 100 repeated instructions')
 -- DMA waits must not repeatedly expose the blocked instruction to breakpoints.
 for i=0,31 do mem:write_u32(0x06004000+4*i,0x12340000+i)end
 upload({0x99801000,0xc0010020,0x00003500,0xf0000000})
 dsp.state.CT0.value=0
 dbg:command('temp0=0')
 bp=dsp.debug:bpset(2,nil,'temp0=temp0+1;go')
 mem:write_u32(0x05fe0080,0x18000)
 emu.wait(0.001)
 assert(dsp.state.PC.value==4 and dsp.state.CT0.value==32,string.format('debugger DMA wait did not finish PC=%x CT0=%x SR=%x',dsp.state.PC.value,dsp.state.CT0.value,dsp.state.SR.value))
 dsp.debug:bpclear(bp)
 dbg:command('printf "DSP_DMA_BREAK_COUNT=%d",temp0')
 count=false
 for i=1,#dbg.consolelog do
  local line=dbg.consolelog[i]
  if line and line:match('^DSP_DMA_BREAK_COUNT=1%s*$')then count=true end
 end
 assert(count,'blocked instruction caused spurious debugger breakpoint hits')
 print('SCUDSP_DEBUG_SCHEDULER_PASS scheduled loop and DMA breakpoint counts')
end
scudsp_debug_thread=coroutine.create(function()
 local ok,err=pcall(run)
 if not ok then print('SCUDSP_DEBUG_SCHEDULER_FAIL '..tostring(err))end
 m:exit()
end)
local ok,err=coroutine.resume(scudsp_debug_thread)
if not ok then print('SCUDSP_DEBUG_SCHEDULER_FAIL '..tostring(err));m:exit()end
