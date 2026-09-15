-- Standalone Lua fixture. Run from a temporary directory:
-- lua /path/test_sound_probe.lua /path/afterburner2_sound_probe.lua
local script = assert(arg[1])
local now, callback, reads = 0, nil, 0
local function share(size)
    return {size=size, read_u16=function(self, offset)
        assert(offset >= 0 and offset + 1 < self.size and offset % 2 == 0)
        reads = reads + 1
        return offset & 0xffff
    end}
end
local main = {state={PC={value=0x0607bbc4}, R1={value=0x06004e64}, VBR={value=0x06000000}, R2={value=0x66000000}}}
local sound = {state={PC={value=0x7ea}, SR={value=0x2700},
    A2={value=0x806bc}, A5={value=0x100000}, A7={value=0x7fffe}}}
local scsp = {items={['15/m_udata.data[i]']=0x80,
    ['0/m_current_level']=2, ['0/m_timers[i].counter']=0xff,
    ['0/m_Slots[slot].active']=999}}
local scu = {items={['0/m_ism']=0xbfff,['0/m_ist']=0x800,
    ['0/m_dma[0].live_count']=0,['0/m_current_irq_level']=5,['0/m_timer0_counter']=99}}
manager = {machine={devices={[':maincpu']=main,[':audiocpu']=sound,[':scsp']=scsp,[':scu']=scu},
    memory={shares={[':sound_ram']=share(0x80000),[':workram_h']=share(0x100000)}}}}
emu = {time=function() return now end,
    register_frame_done=function(f) callback=f end,
    item=function(value) return {read=function(_, index) assert(index==0);return value end} end}
dofile(script)
callback();assert(reads==0)
now=19.99;callback();assert(reads==0)
local function readfile()
    local f=assert(io.open('afterburner2-sound-probe.txt'));local s=f:read('a');f:close();return s
end
now=20;callback();local a=readfile();local n=reads
assert(a:find('sound A5=00100000',1,true))
assert(a:find('SCU 0/m_ism=bfff',1,true))
assert(a:find('SCU 0/m_dma[0].live_count=0',1,true))
assert(not a:find('m_timer0_counter',1,true))
assert(a:find('main-R1 004e64:',1,true))
assert(not a:find('main-R2 ',1,true))
assert(a:find('DMA-vector 4b=',1,true))
assert(a:find('SCSP 15/m_udata.data[i]=80',1,true))
assert(a:find('ready 0004f0:',1,true))
assert(a:find('sound-A7 07fffe: fffe',1,true)) -- clamped at RAM boundary
assert(not a:find('m_Slots',1,true))
assert(not a:find('sound-A2 ',1,true)) -- uninstalled expansion is not a RAM alias
assert(not a:find('sound-A5 ',1,true)) -- never read SCSP MMIO via A5
callback();assert(reads==n and readfile()==a)
now=21;callback();now=22;callback();local b=readfile()
local _, count=b:gsub('SOUNDPROBE t=', '');assert(count==3)
n=reads;now=30;callback();assert(reads==n and readfile()==b)
manager.machine.devices[':scsp']=nil
dofile(script);callback();assert(readfile()==b) -- graceful missing-device failure
print('Sound probe: schedule, cap, state selection, RAM boundaries and failure checks passed')
