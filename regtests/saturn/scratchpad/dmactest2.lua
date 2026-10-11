-- SH-2 DMAC timing: cycle-stealing longword copy; progress sampled at two frame boundaries
-- by binary search over the destination (zeroed beforehand, source all ones).
local m = manager.machine
local cpu = m.devices[":maincpu"]
local sp = cpu.spaces["program"]
local out = io.open(os.getenv("BT_OUT") or "dma.txt", "w")
local N = 0x20000          -- longwords (512 KB): ~3 ms at 1 cycle/long ... plenty for the sample window

local tests = {
  { "wram-h -> wram-h", 0x06010000, 0x06080000 },
  { "wram-h -> wram-l", 0x06010000, 0x00280000 },
  { "wram-l -> wram-h", 0x00210000, 0x06080000 },
  { "bios   -> wram-h", 0x00000000, 0x06080000 },
}

local function progress(dst)
  -- number of leading nonzero longwords of the destination (monotonic while the copy runs)
  local lo, hi = 0, N
  while lo < hi do
    local mid = (lo + hi + 1) // 2
    if sp:read_u32(dst + (mid - 1) * 4) ~= 0 then lo = mid else hi = mid - 1 end
  end
  return lo
end

local frame, idx, state, t0, p1 = 0, 1, 0, 0, 0
emu.register_frame_done(function()
  frame = frame + 1
  if frame < 500 then return end
  local t = tests[idx]
  if state == 0 then
    local code = { 0x3000, 0x89FD }
    for i, w in ipairs(code) do sp:write_u16(0x06000100 + (i - 1) * 2, w) end
    sp:write_u32(0x46000100, 0)
    cpu.state["SR"].value = 0xf0
    cpu.state["PC"].value = 0x06000100
    sp:write_u32(0xffffffb0, 0)
    for i = 0, N - 1 do sp:write_u32(t[3] + i * 4, 0) end
    if t[2] >= 0x06000000 or (t[2] >= 0x00200000 and t[2] < 0x00300000) then
      for i = 0, N - 1 do sp:write_u32(t[2] + i * 4, 0xffffffff) end
    end
    sp:write_u32(0xffffff80, t[2])
    sp:write_u32(0xffffff84, t[3])
    sp:write_u32(0xffffff88, N)
    sp:write_u32(0xffffff8c, 0x5a01)
    sp:write_u32(0xffffffb0, 0x0001)
    state, t0 = 1, frame
  elseif state == 1 and frame == t0 + 2 then
    p1 = progress(t[3])
    state = 2
  elseif state == 2 and frame == t0 + 4 then
    local p2 = progress(t[3])
    local clk = (m.screens[":screen"].width == 352 or m.screens[":screen"].width == 704) and 28636360 or 26874100
    local fps = 1.0 / m.screens[":screen"].frame_period
    local per = (p2 > p1) and (2 * clk / fps / (p2 - p1)) or 0
    out:write(string.format("%s %.2f cycles per longword (progress %d -> %d)\n", t[1], per, p1, p2))
    sp:write_u32(0xffffffb0, 0)
    sp:write_u32(0xffffff8c, 0)
    idx = idx + 1
    state = 0
    if idx > #tests then out:close(); m:exit() end
  end
end)
