-- license:BSD-3-Clause
-- Real reset input, VBLANK sampling, and an SH-2 NMI handler counting pulses.
local m=manager.machine;local c=m.devices[':maincpu'];local h=c.spaces.program
local screen=m.screens[':screen'];local started=false
local function command(code)
 h:write_u8(0x00100063,1);h:write_u8(0x0010001f,code)
 for i=1,1000 do emu.wait(0.00001);if (h:read_u8(0x00100063)&1)==0 then return end end
 error('SMPC command timeout')
end
local function sample()
 emu.wait(screen:time_until_pos(224,100))
 h:write_u8(0x00100001,1);h:write_u8(0x00100003,0);command(0x10)
 return (h:read_u8(0x00100061)&16)~=0
end
local function count()return h:read_u32(0x0600a000)end
reset_test_subscription=emu.add_machine_frame_notifier(function()
 if started then return end;started=true
 coroutine.resume(coroutine.create(function()
  local ok,e=pcall(function()
   local button=assert(m.ioport.ports[':RESET'].fields['Reset Button'])
   h:write_u32(0x05fe00a0,0xffff)
   h:write_u32(0x0600802c,0x06009000);h:write_u32(0x0600a000,0)
   for i,word in ipairs({0x2f06,0x2f16,0xd104,0x6012,0x7001,0x2102,0x61f6,0x60f6,0x002b,0x0009,0x0009,0x0009})do h:write_u16(0x06009000+2*(i-1),word)end
   h:write_u32(0x06009018,0x0600a000)
   h:write_u16(0x0600c000,0xaffe);h:write_u16(0x0600c002,0x0009)
   c.state.SR.value=0xf0;c.state.VBR.value=0x06008000
   c.state.R15.value=0x2600b000;c.state.CURPC.value=0x0600c000
   command(0x19)
   local function press(expected)
    emu.wait(screen:time_until_pos(100,100));button:set_value(1)
    local held=0
    for i=1,8 do
     if sample()then held=held+1 end
     assert(count()==(held>=3 and expected+1 or expected),'reset NMI ignored three-VINT debounce')
    end
    assert(held>=3,'reset input did not reach SMPC')
   end
   local function release(expected)
    button:set_value(0)
    for i=1,3 do sample();assert(count()==expected,'held/released switch repeated NMI')end
    assert(not sample(),'RESB remained pressed after release')
   end
   press(0);release(1)
   command(0x1a);button:set_value(1)
   for i=1,7 do sample();assert(count()==1,'RESDISA allowed reset-button NMI')end
   command(0x18);emu.wait(0.0001);assert(count()==2,'NMIREQ incorrectly obeyed RESDISA')
   release(2);command(0x19)
   -- A one-sample press, plus the input manager's release propagation, stays
   -- below three samples and must not produce an NMI.
   button:set_value(1)
   repeat until sample()
   button:set_value(0)
   for i=1,4 do sample();assert(count()==2,'short reset press generated NMI')end
   press(2);release(3)
   print('SMPC_RESET_PASS three-VINT debounce, short/repeated presses, RESB, RESDISA and unconditional NMIREQ')
  end)
  if not ok then print('SMPC_RESET_FAIL '..tostring(e))end
  m:exit()
 end))
end)
