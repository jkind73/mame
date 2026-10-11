local m = manager.machine
local out = io.open(os.getenv("BT_OUT") or "kcount.txt", "w")
local sp = m.devices[":maincpu"].spaces["program"]
local prev, keyon = {}, {}
emu.register_frame_done(function()
  local t = m.time:as_double()
  for slot = 0, 31 do
    local on = (sp:read_u16(0x05B00000 + slot * 0x20) & 0x0800) ~= 0
    if on and not prev[slot] then local s = math.floor(t); keyon[s] = (keyon[s] or 0) + 1 end
    prev[slot] = on
  end
  if t >= 125 then
    local k = {}
    for s = 85, 124 do k[#k + 1] = string.format("%d:%d", s, keyon[s] or 0) end
    out:write("keyons per second (MAME, no input): " .. table.concat(k, " ") .. "\n")
    out:close(); m:exit()
  end
end)
