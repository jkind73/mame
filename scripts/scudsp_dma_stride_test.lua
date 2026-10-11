-- license:BSD-3-Clause
-- DSP output DMA increments once on the 32-bit C bus, twice on the 16-bit B bus.
local m=manager.machine
local mem=m.devices[':maincpu'].spaces.program
local dsp=m.devices[':scu:scudsp']
local function run()
 for _,base in ipairs({0x06008000,0x05c08000})do
  for _,field in ipairs({0,2,3,4,5,6,7})do
   for _,hold in ipairs({0,0x4000})do
    local step=field==0 and 0 or (1<<field)
    local bbus=base<0x06000000
    local last=base+3*step*(bbus and 2 or 1)+(bbus and step or 2)
    for a=base-2,last+16,2 do mem:write_u16(a,0xa55a)end
    local expected={}
    for i=0,3 do
     local value=0x12340000|((i+1)*0x101)
     dsp.spaces.data:write_u32(i,value)
     local a=base+i*step*(bbus and 2 or 1)
     expected[a]=value>>16;expected[a+(bbus and step or 2)]=value&0xffff
    end
    mem:write_u32(0x05fe0080,0x8000)
    mem:write_u32(0x05fe0084,0xc0001004|(field<<15)|hold)
    mem:write_u32(0x05fe0084,0xf0000000)
    dsp.state.CT0.value=0;dsp.state.WA0.value=base>>2
    mem:write_u32(0x05fe0080,0x18000);emu.wait(0.0001)
    assert(dsp.state.SR.value&0x810000==0,'DMA did not complete')
    assert(dsp.state.CT0.value==4,'DMA consumed wrong data-RAM count')
    for a=base-2,last+16,2 do
     local want=expected[a]or 0xa55a
     assert(mem:read_u16(a)==want,string.format('DMA stride/guard base=%08x field=%d hold=%x address=%08x got=%04x expected=%04x',base,field,hold,a,mem:read_u16(a),want))
    end
    local final=hold~=0 and (base>>2)or ((base+3*step*(bbus and 2 or 1)+4)>>2)
    assert(dsp.state.WA0.value==final,'DMA external address-register update wrong')
   end
  end
 end
 print('SCUDSP_DMA_STRIDE_PASS C/B bus payload, untouched neighbours, CT and WA0, held/non-held')
end
thread=coroutine.create(function()local ok,err=pcall(run);if not ok then print('SCUDSP_DMA_STRIDE_FAIL '..tostring(err))end;m:exit()end)
coroutine.resume(thread)
