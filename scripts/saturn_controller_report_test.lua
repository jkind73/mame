-- license:BSD-3-Clause
-- Actual input ports -> controller devices -> timed SMPC INTBACK packets.
local m=manager.machine;local h=m.devices[':maincpu'].spaces.program
local kind=assert(os.getenv('SATURN_CONTROLLER_TEST_KIND'))
local function field(tag,mask)
 local p=assert(m.ioport.ports[tag],'missing port '..tag)
 for _,f in pairs(p.fields)do if f.mask==mask then return f end end
 error('missing field '..tag..' '..mask)
end
local function set(tag,mask,value)field(tag,mask):set_value(value)end
local function report()
 h:write_u8(0x00100001,0);h:write_u8(0x00100003,0xc8);h:write_u8(0x00100005,0xf0)
 h:write_u8(0x00100063,1);h:write_u8(0x0010001f,0x10)
 for i=1,500 do
  emu.wait(0.0001)
  if (h:read_u8(0x00100063)&1)==0 then
   assert((h:read_u8(0x00100061)&0x80)~=0,'missing peripheral status')
   local r={};for j=0,31 do r[j+1]=h:read_u8(0x00100021+j*2)end;return r
  end
 end
 error('INTBACK did not finish')
end
local function expect(expected)
 local r=report()
 for i,v in ipairs(expected)do assert(r[i]==v,string.format('packet byte %d: %02x != %02x',i,r[i],v))end
end
local function run()
 emu.wait(0.03)
 if kind=='analog' then
  local tag=':ctrl1:analog:'
  set(tag..'ANALOG_Y',0xff,128);set(tag..'ANALOG_Z',0xff,32)
  for _,test in ipairs({{170,0x7f},{160,0x7f},{149,0xff},{86,0xbf},{96,0xbf},{107,0xff}})do
   set(tag..'ANALOG_X',0xff,test[1]);emu.wait(0.02)
   expect({0xf1,0x15,test[2],0xff,test[1],128,32})
  end
 elseif kind=='keyboard' then
  local tag=':ctrl1:keyboard:KEY.'
  for _,test in ipairs({{4,4,0xfe,0xf8,0x22},{4,16,0xff,0x78,0x24},{2,32,0xff,0xf0,0x15}})do
   set(tag..test[1],test[2],1);emu.wait(0.02)
   expect({0xf1,0x34,test[3],test[4],0x0e,test[5]})
   set(tag..test[1],test[2],0);emu.wait(0.02)
  end
  for _,test in ipairs({{11,1,0x58,0x40},{15,0x40,0x7e,0x10}})do
   for press=0,1 do
    set(tag..test[1],test[2],1);emu.wait(0.02)
    expect({0xf1,0x34,0xff,0xf8,0x0e|((press==1)and test[4]or 0),test[3]})
    set(tag..test[1],test[2],0);emu.wait(0.02)
    expect({0xf1,0x34,0xff,0xf8,7|((press==0)and test[4]or 0),test[3]})
   end
  end
 elseif kind=='multitap' then
  local tag=':ctrl1:multitap:'
  set(tag..'ctrl1:joypad:JOY',0x0400,1)
  set(tag..'ctrl6:joypad:JOY',0x0100,1)
  set(tag..'ctrl3:analog:ANALOG_X',0xff,170)
  set(tag..'ctrl3:analog:ANALOG_Y',0xff,128)
  set(tag..'ctrl3:analog:ANALOG_Z',0xff,32)
  set(tag..'ctrl5:keyboard:KEY.4',4,1);emu.wait(0.02)
  expect({0x16,0x02,0xfb,0xff,0xff,0x15,0x7f,0xff,170,128,32,0xff,0x34,0xfe,0xf8,0x0e,0x22,0x02,0xfe,0xff})
 elseif kind=='multitap_saved' then
  local tag=':ctrl1:multitap:ctrl6:multicontroller:ANALOG_X'
  set(tag,255,180);emu.wait(0.02)
  report();assert((h:read_u8(0x00100061)&0x20)~=0,'long report lacks NPE')
  m:save('pending_controller');emu.wait(0.05)
  local function continuation()
   h:write_u8(0x00100001,0x80);emu.wait(0.002)
   local expected={128,128,0,0,0x16,0xff,0xff,180,128,0,0}
   for i=1,32 do
    local value=i<=#expected and expected[i]or(i==32 and 0x10 or 0xff)
    assert(h:read_u8(0x0010001f+i*2)==value,'pending report/padding mismatch '..i)
   end
   assert((h:read_u8(0x00100061)&0x60)==0,'continued report PDL/NPE did not finish')
  end
  set(tag,255,200);emu.wait(0.02);continuation()
  m:load('pending_controller');emu.wait(0.05)
  set(tag,255,220);emu.wait(0.02);continuation()
 elseif kind=='multicontroller' then
  local tag=':ctrl1:multicontroller:'
  expect({0xf1,0x16,0xff,0xff,128,128,0,0})
  for _,test in ipairs({{145,0x7f},{100,0x7f},{85,0xff},{100,0xff}})do
   set(tag..'TRIGGER_R',255,test[1]);emu.wait(0.02)
   expect({0xf1,0x16,0xff,test[2],128,128,test[1],0})
  end
  set(tag..'TRIGGER_R',255,0);set(tag..'TRIGGER_L',255,145)
  set(tag..'ANALOG_X',255,0);emu.wait(0.02)
  expect({0xf1,0x16,0xff,0xf7,1,128,0,145})
  -- Stick positions do not generate the independent directional switches.
  set(tag..'JOY',0x8000,1);emu.wait(0.02)
  expect({0xf1,0x16,0x7f,0xf7,1,128,0,145})
  set(tag..'JOY',0x8000,0)
  set(tag..'ANALOG_X',255,255);set(tag..'ANALOG_Y',255,255)
  set(tag..'TRIGGER_L',255,0);emu.wait(0.02)
  local r=report();assert(r[5]>=218 and r[5]<=219 and r[6]==r[5],'stick gate is not circular')
  -- Mode transitions calibrate the current positions to neutral, not power-on defaults.
  set(tag..'ANALOG_X',255,170);set(tag..'ANALOG_Y',255,100)
  set(tag..'TRIGGER_R',255,20);set(tag..'TRIGGER_L',255,30)
  field(tag..'MODE',1).user_value=0;emu.wait(0.02)
  expect({0xf1,0x02,0xff,0xff})
  field(tag..'MODE',1).user_value=1;emu.wait(0.02)
  expect({0xf1,0x16,0xff,0xff,128,128,0,0})
  set(tag..'ANALOG_X',255,180);set(tag..'ANALOG_Y',255,110)
  set(tag..'TRIGGER_R',255,165);set(tag..'TRIGGER_L',255,175);emu.wait(0.02)
  expect({0xf1,0x16,0xff,0x77,138,138,145,145})
  m:save('multicontroller');emu.wait(0.05)
  field(tag..'MODE',1).user_value=0;emu.wait(0.02)
  expect({0xf1,0x02,0xff,0xff})
  field(tag..'MODE',1).user_value=1
  m:load('multicontroller');emu.wait(0.05)
  -- Configuration input is external to the controller's saved calibration.
  field(tag..'MODE',1).user_value=1;emu.wait(0.02)
  expect({0xf1,0x16,0xff,0x77,138,138,145,145})
 elseif kind=='segatap' then
  local tag=':ctrl1:segatap:'
  set(tag..'ctrl1:joy_md3:JOY',0x0400,1)
  set(tag..'ctrl2:joy_md6:JOY',0x0040,1);emu.wait(0.02)
  expect({0x04,0xe1,0xfb,0xe2,0xff,0xbf,0xe3,0,0,0,0xff})
 elseif kind=='twin_stick' then
  local tag=':ctrl1:twin_stick:JOY'
  expect({0xf1,0x02,0xff,0xff})
  for _,mask in ipairs({0x8000,0x4000,0x2000,0x1000,0x0800,0x0400,0x0200,0x0100,0x0080,0x0040,0x0020,0x0010,0x0008})do
   set(tag,mask,1);emu.wait(0.02)
   local value=0xffff~mask
   expect({0xf1,0x02,value>>8,value&255})
   set(tag,mask,0);emu.wait(0.02)
   expect({0xf1,0x02,0xff,0xff})
  end
  -- Both sticks can report diagonals simultaneously.
  for _,mask in ipairs({0x8000,0x1000,0x0040,0x0100})do set(tag,mask,1)end
  emu.wait(0.02);expect({0xf1,0x02,0x6e,0xbf})
 else error('unknown controller test')end
 print('SATURN_CONTROLLER_REPORT_PASS '..kind);m:exit()
end
emu.register_frame_done(function()
 if CONTROLLER_REPORT_TEST_STARTED then return end
 CONTROLLER_REPORT_TEST_STARTED=true
 coroutine.resume(coroutine.create(function()
  local ok,e=pcall(run);if not ok then print('SATURN_CONTROLLER_REPORT_FAIL '..tostring(e));m:exit()end
 end))
end)
