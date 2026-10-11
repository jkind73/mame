-- SH-2 instruction timing micro test: loops of code constructs, run uncached from Work RAM-H,
-- timed with the free-running timer. Prints cycles per iteration.
local m = manager.machine
local cpu = m.devices[":maincpu"]
local sp = cpu.spaces["program"]
local N = 4000
local RES = 0x06000600
local out = io.open(os.getenv("BT_OUT") or "bt2.txt", "w")

local NOP, SETT, CLRT = 0x0009, 0x0018, 0x0008
-- name, body words (the loop adds dt r2 / bf), leading nops shifting the alignment
local bodies = {
  { "jsr @r7 ; nop / rts ; nop",  { 0x470B, NOP }, "jsr" },
  { "jsr @r7 ; nop / rts ; add",  { 0x470B, NOP }, "jsr2" },
  { "bsrf r7 ; nop / rts ; nop",  { 0x0703, NOP }, "bsrf" },
  { "braf r7 ; nop (to +4)",      { 0x0723, NOP, NOP, NOP }, "braf" },
  { "nop x2 jsr @r7 ; mov",       { NOP, NOP, 0x470B, 0x6143 }, "jsr" },
}

local function program(body, lead)
  local w = { 0x6031, 0x2601 }
  for i = 1, lead do w[#w + 1] = NOP end
  local loop_start = #w   -- index of the first word of the loop
  for _, b in ipairs(body) do w[#w + 1] = b end
  w[#w + 1] = 0x4210                                     -- dt r2
  local bf_index = #w
  w[#w + 1] = 0x8B00 | ((-(bf_index - loop_start + 2)) & 0xff)  -- bf loop_start
  w[#w + 1] = 0x6031; w[#w + 1] = 0x8161                 -- end timestamp
  w[#w + 1] = 0x3000; w[#w + 1] = 0x89FD                 -- park
  return w, loop_start
end

local tests = {}
for _, b in ipairs(bodies) do
  for lead = 0, 1 do
    tests[#tests + 1] = { string.format("%-30s lead=%d", b[1], lead), b[2], lead, b[3] }
  end
end

local frame, idx, started, wait = 0, 1, false, 0
emu.register_frame_done(function()
  frame = frame + 1
  if frame < 500 then return end
  if started then
    wait = wait + 1
    if wait >= 6 then
      local t = tests[idx]
      local f0, f1 = sp:read_u16(RES), sp:read_u16(RES + 2)
      local tcr = sp:read_u8(0xfffffe16)
      local div = ({ 8, 32, 128, 1 })[(tcr & 3) + 1]
      out:write(string.format("%s %.3f\n", t[1], ((f1 - f0) & 0xffff) * div / N))
      idx = idx + 1
      started = false
      wait = 0
      if idx > #tests then out:close(); m:exit() end
    end
    return
  end
  local t = tests[idx]
  local code, ls = program(t[2], t[3])
  -- the jmp/bt/bra bodies jump to the next instruction (disp 0 or r7)
  for i, w in ipairs(code) do sp:write_u16(0x06000100 + (i - 1) * 2, w) end
  for line = 0, 7 do sp:write_u32(0x46000100 + line * 16, 0) end
  sp:write_u16(RES, 0); sp:write_u16(RES + 2, 0)
  -- r7 = the instruction after the delay slot of "jmp @r7 ; nop" (index ls + 2)
  cpu.state["R7"].value = 0x26000100 + (ls + 2) * 2
  local kind = t[4]
  if kind == "jsr" or kind == "jsr2" then
    sp:write_u16(0x06000300, 0x000B); sp:write_u16(0x06000302, kind == "jsr" and NOP or 0x7401)
    cpu.state["R7"].value = 0x26000300
  elseif kind == "bsrf" then
    sp:write_u16(0x06000300, 0x000B); sp:write_u16(0x06000302, NOP)
    local pc = 0x26000100 + (ls + 2) * 2        -- address of the bsrf (body index 0)
    cpu.state["R7"].value = (0x26000300 - (pc + 4)) & 0xffffffff
  elseif kind == "braf" then
    local pc = 0x26000100 + (ls + 2) * 2
    cpu.state["R7"].value = 4                   -- braf target = pc + 4 + 4 = the instruction after the slot + 2
  end
  cpu.state["R1"].value = 0x26000400
  cpu.state["R4"].value = 0x26000800
  cpu.state["R5"].value = 0x26000900
  cpu.state["R15"].value = 0x26001000
  cpu.state["R0"].value = 0x20
  cpu.state["R2"].value = N
  cpu.state["R3"].value = 0xfffffe12
  cpu.state["R6"].value = 0x26000600
  cpu.state["SR"].value = 0xf0
  cpu.state["PC"].value = 0x26000100
  started = true
end)
