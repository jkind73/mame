-- license:BSD-3-Clause
-- SH-2 exception entry, interpreter versus DRC (SH7604 hardware manual 4.5: TRAPA, general illegal instruction,
-- illegal slot instruction; 4.3: address error). Every sequence is run on the master SH-2 with a distinct parked
-- handler per vector; the script reports which vector was taken and what was stacked. The expected values come from
-- the manual, so a passing run in both cores proves parity as well as correctness:
--
--   mame saturn... -drc   -autoboot_script test_sh2_exception_parity.lua
--   mame saturn... -nodrc -autoboot_script test_sh2_exception_parity.lua
local machine = manager.machine
local cpu = machine.devices[':maincpu']
local mem = cpu.spaces['program']

local CODE0, VBR, SP0 = 0x06010000, 0x06001000, 0x06000F00
local HANDLER_BASE = 0x06000800
-- every case runs at its own address: the DRC keeps compiled blocks that a script write does not invalidate
local code_base = CODE0
local function rel(n) return { rel = n } end
local function resolve(v) if type(v) == 'table' then return code_base + v.rel end return v end
local END_LOOP = rel(0x20)
local NOP = 0x0009
local SETT, BTSELF = 0x0018, 0x89FE
local function park(address)
    mem:write_u16(address, SETT)
    mem:write_u16(address + 2, BTSELF)
end
local function handler(vector) return HANDLER_BASE + vector * 0x10 end
local VECTORS = { 4, 6, 9, 0x20 }

-- vector: expected vector or nil for "no exception"; pc: expected stacked PC
local cases = {
    { name = 'TRAPA #20h', code = { 0xC320 }, vector = 0x20, pc = rel(2) },
    { name = 'TRAPA #20h in a delay slot position is illegal slot', code = { 0xA002, 0xC320 }, vector = 6, pc = rel(8) },
    { name = 'undefined code', code = { 0xF000 }, vector = 4, pc = rel(0) },
    { name = 'undefined code after other instructions', code = { NOP, NOP, 0xF000 }, vector = 4, pc = rel(4) },
    { name = 'undefined code after one NOP', code = { NOP, 0xF000 }, vector = 4, pc = rel(2) },
    { name = 'undefined code after MOV #1,R0', code = { 0xE001, 0xF000 }, vector = 4, pc = rel(2) },
    { name = 'TRAPA after two NOPs', code = { NOP, NOP, 0xC320 }, vector = 0x20, pc = rel(6) },
    { name = 'BRA in a delay slot', code = { 0xA002, 0xA001 }, vector = 6, pc = rel(8) },
    { name = 'JMP @R2 in a delay slot', code = { 0xA002, 0x422B }, r = { [2] = rel(0x20) }, vector = 6, pc = rel(8) },
    { name = 'BT in a delay slot', code = { 0xA002, 0x8901 }, vector = 6, pc = rel(8) },
    { name = 'undefined code in a delay slot', code = { 0xA002, 0xF000 }, vector = 6, pc = rel(8) },
    { name = 'legal instruction in a delay slot', code = { 0xA00E, NOP }, vector = nil },
    { name = 'BSR then odd SP access in the delay slot', code = { 0xB00E, 0x2102 }, r = { [1] = 0x06000602 }, vector = 9, pc = rel(0x20) },
}

local failures, index, phase, frames = 0, 0, 'boot', 0
local list = os.getenv('SH2EX_LIST')
if list then
    local picked = {}
    for n in list:gmatch('%d+') do picked[#picked + 1] = cases[tonumber(n)] end
    cases = picked
end

local function start_case(c)
    code_base = CODE0 + (index - 1) * 0x100
    for i = 0, 0x40 - 1 do mem:write_u16(code_base + i * 2, NOP) end
    for i, w in ipairs(c.code) do mem:write_u16(code_base + (i - 1) * 2, w) end
    park(resolve(END_LOOP))
    for _, v in ipairs(VECTORS) do
        park(handler(v))
        mem:write_u32(VBR + v * 4, handler(v))
    end
    mem:write_u32(SP0 - 4, 0xDEADBEEF)
    mem:write_u32(SP0 - 8, 0xDEADBEEF)
    for i = 0, 15 do cpu.state['R' .. i].value = 0 end
    for reg, value in pairs(c.r or {}) do cpu.state['R' .. reg].value = resolve(value) end
    cpu.state['R15'].value = SP0
    cpu.state['VBR'].value = VBR
    cpu.state['SR'].value = 0xF0
    cpu.state['PC'].value = code_base
end

local function taken_vector(pc)
    for _, v in ipairs(VECTORS) do
        if pc >= handler(v) and pc <= handler(v) + 2 then return v end
    end
    return nil
end

local function check_case(c)
    local pc = cpu.state['PC'].value
    local vector = taken_vector(pc)
    local ok, detail
    if c.vector then
        local sp = cpu.state['R15'].value
        local stacked_pc, stacked_sr = mem:read_u32(sp), mem:read_u32(sp + 4)
        ok = vector == c.vector and sp == SP0 - 8 and stacked_pc == resolve(c.pc) and (stacked_sr & ~1) == 0xF0
        detail = string.format('vector=%s sp=%08x stacked pc=%08x (want %08x) sr=%08x', tostring(vector), sp, stacked_pc, resolve(c.pc), stacked_sr)
    else
        ok = vector == nil and pc >= resolve(END_LOOP) and pc <= resolve(END_LOOP) + 2
        detail = string.format('pc=%08x vector=%s', pc, tostring(vector))
    end
    print(string.format('SH2-EX %-52s %s  %s', c.name, ok and 'PASS' or 'FAIL', detail))
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
            print(failures == 0 and 'SH2-EX ALL PASS' or ('SH2-EX FAILURES: ' .. failures))
            machine:exit()
            return
        end
        start_case(cases[index])
        frames = 0
        phase = 'run'
        return
    end
    frames = frames + 1
    if frames >= 2 then
        check_case(cases[index])
        phase = 'setup'
    end
end)
