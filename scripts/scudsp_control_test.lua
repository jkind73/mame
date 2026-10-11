-- license:BSD-3-Clause
-- Real DSP control ports, instruction stepping and address-wrap delay slots.
local m=manager.machine
local mem=m.devices[':maincpu'].spaces.program
local dsp=m.devices[':scu:scudsp']
local function control(v)mem:write_u32(0x05fe0080,v)end
local function upload(address,words)
 control(0x8000|address)
 for _,v in ipairs(words)do mem:write_u32(0x05fe0084,v)end
 control(0x8000|address)
end
local function step()control(0x20000)end
local function run()
 if m.debugger then m.debugger:command("trace dsp.trace,:scu:scudsp,noloop")end
 upload(255,{0xd0000007,0x9000002a})
 upload(7,{0x90000055,0xf8000000})
 control(0x80ff);dsp.state.RX.value=0
 step();assert(dsp.state.PC.value==7,'wrapped jump target wrong')
 step();assert(dsp.state.RX.value==42 and dsp.state.PC.value==7 and dsp.state.CURPC.value==0,'wrapped delay slot/debugger PC lost')
 step();assert(dsp.state.RX.value==85,'target did not execute after delay slot')
 upload(0,{0xa9ffffff});step();assert(dsp.state.LOP.value==0xfff,'LOP width wrong')
 -- X, Y and D1 read the same word and increment CT only once.
 mem:write_u32(0x05fe0088,0);mem:write_u32(0x05fe008c,3);mem:write_u32(0x05fe008c,11)
 upload(0,{0x02493504});dsp.state.CT0.value=0;step()
 assert(dsp.state.RX.value==3 and dsp.state.RY.value==3 and dsp.state.PL.value==3 and dsp.state.CT0.value==1,'parallel bank reads differ')
 -- LPS repeats its following move exactly LOP+1 times.
 upload(0,{0xe8000000,0x00001007});dsp.state.LOP.value=2;dsp.state.CT0.value=0
 for i=1,4 do step()end
 assert(dsp.state.CT0.value==3 and dsp.state.PC.value==2 and dsp.state.LOP.value==0,'LPS repeated wrong instruction/count')
 upload(0,{0xe8000000,0x00001007});dsp.state.LOP.value=2;dsp.state.CT0.value=0;step()
 local state=m.options.entries['state_directory']:value()..'/lps.sta'
 m:save(state);emu.wait(0.02)
 for i=1,3 do step()end
 m:load(state);if not emu.wait(0.02)then emu.wait(0.02)end
 assert(dsp.state.CT0.value==0 and dsp.state.LOP.value==2,'active LPS state was not restored')
 for i=1,3 do step()end
 assert(dsp.state.CT0.value==3 and dsp.state.PC.value==2,'restored LPS did not finish')
 -- Pause while stopped must not inhibit the next EX start.
 upload(0,{0x90000066,0xf8000000});control(0x2000000);control(0x18000)
 emu.wait(0.00001)
 assert(dsp.state.RX.value==102 and dsp.state.SR.value&0x10000==0,'stopped EP inhibited EX')
 -- Full-width EP/PR writes must preserve EX, not stop the running program.
 upload(0,{0xd0000000,0x90000011})
 control(0x18000);emu.wait(0.00001)
 control(0x2000000)
 assert(dsp.state.SR.value&0x10000~=0,'pause write cleared EX')
 assert(mem:read_u32(0x05fe0080)&0x10000==0,'paused DSP reports itself as running')
 local paused_pc=dsp.state.PC.value
 emu.wait(0.00001)
 assert(dsp.state.PC.value==paused_pc,'paused program advanced')
 dsp.state.RX.value=0;control(0x4000000);emu.wait(0.00001)
 assert(dsp.state.SR.value&0x10000~=0 and dsp.state.RX.value==17,'resume write stopped execution')
 control(0)
 upload(0,{0x90000077});control(0x18000)
 -- A stop+ES write is not a stopped-program step; only the next ES can step.
 control(0x20000)
 assert(dsp.state.PC.value==0,'ES executed while stopping a running program')
 control(0x20000)
 assert(dsp.state.PC.value==1 and dsp.state.RX.value==119,'stopped ES failed')
 assert(mem:read_u32(0x05fe0080)&0xff==1,'control port reports PC one instruction too far')
 upload(255,{0xf8000000});step()
 local status=mem:read_u32(0x05fe0080)
 assert(status&0xff==0 and status&0x40000~=0,'END address wrap or end flag wrong')
 assert(mem:read_u32(0x05fe0080)&0x40000==0,'end flag was not cleared by read')
 -- END and a new EX start must leave an independent DMA running.
 for i=0,31 do mem:write_u32(0x06004000+4*i,0x12340000+i)end
 upload(0,{0x99801000,0xc0010020,0xf0000000,0x90000055,0xf0000000})
 dsp.state.CT0.value=0;control(0x18000);emu.wait(0.000001)
 assert(dsp.state.SR.value&0x810000==0x800000,'END did not leave DMA running')
 control(0x10000);emu.wait(0.00005)
 assert(dsp.state.RX.value==85 and dsp.state.SR.value&0x810000==0 and dsp.state.CT0.value==32,'EX restart canceled independent DMA')
 -- Signed MVI and every documented condition with all four flag combinations.
 for flags=0,15 do
  for _,mask in ipairs({1,2,3,4,8})do
   for _,positive in ipairs({0,32})do
    local condition=mask|positive
    local expected=positive~=0 and flags&mask~=0 or positive==0 and flags&mask==0
    upload(0,{0x9207ffff|(condition<<19)})
    dsp.state.SR.value=((flags&1)<<21)|(((flags>>1)&1)<<22)|(((flags>>2)&1)<<20)|(((flags>>3)&1)<<23)
    dsp.state.RX.value=0;step()
    assert(dsp.state.RX.value==(expected and 0xffffffff or 0),'conditional MVI differs')
   end
  end
 end
 if m.debugger then
  m.debugger:command("trace off,:scu:scudsp")
  local file=assert(io.open('dsp.trace','r'));local trace=file:read('*a');file:close()
  assert(trace:find('FF:') and trace:find('00:'),'DSP debugger did not trace wrapped branch/delay slot')
 end
 print('SCUDSP_CONTROL_PASS wrap delay, signed conditional MVI matrix, LOP width, stopped pause')
end
scudsp_control_thread=coroutine.create(function()
 local ok,err=pcall(run)
 if not ok then print('SCUDSP_CONTROL_FAIL '..tostring(err))end
 m:exit()
end)
local ok,err=coroutine.resume(scudsp_control_thread)
if not ok then print('SCUDSP_CONTROL_FAIL '..tostring(err));m:exit()end
