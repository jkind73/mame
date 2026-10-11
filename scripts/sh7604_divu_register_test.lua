-- license:BSD-3-Clause
-- Values from YabauseUT sh2.c div_mirror_test/div_operation_test.
local machine=manager.machine
local cpu=machine.devices[':maincpu']
local s=cpu.spaces.program
local path=assert(os.getenv('SH7604_DIVU_STATE_PATH'))
local phase=0
local function equal(a,v,label) assert(s:read_u32(a)==v,string.format('%s at %08x: %08x',label,a,s:read_u32(a))) end
local function copies(q,r)
    for _,window in ipairs({0,0x20}) do
        for _,a in ipairs({0xffffff04,0xffffff14,0xffffff1c}) do equal(a+window,q,'quotient') end
        for _,a in ipairs({0xffffff10,0xffffff18}) do equal(a+window,r,'remainder') end
    end
end
local function run()
    s:write_u32(0x05fe00a0,0xffffffff);cpu.state.SR.value=0xf0
    local base=0x26020000
    for _,window in ipairs({0,0x20}) do
        -- Execute actual word/longword stores and loads through the CPU map.
        for _,word in ipairs({false,true}) do
            for _,value in ipairs({0x0102,0xffff,0xa5a5}) do
                s:write_u16(base,word and 0x2101 or 0x2102) -- MOV.W/L R0,@R1
                s:write_u16(base+2,word and 0x6211 or 0x6212) -- MOV.W/L @R1,R2
                s:write_u16(base+4,0xaffe);s:write_u16(base+6,9)
                cpu.state.R0.value=0xdead0000|value;cpu.state.R1.value=0xffffff0c+window+(word and 2 or 0)
                cpu.state.CURPC.value=base;emu.wait(0.001)
                assert((cpu.state.R2.value&0xffff)==value,'VCRDIV CPU read-back')
                equal(0xffffff0c,value,'VCRDIV upper read-zero/lower R/W')
                equal(0xffffff2c,value,'VCRDIV window alias')
                base=base+16
            end
        end
        s:write_u32(0xffffff00+window,0x10)
        s:write_u32(0xffffff10+window,1);s:write_u32(0xffffff14+window,9)
        emu.wait(0.001);copies(0x10000000,9)
        s:write_u32(0xffffff04+window,0x10000009)
        emu.wait(0.001);copies(0x01000000,9)
    end
    -- Copies are independent writable storage; writing them does not start DIVU.
    s:write_u32(0xffffff18,0x01020304);s:write_u32(0xffffff3c,0x89abcdef)
    equal(0xffffff38,0x01020304,'copy high write');equal(0xffffff1c,0x89abcdef,'copy low write')
    equal(0xffffff10,9,'copy write changed dividend high');equal(0xffffff14,0x01000000,'copy write started division')
    s:write_u32(0xffffff30,0x11223344)
    equal(0xffffff18,0x01020304,'dividend storage changed result copy')
    s:write_u32(0xffffff10,0);s:write_u32(0xffffff14,0x12345)
    emu.wait(0.001);copies(0x1234,5)
    s:write_u32(0xffffff00,0);s:write_u32(0xffffff08,0);s:write_u32(0xffffff04,0x10000000)
    emu.wait(0.001);copies(0x7fffffff,s:read_u32(0xffffff10))
    assert(s:read_u32(0xffffff08)==1,'overflow flag')
    s:write_u32(0xffffff18,0x01020304);s:write_u32(0xffffff1c,0x89abcdef)
    s:write_u32(0xffffff0c,0x0102);phase=1
end
sh7604_divu_thread=coroutine.create(run)
local ok,err=coroutine.resume(sh7604_divu_thread)
if not ok then print('SH7604_DIVU_FAIL '..tostring(err));machine:exit() end
sh7604_divu_frames=emu.add_machine_frame_notifier(function()
    if phase==0 then return end
    local ok,err=pcall(function()
        if phase==1 then machine:save(path);phase=2
        elseif phase==2 then
            s:write_u32(0xffffff18,0);s:write_u32(0xffffff1c,0);s:write_u32(0xffffff0c,0)
            machine:load(path);phase=3
        elseif phase==3 then
            equal(0xffffff38,0x01020304,'saved high copy');equal(0xffffff3c,0x89abcdef,'saved low copy')
            equal(0xffffff2c,0x0102,'saved VCRDIV')
            print('SH7604_DIVU_PASS CPU widths, VCRDIV read-back, both DIVU windows, writable independent copies, division replacement, overflow and scheduled save/load')
            machine:exit()
        end
    end)
    if not ok then print('SH7604_DIVU_FAIL '..tostring(err));machine:exit() end
end)
