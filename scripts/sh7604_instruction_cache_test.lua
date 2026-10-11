-- license:BSD-3-Clause
-- Instruction execution must use the private cache, including cache-array patches.
local m=manager.machine
local cpu=m.devices[':maincpu'];local mem=cpu.spaces.program
local function run()
 local pc=0x06008000
 mem:write_u32(pc,0xe707affe);mem:write_u32(pc+4,0x00090009)
 mem:write_u8(0xfffffe92,0x11)
 mem:write_u32(0xc0000000,0xe72aaffe);mem:write_u32(0xc0000004,0x00090009)
 mem:write_u32(0xc0000008,0x00090009);mem:write_u32(0xc000000c,0x00090009)
 mem:write_u32(0x66008004,0)
 cpu.state.SR.value=0xf0;cpu.state.R7.value=0;cpu.state.CURPC.value=pc
 emu.wait(0.0001)
 assert(cpu.state.R7.value==42,'executed RAM opcode instead of cached instruction: '..cpu.state.R7.value)
 -- Private executable contents and the prefetch state survive save/load.
 local state=m.options.entries['state_directory']:value()..'/instruction-cache.sta'
 m:save(state);emu.wait(0.02)
 mem:write_u32(0xc0000000,0xe763affe);cpu.state.R7.value=0;cpu.state.CURPC.value=pc;emu.wait(0.0001)
 assert(cpu.state.R7.value==99,'modified cache-array instruction did not execute')
 m:load(state);if not emu.wait(0.02)then emu.wait(0.02)end
 cpu.state.R7.value=0;cpu.state.CURPC.value=pc;emu.wait(0.0001)
 assert(cpu.state.R7.value==42,'saved executable cache was not restored')
 -- An external/cache-through code write does not silently replace the private instruction.
 mem:write_u32(pc|0x20000000,0xe709affe)
 cpu.state.R7.value=0;cpu.state.CURPC.value=pc;emu.wait(0.0001)
 assert(cpu.state.R7.value==42,'external RAM code write incorrectly snooped instruction cache')
 mem:write_u32(pc|0x20000000,0xe707affe)
 -- Cache-through execution must still use RAM, even while CE is set.
 cpu.state.R7.value=0;cpu.state.CURPC.value=pc|0x20000000;emu.wait(0.0001)
 assert(cpu.state.R7.value==7,'cache-through instruction incorrectly used cache')
 -- A mismatch in a native branch's delay slot must preserve its target.
 mem:write_u32(pc,0xa002e707);mem:write_u32(pc+4,0xe6630009);mem:write_u32(pc+8,0xaffe0009)
 mem:write_u8(0xfffffe92,0x11)
 mem:write_u32(0xc0000000,0xa002e72a);mem:write_u32(0xc0000004,0xe6630009);mem:write_u32(0xc0000008,0xaffe0009)
 mem:write_u32(0x66008004,0)
 cpu.state.R6.value=0;cpu.state.R7.value=0;cpu.state.CURPC.value=pc;emu.wait(0.0001)
 assert(cpu.state.R7.value==42 and cpu.state.R6.value==0,'cached delay-slot fallback lost native branch target')
 -- Indirect jumps, subroutine returns and interrupt returns preserve native side effects.
 for _,op in ipairs({0x412b,0x000b,0xb002,0x002b})do
  mem:write_u32(pc,(op<<16)|0xe707);mem:write_u32(pc+4,0xe6630009);mem:write_u32(pc+8,0xaffe0009)
  mem:write_u8(0xfffffe92,0x11)
  mem:write_u32(0xc0000000,(op<<16)|0xe72a);mem:write_u32(0xc0000004,0xe6630009);mem:write_u32(0xc0000008,0xaffe0009)
  mem:write_u32(0x66008004,0)
  mem:write_u32(0x2600a000,pc+8);mem:write_u32(0x2600a004,0xf0)
  cpu.state.R1.value=pc+8;cpu.state.PR.value=pc+8;cpu.state.R15.value=0x2600a000
  cpu.state.R6.value=0;cpu.state.R7.value=0;cpu.state.CURPC.value=pc;emu.wait(0.0001)
  assert(cpu.state.R7.value==42 and cpu.state.R6.value==0,'cached dynamic delay slot lost branch target')
  if op==0x002b then assert(cpu.state.R15.value==0x2600a008,'cached RTE slot popped stack twice')end
  if op==0xb002 then assert(cpu.state.PR.value==pc+4,'cached BSR slot lost return address')end
 end
 -- Cached executable instructions may differ even from an illegal opcode in RAM.
 mem:write_u32(pc,0x0000affe);mem:write_u32(pc+4,0x00090009)
 mem:write_u8(0xfffffe92,0x11);mem:write_u32(0xc0000000,0xe72aaffe);mem:write_u32(0xc0000004,0x00090009)
 mem:write_u32(0x66008004,0)
 cpu.state.R7.value=0;cpu.state.CURPC.value=pc;emu.wait(0.0001)
 assert(cpu.state.R7.value==42,'illegal RAM opcode was decoded instead of cached code')
 mem:write_u32(pc,0xe707affe)
 -- Purging removes the private instruction and refills from RAM.
 mem:write_u8(0xfffffe92,0x11);cpu.state.R7.value=0;cpu.state.CURPC.value=pc;emu.wait(0.0001)
 assert(cpu.state.R7.value==7,'purged instruction did not refill from RAM')
 print('SH7604_INSTRUCTION_CACHE_PASS private cached opcode, cache-through, purge/refill')
end
thread=coroutine.create(function()local ok,err=pcall(run);if not ok then print('SH7604_INSTRUCTION_CACHE_FAIL '..tostring(err))end;m:exit()end)
coroutine.resume(thread)
