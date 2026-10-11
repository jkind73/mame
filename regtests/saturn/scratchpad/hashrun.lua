local m = manager.machine
local out = io.open(os.getenv("BT_OUT") or "hashrun.txt", "w")
local cpu = m.devices[":maincpu"]
local slv = m.devices[":slave"]
local sp = cpu.spaces["program"]
local stop = tonumber(os.getenv("HASH_FRAME") or "1500")
local n = 0
local function hash(base, len)
  local h = 0
  for a = base, base + len - 4, 4 do h = (h * 31 + sp:read_u32(a)) & 0xffffffff end
  return h
end
emu.register_frame_done(function()
  n = n + 1
  if n % (stop // 2) == 0 or n == stop then
    out:write(string.format("frame %d t=%.9f mpc=%08x spc=%08x r0=%08x/%08x wramh=%08x wraml=%08x vdp1=%08x vdp2=%08x\n", n, m.time:as_double(),
      cpu.state["PC"].value, slv.state["PC"].value, cpu.state["R0"].value, slv.state["R0"].value,
      hash(0x06000000, 0x100000), hash(0x00200000, 0x100000), hash(0x05C00000, 0x80000), hash(0x05E00000, 0x80000)))
    out:flush()
  end
  if n >= stop then out:close(); m:exit() end
end)
