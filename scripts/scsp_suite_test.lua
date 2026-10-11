-- license:BSD-3-Clause
-- Read the supplied scsptest text map; also capture ordinary demo output.
local m=manager.machine
local mem=m.devices[':maincpu'].spaces.program
local dir=m.options.entries['snapshot_directory']:value()
local kind=os.getenv('SCSP_DISC_KIND') or 'suite'
local frame=0
local function button(mask,value)
    local found=false
    for tag,port in pairs(m.ioport.ports) do
        if tag:find('ctrl1') then for _,field in pairs(port.fields) do
            if field.mask==mask then field:set_value(value);found=true end
        end end
    end
    assert(found,'Missing controller field')
end
scsp_suite_subscription=emu.add_machine_frame_notifier(function()
    frame=frame+1
    if kind=='cronsf' then
        -- Root contains Tests; enter it and load the first bundled NSF.
        if frame==900 or frame==960 then button(0x400,1) end
        if frame==905 or frame==965 then button(0x400,0) end
        -- Play each bundled file, returning and moving down one entry.
        for song=1,4 do
            local base=960+song*720
            if frame==base then button(0x100,1) end
            if frame==base+30 then button(0x100,0) end
            if frame==base+60 then button(0x2000,1) end
            if frame==base+65 then button(0x2000,0) end
            if frame==base+120 then button(0x400,1) end
            if frame==base+125 then button(0x400,0) end
        end
    end
    if frame%300~=0 then return end
    m.screens[':screen']:snapshot(string.format('%s/frame-%04d.png',dir,frame))
    print(string.format('SCSP_DISC frame=%d PC=%08x R1=%08x TVMD=%04x IST=%08x SCIPD=%04x',frame,
        m.devices[':maincpu'].state.CURPC.value,m.devices[':maincpu'].state.R1.value,
        mem:read_u16(0x05f80000),mem:read_u32(0x05fe00a4),mem:read_u16(0x05b00420)))
    if kind=='cronsf' then
        local cpu=m.devices[':maincpu']
        local slave=m.devices[':slave']
        print(string.format('CRO SLAVE PC=%08x SR=%08x VBR=%08x ENTRY=%08x',slave.state.CURPC.value,slave.state.SR.value,slave.state.VBR.value,mem:read_u32(0x06000250)))
        print(string.format('CRO SR=%08x R2=%08x IMS=%08x PCWORDS=%04x %04x %04x %04x',cpu.state.SR.value,cpu.state.R2.value,
            mem:read_u32(0x05fe00a0),mem:read_u16(cpu.state.CURPC.value),mem:read_u16(cpu.state.CURPC.value+2),
            mem:read_u16(cpu.state.CURPC.value+4),mem:read_u16(cpu.state.CURPC.value+6)))
    end
    if kind=='adpcm' then return end
    local lines={}
    for y=0,30 do
        local line=''
        for x=0,(kind=='suite' and 79 or 39) do
            local a=x+(kind=='suite' and 4 or 2)
            local base=kind=='suite' and 0x05e30000 or 0x05e20000
            local v=mem:read_u32(base+(((y+(a&0x40))<<6)+(a&63))*4)&255
            line=line..string.char(v>=32 and v<127 and v or 32)
        end
        lines[#lines+1]=line
    end
    local text=table.concat(lines,'\n')
    if kind=='cronsf' then
        for _,base in ipairs({0x05e00000,0x05e08000}) do
            print(string.format('CRO TEXT BANK %08x',base))
            for y=0,20 do
                local line=''
                for x=0,39 do
                    local a=x+2
                    local word=mem:read_u32(base+((((y*2)+(a&0x40))<<6)+(a&63))*4)&0xffff
                    local ch=((word-0x1000)>>1)&255
                    line=line..string.char(ch>=32 and ch<127 and ch or 32)
                end
                if line:find('%S') then print(line) end
            end
        end
        return
    end
    if not text:find('scsptest') then return end
    print(text)
    if text:find('Done%.') then
        local f=assert(io.open(dir..'/results.txt','w'));f:write(text);f:close()
        print(text:find('FAIL') and 'SCSP_SUITE_FAIL' or 'SCSP_SUITE_PASS')
        m:exit()
    end
end)
