local m = manager.machine
local out = io.open(os.getenv("BT_OUT") or "stcmp.txt", "w")
local cpu = m.devices[":maincpu"]
local sp = cpu.spaces["program"]
local n = 0
local function hash(base, len)
  local h = 0
  for a = base, base + len - 4, 4 do h = (h * 31 + sp:read_u32(a)) & 0xffffffff end
  return h
end
emu.register_frame_done(function()
  n = n + 1
  if n == 1500 or n == 3000 or n == 4500 then
    out:write(string.format("frame %d t=%.6f pc=%08x fb=%08x vram1=%08x wramh=%08x\n", n, m.time:as_double(), cpu.state["PC"].value,
      hash(0x05C80000, 0x40000), hash(0x05C00000, 0x80000), hash(0x06000000, 0x100000)))
    out:flush()
  end
  if n >= 4500 then out:close(); m:exit() end
end)
