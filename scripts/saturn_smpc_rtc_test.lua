-- license:BSD-3-Clause
-- SMPC calendar commands, BCD carry, leap years and save/load phase.
if SMPC_RTC_TEST_ACTIVE then return end
SMPC_RTC_TEST_ACTIVE=true
local m=manager.machine;local h=m.devices[':maincpu'].spaces.program
local function command(code)
 h:write_u8(0x00100063,1);h:write_u8(0x0010001f,code)
 assert(h:read_u8(0x0010005f)==code,'OREG31 missing during command')
 for i=1,1000 do emu.wait(0.00001);if (h:read_u8(0x00100063)&1)==0 then return end end
 error('SMPC command did not finish')
end
local function data()
 local rtc=m.devices[':smpc:rtc'];assert(rtc,'calendar subdevice missing')
 for name,id in pairs(rtc.items)do if name:match('/m_data$')then return emu.item(id)end end
 error('calendar data missing')
end
local phase=0;local saved_time=0;local next_tick=0;local path=assert(os.getenv("SMPC_RTC_STATE_PATH"))
local function run()
 emu.wait(0.001)
 for _,test in ipairs({
  {{0x19,0x99,0x5c,0x31,0x23,0x59,0x59},{0x20,0,0x61,1,0,0,0}},
  {{0x20,0,0x12,0x28,0x23,0x59,0x59},{0x20,0,0x22,0x29,0,0,0}},
  {{0x20,1,0x32,0x28,0x23,0x59,0x59},{0x20,1,0x43,1,0,0,0}}
 })do
  for i,v in ipairs(test[1])do h:write_u8(0x00100001+2*(i-1),v)end
  command(0x16);emu.wait(1)
  for i,v in ipairs(test[2])do assert(data():read(i-1)==v,'calendar rollover byte '..i)end

 end
 local settings={0,0,2,4};local year=data():read(1);local day=data():read(3)
 for i,v in ipairs(settings)do h:write_u8(0x00100001+2*(i-1),v)end
 command(0x17);assert(data():read(1)==year and data():read(3)==day,'SETSMEM changed calendar')
 h:write_u8(0x00100001,1);h:write_u8(0x00100003,0);command(0x10)
 for i,v in ipairs(settings)do assert(h:read_u8(0x00100039+2*(i-1))==v,'saved mono/language setting '..i)end
 for i=0,6 do assert(h:read_u8(0x00100023+2*i)==data():read(i),'INTBACK clock byte '..i)end
 print('SMPC_RTC_CALENDAR_PASS');phase=1
end
postload_subscription=emu.add_machine_post_load_notifier(function()if phase==4 then phase=5 end end)
emu.register_frame_done(function()
 local ok,e=pcall(function()
  if phase==1 then
   for i,v in ipairs({0x19,0x99,0x5c,0x31,0x23,0x59,0x59})do h:write_u8(0x00100001+2*(i-1),v)end
   h:write_u8(0x00100063,1);h:write_u8(0x0010001f,0x16);phase=2
  elseif phase==2 then
   assert(data():read(6)==0x59,'save setup did not complete');saved_time=m.time:as_double();m:save(path);phase=3
  elseif phase==3 and data():read(6)~=0x59 then
   assert(data():read(0)==0x20 and data():read(1)==0 and data():read(6)==0,'pre-load century carry')
   phase=4;m:load(path)
  elseif phase==5 then
   assert(m.time:as_double()>=saved_time and m.time:as_double()<math.floor(saved_time)+1,'load did not restore timer epoch')
   assert(data():read(6)==0x59,'calendar bytes not restored');phase=6
  elseif phase==6 and data():read(6)~=0x59 then
   assert(data():read(0)==0x20 and data():read(6)==0,'saved calendar carry')
   assert(math.abs(m.time:as_double()-(math.floor(saved_time)+1))<0.04,'RTC oscillator phase not restored')
   next_tick=math.floor(m.time:as_double())+1;phase=7;m:soft_reset()
  elseif phase==7 then
   assert(data():read(0)==0x20 and data():read(1)==0,'warm reset changed calendar')
   if m.time:as_double()<next_tick then assert(data():read(6)==0,'warm reset added an immediate tick')
   else
    assert(data():read(6)==1 and m.time:as_double()-next_tick<0.04,'warm reset rephased oscillator')
    print('SMPC_RTC_PASS century, leap/non-leap, OREG31, INTBACK, scheduled save/load and warm-reset oscillator phase');m:exit()
   end
  end
 end)
 if not ok then print('SMPC_RTC_FAIL '..tostring(e));m:exit()end
end)
coroutine.resume(coroutine.create(function()local ok,e=pcall(run);if not ok then print('SMPC_RTC_FAIL '..tostring(e));m:exit()end end))
