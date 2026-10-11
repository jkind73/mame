-- license:BSD-3-Clause
-- Real-device SCSP DMA phases and free-running sample interrupts.
local m=manager.machine
local mem=m.devices[':maincpu'].spaces.program
local function r(a)return mem:read_u16(0x05b00000+a)end
local function w(a,v)mem:write_u16(0x05b00000+a,v)end
local function start(address,reg,bytes,flags)
 w(0x412,address&0xfffe);w(0x414,((address>>4)&0xf000)|reg);w(0x416,flags|0x1000|bytes)
end
local function run()
 w(0x41e,0);w(0x42a,0);w(0x422,0x7ff);w(0x42e,0x7ff)
 -- Detect an edge while disabled, then measure the next sample interval.
 local clock=22579200
 local tick=1/clock;local fs=512*tick
 while r(0x420)&0x400==0 do emu.wait(tick)end
 assert(r(0x42c)&0x400~=0,'disabled main pending missing')
 w(0x422,0x400);assert(r(0x420)&0x400==0 and r(0x42c)&0x400~=0,'pending latches not independent')
 w(0x42e,0x400)
 emu.wait(fs*0.4);w(0x41e,0x400);w(0x42a,0x400)
 emu.wait(fs*0.5);assert(r(0x420)&0x400==0,'enable restarted/advanced sample phase')
 emu.wait(fs*0.11);assert(r(0x420)&0x400~=0 and r(0x42c)&0x400~=0,'1Fs edge missing or phase restarted')
 w(0x41e,0);w(0x42a,0)
 for direction=0,1 do
  for gate=0,1 do
   for i=0,15 do
    mem:write_u16(0x05a10000+2*i,direction==0 and (0x2300+8*i) or 0xa5a5)
    w(0x700+2*i,direction==1 and (0x3400+8*i) or 0x5a5a)
   end
   w(0x422,0x10);w(0x42e,0x10)
   start(0x10000,0x700,32,(direction<<13)|(gate<<14))
   assert(r(0x416)&0x1000~=0,'DEXE completed synchronously')
   assert(r(0x420)&0x10==0 and r(0x42c)&0x10==0,'premature DMA IRQ')
   -- CPU parameter writes/DEXE=0 cannot interrupt an active transfer.
   w(0x412,0x2222);w(0x416,0)
   assert(r(0x412)==0 and r(0x416)&0x1000~=0,'active parameters modified or DMA aborted')
   emu.wait(tick*2)
   assert(r(0x416)&0x1000~=0,'DMA did not consume bus phases')
   emu.wait(0.00003)
   assert(r(0x416)&0x1000==0,'DMA stuck busy')
   assert(r(0x420)&0x10~=0 and r(0x42c)&0x10~=0,'DMA completion pending missing')
   for i=0,15 do
    local ram=mem:read_u16(0x05a10000+2*i);local reg=r(0x700+2*i)
    local payload=gate==1 and 0 or ((direction==0 and 0x2300 or 0x3400)+8*i)
    assert((direction==0 and reg or ram)==payload,'DMA payload differs')
    assert((direction==0 and ram or reg)==((direction==0 and 0x2300 or 0x3400)+8*i),'DMA disturbed source')
   end
  end
 end
 -- Reasserting DEXE reloads the unchanged programmed addresses and count.
 start(0x10000,0x700,32,0)
 emu.wait(0.00003)
 assert(r(0x412)==0 and r(0x414)==0x1700 and r(0x416)==32,'DMA parameter read-back changed')
 for i=0,15 do mem:write_u16(0x05a10000+2*i,0x4500+8*i);w(0x700+2*i,0)end
 w(0x416,r(0x416)|0x1000)
 emu.wait(0.00003)
 for i=0,15 do assert(r(0x700+2*i)==0x4500+8*i,'repeated DMA did not reload parameters')end
 -- A register-directed transfer crossing the controller cannot rewrite itself.
 start(0x10000,0x400,0x18,0x4000);emu.wait(0.00003)
 assert(r(0x414)==0x1400 and r(0x416)==0x4018,'DMA changed its own parameters')
 -- A real 68000 register-reading loop must progress and pay contention waits.
 local audio=m.devices[':audiocpu']
 mem:write_u32(0x05a00000,0x00008000);mem:write_u32(0x05a00004,0x00000200)
 for i,op in ipairs({0x3210,0x5280,0x60fa})do mem:write_u16(0x05a001fe+i*2,op)end
 mem:write_u8(0x0010001f,0x06);emu.wait(0.0001)
 audio.state.SR.value=0x2700;audio.state.A0.value=0x100700;audio.state.D0.value=0;audio.state.CURPC.value=0x200
 emu.wait(0.0002);local baseline=audio.state.D0.value
 assert(baseline>0,'68000 diagnostic did not run')
 audio.state.D0.value=0
 start(0x30000,0x700,0x7e4,0x2000);emu.wait(0.0002)
 local contended=audio.state.D0.value
 print(string.format('68000 register loop baseline=%d contended=%d',baseline,contended))
 assert(contended>0 and contended<baseline,'68000 did not pay DMA waits or was held unnecessarily')
 emu.wait(0.0003)
 -- The SH-2 bus timing path must also see internal SCSP DMA contention.
 local cpu=m.devices[':maincpu']
 for i,op in ipairs({0x6011,0x7701,0xaffc,0x0009})do mem:write_u16(0x06007ffe+i*2,op)end
 cpu.state.SR.value=0xf0;cpu.state.R1.value=0x25a30000;cpu.state.R7.value=0;cpu.state.CURPC.value=0x06008000
 local sh_baseline,sh_contended=0,0
 for trial=1,16 do
  cpu.state.R7.value=0
  emu.wait(0.0002);sh_baseline=sh_baseline+cpu.state.R7.value
  cpu.state.R7.value=0
  start(0x30000,0x700,0x7e4,0x2000);emu.wait(0.0002)
  sh_contended=sh_contended+cpu.state.R7.value
  assert(r(0x416)&0x1000~=0,'contention benchmark DMA finished early')
  emu.wait(0.0003+tick*(trial%4))
 end
 print(string.format('SH-2 sound RAM loop baseline=%d contended=%d',sh_baseline,sh_contended))
 assert(sh_contended>0 and sh_contended<sh_baseline,'SH-2 did not pay SCSP DMA waits')
 -- Check actual 1Fs autovector delivery through the shared bit-7 level controls.
 mem:write_u32(0x05a0006c,0x300)
 for i,op in ipairs({0x5283,0x33fc,0x0400,0x0010,0x0422,0x4e73})do mem:write_u16(0x05a002fe+i*2,op)end
 audio.state.D3.value=0;audio.state.SR.value=0x2000
 w(0x424,0x80);w(0x426,0x80);w(0x428,0);w(0x41e,0x400)
 emu.wait(0.0001)
 assert(audio.state.D3.value>=3,'1Fs sound CPU interrupt did not recur')
 w(0x41e,0);audio.state.SR.value=0x2700
 -- DMA-end level bits route to the real 68000 autovector and clear on SCIRE.
 mem:write_u32(0x05a00070,0x340)
 for i,op in ipairs({0x5284,0x33fc,0x0010,0x0010,0x0422,0x4e73})do mem:write_u16(0x05a0033e+i*2,op)end
 audio.state.D4.value=0;audio.state.SR.value=0x2000
 w(0x424,0);w(0x426,0);w(0x428,0x10);w(0x422,0x10);w(0x41e,0x10)
 start(0x10000,0x700,32,0)
 emu.wait(0.00005)
 assert(audio.state.D4.value==1 and r(0x420)&0x10==0,'DMA-end level-4 interrupt routing/clear failed')
 w(0x41e,0);audio.state.SR.value=0x2700
 -- Start in the pre-save callback so the file genuinely contains an active transfer.
 local state=os.getenv('SCSP_DMA_STATE')
 local saved_busy,loaded_busy=false,false
 local pre=emu.add_machine_pre_save_notifier(function()
  start(0x20000,0x700,256,0x6000)
  saved_busy=r(0x416)&0x1000~=0
 end)
 local post=emu.add_machine_post_load_notifier(function()loaded_busy=r(0x416)&0x1000~=0 end)
 m:save(state);emu.wait(0.02)
 assert(saved_busy and r(0x416)&0x1000==0,'saved transfer did not finish')
 m:load(state)
 -- Loading cancels/resumes outstanding Lua waits; a fresh wait allows emulation to advance.
 if not emu.wait(0.02)then emu.wait(0.02)end
 assert(loaded_busy and r(0x416)&0x1000==0 and r(0x420)&0x10~=0,'restored DMA did not finish')
 print('SCSP_DMA_SAMPLE_PASS asynchronous phases, both directions/gates, source preservation, protected controls, completion IRQ, 1Fs phase/pending, save/load')
end
scsp_dma_sample_thread=coroutine.create(function()
 local ok,err=pcall(run)
 if not ok then print('SCSP_DMA_SAMPLE_FAIL '..tostring(err))end
 m:exit()
end)
local ok,err=coroutine.resume(scsp_dma_sample_thread)
if not ok then print('SCSP_DMA_SAMPLE_FAIL '..tostring(err));m:exit()end
