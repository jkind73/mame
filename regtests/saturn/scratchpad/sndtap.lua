local m = manager.machine
local out = io.open(os.getenv("BT_OUT") or "sndtap.txt", "w")
local cpu = m.devices[":maincpu"]
local sp = cpu.spaces["program"]
local n = 0
local byPC, total, first, firstT = {}, 0, nil, nil
local tap = sp:install_write_tap(0x05A00000, 0x05A7FFFF, "sndtap", function(offset, data, mask)
  local pc = cpu.state["PC"].value
  byPC[pc] = (byPC[pc] or 0) + 1
  total = total + 1
  if not first then first = offset; firstT = m.time:as_double() end
  return data
end)
emu.register_frame_done(function()
  n = n + 1
  if n % 20 == 0 then
    local a = {}
    for k, v in pairs(byPC) do a[#a + 1] = { k, v } end
    table.sort(a, function(x, y) return x[2] > y[2] end)
    local s = {}
    for i = 1, math.min(4, #a) do s[#s + 1] = string.format("%08x:%d", a[i][1], a[i][2]) end
    out:write(string.format("frame %d t=%.3f writes=%d  %s\n", n, m.time:as_double(), total, table.concat(s, " ")))
    out:flush()
  end
  if n >= 200 then out:close(); m:exit() end
end)
