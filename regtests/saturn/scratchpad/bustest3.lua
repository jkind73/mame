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
  { "nop",                    { NOP } },
  { "stc sr,r4",              { 0x0402 } },
  { "stc gbr,r4",             { 0x0412 } },
  { "stc vbr,r4",             { 0x0422 } },
  { "sts mach,r4",            { 0x040A } },
  { "sts macl,r4",            { 0x041A } },
  { "sts pr,r4",              { 0x042A } },
  { "lds r4,mach",            { 0x440A } },
  { "lds r4,macl",            { 0x441A } },
  { "lds r4,pr",              { 0x442A } },
  { "ldc r4,gbr",             { 0x441E } },
  { "ldc r4,vbr",             { 0x442E } },
  { "sts.l pr,@-r15 ; lds.l", { 0x4F22, 0x4F26 } },
  { "stc.l gbr,@-r15 ; ldc.l",{ 0x4F13, 0x4F17 } },
  { "stc.l vbr,@-r15 ; ldc.l",{ 0x4F23, 0x4F27 } },
  { "sts.l mach ; lds.l mach",{ 0x4F02, 0x4F06 } },
  { "sts.l macl ; lds.l macl",{ 0x4F12, 0x4F16 } },
  { "mov.l r4,@-r15 / @r15+", { 0x2F46, 0x64F6 } },
  { "mov.w r4,@-r15 / @r15+", { 0x2F45, 0x64F5 } },
  { "mov.b r4,@-r15 / @r15+", { 0x2F44, 0x64F4 } },
  { "mov.l @(4,r1),r4",       { 0x5411 } },
  { "mov.l r4,@(4,r1)",       { 0x1141 } },
  { "mov.w @(2,r1),r0",       { 0x8511 } },
  { "mov.b r0,@(2,r1)",       { 0x8012 } },
  { "mov.l @(r0,r1),r4",      { 0x041E } },
  { "mov.l r4,@(r0,r1)",      { 0x014E } },
  { "mov.l @(2,gbr),r0",      { 0xC602 } },
  { "mova @(2,pc),r0",        { 0xC702 } },
  { "mov.w @(1,pc),r4",       { 0x9401, NOP } },
  { "mulu.w r4,r4",           { 0x244E } },
  { "muls.w r4,r4",           { 0x244F } },
  { "mul.l r4,r4",            { 0x0447 } },
  { "dmuls.l r4,r4",          { 0x344D } },
  { "dmulu.l r4,r4",          { 0x3445 } },
  { "mac.l @r1+,@r1+",        { 0x041F + 0x0 } },
  { "mac.w @r1+,@r1+",        { 0x411F } },
  { "mul.l ; sts macl",       { 0x0447, 0x041A } },
  { "div0u",                  { 0x0019 } },
  { "div1 r4,r5",             { 0x3544 + 0x0 } },
  { "div0s r4,r5",            { 0x2547 } },
  { "tas.b @r1",              { 0x411B } },
  { "cmp/str r4,r5",          { 0x254C } },
  { "xtrct r4,r5",            { 0x254D } },
  { "swap.w r4,r5",           { 0x6549 } },
  { "extu.w r4,r5",           { 0x654D } },
  { "negc r4,r5",             { 0x655A } },
  { "rotcl r4",               { 0x4424 } },
  { "shll16 r4",              { 0x4428 } },
  { "movt r4",                { 0x0429 } },
  { "clrmac",                 { 0x0028 } },
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
  for lead = 0, 0 do
    tests[#tests + 1] = { string.format("%-26s lead=%d", b[1], lead), b[2], lead }
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
