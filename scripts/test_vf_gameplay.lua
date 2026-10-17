
local frame = 0
local in0 = manager.machine.ioport.ports[':IN.0']
local in1 = manager.machine.ioport.ports[':IN.1']

local coin1 = in0.fields['Coin 1']
local start1 = in0.fields['1 Player Start']
local p1_b1 = in1.fields['P1 Button 1']
local p1_b2 = in1.fields['P1 Button 2']
local p1_right = in1.fields['P1 Right']

emu.register_frame_done(function()
    frame = frame + 1

    -- Insert Coin at frame 200..210
    if frame >= 200 and frame <= 210 then
        coin1:set_value(1)
    else
        coin1:set_value(0)
    end

    -- Press 1P Start at frame 260..270
    if frame >= 260 and frame <= 270 then
        start1:set_value(1)
    else
        start1:set_value(0)
    end

    -- Character select: snapshot and press Button 1 (Punch) to select character at frame 380..390
    if frame == 370 then
        manager.machine.video:snapshot()
        print('Snapshot at Character Select (frame ' .. tostring(frame) .. ')')
    end
    if frame >= 380 and frame <= 390 then
        p1_b1:set_value(1)
    end

    -- Round 1 start snapshot
    if frame == 550 then
        manager.machine.video:snapshot()
        print('Snapshot at Round 1 start (frame ' .. tostring(frame) .. ')')
    end

    -- Walk forward and attack at frames 600..750
    if frame >= 600 and frame <= 800 then
        p1_right:set_value(1)
        if frame % 20 < 10 then
            p1_b1:set_value(1)
        else
            p1_b1:set_value(0)
        end
        if frame % 30 < 10 then
            p1_b2:set_value(1)
        else
            p1_b2:set_value(0)
        end
    else
        p1_right:set_value(0)
    end

    -- Fighting action snapshots
    if frame == 650 or frame == 720 or frame == 800 then
        manager.machine.video:snapshot()
        print('Snapshot during combat (frame ' .. tostring(frame) .. ')')
    end
end)
