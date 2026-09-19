-- Read-only sound-startup snapshots for the unresolved After Burner II wait.
-- Run with an existing BOOTCPU build; rebuilding MAME is not necessary:
-- mame saturnjp aburner2 -verbose -log -autoboot_delay 0 -autoboot_script regtests/saturn/afterburner2_sound_probe.lua
-- Wait at least 23 emulated seconds. Output: afterburner2-sound-probe.txt
-- Uses CPU state, backing RAM and SCSP/SCU save-item inspection, never MMIO handlers.
local output = 'afterburner2-sound-probe.txt'
local captures = 0
local next_time = 20
local failed = false

-- A pending DMA-end bit with IMS=BFFF needs ordering evidence: whether the
-- BIOS restores the mask, or another vector fetch masks it again. These taps
-- observe existing accesses and return nil, never changing bus data.
local taps, events = {}, {}
local taps_started = false
local function install_irq_taps(machine)
    if taps_started then return end
    local main = machine.devices[':maincpu']
    if not main or not main.spaces or not main.spaces['program'] then return end
    taps_started = true
    local space = main.spaces['program']
    local function observe(kind)
        return function(address, data, mask)
            local now = emu.time()
            if now >= 19 and now <= 23 and #events < 12000 then
                events[#events + 1] = string.format(
                    'IRQTRACE t=%.9f %s addr=%08x data=%08x mask=%08x sampledpc=%08x',
                    now, kind, address, data, mask, main.state['PC'].value)
            end
            -- No return value: the original memory access is unmodified.
        end
    end
    for _, base in ipairs({0x05fe0000, 0x25fe0000}) do
        taps[#taps + 1] = space:install_write_tap(base, base + 0x63,
            'ab2-dma-writes', observe('DMA-write'))
        taps[#taps + 1] = space:install_write_tap(base + 0xa0, base + 0xab,
            'ab2-irq-writes', observe('IRQ-write'))
    end
    -- IRQ vector fetches go through the CPU address-space helper. Other
    -- reads of the same table may also appear; these are address observations,
    -- not an assertion that every read is an acknowledged interrupt.
    taps[#taps + 1] = space:install_read_tap(0x06000100, 0x0600013f,
        'ab2-vector-reads', observe('vector-read'))
end
local function remove_irq_taps()
    for _, tap in ipairs(taps) do tap:remove() end
    taps = {}
end

local function snapshot(machine, now)
    local sound = assert(machine.devices[':audiocpu'], 'sound CPU not found')
    local main = assert(machine.devices[':maincpu'], 'main CPU not found')
    local scsp = assert(machine.devices[':scsp'], 'SCSP not found')
    local ram = assert(machine.memory.shares[':sound_ram'], 'sound RAM not found')
    local work = assert(machine.memory.shares[':workram_h'], 'high work RAM not found')
    local text = {}
    local function line(fmt, ...) text[#text + 1] = string.format(fmt, ...) end
    line('SOUNDPROBE t=%.9f capture=%d', now, captures + 1)
    line('IRQTRACE taps=%s buffered=%d (sampled PC may lag under DRC)', tostring(taps_started), #events)
    for _, event in ipairs(events) do line('%s', event) end
    events = {}
    for _, pair in ipairs({{'main', main}, {'sound', sound}}) do
        local names = {}
        for name in pairs(pair[2].state) do names[#names + 1] = name end
        table.sort(names)
        for _, name in ipairs(names) do
            line('%s %s=%08x', pair[1], name, pair[2].state[name].value)
        end
    end
    -- Inspect registered SCSP state directly. Reading SCIPD/SCIRE via an
    -- emulated address space is deliberately avoided, as are timer syncs.
    local names = {}
    for name in pairs(scsp.items) do
        if name:find('m_udata.data', 1, true) or name:find('m_timers', 1, true)
            or name:find('m_current_level', 1, true)
            or name:find('m_mcipd', 1, true) or name:find('m_mcieb', 1, true) then
            names[#names + 1] = name
        end
    end
    table.sort(names)
    assert(#names > 0, 'SCSP save items not exposed by this build')
    for _, name in ipairs(names) do
        line('SCSP %s=%x', name, emu.item(scsp.items[name]):read(0))
    end
    -- Sound startup can complete before the next wait. Record SCU state
    -- directly as well so DMA activity and IRQ delivery can be distinguished
    -- without reading/acknowledging emulated registers.
    local scu = machine.devices[':scu']
    if scu then
        local fields = {}
        for name in pairs(scu.items) do
            if name:find('m_dma', 1, true) or name:find('m_ism', 1, true)
                or name:find('m_ist', 1, true) or name:find('m_current_irq', 1, true)
                or name:find('m_current_vector', 1, true)
                or name:find('m_abus', 1, true) then
                fields[#fields + 1] = name
            end
        end
        table.sort(fields)
        for _, name in ipairs(fields) do
            line('SCU %s=%x', name, emu.item(scu.items[name]):read(0))
        end
    else
        line('SCU unavailable')
    end
    local function dump(label, share, address, count)
        address = address & ~1
        count = math.min(count, share.size - address)
        if address < 0 or count <= 0 then return end
        for base = address, address + count - 2, 16 do
            local words = {}
            for at = base, math.min(base + 14, address + count - 2), 2 do
                words[#words + 1] = string.format('%04x', share:read_u16(at))
            end
            line('%s %06x: %s', label, base, table.concat(words, ' '))
        end
    end
    -- Includes reset/interrupt vectors, the ready word, startup routine and
    -- level-2 handler. The full low sound RAM window is needed only once.
    dump('sound', ram, 0, captures == 0 and 0x1000 or 0x100)
    dump('ready', ram, 0x4e0, 0x40)
    -- Saturn BIOS software mask shadow, common interrupt dispatcher and
    -- dispatch tables. Raw RAM: table values may be modified by the game.
    dump('bios-mask', work, 0x340, 0x20)
    dump('bios-dispatch', work, 0x8f0, 0x310)
    for i = 0, 7 do
        local entry = sound.state['A' .. i]
        if entry then
            local addr = entry.value & 0xffffff
            if addr < 0x80000 then dump('sound-A' .. i, ram, addr, 0x80) end
        end
    end
    -- Main CPU wait operands and interrupt vectors are backing RAM, not
    -- address-space accesses. Include handler code when vectors point into
    -- high work RAM; ROM/other-space vectors remain visible as pointers only.
    for i = 0, 15 do
        local entry = main.state['R' .. i]
        if entry then
            local value = entry.value
            local addr = value & 0x1fffffff
            if value < 0x40000000 and addr >= 0x6000000 and addr < 0x8000000 then
                dump('main-R' .. i, work, addr & 0xfffff, 0x40)
            end
        end
    end
    local vbr = main.state['VBR']
    if vbr then
        local addr = vbr.value & 0x1fffffff
        if vbr.value < 0x40000000 and addr >= 0x6000000 and addr < 0x8000000 then
            local offset = addr & 0xfffff
            dump('main-vectors', work, offset + 0x100, 0x80)
            for vector = 0x49, 0x4b do
                local at = offset + vector * 4
                if at + 3 < work.size then
                    local handler = work:read_u16(at) * 0x10000 + work:read_u16(at + 2)
                    line('DMA-vector %02x=%08x', vector, handler)
                    local physical = handler & 0x1fffffff
                    if handler < 0x40000000 and physical >= 0x6000000 and physical < 0x8000000 then
                        dump('DMA-handler', work, physical & 0xfffff, 0x80)
                    end
                end
            end
        end
    end
    local pc = main.state['PC'].value & 0x1fffffff
    if pc >= 0x6000000 and pc < 0x8000000 then
        dump('main-PC', work, (pc & 0xfffff) & ~0x7f, 0x200)
    end
    local f = assert(io.open(output, captures == 0 and 'w' or 'a'))
    f:write(table.concat(text, '\n'), '\n\n')
    f:close()
end

emu.register_frame_done(function()
    if failed or captures == 3 then return end
    local installed, install_error = pcall(install_irq_taps, manager.machine)
    if not installed then
        failed = true
        remove_irq_taps()
        print('SOUNDPROBE tap installation failed: ' .. tostring(install_error))
        return
    end
    if emu.time() < next_time then return end
    local ok, err = pcall(snapshot, manager.machine, emu.time())
    if not ok then
        failed = true
        remove_irq_taps()
        print('SOUNDPROBE failed: ' .. tostring(err))
        return
    end
    captures = captures + 1
    if captures == 3 then remove_irq_taps() end
    next_time = emu.time() + 1
    print(string.format('SOUNDPROBE saved %d/3 to %s', captures, output))
end)
