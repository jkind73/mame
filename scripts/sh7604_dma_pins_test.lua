-- license:BSD-3-Clause
-- Connected real SH7604 pins/data ports: request modes, phase timing, arbitration and saves.
local machine=manager.machine
local cpu=machine.devices[':maincpu']
local space=cpu.spaces.program
local io=0x01000000
local function r(n) return space:read_u32(io+n*4) end
local function w(n,v) space:write_u32(io+n*4,v) end
local function reg(ch,n) return 0xffffff80+ch*16+n*4 end
local function count(ch) return space:read_u32(reg(ch,2)) end
local function setup(ch,src,dst,n,control)
    space:write_u32(reg(ch,0),src);space:write_u32(reg(ch,1),dst)
    space:write_u32(reg(ch,2),n);space:read_u32(reg(ch,3));space:write_u32(reg(ch,3),control)
end
local function clear()
    space:write_u32(0xffffffb0,0);emu.wait(0.0001)
    for ch=0,1 do space:read_u32(reg(ch,3));space:write_u32(reg(ch,3),0);space:write_u8(0xfffffe71+ch,0) end
    space:read_u32(0xffffffb0);space:write_u32(0xffffffb0,0)
    space:write_u8(0xfffffe91,0);w(16,0);w(13,3);w(12,0);w(14,0);w(15,0)
    w(1,11);w(2,7);space:write_u32(0xffffffe4,0xa55a00fc);space:write_u32(0xffffffe0,0xa55a03f0);space:write_u32(0xffffffec,0xa55a0000);w(0,0)
end
local function source(a,n)
    for i=0,n-1 do space:write_u32(a+4*i,0xaa000001+i) end
end
local function trace()
    local rows={}
    for i=0,r(0)-1 do
        local a=io+0x100+i*16
        rows[#rows+1]={space:read_u32(a),space:read_u32(a+4),space:read_u32(a+8),space:read_u32(a+12)}
    end
    return rows
end
local function writes_order(rows)
    local order={}
    for _,t in ipairs(rows) do
        if t[2]==2 and t[3]>=0x06002000 and t[3]<0x06004000 then
            order[#order+1]=t[3]<0x06003000 and 0 or 1
        end
    end
    return table.concat(order)
end
local phase=0
local function run()
    cpu.state.SR.value=0xf0
    clear();source(0x06001000,16)
    setup(0,0x06001000,0x06002000,3,0x5801)
    w(0,0);space:write_u32(0xffffffb0,1);emu.wait(0.0001)
    assert(count(0)==3,'inactive level request transferred')
    w(13,2);emu.wait(0.000002)
    assert(count(0)==3 and r(0)==0,'external request started before three clocks')
    emu.wait(0.001);assert(count(0)==0 and (space:read_u32(reg(0,3))&2)~=0,'active-low level completion')
    clear();source(0x06001000,3);setup(0,0x06001000,0x06002000,3,0x5841);space:write_u32(0xffffffb0,1)
    for remaining=2,0,-1 do
        w(13,2);emu.wait(0.001);assert(count(0)==remaining,'falling edge count')
        emu.wait(0.001);assert(count(0)==remaining,'held edge repeated')
        w(13,3);emu.wait(0.00001);assert(count(0)==remaining,'wrong edge accepted')
    end
    clear();w(13,2);source(0x06001000,2);setup(0,0x06001000,0x06002000,2,0x5861);space:write_u32(0xffffffb0,1)
    w(13,3);emu.wait(0.001);assert(count(0)==1,'rising edge missing')
    w(13,2);emu.wait(0.001);assert(count(0)==1,'fall accepted in rising mode')
    w(13,3);emu.wait(0.001);assert(count(0)==0,'second rising edge missing')
    -- Both polarities and selected bus phases, including the half-clock tail.
    for _,high in ipairs({0,1}) do for _,am in ipairs({0,1}) do
        clear();w(14,high);source(0x06001000,1)
        setup(0,0x06001000,0x06002000,1,0x5a01|high*0x80|am*0x100)
        w(0,0);space:write_u32(0xffffffb0,1);emu.wait(0.001)
        local active,inactive,read,write
        for _,t in ipairs(trace()) do
            if t[2]==0x10 and t[4]==high then active=t[1]
            elseif t[2]==0x10 then inactive=t[1]
            elseif t[2]==1 and t[3]==0x06001000 then read=t[1]
            elseif t[2]==2 and t[3]==0x06002000 then write=t[1] end
        end
        assert(active==(am==0 and read or write),'DACK selected wrong phase')
        assert(inactive-active==(am==0 and 23 or 15),'DACK half-cycle tail/wait extension')
        assert(inactive< (am==0 and write or active+16),'DACK phase end')
    end end
    -- Fixed/cycle-steal alternation, fixed/burst tenure, round-robin/burst.
    for _,case in ipairs({{0,0,1,'01010101'},{0x10,0x10,1,'00001111'},{0x10,0x10,9,'01010101'},{0,0x10,1,'01010101'}}) do
        clear();source(0x06001000,4);source(0x06001100,4)
        setup(0,0x06001000,0x06002000,4,0x5a01|case[1])
        setup(1,0x06001100,0x06003000,4,0x5a01|case[2])
        w(0,0);space:write_u32(0xffffffb0,case[3]);emu.wait(0.002)
        assert(count(0)==0 and count(1)==0,'two-channel completion')
        assert(writes_order(trace())==case[4],'arbitration order '..writes_order(trace()))
    end
    -- Round-robin keeps the last winner low even when both channels go idle.
    clear();source(0x06001000,2);source(0x06001100,2)
    setup(0,0x06001000,0x06002000,1,0x5a01);space:write_u32(0xffffffb0,9);emu.wait(0.001)
    space:write_u32(0xffffffb0,8)
    setup(0,0x06001000,0x06002000,1,0x5a01);setup(1,0x06001100,0x06003000,1,0x5a01)
    w(0,0);space:write_u32(0xffffffb0,9);emu.wait(0.001)
    assert(writes_order(trace())=='10','round-robin priority lost across idle')
    -- A reserved request selector must not act as an external or auto request.
    clear();source(0x06001000,3);space:write_u8(0xfffffe71,3)
    setup(0,0x06001000,0x06002000,3,0x5801);space:write_u32(0xffffffb0,1);w(13,2);emu.wait(0.001)
    assert(count(0)==3,'reserved RS transferred')
    setup(0,0x06001000,0x06002000,3,0x5a01);emu.wait(0.001)
    assert(count(0)==0,'AR failed to override RS')
    -- A higher-priority request can preempt channel 1 only between complete units.
    clear();source(0x06001000,2);source(0x06001100,4)
    setup(1,0x06001100,0x06003000,4,0x5a11);w(0,0);space:write_u32(0xffffffb0,1)
    emu.wait(0.000028);setup(0,0x06001000,0x06002000,2,0x5a01);emu.wait(0.002)
    assert(writes_order(trace())=='110101','burst preemption/unit ownership '..writes_order(trace()))
    -- Latched edge bursts finish despite deassertion. Level bursts drain already
    -- accepted requests (two dual / three single) before releasing the CPU/bus.
    clear();source(0x06001000,6);setup(0,0x06001000,0x06002000,6,0x5851)
    w(12,1);space:write_u32(0xffffffb0,1);w(13,2);emu.wait(0.002)
    assert(count(0)==0,'edge burst stopped on deassertion')
    clear();source(0x06001000,6);setup(0,0x06001000,0x06002000,6,0x5811)
    w(12,1);space:write_u32(0xffffffb0,1);w(13,2);emu.wait(0.002)
    assert(count(0)==4,'dual level burst did not drain accepted request')
    local pc=cpu.state.PC.value;emu.wait(0.001)
    assert(count(0)==4 and (pc==0x100 or pc==0x102),'waiting burst stranded CPU')
    w(13,2);emu.wait(0.002);assert(count(0)==0,'level burst did not resume')
    clear()
    for i=0,5 do space:write_u8(0x06001000+i,0x40+i) end
    setup(0,0x06001000,0xffffff03,6,0x1019);w(12,1)
    space:write_u32(0xffffffb0,1);w(13,2);emu.wait(0.002)
    assert(count(0)==3 and r(7)==3,'single level burst did not drain three accepted requests')
    for size,bytes in ipairs({1,2,4}) do
        local ts=(size-1)*0x400
        for _,input in ipairs({false,true}) do
            clear();w(3,0x40)
            for n=0,2 do
                if bytes==1 then space:write_u8(0x06001000+n,0x80+n)
                elseif bytes==2 then space:write_u16(0x06001000+n*2,0x8000+n)
                else space:write_u32(0x06001000+n*4,0x80000000+n) end
            end
            local control=input and (0x7109|ts) or (0xd009|ts)
            setup(0,input and 0xffffffff or 0x06001000,input and 0x06002000 or 0xffffff03,3,control)
            space:write_u32(0xffffffb0,1);w(13,2);emu.wait(0.002)
            assert(count(0)==0 and (space:read_u32(0xffffffb0)&4)==0,'single-address completion/ignored address AE')
            assert(r(11)==0,'single-address callback outside DACK')
            if input then
                assert(r(5)==3,'single-address source callback count')
                local value=bytes==1 and space:read_u8(0x06002000+2) or bytes==2 and space:read_u16(0x06002000+4) or space:read_u32(0x06002000+8)
                assert(value==0x42,'single-address input payload')
                assert(space:read_u32(reg(0,0))==0xffffffff,'ignored SAR changed')
            else
                assert(r(7)==3,'single-address destination callback count')
                assert(r(9)==(bytes==1 and 0x82 or bytes==2 and 0x8002 or 0x80000002),'single-address output payload')
                assert(space:read_u32(reg(0,1))==0xffffff03,'ignored DAR changed')
            end
        end
    end
    clear();w(3,0x10);space:write_u32(0xffffffe4,0xa55a007c)
    setup(0,0xffffffff,0x06002000,1,0x7909);w(0,0)
    space:write_u32(0xffffffb0,1);w(13,2);emu.wait(0.001)
    assert(space:read_u32(0x06002000)==0x10111213 and r(5)==4 and r(11)==0,'8-bit bus assembly/DACK/data port masks')
    -- A short 16-byte unit fetches all four words and writes only the final TCR.
    for _,n in ipairs({1,2,3,4,5,7}) do
        clear();source(0x06001000,8)
        for i=0,7 do space:write_u32(0x06002000+i*4,0xdeadbeef) end
        setup(0,0x06001000,0x06002000,n,0x5e01);w(0,0);space:write_u32(0xffffffb0,1);emu.wait(0.003)
        local reads,writes=0,0
        for _,t in ipairs(trace()) do
            if t[2]==1 and t[3]>=0x06001000 and t[3]<0x06001020 then reads=reads+1 end
            if t[2]==2 and t[3]>=0x06002000 and t[3]<0x06002020 then writes=writes+1 end
        end
        assert(reads==math.ceil(n/4)*4 and writes==n,'short burst fetch/write count')
        assert(space:read_u32(0x06002000+n*4)==0xdeadbeef,'short burst overrun')
    end
    -- SDRAM's read acknowledgement spans the complete burst, including waits.
    clear();source(0x06001000,4)
    space:write_u32(0xffffffe0,0xa55a03f1);space:write_u32(0xffffffec,0xa55a0040)
    setup(0,0x06001000,0x06002000,4,0x5e01);w(0,0);space:write_u32(0xffffffb0,1);emu.wait(0.001)
    local active,inactive,pulses=nil,nil,0
    for _,t in ipairs(trace()) do
        if t[2]==0x10 and t[4]==0 then active=t[1];pulses=pulses+1
        elseif t[2]==0x10 then inactive=t[1] end
    end
    assert(pulses==1 and inactive-active==23,'SDRAM acknowledgement split or lost wait span')
    -- Module stop freezes an accepted read phase, including its DACK state.
    clear();source(0x06001000,2)
    w(1,100);w(2,100);setup(0,0x06001000,0x06002000,2,0x5a11)
    space:write_u32(0xffffffb0,1);emu.wait(0.00002)
    assert(cpu.state.DACK0.value==0 and count(0)==2,'module-stop fixture missed read phase')
    space:write_u8(0xfffffe91,0x10);emu.wait(0.05)
    assert(cpu.state.DACK0.value==0 and count(0)==2,'module stop progressed DMA/pins')
    space:write_u8(0xfffffe91,0);emu.wait(0.001)
    assert(count(0)==0 and cpu.state.DACK0.value==1,'module restart failed to complete/release DMA')
    -- Forced stop finishes the accepted read/write unit; no later unit runs.
    for _,abort in ipairs({0x10,0x20}) do
        clear();source(0x06001000,3);setup(0,0x06001000,0x06002000,3,0x5a11)
        w(12,abort);space:write_u32(0xffffffb0,1);emu.wait(0.001)
        assert(count(0)==2,'abort did not finish exactly the accepted unit')
        assert((space:read_u32(reg(0,3))&2)==0,'aborted non-final transfer set TE')
        if abort==0x20 then assert((space:read_u32(0xffffffb0)&2)~=0,'NMI did not inhibit DMA') end
    end
    clear();source(0x06001000,3)
    -- Internal bus tenure must not clear a HALT driven by another device.
    space:write_u16(0x06007000,0x7701);space:write_u16(0x06007002,0xaffd);space:write_u16(0x06007004,0x0009)
    cpu.state.R7.value=0;cpu.state.CURPC.value=0x06007000;emu.wait(0.001)
    assert(cpu.state.R7.value>0,'HALT fixture CPU did not execute')
    w(17,1);emu.wait(0.0001);local held=cpu.state.R7.value
    for _,burst in ipairs({0,0x10}) do
        clear();source(0x06001000,3);setup(0,0x06001000,0x06002000,3,0x5a01|burst)
        space:write_u32(0xffffffb0,1);emu.wait(0.002)
        assert(count(0)==0 and cpu.state.R7.value==held,'DMA released external HALT')
    end
    w(17,0);emu.wait(0.001);assert(cpu.state.R7.value>held,'external HALT clear failed to resume CPU')
    cpu.state.CURPC.value=0x100;clear();source(0x06001000,3)
    -- Long bus waits make a live read/write unit span a scheduled save boundary.
    w(1,30000);w(2,30000);source(0x06001100,3)
    setup(0,0x06001000,0x06002000,3,0x5a11);setup(1,0x06001100,0x06003000,3,0x5a11)
    w(0,0);space:write_u32(0xffffffb0,9);phase=1
end
sh7604_dma_pin_thread=coroutine.create(run)
local ok,err=coroutine.resume(sh7604_dma_pin_thread)
if not ok then print('SH7604_DMA_PIN_FAIL '..tostring(err));machine:exit() end
local savepath=assert(os.getenv('SH7604_DMA_PIN_STATE_PATH'))
local saved_count,saved_ack,saved_trace,first_trace
sh7604_dma_pin_load=emu.add_machine_post_load_notifier(function()
    if phase==3 then
        assert(count(0)==saved_count and cpu.state.DACK0.value==saved_ack,'active unit/pin not restored')
        phase=4
    end
end)
local function signature(rows)
    local result={}
    for i=saved_trace+1,#rows do local t=rows[i];result[#result+1]=table.concat(t,',') end
    return table.concat(result,';')
end
sh7604_dma_pin_frames=emu.add_machine_frame_notifier(function()
    if phase==0 then return end
    local ok,err=pcall(function()
        if phase==1 then
            saved_count=count(0);saved_ack=cpu.state.DACK0.value;saved_trace=r(0)
            assert(saved_count==3 and saved_ack==0,'fixture not in live read phase')
            machine:save(savepath);phase=2
        elseif phase==2 then
            if count(0)==0 and count(1)==0 and (space:read_u32(reg(0,3))&2)~=0 then
                first_trace=signature(trace());machine:load(savepath);phase=3
            end
        elseif phase==4 and count(0)==0 and count(1)==0 and (space:read_u32(reg(0,3))&2)~=0 then
            assert(signature(trace())==first_trace,'restored live DMA trace diverged')
            print('SH7604_DMA_PIN_PASS external levels/edges, phases/polarities, single ports, beat widths, arbitration/preemption, accepted bursts, abort and live scheduled save/load')
            machine:exit()
        end
    end)
    if not ok then print('SH7604_DMA_PIN_FAIL '..tostring(err));machine:exit() end
end)
