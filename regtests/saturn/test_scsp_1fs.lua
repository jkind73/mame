-- license:BSD-3-Clause
-- SCSP 1Fs (sample tick) interrupt: SCIPD/MCIPD bit 10 must be requested once per output sample (44.1 kHz), not once
-- per sound-stream update batch (ST-077 interrupt table: source 10, "sample interval").
--
-- The master SH-2 is parked on a polling loop that watches the SCU IST "sound request" bit, which the SCSP main-CPU
-- interrupt line sets, clears it and counts. The loop never touches the SCSP (any SCSP access would itself update
-- the sound stream and hide the batching), MCIEB bit 10 is enabled once from outside. Over a fixed emulated
-- interval the count must equal the number of samples produced.
--
--   mame saturnjp -rompath <roms> -nothrottle -video none -sound none -autoboot_script test_scsp_1fs.lua
local machine = manager.machine
local cpu = machine.devices[':maincpu']
local mem = cpu.spaces['program']

local CODE, COUNTER = 0x06000100, 0x06000200
local MEASURE = 1.0 -- emulated seconds
local RATE = 44100

-- SH-2 program at CODE:
--   mov.l ist,r1 ; mov.l ct,r3 ; mov #0,r4 ; mov.l notmask,r6 ; mov #0x40,r7
-- loop: mov.l @r1,r5 ; tst r5,r7 ; bt loop ; mov.l r6,@r1 ; add #1,r4 ; mov.l r4,@r3 ; bra loop ; nop
local program = {
    0xD106, 0xD307, 0xE400, 0xD607, 0xE740,
    0x6512, 0x2758, 0x89FC, 0x2162, 0x7401, 0x2342, 0xAFF8, 0x0009,
}
local audiocpu = machine.devices[':audiocpu']
local function load_program()
    -- park the 68K too: the BIOS sound driver rewrites the SCSP interrupt registers
    mem:write_u16(0x05A00400, 0x60FE) -- bra.s *
    audiocpu.state['PC'].value = 0x400
    audiocpu.state['SR'].value = 0x2700
    for i, w in ipairs(program) do mem:write_u16(CODE + (i - 1) * 2, w) end
    mem:write_u16(CODE + 26, 0x0009) -- pad to the literal pool
    mem:write_u32(CODE + 28, 0x25FE00A4) -- SCU IST, cache-through
    mem:write_u32(CODE + 32, COUNTER)
    mem:write_u32(CODE + 36, 0xFFFFFFBF) -- clear IST bit 6 (sound request) only
    mem:write_u32(COUNTER, 0)
    -- bus-level writes from the script do not go through the CPU's cache-through alias handling: use the base address
    mem:write_u16(0x05B0042A, 0x0400) -- MCIEB: sample interval interrupt to the main CPU
end

local phase, t0, c0 = 'boot', 0, 0
emu.register_frame_done(function()
    if phase == 'boot' then
        if emu.time() < 3.0 then return end
        load_program()
        cpu.state['PC'].value = CODE
        cpu.state['SR'].value = 0xF0
        phase = 'settle'
        t0 = emu.time()
        return
    end
    if phase == 'settle' then
        if emu.time() - t0 < 0.1 then return end
        t0, c0 = emu.time(), mem:read_u32(COUNTER)
        phase = 'measure'
        return
    end
    if phase == 'measure' and emu.time() - t0 >= MEASURE then
        local dt = emu.time() - t0
        local n = mem:read_u32(COUNTER) - c0
        local expect = dt * RATE
        local ok = math.abs(n - expect) <= expect * 0.02
        print(string.format('SCSP-1FS count=%d expected=%.0f over %.3f s: %s', n, expect, dt, ok and 'PASS' or 'FAIL'))
        machine:exit()
    end
end)
