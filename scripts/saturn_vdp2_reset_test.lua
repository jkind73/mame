-- license:BSD-3-Clause
-- Reset must clear both public mode registers and their decoded controls.
if VDP2_RESET_TEST_ACTIVE then return end
VDP2_RESET_TEST_ACTIVE=true
local m=manager.machine;local h=m.devices[':maincpu'].spaces.program
local phase=0
local modes={0x81e3,0x8107,0x8010}
local function value(field)
 for name,id in pairs(m.devices[':vdp2'].items)do
  if name:match('/'..field..'$')then return emu.item(id):read(0)end
 end
 error('missing VDP2 field '..field)
end
emu.register_frame_done(function()
 local ok,e=pcall(function()
  if phase%2==0 then
   local mode=modes[phase//2+1]
   if not mode then print('SATURN_VDP2_RESET_PASS TVMD, EXTEN, decoded display/interlace/resolution and external controls');m:exit();return end
   h:write_u16(0x05f80000,mode);h:write_u16(0x05f80002,0x0303);h:write_u16(0x05f80006,0x800f)
   assert(h:read_u16(0x05f80006)==0x8000,'VRSIZE write or read-only version')
   assert(h:read_u16(0x05f80000)==mode,'mode setup')
   phase=phase+1;m:soft_reset()
  else
   assert(h:read_u16(0x05f80000)==0,'TVMD retained across reset')
   assert(h:read_u16(0x05f80002)==0,'EXTEN retained across reset')
   assert(h:read_u16(0x05f80006)==0 and value('m_vramsz')==0,'VRSIZE retained across reset')
   for _,field in ipairs({'m_disp','m_bdclmd','m_lsmd','m_vreso','m_hreso','m_exlten','m_exsyen','m_dasel','m_exbgen'})do
    assert(value(field)==0,'decoded reset mismatch '..field)
   end
   assert((h:read_u16(0x05f80004)&8)~=0,'reset display not blanked')
   phase=phase+1
  end
 end)
 if not ok then print('SATURN_VDP2_RESET_FAIL '..tostring(e));m:exit()end
end)
