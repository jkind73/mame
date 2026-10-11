-- license:BSD-3-Clause
-- Real-disc race exploration/replay. Screenshots and command lists require review.
local m = manager.machine
local root = assert(os.getenv('VKYOUTE2_RACE_OUTPUT'))
local frame, bad, token = 0, 0, -1
local fields, events, taps = {{}, {}}, {}, {}
for tag, port in pairs(m.ioport.ports) do
    local player = tag:find('ctrl1') and 1 or (tag:find('ctrl2') and 2 or nil)
    if player then for _, field in pairs(port.fields) do table.insert(fields[player], field) end end
end
local function event(f, p1, p2, duration)
    table.insert(events, {frame=f, masks={p1,p2}, duration=duration})
end
local plan = os.getenv('VKYOUTE2_RACE_INPUTS')
if plan then
    for line in io.lines(plan) do
        local f,a,b,d = line:match('^(%d+),(%x+),(%x+),(%d+)')
        if f then event(tonumber(f),tonumber(a,16),tonumber(b,16),tonumber(d)) end
    end
end
local applied = assert(io.open(root..'/input-applied.csv','w'))
applied:write('frame,p1,p2,duration\n')
for _, tag in ipairs({':maincpu', ':slave'}) do
    taps[#taps+1] = m.devices[tag].spaces.program:install_write_tap(0x01000000,0x01ffffff,'race invalid init',function(a,v,mask)
        if mask == 0xffffffff then
            bad=bad+1
            if bad <= 10 then print(string.format('BAD_INIT frame=%d cpu=%s address=%08x',frame,tag,a));io.stdout:flush() end
        end
    end)
end
local mem = m.devices[':maincpu'].spaces.program
local function coordinate(v)
    v=v&0x1fff
    return v>=0x1000 and v-0x2000 or v
end
local function commands()
    local file=assert(io.open(string.format(root..'/frame-%05d-vdp1.csv',frame),'w'))
    file:write('address,control,link,mode,colour,source,size,xa,ya,xb,yb,xc,yc,xd,yd\n')
    local address,ret,count,polygons,invalid,ended,loop = 0,nil,0,0,0,false,false
    local seen={}
    for _=1,8192 do
        if seen[address] then loop=true;break end
        seen[address]=true
        local w={}
        for i=0,15 do w[i]=mem:read_u16(0x05c00000+address+2*i) end
        count=count+1
        file:write(string.format('%05x,%04x,%04x,%04x,%04x,%04x,%04x',address,w[0],w[1],w[2],w[3],w[4],w[5]))
        for i=6,13 do file:write(','..coordinate(w[i])) end
        file:write('\n')
        if w[0]&0x8000~=0 then ended=true;break end
        if w[0]&0x4000==0 then
            if w[0]&15>=12 then invalid=invalid+1;break end
            if w[0]&15==2 or w[0]&15==3 or w[0]&15==4 then polygons=polygons+1 end
        end
        local next=(address+32)&0x7ffff
        local jump=(w[0]>>12)&3
        if jump==1 then next=((w[1]<<3)&~31)&0x7ffff
        elseif jump==2 then if not ret then ret=next end;next=((w[1]<<3)&~31)&0x7ffff
        elseif jump==3 and ret then next=ret;ret=nil end
        address=next
    end
    file:close()
    return count,polygons,invalid,ended,loop
end
local finished=false
local function finish()
    if finished then return end
    finished=true
    for p=1,2 do for _,field in ipairs(fields[p]) do field:set_value(0) end end
    applied:close()
    print(string.format('RACE_RUN_COMPLETE frame=%d bad_init=%d',frame,bad));io.stdout:flush()
    m:exit()
end
local every=tonumber(os.getenv('VKYOUTE2_RACE_EVERY'))or 180
local limit=tonumber(os.getenv('VKYOUTE2_RACE_FRAMES'))or 36000
race_capture=emu.add_machine_frame_notifier(function()
    frame=frame+1
    if frame%15==0 then
        local file=io.open(root..'/control.txt','r')
        local value=file and file:read('*a')or ''
        if file then file:close() end
        if value:find('exit')then finish();return end
        local id,a,b,d=value:match('^(%d+)%s+(%x+)%s+(%x+)%s+(%d+)')
        if id and tonumber(id)~=token then
            token=tonumber(id);a=tonumber(a,16);b=tonumber(b,16);d=tonumber(d)
            event(frame,a,b,d)
            applied:write(string.format('%d,%04x,%04x,%d\n',frame,a,b,d));applied:flush()
            print(string.format('INPUT frame=%d p1=%04x p2=%04x duration=%d',frame,a,b,d));io.stdout:flush()
        end
    end
    local masks={0,0}
    for _,e in ipairs(events)do
        if frame>=e.frame and frame<e.frame+e.duration then
            for p=1,2 do masks[p]=masks[p]|e.masks[p] end
        end
    end
    for p=1,2 do for _,field in ipairs(fields[p])do field:set_value(field.mask&masks[p]~=0 and 1 or 0)end end
    if frame%every==0 then
        m.screens[':screen']:snapshot(string.format(root..'/frame-%05d.png',frame))
        local count,polygons,invalid,ended,loop=commands()
        print(string.format('RACE_FRAME frame=%d time=%.6f master=%08x slave=%08x commands=%d polygons=%d invalid=%d ended=%s loop=%s bad=%d',frame,m.time:as_double(),m.devices[':maincpu'].state.PC.value,m.devices[':slave'].state.PC.value,count,polygons,invalid,tostring(ended),tostring(loop),bad));io.stdout:flush()
    end
    if frame>=limit then finish()end
end)
