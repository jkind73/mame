-- license:BSD-3-Clause
-- Full save names and slash-containing module descriptions must both work.
local m=manager.machine
local ok,err=pcall(function()
 local found=0
 for index=0,100000 do
  local item=emu.item(index)
  if item.size==0 then assert(item.name=='');break end
  assert(type(item.name)=='string' and #item.name>0,'missing canonical save-item name')
  for _,target in ipairs({{':billboard:io','m_cmd'}, {':vdp2','m_hcounter_latch'}, {':vdp2','m_vcounter_latch'}})do
   if item.name:find('/'..target[1]..'/0/'..target[2],1,true)then
    assert(m.devices[target[1]].items['0/'..target[2]]==index,'device.items lost a module containing a slash')
    assert(item:read(0)==0,'cold startup field is not initialized: '..item.name)
    found=found+1
   end
  end
 end
 assert(found==3,'missing expected startup fields')
 local retained=emu.item(m.devices[':billboard:io'].items['0/m_cmd'])
 for i=1,10000 do local temporary=emu.item(i%1000);assert(type(temporary.name)=='string')end
 collectgarbage('collect')
 assert(retained.name:find('/:billboard:io/0/m_cmd',1,true) and retained:read(0)==0,'save-item name lifetime failed')
 print('SATURN_STATE_ITEMS_PASS canonical names, I/O device lookup and cold latches/command')
end)
if not ok then print('SATURN_STATE_ITEMS_FAIL '..tostring(err))end
m:exit()
