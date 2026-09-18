local m=manager.machine
local done=false
emu.register_frame_done(function()
    if done then return end
    done=true
    local items=m.devices[":"].items
    local found={}
    for name,index in pairs(items) do
        local field=name:match('([^/]+)$')
        if field=='m_system_halt' or field=='m_prev_hint' or field=='m_prev_vint' then
            found[field]=true
            print('SYNC_STATE registered '..field)
        end
    end
    assert(found.m_system_halt,'wrong/missing root save-item enumeration')
    for _,field in ipairs({'m_prev_hint','m_prev_vint'}) do
        print('SYNC_STATE '..field..' '..(found[field] and 'registered' or 'MISSING'))
    end
    m:exit()
end)
