-- SH-2 DMAC timing: a cycle-stealing longword copy, timed by the machine time of its destination writes.
local m = manager.machine
local cpu = m.devices[":maincpu"]
local sp = cpu.spaces["program"]
local out = io.open(os.getenv("BT_OUT") or "dma.txt", "w")
local N = 2048

local tests = {
  { "wram-h -> wram-h", 0x06040000, 0x06080000 },
  { "wram-h -> wram-l", 0x06040000, 0x00280000 },
  { "wram-l -> wram-h", 0x00240000, 0x06080000 },
  { "bios   -> wram-h", 0x00000100, 0x06080000 },
  { "wram-h -> vdp2vram", 0x06040000, 0x25e00000 },
  { "wram-h -> vdp1vram", 0x06040000, 0x25c00000 },
}

local armed, first, last, writes = false, 0, 0, 0
local function tap(offset, data, mask)
  if armed then
    local t = m.time:as_double()
    if writes == 0 then first = t end
    last = t
    writes = writes + 1
  end
end
sp:install_write_tap(0x06080000, 0x06081fff, "dma_wramh", tap)
sp:install_write_tap(0x00280000, 0x00281fff, "dma_wraml", tap)
sp:install_write_tap(0x05e00000, 0x05e01fff, "dma_vdp2", tap)
sp:install_write_tap(0x05c00000, 0x05c01fff, "dma_vdp1", tap)

local frame, idx, state, t0 = 0, 1, 0, 0
emu.register_frame_done(function()
  frame = frame + 1
  if frame < 500 then return end
  local t = tests[idx]
  if state == 0 then
    local code = { 0x3000, 0x89FD }                  -- park in a cached loop
    for i, w in ipairs(code) do sp:write_u16(0x06000100 + (i - 1) * 2, w) end
    sp:write_u32(0x46000100, 0)
    cpu.state["SR"].value = 0xf0
    cpu.state["PC"].value = 0x06000100
    sp:write_u32(0xffffffb0, 0)
    sp:write_u32(0xffffff80, t[2])              -- SAR0
    sp:write_u32(0xffffff84, t[3])              -- DAR0
    sp:write_u32(0xffffff88, N)                 -- TCR0
    sp:write_u32(0xffffff8c, 0x5a01)            -- CHCR0: long, src/dst increment, auto request, DE
    armed, writes = true, 0
    sp:write_u32(0xffffffb0, 0x0001)            -- DMAOR: DME
    state, t0 = 1, frame
  elseif state == 1 and frame >= t0 + 3 then
    armed = false
    local clk = (m.screens[":screen"].width == 352 or m.screens[":screen"].width == 704) and 28636360 or 26874100
    local cyc = writes > 1 and (last - first) * clk / (writes - 1) or 0
    out:write(string.format("%s %.2f cycles per longword (%d writes)\n", t[1], cyc, writes))
    sp:write_u32(0xffffffb0, 0)
    sp:write_u32(0xffffff8c, 0)
    idx = idx + 1
    state = 0
    if idx > #tests then out:close(); m:exit() end
  end
end)
