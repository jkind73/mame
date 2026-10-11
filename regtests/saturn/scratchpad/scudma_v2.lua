-- SCU DMA from the VDP2 areas to Work RAM-H (MiSTer probe lead: MAME flagged it illegal)
local m = manager.machine
local sp = m.devices[":maincpu"].spaces["program"]
local out = io.open(os.getenv("BT_OUT") or "scudma_v2.txt", "w")
local S = 0x05FE0000
local frames, started = 0, false
local function run(src, dst, count, label)
  for i = 0, count - 1 do sp:write_u8(dst + i, 0) end
  sp:write_u32(S + 0xA0, 0xffffffff)
  sp:write_u32(S + 0xA4, 0)
  sp:write_u32(S + 0x00, src); sp:write_u32(S + 0x04, dst); sp:write_u32(S + 0x08, count)
  sp:write_u32(S + 0x0C, 0x101); sp:write_u32(S + 0x14, 0x7)
  sp:write_u32(S + 0x10, 0x100); sp:write_u32(S + 0x10, 0x101)
  local t0 = m.time:as_double()
  local st
  repeat
    emu.wait(emu.attotime.from_usec(2))
    st = sp:read_u32(S + 0xA4)
  until (st & 0x1800) ~= 0 or m.time:as_double() - t0 > 0.02
  local got = {}
  for i = 0, 7 do got[#got + 1] = string.format("%02x", sp:read_u8(dst + i)) end
  out:write(string.format("%s: IST=%08x (end %s, illegal %s) first bytes %s\n", label, st, (st & 0x800) ~= 0 and "yes" or "no", (st & 0x1000) ~= 0 and "yes" or "no", table.concat(got, " ")))
end
emu.register_frame_done(function()
  frames = frames + 1
  if started or frames < 700 then return end
  started = true
  coroutine.wrap(function()
    local ok, err = pcall(function()
      for i = 0, 31 do sp:write_u8(0x05E00100 + i, 0x40 + i); sp:write_u16(0x05F00000 + i * 2, 0x7000 + i) end
      run(0x05E00100, 0x06050000, 32, "VDP2 VRAM to WRAM-H")
      run(0x05F00000, 0x06050000, 32, "VDP2 CRAM to WRAM-H")
      run(0x05C00000, 0x06050000, 32, "VDP1 VRAM to WRAM-H")
      run(0x06050000, 0x05E00200, 32, "WRAM-H to VDP2 VRAM")
    end)
    if not ok then out:write("ERR " .. tostring(err) .. "\n") end
    out:close(); m:exit()
  end)()
end)
