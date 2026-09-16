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
            return cases[#cases]
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
        -- ST-058 pp.250–252: offset only the final top-screen result.
        -- Raw 50:50 red/green is 127,127,0. Offset-before-blend or an
        -- already-offset second image gives different independent colors.
        add('offset-after-blend',0x0102,1,15,0x8f7f00).offset={1,0,16,0,0,0,0,0}
        add('lower-offset-isolation',0x0102,1,15,0x7f7f00).offset={2,0,16,32,64,0,0,0}
        add('offset-signed-clamp',0x0102,1,15,0xff0000).offset={1,0,255,0x180,0,0,0,0}
        add('offset-bank-B',0x0102,1,15,0x7f7f1f).offset={1,1,0x100,0,0,0,0,31}
        -- ST-058 pp.189–195. Predicates describe retained pixels, not
        -- the active (suppressed) area: LOG=0 ORs active areas, LOG=1 ANDs.
        local windows={
            {0x00,'disabled-LOG0',function(a,b) return true end},
            {0x80,'disabled-LOG1',function(a,b) return false end},
            {0x03,'W0-inside',function(a,b) return a end},
            {0x83,'W0-inside-LOG1',function(a,b) return a end},
            {0x02,'W0-outside',function(a,b) return not a end},
            {0x82,'W0-outside-LOG1',function(a,b) return not a end},
            {0x0c,'W1-inside',function(a,b) return b end},
            {0x8c,'W1-inside-LOG1',function(a,b) return b end},
            {0x0f,'intersection',function(a,b) return a and b end},
            {0x8f,'union',function(a,b) return a or b end},
            {0x0b,'difference',function(a,b) return a and not b end},
            {0x8b,'mixed-union',function(a,b) return a or not b end},
        }
        for _,calculation in ipairs({false,true}) do
            for _,window in ipairs(windows) do
                local c=add((calculation and 'calculation-' or 'coverage-')..window[2],
                    0x0102,calculation and 1 or 0,15,0xff0000)
                c.window={control=window[1],keep=window[3],calculation=calculation}
            end
        end
        -- ST-058 pp.184–187: per-line X bounds retain the register Y bounds.
        -- Each window is tested crossing the physical end of VRAM; the other
        -- table has a disjoint ordinary base. Also include empty/inverted rows.
        for _,calculation in ipairs({false,true}) do
            for _,which in ipairs({3,7,9,10}) do
                local window=windows[which]
                local c=add((calculation and 'line-calculation-' or 'line-coverage-')..window[2],
                    0x0102,calculation and 1 or 0,15,0xff0000)
                c.window={control=window[1],keep=window[3],calculation=calculation,line=true,
                    wrap=(which==7 or which==10) and 1 or 0}
            end
        end
        -- ST-058 pp.117–119: upper-left source sample, independent H/V
        -- sizes, and VCSC suppression. Lower-screen pixels must not mosaic.
        for _,size in ipairs({{1,1},{3,5},{16,16},{7,2}}) do
            for _,blend in ipairs({false,true}) do
                local c=add('mosaic-'..size[1]..'x'..size[2]..(blend and '-blend' or ''),
                    0x0102,blend and 1 or 0,15,0xff0000)
                c.mosaic={width=size[1],height=size[2],blend=blend}
            end
        end
        -- ST-058 pp.172–174,231,241–244: LNCL is a selected second
        -- image, not a globally painted layer or a cumulative lower result.
        for _,per_line in ipairs({false,true}) do
            for _,kind in ipairs({'top','second-ratio','lower','disabled'}) do
                local control=kind=='second-ratio' and 0x0201 or kind=='lower' and 3 or kind=='disabled' and 2 or 1
                local c=add('line-color-'..kind..(per_line and '-rows' or '-single'),
                    0x0102,control,15|(31<<8),0xff0000)
                c.line_color={per_line=per_line,kind=kind}
            end
        end
        -- ST-058 pp.228–229,245–247: bitmap attributes, per-dot code
        -- selection, effective priority zero and subordinate CC enable.
        local function special(kind,mode,attribute,select,enabled,base,lower)
            local c=add('special-'..kind..'-'..mode..'-'..tostring(attribute)..'-'..select..'-'..tostring(enabled),
                (lower<<8)|base,enabled and 1 or 0,15,0xff0000)
            c.special={kind=kind,mode=mode,attribute=attribute,select=select,
                enabled=enabled,base=base,lower=lower}
        end
        for mode=0,2 do
            for _,attribute in ipairs({false,true}) do
                for select=0,1 do special('priority',mode,attribute,select,false,2,3) end
            end
        end
        special('priority',1,true,0,false,0,0) -- promote base zero to one
        special('priority',1,false,0,false,1,0) -- demote base one to zero
        for mode=0,3 do
            for _,attribute in ipairs({false,true}) do
                for select=0,1 do
                    for _,enabled in ipairs({false,true}) do
                        special('calculation',mode,attribute,select,enabled,2,1)
                    end
                end
            end
        end
        for select=0,1 do special('combined',2,true,select,true,2,3) end
        -- ST-058 pp.187–190: framebuffer MSB supplies SW for palette
        -- sprite types 2–7. Exercise both retained areas and window uses.
        for sprite_type=2,7 do
            for _,calculation in ipairs({false,true}) do
                for _,inside in ipairs({false,true}) do
                    local c=add('sprite-window-'..sprite_type..'-'..tostring(calculation)..'-'..tostring(inside),
                        0x0102,calculation and 1 or 0,15,0xff0000)
                    c.sprite_window={sprite_type=sprite_type,calculation=calculation,inside=inside}
                end
            end
        end
        -- All three enabled windows: cross every area polarity with both
        -- active-area LOG settings. Expected retained predicates use De Morgan.
        for area=0,7 do
            for logic=0,1 do
                for _,calculation in ipairs({false,true}) do
                    local c=add('mixed-window-'..area..'-'..logic..'-'..tostring(calculation),
                        0x0102,calculation and 1 or 0,15,0xff0000)
                    c.sprite_window={sprite_type=2,calculation=calculation,inside=(area&4)~=0,
                        mixed={area=area,logic=logic}}
                end
            end
        end
        -- ST-058 pp.238–240: opaque designated top/second screen,
        -- horizontal 1:1:2 filtering, normal resolution and CRAM mode 0.
        for source=0,1 do
            for _,second in ipairs({false,true}) do
                for _,enabled in ipairs({false,true}) do
                    local control=1|(source==0 and 0x2000 or 0x4000)|(second and 0x200 or 0)|(enabled and 0x8000 or 0)
                    local c=add('gradation-'..source..'-'..tostring(second)..'-'..tostring(enabled),
                        0x0102,control,15|(7<<8),0xff0000)
                    c.gradation={source=source,second=second,enabled=enabled}
                end
            end
        end
    end
end
assert(#cases==(composition and 466 or 46))
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
    if c.window then
        reg(0xc0,31*2);reg(0xc2,17);reg(0xc4,127*2);reg(0xc6,63)
        reg(0xc8,63*2);reg(0xca,31);reg(0xcc,255*2);reg(0xce,127)
        if c.window.calculation then reg(0xd6,c.window.control<<8)
        else reg(0xd0,c.window.control) end
    end
    if c.window and c.window.line then
        -- Keep bitmap and back data disjoint from the wrapping table. Map 2
        -- starts at 0x40000; the original map-4 fill is no longer displayed.
        reg(0x3c,0x0012)
        for offset=0,0xfffc,4 do space:write_u32(vram+0x40000+offset,dot) end
        space:write_u16(vram+0x5fffe,0x7c00);reg(0xac,2)
        c.table_bases={}
        for window=0,1 do
            local base=window==c.window.wrap and capacity-16 or 0x60000
            c.table_bases[window+1]=base
            for row=0,255 do
                local narrow=(row+window)%2==0
                local left,right=narrow and 31 or 63,narrow and 127 or 255
                if row%(window==0 and 7 or 8)==0 then left,right=200,100 end
                space:write_u32(vram+((base+row*4)%capacity),(left*2<<16)|(right*2))
            end
            local wordbase=base//2
            reg(0xd8+window*4,0x8000|(wordbase>>16));reg(0xda+window*4,wordbase&0xffff)
        end
    end
    if c.mosaic then
        -- Distinct top/bottom patterns expose accidental resampling of the
        -- already-composited output. Top zero is transparent; bottom is opaque.
        local top=0x80000%capacity
        for y=0,255 do
            for x=0,511,8 do
                local foreground,background=0,0
                for dotx=x,x+7 do
                    foreground=(foreground<<4)|((dotx//3+y//5)%3)
                    background=(background<<4)|(3+(dotx//7+y//11)%2)
                end
                space:write_u32(vram+top+y*256+x//2,foreground)
                space:write_u32(vram+0x20000+y*256+x//2,background)
            end
        end
        reg(0x22,((c.mosaic.height-1)<<12)|((c.mosaic.width-1)<<8)|1)
        reg(0x70,5);reg(0x74,7)
        -- A live, nonzero vertical-cell table must be ignored even for 1x1
        -- mosaic. Its nine-line displacement would change the expected colors.
        reg(0x9a,1);reg(0x9c,3);reg(0x9e,0)
        for offset=0,252,4 do space:write_u32(vram+0x60000+offset,0x00090000) end
    end
    if c.line_color then
        -- The wrapping table must not alias displayed bitmap or back data.
        reg(0x3c,0x0012)
        for offset=0,0xfffc,4 do space:write_u32(vram+0x40000+offset,dot) end
        space:write_u16(vram+0x5fffe,0x7c00);reg(0xac,2)
        space:write_u16(cram+10,0x7c00) -- pen 5 blue; pen 3 remains yellow
        c.line_color.base=capacity-8
        for row=0,255 do
            space:write_u16(vram+((c.line_color.base+row*2)%capacity),0xf800|(row%2==0 and 5 or 3))
        end
        local wordbase=c.line_color.base//2
        reg(0xa8,(c.line_color.per_line and 0x8000 or 0)|(wordbase>>16))
        reg(0xaa,wordbase&0xffff)
        reg(0xe8,c.line_color.kind=='lower' and 2 or 1)
        reg(0x10e,(31<<8)|7) -- distinct line, back and normal-layer ratios
    end
    if c.special then
        local top=0x80000%capacity
        for y=0,255 do
            for x=0,511,8 do
                local data=0
                for dotx=x,x+7 do data=(data<<4)|((dotx//4+y//3)%3) end
                space:write_u32(vram+top+y*256+x//2,data)
            end
        end
        for offset=0,0xfffc,4 do space:write_u32(vram+0x20000+offset,0x55555555) end
        space:write_u16(cram+2,0x801f) -- red with color-data MSB set
        space:write_u16(cram+4,0x03e0) -- green with color-data MSB clear
        space:write_u16(cram+10,0x7c00) -- opaque blue lower screen
        local t=c.special
        reg(0x24,t.select);reg(0x26,0x0102) -- code 2 in A, code 1 in B
        reg(0xea,t.kind=='calculation' and 0 or t.mode)
        reg(0xee,t.kind=='priority' and 0 or t.kind=='combined' and 3 or t.mode)
        reg(0x2c,t.attribute and (t.kind=='priority' and 0x20 or t.kind=='combined' and 0x30 or 0x10) or 0)
    end
    if c.sprite_window then
        -- Stop BIOS command drawing and automatic bank changes. The caller
        -- waits before touching the draw bank, then requests a manual change.
        space:write_u16(0x05d00004,0);space:write_u16(0x05d0000c,0)
        space:write_u16(0x05d00000,0);space:write_u16(0x05d00002,3)
        reg(0xe0,0x10|c.sprite_window.sprite_type)
        local control=0x20|(c.sprite_window.inside and 0x10 or 0)
        if c.sprite_window.mixed then
            local m=c.sprite_window.mixed
            control=control|0x0a|(m.area&1)|((m.area&2)<<1)|(m.logic<<7)
            -- Normal-resolution window X coordinates are doubled in registers.
            reg(0xc0,31*2);reg(0xc2,17);reg(0xc4,127*2);reg(0xc6,63)
            reg(0xc8,63*2);reg(0xca,31);reg(0xcc,255*2);reg(0xce,127)
        end
        if c.sprite_window.calculation then reg(0xd6,control<<8)
        else reg(0xd0,control) end
    end
    if c.gradation then
        reg(0x0e,0) -- Gradation requires CRAM mode 0, not the default mode 1.
        local base=c.gradation.source==0 and (0x80000%capacity) or 0x20000
        for y=0,255 do
            for x=0,511,8 do
                local value=0
                for sx=x,x+7 do value=(value<<4)|((sx//3+y//5)%4+1) end
                space:write_u32(vram+base+(y*512+x)//2,value)
            end
        end
    end
    if c.offset then
        for word,value in ipairs(c.offset) do reg(0x10e+word*2,value) end
    end
    reg(0,0x8000)
    c.dot=c.gradation and c.gradation.source==0 and 0x11122233 or c.special and 0x00001111 or c.mosaic and 0x00011122 or dot;c.capacity=capacity
    c.address=(c.table_bases or c.line_color) and 0x40000 or c.cell and 0x20000 or (0x80000%capacity)
end
local function paint_sprite_window(inverted)
    -- CPU framebuffer accesses target only the drawing bank (ST-013 p.38).
    -- 16-bit 512x256 mode: every stored pixel is either 0000 or 8000.
    for y=0,255 do
        for x=0,511,2 do
            local data=0
            for sx=x,x+1 do
                local inside=(sx//13+y//9)%2==0
                if inverted then inside=not inside end
                data=(data<<16)|(inside and 0x8000 or 0)
            end
            space:write_u32(0x05c80000+(y*512+x)*2,data)
        end
    end
    space:write_u16(0x05d00002,3)
end
local function pixels(expected)
    local c=cases[index]
    local xs=(c.window or c.mosaic or c.special or c.sprite_window) and {30,31,32,62,63,64,126,127,128,254,255,256} or {8,31,127,255}
    local ys=(c.window or c.mosaic or c.special or c.sprite_window) and {16,17,18,30,31,32,62,63,64,126,127,128} or {8,17,63,127}
    if c.gradation then
        -- Do not assign hardware expectations to unspecified left-edge history.
        xs={2,3,4,5,6,7,8,11,12,31,127,255};ys={8,17,63,127}
    end
    if c.line_color then ys={0,1,2,3,4,5,7,8,17,63,127,223} end
    for _,y in ipairs(ys) do
        for _,x in ipairs(xs) do
            local actual=screen:pixel(x,y)&0xffffff
            local want=expected
            if c.sprite_window and expected~=0x0000ff then
                local inside=(x//13+y//9)%2==0
                local keep=inside==c.sprite_window.inside
                if c.sprite_window.mixed then
                    local m=c.sprite_window.mixed
                    local a=(x>=31 and x<=127 and y>=17 and y<=63)==((m.area&1)~=0)
                    local b=(x>=63 and x<=255 and y>=31 and y<=127)==((m.area&2)~=0)
                    if m.logic==0 then keep=keep and a and b
                    else keep=keep or a or b end
                end
                if c.sprite_window.calculation then want=keep and 0x7f7f00 or 0xff0000
                else want=keep and 0xff0000 or 0x00ff00 end
            end
            if c.gradation and expected~=0x0000ff then
                local g=c.gradation
                local function color(sx) return ({0xff0000,0x00ff00,0xffff00,0xffffff})[(sx//3+y//5)%4+1] end
                local top=g.source==0 and color(x) or 0xff0000
                local lower=g.source==1 and color(x) or 0x00ff00
                local ratio=g.second and 7 or 15
                if g.enabled then
                    lower=0
                    for _,shift in ipairs({0,8,16}) do
                        local a=(color(x)>>shift)&255
                        local b=(color(x-1)>>shift)&255
                        local d=(color(x-2)>>shift)&255
                        lower=lower|((a//2+b//4+d//4)<<shift)
                    end
                    if g.source==0 then ratio=15 end
                end
                want=0
                for _,shift in ipairs({0,8,16}) do
                    want=want|(((((top>>shift)&255)*(31-ratio)+((lower>>shift)&255)*(ratio+1))//32)<<shift)
                end
            end
            if c.special and expected~=0x0000ff then
                local t=c.special
                local code=(x//4+y//3)%3
                local matches=code==(t.select==0 and 2 or 1)
                local priority=t.base
                if t.kind~='calculation' and t.mode~=0 then
                    priority=(t.base//2)*2+((t.attribute and (t.mode==1 or matches)) and 1 or 0)
                end
                want=0x0000ff
                if code~=0 and priority~=0 and priority>=t.lower then
                    local calculate=t.enabled
                    local mode=t.kind=='combined' and 3 or t.kind=='priority' and 0 or t.mode
                    if mode==1 then calculate=calculate and t.attribute
                    elseif mode==2 then calculate=calculate and t.attribute and matches
                    elseif mode==3 then calculate=calculate and code==1 end
                    if calculate then want=code==1 and 0x7f007f or 0x007f7f
                    else want=code==1 and 0xff0000 or 0x00ff00 end
                end
            end
            if c.line_color and expected~=0x0000ff then
                if c.line_color.kind=='disabled' then want=0xff0000
                elseif c.line_color.kind=='lower' then want=0x7f7f00
                else
                    local line=(c.line_color.per_line and y%2==1) and 0xffff00 or 0x0000ff
                    local ratio=c.line_color.kind=='second-ratio' and 7 or 15
                    want=0
                    for _,shift in ipairs({0,8,16}) do
                        local top=(0xff0000>>shift)&255
                        local under=(line>>shift)&255
                        want=want|(((top*(31-ratio)+under*(ratio+1))//32)<<shift)
                    end
                end
            end
            if c.mosaic and expected~=0x0000ff then
                local sx=(x//c.mosaic.width)*c.mosaic.width+5
                local sy=(y//c.mosaic.height)*c.mosaic.height+7
                local code=(sx//3+sy//5)%3
                local lower=(x//7+y//11)%2==0 and 0xffff00 or 0xffffff
                if code==0 then want=lower
                else
                    local upper=code==1 and 0xff0000 or 0x00ff00
                    want=upper
                    if c.mosaic.blend then
                        want=0
                        for _,shift in ipairs({0,8,16}) do
                            want=want|(((((upper>>shift)&255)+((lower>>shift)&255))//2)<<shift)
                        end
                    end
                end
            end
            if c.window and expected~=0x0000ff then
                local w0=x>=31 and x<=127 and y>=17 and y<=63
                local w1=x>=63 and x<=255 and y>=31 and y<=127
                if c.window.line then
                    -- Analytic screen-coordinate oracle; no table readback.
                    local narrow=x>=31 and x<=127
                    local wide=x>=63 and x<=255
                    w0=(y%2==0 and narrow or y%2==1 and wide) and y>=17 and y<=63 and y%7~=0
                    w1=(y%2==0 and wide or y%2==1 and narrow) and y>=31 and y<=127 and y%8~=0
                end
                local keep=c.window.keep(w0,w1)
                if c.window.calculation then want=keep and 0x7f7f00 or 0xff0000
                else want=keep and 0xff0000 or 0x00ff00 end
            end
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
    if phase=='configure' then
        configure(cases[index]);phase=cases[index].sprite_window and 'sprite-draw' or 'render';wait=3
    elseif wait>0 then wait=wait-1
    elseif phase=='sprite-draw' then
        paint_sprite_window(false);phase='render';wait=3
    elseif phase=='render' then
        pixels(cases[index].expected or 0xff0000);reference=screen:pixels();assert(#reference>0)
        saved=false;os.remove(output..'/runtime.sta');machine:save(output..'/runtime.sta');phase='save';wait=3
    elseif phase=='save' then
        assert(saved,'save notification missing')
        local f=assert(io.open(output..'/runtime.sta','rb'));assert(f:seek('end')>1000);f:close()
        space:write_u32(vram+cases[index].address,0);space:write_u16(cram+2,0x03e0)
        if cases[index].table_bases then
            for _,base in ipairs(cases[index].table_bases) do
                for row=0,255 do space:write_u32(vram+((base+row*4)%cases[index].capacity),0) end
            end
        end
        if cases[index].line_color then
            for row=0,255 do
                space:write_u16(vram+((cases[index].line_color.base+row*2)%cases[index].capacity),0)
            end
            reg(0xa8,0);reg(0xaa,0);reg(0xe8,0);reg(0x10e,0)
        end
        reg(0x24,0);reg(0x26,0);reg(0x2c,0);reg(0xea,0);reg(0xee,0)
        reg(0x22,0);reg(0xec,0)
        for offset=0xc0,0xde,2 do reg(offset,0) end
        for offset=0x110,0x11e,2 do reg(offset,0) end
        reg(0xf8,0);reg(0xfa,0);reg(0xfc,0);reg(0x0e,0);reg(6,cases[index].large and 0 or 0x8000)
        if cases[index].sprite_window then
            paint_sprite_window(true);phase='sprite-mutate-second'
        else phase='mutated' end
        wait=3
    elseif phase=='sprite-mutate-second' then
        -- The first change exposes the previous display bank to CPU writes.
        -- Overwrite it too: restoring ownership alone must not pass replay.
        paint_sprite_window(true);phase='mutated';wait=3
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
