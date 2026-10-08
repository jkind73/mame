-- license:BSD-3-Clause
-- Replay ordinary input fields for reproducible game tests.
-- SATURN_SURVEY_INPUTS names a text file: frame port mask value (mask in hex).
dofile('scripts/saturn_game_survey.lua')
local events = {}
for line in io.lines(assert(os.getenv('SATURN_SURVEY_INPUTS'))) do
    local f, port, mask, value = line:match('^(%d+)%s+(%S+)%s+(%x+)%s+(%d+)')
    if f then
        f = tonumber(f)
        events[f] = events[f] or {}
        table.insert(events[f], {port=port,mask=tonumber(mask,16),value=tonumber(value)})
    end
end
local frame = 0
saturn_game_inputs_subscription = emu.add_machine_frame_notifier(function()
    frame = frame + 1
    for _,event in ipairs(events[frame] or {}) do
        local port = assert(manager.machine.ioport.ports[event.port], 'Missing input port '..event.port)
        local found = false
        for name,field in pairs(port.fields) do
            if field.mask == event.mask then
                field:set_value(event.value)
                print(string.format('INPUT frame=%d port=%s field=%s value=%d', frame,event.port,name,event.value))
                found = true
            end
        end
        assert(found, 'Missing input mask')
    end
end)
