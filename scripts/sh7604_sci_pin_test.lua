-- license:BSD-3-Clause
-- Timed serial pin tests on the real SH7604: clocks, formats, errors and DMA.
local machine=manager.machine
local cpu=machine.devices[':maincpu']
local space=cpu.spaces.program
local phi=math.floor(14318181*1708/455/2)
local bit=128*4/phi
local function read(reg) return space:read_u8(0xfffffe00+reg) end
local function write(reg,value) space:write_u8(0xfffffe00+reg,value) end
local function config(format,control,brr)
    write(2,0)
    space:write_u8(0xfffffe91,1);space:write_u8(0xfffffe91,0)
    write(0,format);write(1,brr or 3)
    cpu.state.RXD.value=1;cpu.state.SCK.value=1
    write(2,control)
    emu.wait(bit*2)
end
local function frame(value,format,mp,bad_parity,bad_stop)
    local bits={0}
    local count=(format&0x40)~=0 and 7 or 8
    local parity=0
    for n=0,count-1 do local v=(value>>n)&1;bits[#bits+1]=v;parity=parity~v end
    if (format&4)~=0 then bits[#bits+1]=mp and 1 or 0
    elseif (format&0x20)~=0 then bits[#bits+1]=parity~((format>>4)&1)~(bad_parity and 1 or 0) end
    bits[#bits+1]=bad_stop and 0 or 1
    if (format&8)~=0 then bits[#bits+1]=1 end
    return bits
end
local function receive(value,format,ext,mp,bad_parity,bad_stop)
    for _,v in ipairs(frame(value,format,mp,bad_parity,bad_stop)) do
        cpu.state.RXD.value=v
        if ext then
            for n=1,16 do
                cpu.state.SCK.value=0;emu.wait(0.000005)
                cpu.state.SCK.value=1;emu.wait(0.000005)
            end
        else emu.wait(bit) end
    end
    cpu.state.RXD.value=1;emu.wait(bit)
end
local function run()
    space:write_u16(0x26003000,0xaffe);space:write_u16(0x26003002,0x0009)
    cpu.state.CURPC.value=0x26003000;cpu.state.SR.value=0xf0
    space:write_u32(0x05fe00a0,0xffffffff)
    space:write_u16(0xfffffe60,0x7000)
    -- Observe actual TXD at each bit centre in every asynchronous format.
    for _,fmt in ipairs({0,0x40,0x20,0x30,0x68,0x78,4,0x4c}) do
        config(fmt,0x20)
        write(3,0xa5);read(4);write(4,(fmt&4)~=0 and 1 or 0)
        for index,expected in ipairs(frame(0xa5,fmt,true)) do
            emu.wait(bit/2);assert(cpu.state.TXD.value==expected,string.format('TXD fmt=%02x bit=%d expected=%d actual=%d SSR=%02x',fmt,index,expected,cpu.state.TXD.value,read(4)))
            emu.wait(bit/2)
        end
        emu.wait(bit/4);assert((read(4)&0x84)==0x84,'TX did not finish')
    end
    config(0,0x22);write(3,0xa5);read(4);write(4,0)
    local txbits=frame(0xa5,0,false)
    for edge=1,161 do
        cpu.state.SCK.value=0;emu.wait(0.000005)
        cpu.state.SCK.value=1;emu.wait(0.000005)
        if edge<=145 and (edge-1)%16==0 then
            assert(cpu.state.TXD.value==txbits[1+(edge-1)//16],'external asynchronous TXD')
        end
    end
    assert((read(4)&0x84)==0x84,'external asynchronous completion')
    -- Receive through RXD with internal and external 16x SCK clocks.
    for _,ext in ipairs({false,true}) do
        for _,fmt in ipairs({0,0x40,0x20,0x30,0x68,0x78}) do
            config(fmt,0x50|(ext and 2 or 0));receive(0xa5,fmt,ext)
            assert((read(4)&0x78)==0x40,'RX flag/error state')
            assert(read(5)==((fmt&0x40)~=0 and 0x25 or 0xa5),'RX pin data/length')
        end
    end
    config(0,0x50);cpu.state.RXD.value=0;emu.wait(bit/4);cpu.state.RXD.value=1;emu.wait(bit)
    assert((read(4)&0x78)==0,'false start produced a byte')
    config(0x20,0x50);receive(0x13,0x20,false,false,true)
    assert((read(4)&0x78)==8 and read(5)==0x13,'parity error/data retention')
    receive(0x24,0x20,false);assert(read(5)==0x13,'receiver ignored latched error')
    read(4);write(4,0);receive(0x24,0x20,false,false,false,true)
    assert((read(4)&0x78)==0x10 and read(5)==0x24,'framing error')
    config(0,0x50);receive(0x35,0,false);receive(0x46,0,false)
    assert((read(4)&0x60)==0x60 and read(5)==0x35,'overrun replaced unread byte')
    config(4,0x58);receive(0x57,4,false,false,false,true)
    assert((read(4)&0x7a)==0 and (read(2)&8)~=0,'MPIE failed to suppress data/errors')
    receive(0x68,4,false,true)
    assert((read(4)&0x42)==0x42 and (read(2)&8)==0 and read(5)==0x68,'multiprocessor address wake')
    -- Actual GPIO RX frames drive both DMA channels; CPU RDR reads don't acknowledge RXI.
    for channel=0,1 do
        config(0,0x10)
        local off=channel*16
        local dst=0x26004000+channel*0x100
        space:read_u32(0xffffff8c+off);space:write_u32(0xffffff8c+off,0)
        space:write_u32(0xffffffb0,0)
        space:write_u8(0xfffffe71+channel,1)
        space:write_u32(0xffffff80+off,0xfffffe05)
        space:write_u32(0xffffff84+off,dst)
        space:write_u32(0xffffff88+off,2)
        space:write_u32(0xffffff8c+off,0x4001)
        space:write_u32(0xffffffb0,1)
        receive(0x79,0,false)
        assert(space:read_u32(0xffffff88+off)==2 and read(5)==0x79 and (read(4)&0x40)~=0,'disabled-RIE/CPU-RDR ack')
        write(2,0x50);emu.wait(0.00001)
        assert(space:read_u32(0xffffff88+off)==1 and space:read_u8(dst)==0x79 and (read(4)&0x40)==0,'RX DMA request/ack')
        receive(0x8a,0,false);emu.wait(0.00001)
        assert(space:read_u32(0xffffff88+off)==0 and space:read_u8(dst+1)==0x8a,'RX DMA rearm/payload')
        assert((space:read_u32(0xffffff8c+off)&2)~=0,'RX DMA completion')
        space:read_u32(0xffffff8c+off);space:write_u32(0xffffff8c+off,0)
    end
    -- Internal synchronous clock and full duplex through actual RXD/TXD/SCKOUT.
    config(0x80,0x20,31);write(3,0x5a);read(4);write(4,0);write(2,0x30)
    local period=16*32/phi
    local last=1;local rises=0
    while rises<8 do
        emu.wait(period/4)
        local clk=cpu.state.SCKOUT.value
        if clk~=last then
            if clk==0 then cpu.state.RXD.value=cpu.state.TXD.value else rises=rises+1 end
            last=clk
        end
    end
    assert(read(5)==0x5a and (read(4)&0x40)~=0,'synchronous internal full duplex')
    write(2,0)
    -- External synchronous clock: eight falling/rising pairs, independent TX/RX data.
    config(0x80,0x32);write(3,0xa5);read(4);write(4,0)
    for n=0,7 do
        cpu.state.SCK.value=0
        assert(cpu.state.TXD.value==((0xa5>>n)&1),'external synchronous TXD')
        cpu.state.RXD.value=(0x3c>>n)&1;emu.wait(0.00001)
        cpu.state.SCK.value=1;emu.wait(0.00001)
    end
    assert(read(5)==0x3c and (read(4)&0xc4)==0xc4,'external synchronous full duplex')
    -- Save/load with both synchronous shifters halfway through a character.
    config(0x80,0x32);write(3,0xa5);read(4);write(4,0)
    local function syncbits(first,last)
        for n=first,last do
            cpu.state.SCK.value=0
            assert(cpu.state.TXD.value==((0xa5>>n)&1),'restored synchronous TX bit')
            cpu.state.RXD.value=(0x3c>>n)&1;emu.wait(0.00001)
            cpu.state.SCK.value=1;emu.wait(0.00001)
        end
    end
    syncbits(0,3)
    local savepath=machine.options.entries.state_directory:value()..'/sci-pins.sta'
    machine:save(savepath);emu.wait(0.02)
    syncbits(4,7);assert(read(5)==0x3c,'first complete synchronous receive')
    machine:load(savepath);emu.wait(0.02)
    assert((read(4)&0x44)==0,'partial receive/transmit state not restored')
    syncbits(4,7)
    assert(read(5)==0x3c and (read(4)&0xc4)==0xc4,'restored synchronous receive')
    -- Asynchronous clock output remains periodic and stops on module standby.
    config(0,1);local clk=cpu.state.SCKOUT.value;local edges=0
    for n=1,8 do emu.wait(bit/4);local v=cpu.state.SCKOUT.value;if v~=clk then edges=edges+1;clk=v end end
    assert(edges>=3,'asynchronous SCK output missing')
    space:write_u8(0xfffffe91,1);emu.wait(bit*2)
    assert(cpu.state.TXD.value==1 and cpu.state.SCKOUT.value==1,'module standby pin reset')
    print('SH7604_PIN_PASS timed TX/RX formats, internal/external clocks, errors, MPIE, both RX DMA channels, synchronous full duplex, module-stop pins')
end
sh7604_sci_pin_thread=coroutine.create(function()
    local ok,err=pcall(run)
    if not ok then print('SH7604_PIN_FAIL '..tostring(err)) end
    machine:exit()
end)
local ok,err=coroutine.resume(sh7604_sci_pin_thread)
if not ok then print('SH7604_PIN_FAIL '..tostring(err));machine:exit() end
