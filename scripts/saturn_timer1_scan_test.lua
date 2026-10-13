-- license:BSD-3-Clause
-- Real VDP2 -> board -> SCU Timer 1 scheduling, including counter discontinuities.
local m=manager.machine;local h=m.devices[':maincpu'].spaces.program
local screen=m.screens[':screen'];local started=false
-- The board reset selects the shared 320-mode oscillator for SCU and VDP2.
local tick=1/math.floor(14318181*1708/455)
timer1_scan_subscription=emu.add_machine_frame_notifier(function()
 if started then return end
 started=true
 coroutine.resume(coroutine.create(function()
  local ok,e=pcall(function()
   h:write_u32(0x05fe00a0,0xffff)
   for mode=0,7 do
    h:write_u16(0x05f80000,0x8000|mode)
    local edge
    if (mode&4)~=0 then edge=((mode&1)~=0 and 0x164 or 0x144)*((mode&2)~=0 and 2 or 1)
    else edge=(((mode&1)~=0 and 0x163 or 0x143)-((mode&2)~=0 and 1 or 0))*((mode&2)~=0 and 2 or 1)end
    for _,setting in ipairs({1,2,0x10,0x20,0x40,0x60,0x69,0x6a,0x80,0xe0,0x100,0})do
     emu.wait(screen:time_until_pos(100,20))
     h:write_u16(0x05fe009a,0)
     h:write_u32(0x05fe0094,setting)
     h:write_u32(0x05fe00a4,0)
     h:write_u16(0x05fe009a,1)
     local count=setting==0 and 512 or setting
     emu.wait(screen:time_until_pos(100,edge)+(8*count-4-0.5)*tick)
     assert((h:read_u32(0x05fe00a4)&4)~=0,'missing HBLANK edge')
     assert((h:read_u32(0x05fe00a4)&16)==0,'Timer 1 fired early')
     emu.wait(tick)
     assert((h:read_u32(0x05fe00a4)&16)~=0,'Timer 1 fired late')
     h:read_u16(0x05f80002)
     print(string.format('TIMER1_SCAN mode=%d set=%03x HCNT=%03x VCNT=%03x',mode,setting,h:read_u16(0x05f80008),h:read_u16(0x05f8000a)))
    end
   end
   print('SATURN_TIMER1_SCAN_PASS all horizontal modes, zero reload and historical table settings')
  end)
  if not ok then print('SATURN_TIMER1_SCAN_FAIL '..tostring(e))end
  m:exit()
 end))
end)
