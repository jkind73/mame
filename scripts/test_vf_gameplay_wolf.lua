
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

    -- Move right 3 times on character select
    -- Tap 1: frame 310..315
    if frame >= 310 and frame <= 315 then
        p1_right:set_value(1)
    -- Tap 2: frame 330..335
    elseif frame >= 330 and frame <= 335 then
        p1_right:set_value(1)
    -- Tap 3: frame 350..355
    elseif frame >= 350 and frame <= 355 then
        p1_right:set_value(1)
    else
        p1_right:set_value(0)
    end

    -- Snapshot Wolf profile at frame 370
    if frame == 370 then
        manager.machine.video:snapshot()
        print('Snapshot at Wolf profile (frame ' .. tostring(frame) .. ')')
    end

    -- Select Wolf at frame 380..390
    if frame >= 380 and frame <= 390 then
        p1_b1:set_value(1)
    else
        p1_b1:set_value(0)
    end

    -- Round 1 start snapshot
    if frame == 560 then
        manager.machine.video:snapshot()
        print('Snapshot at Round 1 start (frame ' .. tostring(frame) .. ')')
    end

    -- Fight at frame 600..750
    if frame >= 600 and frame <= 750 then
        p1_right:set_value(1)
        if frame % 20 < 10 then
            p1_b1:set_value(1)
        else
            p1_b1:set_value(0)
        end
    end

    if frame == 650 or frame == 720 then
        manager.machine.video:snapshot()
        print('Snapshot during Wolf combat (frame ' .. tostring(frame) .. ')')
    end
end)
