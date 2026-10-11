-- SCU DMA with unaligned source, destination and length (SCU manual 2.1, figure 2.1):
-- bytes move one for one from the source address to the destination address.
local m = manager.machine
local sp = m.devices[":maincpu"].spaces["program"]
local out = io.open(os.getenv("BT_OUT") or "scudma_edges.txt", "w")
local S = 0x05FE0000
local frames, started = 0, false

local function run(src, dst, count, dst_add, label)
  for i = 0, 63 do sp:write_u8(0x06050000 + i, 0xa0 + i) end        -- source pattern at WRAM-H
  for i = 0, 31 do sp:write_u16(dst - (dst & 0xf) + (i * 2) - 8, 0) end -- clear around the destination
  sp:write_u32(S + 0xA0, 0xffffffff)
  sp:write_u32(S + 0xA4, 0)
  sp:write_u32(S + 0x00, src); sp:write_u32(S + 0x04, dst); sp:write_u32(S + 0x08, count)
  sp:write_u32(S + 0x0C, 0x100 | dst_add)
  sp:write_u32(S + 0x14, 0x7)
  sp:write_u32(S + 0x10, 0x100)
  sp:write_u32(S + 0x10, 0x101)
  local t0 = m.time:as_double()
  while (sp:read_u32(S + 0xA4) & 0x800) == 0 do
    emu.wait(emu.attotime.from_usec(2))
    if m.time:as_double() - t0 > 0.05 then out:write(label .. ": timeout\n"); return end
  end
  local ok = true
  local line = {}
  for i = -2, count + 1 do
    local expect = (i >= 0 and i < count) and (0xa0 + (src & 0x3f) + i) or 0
    local got = sp:read_u8(dst + i)
    if got ~= expect then ok = false end
    line[#line + 1] = string.format("%02x", got)
  end
  out:write(string.format("%s: %s  [%s]\n", label, ok and "OK" or "MISMATCH", table.concat(line, " ")))
end

emu.register_frame_done(function()
  frames = frames + 1
  if started or frames < 700 then return end
  started = true
  coroutine.wrap(function()
    local ok, err = pcall(function()
      -- the VDP1 VRAM is the B-Bus destination; the source is Work RAM-H
      run(0x06050000, 0x05C40010, 16, 1, "aligned 16")
      run(0x06050001, 0x05C40111, 7, 1, "odd source and destination, 7 bytes")
      run(0x06050003, 0x05C40210, 10, 1, "odd source, aligned destination, 10 bytes")
      run(0x06050000, 0x05C40313, 9, 1, "aligned source, odd destination, 9 bytes")
      run(0x06050002, 0x05C40416, 5, 1, "halfword aligned both, odd length")
    end)
    if not ok then out:write("ERR " .. tostring(err) .. "\n") end
    out:close(); m:exit()
  end)()
end)
