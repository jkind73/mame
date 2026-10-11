-- license:BSD-3-Clause
-- Video-enabled stage speeds and periodic screenshots; no emulated settings changed.
local m=manager.machine
local frames=0
local last_ticks=emu.osd_ticks()
local last_time=m.time:as_double()
emu.register_frame_done(function()
 frames=frames+1
 if frames%300==0 then
  local ticks=emu.osd_ticks()
  local now=m.time:as_double()
  local interval=(now-last_time)*emu.osd_ticks_per_second()/(ticks-last_ticks)*100
  print(string.format('VF2_PERF frames=%d time=%.3f speed=%.2f interval=%.2f',frames,now,m.video.speed_percent*100,interval))
  last_ticks=ticks;last_time=now
  io.stdout:flush()
 end
 if frames%600==0 then m.video:snapshot() end
end)
