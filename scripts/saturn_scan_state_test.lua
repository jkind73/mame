-- license:BSD-3-Clause
-- Preserve board edge detectors, then check that real scan events continue.
local m=manager.machine
local h=m.devices[':maincpu'].spaces.program
local phase=0
local saved={}
local function item(field)
 for name,id in pairs(m.devices[':'].items)do
  if name:match('/'..field..'$')then return emu.item(id)end
 end
 error('scan edge state missing: '..field)
end
local function fail(e)print('SATURN_SCAN_STATE_FAIL '..tostring(e));m:exit()end
scan_state_load_subscription=emu.add_machine_post_load_notifier(function()
 local ok,e=pcall(function()
  for field,value in pairs(saved)do assert(item(field):read(0)==value,field..' not restored')end
  assert(h:read_u16(0x05f80006)==0x8000,'VRSIZE not restored')
  h:write_u32(0x05fe00a0,0xffff);h:write_u32(0x05fe00a4,0)
  phase=3
 end)
 if not ok then fail(e)end
end)
emu.register_frame_done(function()
 local ok,e=pcall(function()
  if phase==0 then
   phase=-1
   h:write_u32(0x05fe00a0,0xffff)
   coroutine.resume(coroutine.create(function()
    local ok,e=pcall(function()
     -- Save away from an edge: queued saves run at the next scheduler boundary.
     emu.wait(m.screens[':screen']:time_until_pos(100,100))
     for _,field in ipairs({'m_prev_hint','m_prev_vint'})do saved[field]=item(field):read(0)end
     h:write_u16(0x05f80006,0x8000)
     m:save(assert(os.getenv('SATURN_SCAN_STATE_PATH')));phase=1
    end)
    if not ok then fail(e)end
   end))
  elseif phase==1 then
   for field,value in pairs(saved)do item(field):write(0,value~1)end
   h:write_u16(0x05f80006,0)
   phase=2;m:load(assert(os.getenv('SATURN_SCAN_STATE_PATH')))
  elseif phase==3 then
   phase=4 -- allow a full frame after the loaded mid-frame position
  elseif phase==4 then
   assert((h:read_u32(0x05fe00a4)&7)==7,'scan IRQ edges lost after load')
   print('SATURN_SCAN_STATE_PASS H/V edge detectors, VRSIZE and subsequent SCU scan events');m:exit()
  end
 end)
 if not ok then fail(e)end
end)
