-- license:BSD-3-Clause
-- Queue two independent SCU sources while SR masks the issued request.
local m=manager.machine;local cpu=m.devices[':maincpu'];local h=cpu.spaces.program
local frame=0;local path=assert(os.getenv('SCU_IRQ_QUEUE_STATE_PATH'))
emu.register_frame_done(function()
 frame=frame+1
 local ok,e=pcall(function()
  if frame==1 then
 cpu.state.SR.value=0xf0
 h:write_u16(0xfffffee0,1) -- SCU supplies vectors; SH-2 autovectors are a different mode.
 h:write_u32(0x05fe00a0,0xbf5f);h:write_u32(0x05fe00a4,0)
 cpu.state.VBR.value=0x06007000;cpu.state.R15.value=0x26009000
 for _,v in ipairs({{0x45,0x06008000,0x06009000},{0x47,0x06008100,0x06009004}})do
  h:write_u32(0x06007000+4*v[1],v[2]);h:write_u32(v[3],0)
  for i,word in ipairs({0xd105,0xe001,0x2102,0xd005,0xd105,0x2012,0x002b,0x0009,0x0009})do h:write_u16(v[2]+2*(i-1),word)end
  h:write_u32(v[2]+24,v[3])
  h:write_u32(v[2]+28,0x25fe00a0)
  h:write_u32(v[2]+32,0xbf5f) -- acknowledge masks all; the handler restores its software mask.
 end
 h:write_u32(0x05fe0080,0x8000);h:write_u32(0x05fe0084,0xf8000000);h:write_u32(0x05fe0080,0x18000)
 h:write_u8(0x00100001,1);h:write_u8(0x00100003,0);h:write_u8(0x00100063,1);h:write_u8(0x0010001f,0x10)

  elseif frame==2 then
   assert((h:read_u32(0x05fe00a4)&0x20)==0,'issued DSP IST did not clear')
   assert((h:read_u32(0x05fe00a4)&0x80)~=0,'SMPC did not queue')
   assert(h:read_u32(0x06009000)==0 and h:read_u32(0x06009004)==0,'masked handlers ran')
   m:save(path)
  elseif frame==3 then
   h:write_u16(0x0600800a,0x0009) -- first handler intentionally does not rearm IMS
   cpu.state.SR.value=0
  elseif frame==4 then
   assert(h:read_u32(0x06009000)==1 and h:read_u32(0x06009004)==0,'queued source ran before software rearmed IMS')
   assert(h:read_u32(0x05fe00a0)==0xbfff and h:read_u32(0x05fe00a4)&0x80~=0,'acknowledgment mask/pending status wrong')
   h:write_u16(0x0600800a,0x2012)
   h:write_u32(0x05fe00a0,0xbf5f)
  elseif frame==5 then
   assert(h:read_u32(0x06009000)==1 and h:read_u32(0x06009004)==1,'queued handler depended on unrelated event')
   m:load(path)
  elseif frame==6 then
   assert(h:read_u32(0x06009000)==0 and h:read_u32(0x06009004)==0,'markers not restored')
   cpu.state.SR.value=0
  elseif frame==7 then
   assert(h:read_u32(0x06009000)==1 and h:read_u32(0x06009004)==1,'pending vector/queue not restored')
   print('SCU_IRQ_QUEUE_PASS queued DSP/SMPC vectors and scheduled pending save/load');m:exit()
  end
 end)
 if not ok then print('SCU_IRQ_QUEUE_FAIL '..tostring(e));m:exit()end
end)
