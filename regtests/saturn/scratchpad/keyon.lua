local m = manager.machine
local out = io.open(os.getenv("BT_OUT") or "keyon.txt", "w")
local snd = m.devices[":audiocpu"]
local sp = snd.spaces["program"]
local per = {}
local total = 0
-- KEYONEX is bit 12 of the first SCSP register word; the slot registers are at 0x100000 + slot*0x20
local tap = sp:install_write_tap(0x100000, 0x100001, "keyonex", function(offset, data, mask)
  if (data & 0x1000) ~= 0 then
    local s = math.floor(m.time:as_double())
    per[s] = (per[s] or 0) + 1
    total = total + 1
  end
  return data
end)
-- the main CPU's sound requests: writes to the SCSP common area from the SH-2
local msp = m.devices[":maincpu"].spaces["program"]
local shw = {}
local tap2 = msp:install_write_tap(0x05B00000, 0x05B0001F, "mainscsp", function(offset, data, mask)
  local s = math.floor(m.time:as_double())
  shw[s] = (shw[s] or 0) + 1
  return data
end)
emu.register_frame_done(function()
  if m.time:as_double() >= 150 then
    local k = {}
    for s = 0, 149 do k[#k + 1] = string.format("%d:%d/%d", s, per[s] or 0, shw[s] or 0) end
    out:write("total keyonex=" .. total .. "\nsec:keyon/sh2scspwrites\n" .. table.concat(k, " ") .. "\n")
    out:close(); m:exit()
  end
end)
