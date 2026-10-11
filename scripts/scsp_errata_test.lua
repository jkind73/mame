-- license:BSD-3-Clause
-- Rel.2.5 errata: physical RAM, SBCTL sign preservation and MIDI bit removal.
local m=manager.machine
local mem=m.devices[':maincpu'].spaces.program
local audio=m.devices[':audiocpu']
local snd=audio.spaces.program
local chip
for _,space in pairs(m.devices[':scsp'].spaces)do chip=space;break end
local function r(a)return mem:read_u16(0x05b00000+a)end
local function w(a,v)mem:write_u16(0x05b00000+a,v)end
local function run()
 -- Deliberately probe software-rule diagnostics; no hardware result is assumed here.
 w(0x400,0);r(0x404)
 emu.wait(0.00004);w(0x400,0x200)
 assert(r(0x400)&0x300==0x200,'MEM4MB/DAC18B configuration lost')
 -- Only the installed 512KiB chip is populated, through both CPU and SCSP paths.
 mem:write_u16(0x05a00000,0x1234);mem:write_u16(0x05a7fffe,0x5678)
 assert(snd:read_u16(0)==0x1234 and snd:read_u16(0x7fffe)==0x5678,'CPU/SCSP RAM not shared')
 local absent_cpu=snd:read_u16(0x80000);local absent_scsp=chip:read_u16(0xffffe)
 snd:write_u16(0x80000,0xaaaa);chip:write_u16(0xffffe,0xbbbb)
 print(string.format('unpopulated bank CPU %04x/%04x SCSP %04x/%04x',absent_cpu,snd:read_u16(0x80000),absent_scsp,chip:read_u16(0xffffe)))
 assert(snd:read_u16(0x80000)==absent_cpu and chip:read_u16(0xffffe)==absent_scsp,'unpopulated second chip became RAM')
 assert(mem:read_u16(0x05a00000)==0x1234 and mem:read_u16(0x05a7fffe)==0x5678,'unpopulated chip aliased installed RAM')
 chip:write_u16(0x7fffe,0x9876);assert(snd:read_u16(0x7fffe)==0x9876,'last physical word not shared')
 -- MIEMP was deleted in three errata entries; it cannot be written back into existence.
 assert(r(0x404)&0x100==0,'deleted empty flag returned')
 w(0x404,0xffff);assert(r(0x404)&0x100==0,'deleted empty flag writable')
 local masks={0,0x7fff,0x8000,0xffff}
 local cases=0
 for bits=8,16,8 do
  for _,value in ipairs({0,0x1234,0x7fff,0x8000,0xfedc,0xffff})do
   for control=0,3 do
    w(0,0x1001) -- key off before restarting the direct slot
    mem:write_u16(0x05a10000,value);mem:write_u16(0x05a10002,value)
    w(2,0);w(4,0);w(6,0xffff);w(8,0x1f);w(0x0c,0x100);w(0x10,0x400)
    w(0,0x1821|(control<<9)|(bits==8 and 0x10 or 0))
    emu.wait(0.0001)
    local raw=bits==8 and (value&0xff00)or value
    local expected=raw~masks[control+1]
    assert(r(0x600)==expected and r(0x640)==expected,string.format('SBCTL%d PCM%d %04x -> expected %04x got %04x/%04x',control,bits,value,expected,r(0x600),r(0x640)))
    cases=cases+1
   end
  end
 end
 w(0,0x1001)
 -- Prohibited opcodes do not acquire invented illegal-instruction exceptions.
 -- Existing RESET compatibility resets the 68000 through SMPC, not SCSP.
 w(0x400,0x205);mem:write_u32(0x05a00000,0x8000);mem:write_u32(0x05a00004,0x300)
 mem:write_u16(0x05a00300,0x60fe);mem:write_u8(0x05a00400,0x12)
 local program={0x4af9,0x0000,0x0400,0x4e70,0x5281,0x60fe}
 for i,op in ipairs(program)do mem:write_u16(0x05a001fe+2*i,op)end
 mem:write_u8(0x0010001f,0x06);emu.wait(0.0001)
 audio.state.SR.value=0x2700;audio.state.D1.value=0;audio.state.CURPC.value=0x200
 emu.wait(0.00003)
 assert(mem:read_u8(0x05a00400)==0x92 and audio.state.D1.value==1,'TAS/RESET compatibility changed')
 emu.wait(0.0002)
 assert(r(0x400)&0x30f==0x205,'RESET opcode reset SCSP')
 print('SCSP_ERRATA_PASS '..cases..' SBCTL cases, MIEMP removal, 512KiB shared RAM/unpopulated bank, MEM4MB/DAC18B, RESET/TAS compatibility')
end
scsp_errata_thread=coroutine.create(function()
 local ok,err=pcall(run)
 if not ok then print('SCSP_ERRATA_FAIL '..tostring(err))end
 m:exit()
end)
local ok,err=coroutine.resume(scsp_errata_thread)
if not ok then print('SCSP_ERRATA_FAIL '..tostring(err));m:exit()end
