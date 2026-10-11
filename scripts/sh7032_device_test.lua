-- license:BSD-3-Clause
-- Timed register, peripheral and physical pin checks on the actual SH-1.
local m=manager.machine
local cpu=m.devices[':maincpu'];local s=cpu.spaces.program
local phi=16000000
local function wait(n)emu.wait((n+0.01)/phi)end
local function r8(a)return s:read_u8(0x05fffe00+a)end
local function w8(a,v)s:write_u8(0x05fffe00+a,v)end
local function r16(a)return s:read_u16(0x05fffe00+a)end
local function w16(a,v)s:write_u16(0x05fffe00+a,v)end
local function w32(a,v)s:write_u32(0x05fffe00+a,v)end
local function f(n,v)if v~=nil then s:write_u32(0x0a000000+4*n,v)else return s:read_u32(0x0a000000+4*n)end end
local function dma(ch,src,dst,count,control)
 local b=0x140+16*ch;r16(b+14);w16(b+14,0);w32(b,src);w32(b+4,dst);w16(b+10,count);w16(b+14,control)
end
local function serial(ch,fmt,ctrl,brr)
 local b=0xc0+8*ch;w8(b+2,0);w8(b,fmt);w8(b+1,brr or 31);w8(b+2,ctrl)
end
local function send(ch,value)
 local b=0xc0+8*ch;w8(b+3,value);r8(b+4);w8(b+4,0)
end
local function run()
 assert(r8(0xc4)==0x84 and r8(0xcc)==0x84,'SCI reset')
 assert(r16(0x1c8)==0x3302 and r16(0x1ca)==0xff95,'PFC reset')
 assert(s:read_u16(0x050001c8)==0x3302,'peripheral decode mirror')
 assert(r16(0x148)==0,'DMAOR reset')
 s:write_u16(0x0f000100,0x55aa);assert(s:read_u16(0x0f002100)==0x55aa and s:read_u16(0x0fffe100)==0x55aa,'area-7 RAM mirrors')
 assert(r8(0x1b8)==0x18 and r8(0x1bb)==0x1f,'WDT reset')
 s:write_u16(0x0fffe100,0x1234);s:write_u16(0x0fffe102,0xabcd)
 -- A request pulse while disabled must not be queued for the next transfer.
 f(0,0);f(0,1)
 -- No transfer without the external request. One edge is one cycle-steal unit.
 dma(0,0x0fffe100,0x0fffe200,2,0x5029);w16(0x148,1);wait(80)
 assert(r16(0x14a)==2 and s:read_u16(0x0fffe200)==0,'unrequested external DMA')
 f(0,0);wait(80)
 assert(r16(0x14a)==1 and s:read_u16(0x0fffe200)==0x1234,'DREQ edge single unit')
 wait(80);assert(r16(0x14a)==1,'edge repeated while pad low')
 f(0,1);f(0,0);wait(80)
 assert(r16(0x14a)==0 and s:read_u16(0x0fffe202)==0xabcd,'second DREQ edge')
 assert((r16(0x14e)&2)==2 and f(0)>=4,'transfer end / DACK phases')
 -- TE is hardware-set; CPU clearing requires read-one/write-zero.
 w16(0x14e,0);assert((r16(0x14e)&2)==0,'TE acknowledgement')
 -- Single-address device -> memory, including byte request interfaces.
 f(1,1);dma(1,0,0x09000210,2,0x4029|0x300);f(1,0);wait(80)
 assert(s:read_u16(0x09000210)==0xabcd and r16(0x15a)==1,'single-address input')
 f(1,1);f(1,0);wait(80);assert(s:read_u16(0x09000212)==0xabce,'single-address second input')
 -- Memory -> device callback; the destination address is not a memory write.
 s:write_u16(0x09000100,0x1234);dma(0,0x09000100,0,1,0x1029|0x200);f(0,1);f(0,0);wait(80)
 assert(f(4)==1 and f(6)==0x1234,'single-address output')
 -- Auto requests and increment modes, followed by address error inhibition.
 dma(2,0x0fffe100,0x0fffe220,2,0x5c09);wait(80)
 assert(s:read_u16(0x0fffe220)==0x1234 and s:read_u16(0x0fffe222)==0xabcd,'auto DMA')
 dma(3,0x0fffe101,0x0fffe240,1,0x5c09);wait(80)
 assert((r16(0x148)&4)==4 and (r16(0x17e)&2)==0,'DMA misalignment')
 r16(0x148);w16(0x148,0);for ch=0,3 do w16(0x14e+16*ch,0)end

 -- Arbitration is observable as writes to the diagnostic bus FIFO.
 for mode=0,3 do
  w16(0x148,0);f(33,0)
  for ch=0,3 do
   for i=0,3 do s:write_u16(0x0fffe300+ch*16+i*2,ch*16+i)end
   dma(ch,0x0fffe300+ch*16,0x0a000080,4,0x1c09)
  end
  w16(0x148,1|(mode<<8));wait(500)
  assert(f(32)==16,'DMA priority trace length')
  local expected={}
  if mode==0 or mode==1 then
   for _,ch in ipairs(mode==0 and {0,3,2,1} or {1,3,2,0})do
    for i=0,3 do expected[#expected+1]=ch*16+i end
   end
  elseif mode==2 then
   for i=0,3 do for _,ch in ipairs({0,3,2,1})do expected[#expected+1]=ch*16+i end end
  else
   for _,ch in ipairs({3,2})do for i=0,3 do expected[#expected+1]=ch*16+i end end
   for i=0,3 do for _,ch in ipairs({1,0})do expected[#expected+1]=ch*16+i end end
  end
  for i,value in ipairs(expected)do assert(f(32+i)==value,string.format('DMA priority %d slot %d got %x expected %x',mode,i,f(32+i),value))end
 end
 w16(0x148,0);for ch=0,3 do r16(0x14e+16*ch);w16(0x14e+16*ch,0)end

 -- WAIT must hold the one single-address bus transaction, including DACK;
 -- all registered SH-1 storage is compared byte-for-byte after restoration.
 f(0,1);cpu.state.WAIT.value=0;local writes=f(4)
 dma(0,0x09000100,0,1,0x1269);w16(0x148,1)
 assert(cpu.state.DACK0.value==1,'active-low DACK idle polarity')
 f(0,0);wait(20)
 assert(f(4)==writes and r16(0x14a)==1 and cpu.state.DACK0.value==0,'WAIT / active-low DACK hold')
 local function cpu_storage()
  local result={}
  for i=0,100000 do local item=emu.item(i);if item.size==0 then break end
   if item.name:find('/:maincpu/',1,true)then result[item.name]=item:read_block(0,item.size*item.count)end
  end
  return result
 end
 local pending=m:buffer_save();local storage=cpu_storage()
 cpu.state.WAIT.value=1;w16(0x148,0)
 assert(m:buffer_load(pending),'DMA in-flight buffer load')
 local restored=m:buffer_save()
 if restored~=pending then
  local function dump(name,data)local file=assert(io.open(name,'wb'));file:write(data);file:close()end
  dump('pending.bin',pending);dump('restored.bin',restored)
  local layout=assert(io.open('layout.tsv','w'));local offset=0
  for i=0,100000 do local item=emu.item(i);if item.size==0 then break end
   layout:write(string.format('%d\t%d\t%d\t%s\n',i,offset,item.size*item.count,item.name));offset=offset+item.size*item.count
  end
  layout:close()
 end
 -- buffer_load runs inside Lua's current resume callback; its timer and
 -- scheduler queue indices necessarily change. Retain the full buffers as
 -- evidence, and compare every byte of every registered SH-1 field.
 local actual=cpu_storage();local fields=0
 for name,data in pairs(storage)do assert(actual[name]==data,'SH-1 restore differs: '..name);fields=fields+1 end
 assert(fields>80,'incomplete SH-1 saved-storage coverage')
 print('SH7032 saved storage restore PASS '..fields..' complete fields')
 wait(30);assert(f(4)==writes,'restored WAIT did not hold DMA')
 cpu.state.WAIT.value=1;wait(40)
 assert(f(4)==writes+1 and r16(0x14a)==0 and cpu.state.DACK0.value==1,'restored single DMA completion')
 w16(0x148,0)
 -- External edge burst does not stop the CPU until a request arrives.
 s:write_u16(0x0fffed00,0x7a01);s:write_u16(0x0fffed02,0xaffd);s:write_u16(0x0fffed04,0x0009)
 cpu.state.R10.value=0;cpu.state.CURPC.value=0x0fffed00
 f(0,1);dma(0,0x0fffe100,0x0fffe500,0,0x5039);w16(0x148,1);wait(80)
 local running=cpu.state.R10.value;assert(running>0 and r16(0x14a)==0,'unrequested burst halted CPU')
 f(0,0);wait(12);local stopped=cpu.state.R10.value;wait(80)
 assert(cpu.state.R10.value==stopped and r16(0x14a)>0xff00,'zero count / burst CPU ownership')
 w16(0x148,0);wait(40)
 assert(cpu.state.R10.value>stopped and (r16(0x14e)&2)==0,'cancelled burst stranded CPU or set TE')
 r16(0x14e);w16(0x14e,0);cpu.state.CURPC.value=0x100
 print('SH7032 DMA requests/acknowledgments PASS')
 -- Actual serial pin loopback: synchronous bytes take eight clock periods.
 f(2,1);serial(1,0x80,0x12);serial(0,0x80,0x20);send(0,0xa5)
 wait(128*9)
 assert((r8(0xcc)&0x78)==0x40 and r8(0xcd)==0xa5,'synchronous pin RX')
 r8(0xcc);w8(0xcc,0);serial(1,0,0x10);serial(0,0,0x20);send(0,0x5a)
 wait(1024*12)
 assert((r8(0xcc)&0x78)==0x40 and r8(0xcd)==0x5a,'asynchronous pin RX')
 assert((r8(0xc4)&0x84)==0x84,'serial complete')
 f(2,0);serial(0,0x80,0x30);r8(0xc4);w8(0xc4,0x84);send(0,0x69);wait(128*9)
 assert((r8(0xc4)&0x60)==0x40,'full-duplex synchronous receive')
 r8(0xc4);w8(0xc4,0x84);wait(128*20)
 assert((r8(0xc4)&0x60)==0,'idle synchronous transmitter kept receive clock running')
 serial(0,0,0);serial(1,0,0)

 -- Both SCI channels share framing semantics, but keep independent state.
 local function frame(value,fmt,badparity,badstop,mp)
  local bits={0};local parity=0;local n=(fmt&0x40)~=0 and 7 or 8
  for i=0,n-1 do local bit=(value>>i)&1;bits[#bits+1]=bit;parity=parity~bit end
  if (fmt&4)~=0 then bits[#bits+1]=mp and 1 or 0
  elseif (fmt&0x20)~=0 then bits[#bits+1]=parity~((fmt>>4)&1)~(badparity and 1 or 0)end
  bits[#bits+1]=badstop and 0 or 1;if(fmt&8)~=0 then bits[#bits+1]=1 end
  return bits
 end
 local function receive(value,fmt,badparity,badstop,mp)
  for _,bit in ipairs(frame(value,fmt,badparity,badstop,mp))do cpu.state.RXD1.value=bit;wait(1024)end
  cpu.state.RXD1.value=1;wait(1024)
 end
 for _,fmt in ipairs({0,0x40,0x20,0x30,0x68,0x78})do
  r8(0xcc);w8(0xcc,0);serial(1,fmt,0x50)
  receive(0xa5,fmt,false,false,false)
  assert((r8(0xcc)&0x78)==0x40 and r8(0xcd)==((fmt&0x40)~=0 and 0x25 or 0xa5),'SCI frame format')
 end
 r8(0xcc);w8(0xcc,0);serial(1,0x20,0x50);receive(0xa5,0x20,true,false,false)
 assert((r8(0xcc)&8)~=0 and (r8(0xcc)&0x40)==0,'SCI parity error')
 r8(0xcc);w8(0xcc,0);serial(1,0,0x50);receive(0xa5,0,false,true,false)
 assert((r8(0xcc)&0x10)~=0,'SCI framing error')
 r8(0xcc);w8(0xcc,0);receive(0xa5,0,false,false,false);receive(0x5a,0,false,false,false)
 assert((r8(0xcc)&0x20)~=0 and r8(0xcd)==0xa5,'SCI receive overrun preserves RDR')
 r8(0xcc);w8(0xcc,0);serial(1,4,0x58);receive(0xa5,4,false,false,false)
 assert((r8(0xcc)&0x40)==0,'SCI MPIE rejects data frame')
 receive(0xa5,4,false,false,true)
 assert((r8(0xcc)&0x42)==0x42 and (r8(0xca)&8)==0,'SCI address frame clears MPIE')
 r8(0xcc);w8(0xcc,0);serial(1,0,0)
 -- Port-function selection routes physical PB8 input to RXD0.
 w16(0x1cc,2);cpu.state.PORTB.value=0xffff;serial(0,0,0x10)
 for _,bit in ipairs(frame(0x96,0,false,false,false))do cpu.state.PORTB.value=bit==1 and 0xffff or 0xfeff;wait(1024)end
 cpu.state.PORTB.value=0xffff;wait(1024)
 assert(r8(0xc5)==0x96 and (r8(0xc4)&0x40)~=0,'PFC serial input routing')
 r8(0xc4);w8(0xc4,0);serial(0,0,0);w16(0x1cc,0)
 print('SH7032 SCI synchronous/asynchronous pins PASS')
 -- Eight ADC inputs use four shared result registers and scan group selection.
 for i=0,7 do f(8+i,17+100*i)end
 w8(0xe8,0x28|6);wait(134)
 assert(r16(0xe4)==(617<<6),string.format('ADC single AN6 result=%04x CSR=%02x',r16(0xe4),r8(0xe8)))
 assert((r8(0xe8)&0xa0)==0x80,'ADC end clears ADST')
 w8(0xe8,0x3e);wait(134+128*2)
 assert(r16(0xe0)==(417<<6) and r16(0xe2)==(517<<6) and r16(0xe4)==(617<<6),'ADC scan group 1')
 w8(0xe8,0);w8(0xe9,0x80);f(16,1);f(16,0);wait(266)
 assert((r8(0xe8)&0x80)~=0,'external ADTRG')
 w8(0xe8,0);w8(0xe9,0)

 w8(0xe8,0x2f);wait(40)
 local snapshot=m:buffer_save()
 w8(0xe8,0);cpu.state.RXD0.value=0;cpu.state.DREQ0.value=1
 assert(m:buffer_load(snapshot),'buffer load')
 assert((r8(0xe8)&0x20)~=0,'ADC in-flight state lost')
 wait(100);assert(r16(0xe6)==(717<<6),'ADC conversion after restore')
 w8(0xe8,0)
 print('SH7032 ADC channels/scan/trigger PASS')
 -- External timer count, capture, compare output, flags and synchronous preset.
 w8(0x104,4);w8(0x105,3);w16(0x10a,2);w16(0x1c4,1);w16(0x1ca,0xff96);w8(0x100,1)
 for i=1,3 do f(17,0);f(17,1)end
 assert(r16(0x108)==3 and (r8(0x107)&1)==1 and (f(8)&1)==1,'ITU external compare')
 w8(0x10f,4);w8(0x100,3);f(23,0);f(23,1)
 assert((r8(0x111)&1)==1,'ITU input capture')
 w8(0x101,3);w16(0x108,0x4321);assert(r16(0x112)==0x4321,'ITU synchronized preset')
 w8(0x100,0);w8(0x101,0)
 -- Phase mode counts both pads in both directions.
 w16(0x11c,0);w8(0x102,0x40);w8(0x100,4)
 f(17,0);f(18,0);local before=r16(0x11c)
 f(18,1);f(17,1);f(18,0);f(17,0)
 assert(r16(0x11c)==((before+4)&0xffff),'ITU quadrature')
 w8(0x100,0);w8(0x102,0)

 local function edge()f(17,0);f(17,1)end
 -- PWM duty transitions and inhibited simultaneous A/B compare matches.
 w8(0x104,0x44);w16(0x108,0);w16(0x10a,2);w16(0x10c,4);w8(0x102,1);w8(0x100,1)
 edge();edge();assert((f(8)&1)==1,'PWM changed before compare clock')
 edge();assert((f(8)&1)==1,'PWM A high')
 edge();edge();assert((f(8)&1)==0 and r16(0x108)==0,'PWM B low and clear')
 w8(0x100,0);r8(0x107);w8(0x107,0);w16(0x108,0);w16(0x10a,2);w16(0x10c,2);w8(0x100,1)
 edge();edge();edge();assert((r8(0x107)&3)==0 and r16(0x108)==3,'simultaneous PWM compare inhibition')
 w8(0x100,0);w8(0x102,0)
 -- Buffer operation in normal timer mode copies BRA3 on A3 match.
 w8(0x122,4);w8(0x123,3);w16(0x126,0);w16(0x128,2);w16(0x12c,7);w8(0x103,1);w8(0x100,8)
 edge();edge();edge();assert(r16(0x128)==7,'ITU output compare buffer')
 w8(0x100,0);w8(0x103,0)
 -- Reset-synchronized PWM uses counter 3 for all three waveform pairs;
 -- counter 4 independently counts and is not cleared by GRA4.
 w16(0x1c6,0xfc);w16(0x1ce,0xaaa0);w8(0x131,3)
 w8(0x122,4);w8(0x132,4);w16(0x126,0);w16(0x136,0)
 w16(0x128,8);w16(0x12a,2);w16(0x138,4);w16(0x13a,6);w8(0x103,0x30);w8(0x100,0x18)
 local startpads=f(9)
 for i=1,9 do
  edge()
  if i==3 then assert((f(9)&12)==((startpads~12)&12),'reset PWM pair 1')end
  if i==5 then assert((f(9)&0x50)==((startpads~0x50)&0x50),'reset PWM pair 2')end
  if i==7 then assert((f(9)&0xa0)==((startpads~0xa0)&0xa0),'reset PWM pair 3')end
 end
 assert(r16(0x126)==0 and r16(0x136)==9,'reset PWM counters')
 local pads=f(9)&0xfc;w8(0x131,0);assert((f(9)&0xfc)==(pads~0xfc),'TOCR polarity')
 w8(0x100,0);w8(0x131,3)
 -- Complementary PWM overshoots on A3, undershoots on counter 4,
 -- and never turns both transistors in a pair on during the dead time.
 w8(0x122,4);w8(0x132,4);w16(0x126,2);w16(0x136,0)
 w16(0x128,8);w16(0x12a,4);w16(0x138,5);w16(0x13a,6);w8(0x103,0x20);w8(0x100,0x18)
 for i=1,45 do
  edge();local v=f(9)
  assert((v&12)~=12 and (v&0x50)~=0x50 and (v&0xa0)~=0xa0,'complementary PWM overlap')
  if i==7 then assert(r16(0x126)==9,'complementary PWM upper overshoot')end
  if i==15 then assert(r16(0x136)==0xffff,'complementary PWM lower undershoot')end
 end
 w8(0x100,0);w8(0x103,0)
 -- TPC groups with different sources have distinct low-nibble NDR addresses.
 w16(0x1c2,0xff);w16(0x1c6,0xff);w16(0x1ce,0xffff)
 w8(0x1f1,4);w8(0x1f3,0xff);w8(0x1f5,0xa0);w8(0x1f7,5)
 w8(0x104,4);w8(0x105,0);w16(0x108,0);w16(0x10a,0);w8(0x100,1)
 edge();assert((r16(0x1c2)&0xff)==0xf5,'TPC group 0 separate trigger')
 w8(0x100,0);w8(0x1f0,1);w8(0x1f7,9);w16(0x108,0);w16(0x10a,3);w16(0x10c,1);w8(0x100,1)
 edge();edge();assert((r16(0x1c2)&15)==1,'TPC B clears only next-data zero bits')
 edge();edge();assert((r16(0x1c2)&15)==9,'TPC A commits next data')
 w8(0x100,0)
 print('SH7032 ITU external/capture/sync/phase PASS')
 -- Watchdog keys and access widths, interval overflow, external pulse.
 w8(0x1b8,0xa5);w8(0x1b9,0x20);assert(r8(0x1b8)==0x18,'WDT byte key rejected')
 w16(0x1b8,0x5aff);w16(0x1b8,0xa520);wait(3)
 assert((r8(0x1b8)&0x80)==0x80,'WDT interval overflow')
 w16(0x1b8,0xa500);w16(0x1b8,0x5aff);w16(0x1b8,0xa560);wait(3)
 assert(cpu.state.WDTOVF.value==0 and (r8(0x1bb)&0x80)~=0,'WDT output/flag')
 wait(128);assert(cpu.state.WDTOVF.value==1 and r8(0x1b8)==0x18,'WDT pulse width and local reset')
 r8(0x1bb);w16(0x1ba,0xa500);assert((r8(0x1bb)&0x80)==0,'WOVF read-clear')
 print('SH7032 watchdog interval/pulse/keys PASS')

 -- Run a guest interrupt handler: no synthetic peripheral acknowledgments.
 local vbr=0x0fffe000;local handler=0x0fffeb00;local count=0x0fffea00
 cpu.state.VBR.value=vbr;cpu.state.R0.value=count
 s:write_u32(vbr+112*4,handler)
 local code={0x6102,0x7101,0x2012,0x6420,0x2230,0x002b,0x0009}
 for i,op in ipairs(code)do s:write_u16(handler+2*(i-1),op)end
 s:write_u32(count,0);cpu.state.R2.value=0x05ffffb8;cpu.state.R3.value=0x5a
 w16(0x18c,0x0030);cpu.state.SR.value=0
 w16(0x1b8,0x5aff);w16(0x1b8,0xa520);wait(120)
 -- Byte writes cannot acknowledge the keyed WDT, so the interrupt remains
 -- eligible after every RTE, exercising persistent request handling.
 assert(s:read_u32(count)>1,'persistent WDT interrupt did not repeat')
 cpu.state.SR.value=0xf0;r8(0x1b8);w16(0x1b8,0xa500);w16(0x18c,0)
 cpu.state.CURPC.value=0x100
 -- Internal watchdog reset selects the correct vector pair and keeps WOVF.
 w16(0x1ba,0x5a60);w16(0x1b8,0x5aff);w16(0x1b8,0xa560);wait(3)
 assert((r8(0x1bb)&0xe0)==0xe0,'WDT reset requested')
 wait(520)
 assert((r8(0x1bb)&0xe0)==0xe0 and cpu.state.CURPC.value>=0x180 and cpu.state.CURPC.value<0x184,'manual watchdog reset / sticky WOVF')

 w16(0x1c4,0x0040);w16(0x184,0x1234);w16(0x1a4,0x5678)
 w16(0x1ba,0x5a40);w16(0x1b8,0x5aff);w16(0x1b8,0xa560);wait(525)
 assert(cpu.state.CURPC.value<0x104 and (r8(0x1bb)&0xe0)==0xc0,'power-on watchdog vector/status')
 assert(r16(0x1c4)==0 and r16(0x184)==0 and r16(0x1a4)==0xffff,'power-on peripheral initialization')
 -- Standby preserves PFC and I/O storage, resets peripheral modules, and
 -- resumes only after the selected WDT oscillator-settling interval.
 w16(0x1b8,0xa501);w8(0x1bc,0x80)
 s:write_u16(0x0fffec00,0x001b);s:write_u16(0x0fffec02,0xaffe);s:write_u16(0x0fffec04,0x0009)
 s:write_u32(vbr+11*4,0x100);cpu.state.VBR.value=vbr;cpu.state.SR.value=0xf0
 cpu.state.CURPC.value=0x0fffec00;wait(40)
 assert(r8(0xc4)==0x84 and r8(0x100)==0x60,'standby module reset')
 assert(cpu.state.CURPC.value==0x0fffec00,'standby PC')
 f(31,1);wait(256*64-100)
 assert(cpu.state.CURPC.value==0x0fffec00,'standby exited before WDT settling')
 wait(150)
 assert(cpu.state.CURPC.value<0x104,string.format('standby NMI wake PC=%08x CSR=%02x ICR=%04x standby=%d settling=%d',cpu.state.CURPC.value,r8(0x1b8),r16(0x18e),emu.item(cpu.items['0/m_standby']):read(0),emu.item(cpu.items['0/m_settling']):read(0)))
 f(31,0)

 -- Ordinary SLEEP keeps peripherals running; a masked request cannot wake.
 cpu.state.CURPC.value=0x0fffec00;w8(0x1bc,0);w16(0x18c,0x0030)
 s:write_u32(count,0);cpu.state.R0.value=count;cpu.state.R2.value=0x05ffffb8;cpu.state.R3.value=0
 cpu.state.SR.value=0xf0;w16(0x1b8,0x5a00);w16(0x1b8,0xa520);wait(600)
 assert(cpu.state.CURPC.value==0x0fffec00 and (r8(0x1b8)&0x80)~=0,'masked SLEEP / running peripherals')
 cpu.state.SR.value=0;wait(120)
 assert(s:read_u32(count)>0,'unmasked SLEEP wake')
 cpu.state.SR.value=0xf0;r8(0x1b8);w16(0x1b8,0xa500);w16(0x18c,0)
 cpu.state.CURPC.value=0x100
 print('SH7032 interrupt/watchdog reset/standby PASS')
 print('SH7032_DEVICE_PASS')
end
emu.register_frame_done(function()end)
local thread=coroutine.create(function()
 local ok,err=pcall(run);if not ok then print('SH7032_DEVICE_FAIL '..tostring(err))end;m:exit()
end)
coroutine.resume(thread)
