-- license:BSD-3-Clause
-- Unmodified BIOS execution/replay; no injected register or memory writes.
local machine=manager.machine
local screen=assert(machine.screens[':screen'])
local main=assert(machine.devices[':maincpu'])
local out=assert(os.getenv('SATURN_RUNTIME_OUTPUT'))
local phase,ticks,save_time,restored,reference='boot',0,nil,false,nil
local subscriptions={}
subscriptions[1]=emu.add_machine_pre_save_notifier(function() save_time=emu.time() end)
subscriptions[2]=emu.add_machine_post_load_notifier(function() restored=true end)
local function capture()
    local pixels,w,h=screen:pixels()
    assert(w>0 and h>0 and #pixels==w*h*4,'invalid screen')
    return {pixels=pixels,time=emu.time(),pc=main.state['PC'].value}
end
local function step()
    ticks=ticks+1
    if phase=='boot' and ticks>=tonumber(os.getenv('SATURN_BIOS_FRAMES') or '900') then
        assert(screen:snapshot(out..'/bios-boot.png')==nil)
        os.remove(out..'/bios.sta');machine:save(out..'/bios.sta');phase='advance'
    elseif phase=='advance' and save_time and emu.time()>=save_time+0.5 then
        reference=capture()
        local visible=false
        local first=string.unpack('I4',reference.pixels)&0xffffff
        for pos=5,#reference.pixels,4 do
            if (string.unpack('I4',reference.pixels,pos)&0xffffff)~=first then visible=true;break end
        end
        assert(visible,'BIOS output is blank; replay equality is not visual boot acceptance')
        assert(screen:snapshot(out..'/bios-reference.png')==nil)
        local f=assert(io.open(out..'/bios.sta','rb'));f:close()
        machine:load(out..'/bios.sta');phase='replay'
    elseif phase=='replay' and restored and emu.time()>=reference.time-0.000001 then
        local replay=capture()
        assert(math.abs(replay.time-reference.time)<0.000001,'replay timing differs')
        assert(replay.pc==reference.pc,'replay SH-2 PC differs')
        assert(replay.pixels==reference.pixels,'replay screen differs')
        assert(screen:snapshot(out..'/bios-replay.png')==nil)
        print(string.format('BIOS_RUNTIME PASS system=%s time=%.9f pc=%08x full-image replay identical',machine.system.name,replay.time,replay.pc))
        phase='done';machine:exit()
    end
end
emu.register_frame_done(function()
    assert(subscriptions[1] and subscriptions[2])
    if phase=='done' then return end
    local ok,err=pcall(step)
    if not ok then print('BIOS_RUNTIME FAIL '..tostring(err));phase='done';machine:exit() end
end)
print('BIOS_RUNTIME starting unmodified BIOS boot/replay smoke')
