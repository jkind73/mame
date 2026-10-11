-- license:BSD-3-Clause
-- Run with -autoboot_delay 0 -autoboot_script and a separate -snapshot_directory.
-- Capture at fixed frame numbers so baseline and changed builds are comparable.
local machine = manager.machine
local screen = machine.screens[":screen"]
local directory = machine.options.entries["snapshot_directory"]:value()
local frames = 0
local targets = { [1] = true, [60] = true, [300] = true, [600] = true, [1200] = true, [1800] = true }
local names = {}
for tag, device in pairs(machine.devices) do
	for name, index in pairs(device.items) do names[index] = tag .. "/" .. name end
end
local layout = assert(io.open(directory .. "/state-layout.tsv", "w"))
local offset = 0
for index = 0, 100000 do
	local item = emu.item(index)
	if item.size == 0 then break end
	local size = item.size * item.count
	layout:write(string.format("%d\t%d\t%d\t%s\n", index, offset, size, item.name or names[index] or "?"))
	offset = offset + size
end
layout:close()

-- Keep the subscription alive across Lua garbage collections.
saturn_vdp_capture_subscription = emu.add_machine_frame_notifier(function()
	frames = frames + 1
	if not targets[frames] then return end
	local prefix = string.format("%s/frame-%04d", directory, frames)
	local pixels, width, height = screen:pixels()
	local file = assert(io.open(prefix .. ".pixels", "wb"))
	file:write(string.pack("<I4I4", width, height), pixels)
	file:close()
	assert(screen:snapshot(prefix .. ".png") == nil)
	machine:save(prefix .. ".sta")
	print(string.format("VDP_CAPTURE frame=%d time=%.9f size=%dx%d", frames,
		machine.time:as_double(), width, height))
end)
