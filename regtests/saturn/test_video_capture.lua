-- Run in a temporary directory: lua test_video_capture.lua /absolute/video_capture.lua
local script = assert(arg[1])
local callback, pressed, reads = nil, false, 0
local sizes = {
 ['m_vdp1_vram']={4,0x100000}, ['m_vdp1_regs']={2,0x20},
 ['m_vdp2_vram']={4,0x100000}, ['m_vdp2_regs']={2,0x200}, ['m_vdp2_cram']={4,0x1000},
 ['m_vdp1_legacy.framebuffer[0]']={2,0x40000}, ['m_vdp1_legacy.framebuffer[1]']={2,0x40000},
 ['m_vdp1_legacy.framebuffer_current_display']={4,4},
 ['m_vdp1_legacy.field_framebuffer[0]']={2,0x40000}, -- excluded derived bank
}
local items = {}
for name, shape in pairs(sizes) do items['0/'..name]=shape end
manager={machine={devices={[':']={items=items}},screens={[':screen']={pixels=function()
 return string.pack('I4I4',0x123456,0xabcdef),2,1 end}},system={name='saturnjp'},input={
 code_from_token=function(_, token) assert(token=='KEYCODE_F12'); return 12 end,
 code_pressed_once=function(_, key) assert(key==12);local p=pressed;pressed=false;return p end}}}
emu={time=function() return 42.5 end,register_frame_done=function(f) callback=f end,
 item=function(shape) return {size=shape[1],count=shape[2]/shape[1],read_block=function(_,at,n)
 assert(at==0 and n<=shape[2]);reads=reads+1;return string.rep('\x56',n) end} end}
local realdate=os.date;os.date=function() return 'fixture' end
local function fire() pressed=true;callback() end
local function parse(name)
 local f=assert(io.open(name,'rb'));local data=f:read('a');f:close()
 assert(data:sub(1,15)=='SATURN-VIDEO-1\n')
 local pos, records=16,{}
 while pos<=#data do
  local len;len,pos=string.unpack('>I4',data,pos)
  local key=data:sub(pos,pos+len-1);pos=pos+len
  local size,n;size,n,pos=string.unpack('>I4I4',data,pos)
  assert(size>0 and n%size==0 and not records[key])
  records[key]=data:sub(pos,pos+n-1);assert(#records[key]==n);pos=pos+n
 end
 assert(pos==#data+1);return records
end
dofile(script);callback();assert(reads==0)
fire();local records=parse('saturn-video-fixture-001.bin')
assert(#records.m_vdp1_vram==0x80000 and #records.m_vdp2_vram==0x100000)
assert(not records['m_vdp1_legacy.field_framebuffer[0]'])
assert(records.metadata:find('time=42.500000000',1,true))
assert(records['screen.pixels']==string.pack('I4I4',0x123456,0xabcdef))
fire();fire();local before=reads;fire();assert(reads==before) -- three-file cap
assert(not io.open('saturn-video-fixture-004.bin','rb'))
dofile(script);fire();assert(parse('saturn-video-fixture-004.bin').metadata) -- no overwrite
items['0/m_vdp1_regs']=nil
dofile(script);fire();assert(not io.open('saturn-video-fixture-005.bin','rb'))
before=reads;fire();assert(reads==before) -- missing item stops capture safely
os.date=realdate
print('Video capture: schema, byte bounds, screen match, cap, collisions and failure tests passed')
