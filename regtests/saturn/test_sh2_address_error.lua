-- license:BSD-3-Clause
-- SH-2 CPU address errors (SH7604 hardware manual 4.3, Table 4.6, Table 4.10). Every case runs a few instructions
-- on the master SH-2 with a vector 9 handler that spins, then checks whether the handler was entered and what
-- was stacked. Run it in both cores and compare the output:
--
--   mame saturnjp -rompath <roms> -nothrottle -video none -sound none -drc   -autoboot_script test_sh2_address_error.lua
--   mame saturnjp -rompath <roms> -nothrottle -video none -sound none -nodrc -autoboot_script test_sh2_address_error.lua
--
-- PC is expected as the start address of the instruction that would run after the faulting one (the branch target
-- when the fault is in a delay slot, the fetch address itself for a fetch error).
local machine = manager.machine
local cpu = machine.devices[':maincpu']
local mem = cpu.spaces['program']

local CODE, HANDLER, VBR, SP0 = 0x06000400, 0x06000800, 0x06001000, 0x06000F00
local END_LOOP = CODE + 0x20
local NOP = 0x0009
-- parked loops use SETT / BT self so that no delayed branch is pending when the script rewrites PC
local SETT, BTSELF = 0x0018, 0x89FE
local function park(address)
    mem:write_u16(address, SETT)
    mem:write_u16(address + 2, BTSELF)
end

local cases = {
    { name = 'word read at odd address', code = { 0x6011 }, r = { [1] = 0x06000601 }, ae = true, pc = CODE + 2 },
    { name = 'longword write off a longword boundary', code = { 0x2102 }, r = { [1] = 0x06000602 }, ae = true, pc = CODE + 2 },
    { name = 'longword read off a longword boundary', code = { 0x6012 }, r = { [1] = 0x06000601 }, ae = true, pc = CODE + 2 },
    { name = 'aligned word read', code = { 0x6011 }, r = { [1] = 0x06000600 }, ae = false },
    { name = 'aligned longword write', code = { 0x2102 }, r = { [1] = 0x06000600 }, ae = false },
    { name = 'byte read at an odd address is legal', code = { 0x6010 }, r = { [1] = 0x06000601 }, ae = false },
    { name = 'fault in a delay slot is taken after the branch', code = { 0xA00E, 0x2102 }, r = { [1] = 0x06000602 }, ae = true, pc = END_LOOP },
    { name = 'fetch from an odd address (JMP)', code = { 0x422B, NOP }, r = { [2] = 0x06000501 }, ae = true, pc = 0x06000501 },
    { name = 'fetch from the on-chip peripheral space (JMP)', code = { 0x422B, NOP }, r = { [2] = 0xFFFFFE00 }, ae = true, pc = 0xFFFFFE00 },
    { name = 'byte read in FFFFFF00-FFFFFFFF', code = { 0x6010 }, r = { [1] = 0xFFFFFF10 }, ae = true, pc = CODE + 2 },
    { name = 'word read in FFFFFF00-FFFFFFFF is legal', code = { 0x6011 }, r = { [1] = 0xFFFFFF10 }, ae = false },
    { name = 'longword read in FFFFFE00-FFFFFEFF', code = { 0x6012 }, r = { [1] = 0xFFFFFE10 }, ae = true, pc = CODE + 2 },
    { name = 'byte read in FFFFFE00-FFFFFEFF is legal', code = { 0x6010 }, r = { [1] = 0xFFFFFE10 }, ae = false },
    { name = 'TAS.B of the cache data array', code = { 0x411B }, r = { [1] = 0xC0000010 }, ae = true, pc = CODE + 2 },
    { name = 'TAS.B of the associative purge space', code = { 0x411B }, r = { [1] = 0x40000010 }, ae = true, pc = CODE + 2 },
    { name = 'TAS.B of work RAM is legal', code = { 0x411B }, r = { [1] = 0x06000600 }, ae = false },
}

local failures, index, phase, frames = 0, 0, 'boot', 0
local list = os.getenv('SH2AE_LIST')
if list then
    local picked = {}
    for n in list:gmatch('%d+') do picked[#picked + 1] = cases[tonumber(n)] end
    cases = picked
end

local function start_case(c)
    for i = 0, 0x40 - 1 do mem:write_u16(CODE + i * 2, NOP) end
    for i, w in ipairs(c.code) do mem:write_u16(CODE + (i - 1) * 2, w) end
    park(END_LOOP)
    park(HANDLER)
    mem:write_u32(VBR + 9 * 4, HANDLER)
    mem:write_u32(VBR + 4 * 4, HANDLER + 0x10) -- general illegal instruction: reported, not expected
    mem:write_u32(VBR + 6 * 4, HANDLER + 0x20) -- illegal slot instruction
    for _, off in ipairs({ 0x10, 0x20 }) do
        park(HANDLER + off)
    end
    mem:write_u32(SP0 - 4, 0xDEADBEEF)
    mem:write_u32(SP0 - 8, 0xDEADBEEF)
    for i = 0, 15 do cpu.state['R' .. i].value = 0 end
    for reg, value in pairs(c.r) do cpu.state['R' .. reg].value = value end
    cpu.state['R15'].value = SP0
    cpu.state['VBR'].value = VBR
    cpu.state['SR'].value = 0xF0
    cpu.state['PC'].value = CODE
end

local function check_case(c)
    local pc = cpu.state['PC'].value
    local in_handler = pc >= HANDLER and pc <= HANDLER + 2
    local ok, detail = true, ''
    if c.ae then
        local sp = cpu.state['R15'].value
        local sp_expect = SP0 - 8
        local stacked_pc, stacked_sr = mem:read_u32(sp), mem:read_u32(sp + 4)
        ok = in_handler and sp == sp_expect and stacked_pc == c.pc and (stacked_sr & ~1) == 0xF0
        detail = string.format('handler=%s sp=%08x stacked pc=%08x (want %08x) sr=%08x', tostring(in_handler), sp, stacked_pc, c.pc, stacked_sr)
    else
        ok = not in_handler and pc >= END_LOOP and pc <= END_LOOP + 2
        detail = string.format('pc=%08x handler=%s', pc, tostring(in_handler))
    end
    if os.getenv('SH2AE_DEBUG') then print(string.format('  pc=%08x sp=%08x vbr=%08x r1=%08x sr=%08x', pc, cpu.state['R15'].value, cpu.state['VBR'].value, cpu.state['R1'].value, cpu.state['SR'].value)) end
    print(string.format('SH2-AE %-52s %s  %s', c.name, ok and 'PASS' or 'FAIL', detail))
    if not ok then failures = failures + 1 end
end

emu.register_frame_done(function()
    if phase == 'boot' then
        if emu.time() < 3.0 then return end
        phase = 'setup'
    end
    if phase == 'setup' then
        index = index + 1
        if index > #cases then
            print(failures == 0 and 'SH2-AE ALL PASS' or ('SH2-AE FAILURES: ' .. failures))
            machine:exit()
            return
        end
        start_case(cases[index])
        frames = 0
        phase = 'run'
        return
    end
    frames = frames + 1
    if os.getenv('SH2AE_DEBUG') then print(string.format('  frame %d pc=%08x sp=%08x', frames, cpu.state['PC'].value, cpu.state['R15'].value)) end
    if frames >= 2 then
        check_case(cases[index])
        phase = 'setup'
    end
end)
