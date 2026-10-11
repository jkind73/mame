-- SH-2 bus timing micro test: a data read/write loop run by the master from a chosen place,
-- timed with the on-chip free-running timer. Prints cycles per iteration.
local m = manager.machine
local cpu = m.devices[":maincpu"]
local sp = cpu.spaces["program"]
local N = 2000
local RES = 0x06000600          -- start FRC at +0, end FRC at +2
local out = io.open(os.getenv("BT_OUT") or "bt.txt", "w")

-- start: FRC read; loop N x { body ; dt r2 ; bf }; FRC read; park
-- r3 = FRC address, r6 = result address, r1 = data address, r2 = count, r0 = write value
local function program(write)
  local body = write and 0x2141 or 0x6411   -- mov.w r4,@r1  /  mov.w @r1,r4
  return {
    0x6031, 0x2601,        -- mov.w @r3,r0 ; mov.w r0,@r6   (start)
    body, 0x4210, 0x8BFC,  -- loop: body ; dt r2 ; bf loop
    0x6031, 0x8161,        -- mov.w @r3,r0 ; mov.w r0,@(2,r6)   (end)
    0x3000, 0x89FD,        -- park: cmp/eq r0,r0 ; bt park
  }
end

local tests = {
  -- name, code alias, data address, write
  { "wramh-read  code=uncached ", 0x26000100, 0x26000400, false },
  { "wramh-write code=uncached ", 0x26000100, 0x26000400, true },
  { "wraml-read  code=uncached ", 0x26000100, 0x20200000, false },
  { "bios-read   code=uncached ", 0x26000100, 0x20000100, false },
  { "vdp2vram-rd code=uncached ", 0x26000100, 0x25e00000, false },
  { "vdp2vram-wr code=uncached ", 0x26000100, 0x25e00000, true },
  { "vdp1vram-rd code=uncached ", 0x26000100, 0x25c00000, false },
  { "scsp-read   code=uncached ", 0x26000100, 0x25a00000, false },
  { "scu-read    code=uncached ", 0x26000100, 0x25fe0000, false },
  { "wramh-read  code=cached   ", 0x06000100, 0x26000400, false },
  { "wraml-read  code=cached   ", 0x06000100, 0x20200000, false },
  { "vdp2vram-rd code=cached   ", 0x06000100, 0x25e00000, false },
}

local frame, idx, started, wait = 0, 1, false, 0
emu.register_frame_done(function()
  frame = frame + 1
  if frame < 500 then return end
  if started then
    wait = wait + 1
    if wait >= 8 then
      local t = tests[idx]
      local f0 = sp:read_u16(RES)
      local f1 = sp:read_u16(RES + 2)
      local tcr = sp:read_u8(0xfffffe16)
      local div = ({ 8, 32, 128, 1 })[(tcr & 3) + 1]
      local cyc = ((f1 - f0) & 0xffff) * div / N
      out:write(string.format("%s %.3f cycles/iter (frc %d..%d div %d)\n", t[1], cyc, f0, f1, div))
      idx = idx + 1
      started = false
      wait = 0
      if idx > #tests then out:close(); m:exit() end
    end
    return
  end
  local t = tests[idx]
  local code = program(t[4])
  for i, w in ipairs(code) do sp:write_u16(0x06000100 + (i - 1) * 2, w) end
  sp:write_u32(0x46000100, 0)  -- associative purge of the loop's cache lines
  sp:write_u32(0x46000110, 0)
  sp:write_u16(RES, 0); sp:write_u16(RES + 2, 0)
  cpu.state["R4"].value = 0x55
  cpu.state["R1"].value = t[3]
  cpu.state["R2"].value = N
  cpu.state["R3"].value = 0xfffffe12
  cpu.state["R6"].value = 0x26000600
  cpu.state["SR"].value = 0xf0
  cpu.state["PC"].value = t[2]
  started = true
end)
