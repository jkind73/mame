local m = manager.machine
local out = io.open(os.getenv("BT_OUT") or "sramhash.txt", "w")
local sp = m.devices[":maincpu"].spaces["program"]
local marks = { 45, 60, 110 }
local done = {}
emu.register_frame_done(function()
  local t = m.time:as_double()
  for _, mk in ipairs(marks) do
    if t >= mk and not done[mk] then
      done[mk] = true
      out:write(string.format("== t=%d\n", mk))
      local row = {}
      for blk = 0, 127 do   -- 4 KB blocks of the 512 KB sound RAM
        local h = 0
        for a = 0, 0xfff, 4 do h = (h * 31 + sp:read_u32(0x05A00000 + blk * 0x1000 + a)) & 0xffffffff end
        row[#row + 1] = string.format("%08x", h)
      end
      out:write(table.concat(row, " ") .. "\n")
      out:flush()
    end
  end
  if t >= 111 then out:close(); m:exit() end
end)
