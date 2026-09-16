-- license:BSD-3-Clause
-- Linked mapped-register/pixel/save-manager fixture; not gameplay.
local machine=manager.machine
local main=assert(machine.devices[':maincpu'])
local space=assert(main.spaces['program'])
local screen=assert(machine.screens[':screen'])
local output=assert(os.getenv('SATURN_RUNTIME_OUTPUT'))
local regbase,vram,cram=0x05f80000,0x05e00000,0x05f00000
local function reg(offset,value) space:write_u16(regbase+offset,value) end
-- ST-058 pp.59–61: normal-screen color capabilities; pp.69–75:
-- one-word names, 16x16 characters and H/V flip encoding.
local composition=os.getenv('SATURN_RUNTIME_COMPOSITION')=='1'
local cases={}
for _,large in ipairs({false,true}) do
    for layer=0,3 do
        local maxdepth=layer==0 and 4 or layer==1 and 3 or 1
        for depth=0,maxdepth do
            cases[#cases+1]={large=large,depth=depth,layer=layer,cell=true}
            if layer<2 then cases[#cases+1]={large=large,depth=depth,layer=layer} end
        end
    end
    cases[#cases+1]={large=large,depth=2,layer=0,cell=true,rotation=true}
end
if composition then
    cases={}
    for _,large in ipairs({false,true}) do
        local function add(name,priority,control,ratios,expected)
            cases[#cases+1]={large=large,depth=0,layer=0,composition=true,
                name=name,priority=priority,control=control,ratios=ratios,expected=expected}
        end
        -- ST-058 priority order and pp.241–244: top-screen CC enable,
        -- top/second ratio selection and all 32 (31-n):(n+1) weights.
        add('tie-NBG0',0x0101,0,0,0xff0000)
        add('NBG1-higher',0x0201,0,0,0x00ff00)
        add('NBG0-priority-zero',0x0100,0,0,0x00ff00)
        for _,second in ipairs({false,true}) do
            for ratio=0,31 do
                local selected=second and 31-ratio or ratio
                local expected=((255*(31-selected)//32)<<16)|((255*(selected+1)//32)<<8)
                add((second and 'second-ratio-' or 'top-ratio-')..ratio,
                    0x0102,second and 0x0201 or 1,ratio|((31-ratio)<<8),expected)
            end
        end
        add('additive-clamp',0x0102,0x0101,0x1f1f,0xffff00)
        add('lower-only-CC',0x0102,2,15,0xff0000)
    end
end
assert(#cases==(composition and 138 or 46))
local index,phase,wait=1,'settle',180
local saved,loaded,reference=false,false,nil
local subscriptions={}
subscriptions[1]=emu.add_machine_pre_save_notifier(function() saved=true end)
subscriptions[2]=emu.add_machine_post_load_notifier(function() loaded=true end)
local function configure(c)
    local layer=c.layer
    -- Initial ST-V/slave startup must finish before isolating the scene.
    space:write_u32(0x06000000,0xaffe0009)
    for _,tag in ipairs({':maincpu',':slave'}) do
        local cpu=machine.devices[tag]
        if cpu then cpu.state['SR'].value=0xf0;cpu.state['PC'].value=0x06000000 end
    end
    reg(0,0);reg(6,c.large and 0x8000 or 0)
    for offset=0x0e,0x11e,2 do reg(offset,0) end
    reg(0x0e,0x1000)
    local cp=layer+4
    local cycle=c.cell and ((layer<<12)|(cp<<8)|(cp<<4)|cp) or cp*0x1111
    for offset=0x10,0x1e,2 do reg(offset,cycle) end
    local bytes=({0.5,1,2,2,4})[c.depth+1]
    local dot=c.depth==0 and 0x11111111 or c.depth==1 and 0x01010101 or c.depth==2 and 0x00010001 or c.depth==3 and 0x801f801f or 0x800000ff
    local poison=c.depth==0 and 0x22222222 or c.depth==1 and 0x02020202 or c.depth==2 and 0x00020002 or c.depth==3 and 0x83e083e0 or 0x8000ff00
    local yellow=({0x33333333,0x03030303,0x00030003,0x83ff83ff,0x8000ffff})[c.depth+1]
    local white=({0x44444444,0x04040404,0x00040004,0xffffffff,0x80ffffff})[c.depth+1]
    local capacity=c.large and 0x100000 or 0x80000
    for offset=0,capacity-4,4 do space:write_u32(vram+offset,poison) end
    if c.cell then
        for entry=0,1023 do
            -- Alternate horizontal flip by character column, vertical by row.
            local flip=c.rotation and 0 or (((entry%32)%2)<<10)|(((entry//32)%2)<<11)
            space:write_u16(vram+((0x80000+entry*2)%capacity),flip)
        end
        for cell=0,3 do
            local color=c.rotation and dot or ({dot,poison,yellow,white})[cell+1]
            for offset=0,64*bytes-4,4 do
                space:write_u32(vram+0x20000+cell*64*bytes+offset,color)
            end
        end
    else
        for offset=0,512*256*bytes-4,4 do space:write_u32(vram+((0x80000+offset)%capacity),dot) end
    end
    space:write_u16(cram+2,0x001f);space:write_u16(cram+4,0x03e0)
    space:write_u16(cram+6,0x03ff);space:write_u16(cram+8,0x7fff)
    space:write_u16(vram+0x7fffe,0x7c00)
    reg(0xac,3);reg(0xae,0xffff)
    reg(0x3c,4<<(layer*4))
    if layer<2 then reg(0x28,((c.depth<<4)|(c.cell and 1 or 2))<<(layer*8))
    else reg(0x2a,((c.depth<<1)|1)<<((layer-2)*4)) end
    if c.cell then reg(0x30+layer*2,0x8004) end
    reg(0x78,1);reg(0x7c,1);reg(0x88,1);reg(0x8c,1)
    reg(layer<2 and 0xf8 or 0xfa,1<<((layer%2)*8));reg(0x20,1<<layer)
    if c.rotation then
        reg(0x20,0x10);reg(0xf8,0);reg(0xfc,1)
        reg(0x2a,0x2100);reg(0x38,0x8004);reg(0x3e,4)
        reg(0x0e,c.large and 0x1023 or 0x110e)
        for word=0,23 do space:write_u32(vram+0x60000+word*4,0) end
        for _,word in ipairs({0,4,5,7,11,19,20}) do space:write_u32(vram+0x60000+word*4,65536) end
        reg(0xbc,3);reg(0xbe,0);reg(0xb2,7)
    end
    if c.composition then
        -- Red NBG0 at map 4, green NBG1 at map 1; blue back screen.
        -- Configure real character-fetch slots for both bitmap consumers.
        for offset=0x10,0x1e,2 do reg(offset,0x4455) end
        reg(0x28,0x0202);reg(0x3c,0x0014);reg(0x20,3)
        reg(0xf8,c.priority);reg(0xec,c.control);reg(0x108,c.ratios)
        if c.name=='additive-clamp' then space:write_u16(cram+4,0x03ff) end
    end
    reg(0,0x8000)
    c.dot=dot;c.capacity=capacity;c.address=c.cell and 0x20000 or (0x80000%capacity)
end
local function pixels(expected)
    for _,y in ipairs({8,17,63,127}) do
        for _,x in ipairs({8,31,127,255}) do
            local actual=screen:pixel(x,y)&0xffffff
            local want=expected
            local c=cases[index]
            if expected==0xff0000 and c.cell and not c.rotation then
                -- Four distinct 8x8 colors distinguish H from V flips, unlike
                -- a symmetric two-color checker. Oracle uses screen coords.
                local column=((x//8)%2) ~ ((x//16)%2)
                local row=((y//8)%2) ~ ((y//16)%2)
                want=({0xff0000,0x00ff00,0xffff00,0xffffff})[row*2+column+1]
            end
            assert(actual==want,string.format('case %d pixel %d,%d: %06x != %06x',index,x,y,actual,want))
        end
    end
end
local function step()
    if phase=='settle' then
        if wait>0 then wait=wait-1 else phase='configure' end
        return
    end
    if phase=='configure' then configure(cases[index]);phase='render';wait=3
    elseif wait>0 then wait=wait-1
    elseif phase=='render' then
        pixels(cases[index].expected or 0xff0000);reference=screen:pixels();assert(#reference>0)
        saved=false;os.remove(output..'/runtime.sta');machine:save(output..'/runtime.sta');phase='save';wait=3
    elseif phase=='save' then
        assert(saved,'save notification missing')
        local f=assert(io.open(output..'/runtime.sta','rb'));assert(f:seek('end')>1000);f:close()
        space:write_u32(vram+cases[index].address,0);space:write_u16(cram+2,0x03e0)
        reg(0xf8,0);reg(0xfa,0);reg(0xfc,0);reg(0x0e,0);reg(6,cases[index].large and 0 or 0x8000)
        phase='mutated';wait=3
    elseif phase=='mutated' then
        pixels(0x0000ff);loaded=false;machine:load(output..'/runtime.sta');phase='load';wait=3
    elseif phase=='load' then
        assert(loaded,'postload notification missing');pixels(cases[index].expected or 0xff0000)
        assert(space:read_u32(vram+cases[index].address)==cases[index].dot,'VRAM not restored')
        assert((space:read_u16(regbase+6)&0x8000)==(cases[index].large and 0x8000 or 0),'VRSIZE not restored')
        local replay=screen:pixels();assert(replay==reference,'postload full image differs')
        assert(screen:snapshot(string.format('%s/case-%02d.png',output,index))==nil)
        print(string.format('VDP2_RUNTIME case=%d layer=NBG%d depth=%d cell=%s rotation=%s large=%s pixels/save/load PASS',index,cases[index].layer,cases[index].depth,tostring(cases[index].cell or false),tostring(cases[index].rotation or false),tostring(cases[index].large)))
        index=index+1
        if index>#cases then print('VDP2_RUNTIME PASS cases='..#cases);phase='done';machine:exit()
        else phase='configure' end
    end
end
emu.register_frame_done(function()
    assert(subscriptions[1] and subscriptions[2]) -- retain notifier subscriptions
    if phase=='done' then return end
    local ok,err=pcall(step)
    if not ok then
        print(string.format('VDP2_RUNTIME context phase=%s pc=%08x tvmd=%04x bgon=%04x back=%04x',phase,main.state['PC'].value,space:read_u16(regbase),space:read_u16(regbase+0x20),space:read_u16(vram+0x7fffe)))
        print('VDP2_RUNTIME FAIL '..tostring(err));phase='done';machine:exit()
    end
end)
print('VDP2_RUNTIME starting synthetic mapped-register/pixel/save-manager fixture')
