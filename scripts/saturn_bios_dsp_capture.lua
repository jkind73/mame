-- license:BSD-3-Clause
-- Atomic saved DSP state and RAM snapshots from the live BIOS chime interval.
local m=manager.machine;local frame=0
local directory=assert(os.getenv('SATURN_DSP_CAPTURE_DIR'))
local fields={'RBP','RBL','DEC','Stopped','LastStep','AccReg','FrcReg','YReg','AdrsReg','InputsReg','ReadPending','ReadNOFL','WritePending','ReadValue','WriteValue','ReadWriteAddr','MixWritten'}
local arrays={{'COEF',64},{'MADRS',32},{'MPRO',512},{'TEMP',128},{'MEMS',32},{'MIXS',16},{'MIXSPrev',16},{'EXTS',2},{'EFREG',16}}
local items={}
local function item(field)
 if items[field]then return items[field]end
 local suffix='m_DSP.'..field
 for name,id in pairs(m.devices[':scsp'].items)do
  if name:sub(-#suffix)==suffix then items[field]=emu.item(id);return items[field]end
 end
 error('missing saved DSP field '..field)
end
local function capture()
 local f=assert(io.open(string.format('%s/frame-%04d.bin',directory,frame),'wb'))
 f:write(string.pack('<I4I4d',0x44535031,frame,m.time:as_double()))
 for _,name in ipairs(fields)do f:write(string.pack('<I4',item(name):read(0)&0xffffffff))end
 for _,array in ipairs(arrays)do
  for i=0,array[2]-1 do f:write(string.pack('<I4',item(array[1]):read(i)&0xffffffff))end
 end
 local ram=m.devices[':audiocpu'].spaces.program:read_range(0,0x7ffff,8)
 assert(#ram==0x80000,'incorrect sound RAM capture size');f:write(ram);f:close()
 print('SATURN_BIOS_DSP_CAPTURE frame='..frame..' stopped='..item('Stopped'):read(0)..' steps='..item('LastStep'):read(0))
end
saturn_bios_dsp_capture_subscription=emu.add_machine_frame_notifier(function()
 frame=frame+1
 if frame>=180 and frame<=540 and frame%30==0 then
  local ok,e=pcall(capture)
  if not ok then print('SATURN_BIOS_DSP_CAPTURE_FAIL '..tostring(e));m:exit()end
 end
 if frame==550 then print('SATURN_BIOS_DSP_CAPTURE_PASS 13 BIOS interval snapshots');m:exit()end
end)
