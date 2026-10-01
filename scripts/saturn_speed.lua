-- license:BSD-3-Clause
-- Saturn speed probe: run with  mame saturn -cart ... -autoboot_script scripts/saturn_speed.lua
-- (or: -script).  Every second of wall time it prints the emulation speed, the slowest frame, and the
-- guest code the master and slave SH-2 were in when frames ended, so a slowdown can be tied to a
-- moment of the game.  Output goes to the console and to saturn_speed.csv in the working directory.
-- This cannot show which host function is slow; use a profiler build for that (see docs).

local machine = manager.machine
local master = machine.devices[":maincpu"]
local slave = machine.devices[":slave"]

local out = io.open("saturn_speed.csv", "w")
if out then out:write("emu_time,wall_s,speed_pct,frames,worst_frame_ms,master_pc_top,slave_pc_top\n") end

local last_wall = os.clock()
local last_emu = machine.time:as_double()
local last_frame_wall = last_wall
local frames = 0
local worst = 0
local pcs_m, pcs_s = {}, {}

local function bump(t, pc)
	local key = pc >> 8 -- 256 byte buckets
	t[key] = (t[key] or 0) + 1
end

local function top(t)
	local best, n = nil, 0
	for k, v in pairs(t) do
		if v > n then best, n = k, v end
	end
	if not best then return "-" end
	return string.format("%08x(%d)", best << 8, n)
end

emu.add_machine_frame_notifier(function()
	local now = os.clock()
	local ms = (now - last_frame_wall) * 1000
	last_frame_wall = now
	if ms > worst then worst = ms end
	frames = frames + 1

	if master then bump(pcs_m, master.state["PC"].value) end
	if slave then bump(pcs_s, slave.state["PC"].value) end

	local wall = now - last_wall
	if wall >= 1.0 then
		local t = machine.time
		local emu_now = t:as_double()
		local speed = (emu_now - last_emu) / wall * 100
		local line = string.format("emu %.1fs speed %5.1f%% frames %d worst %.1fms master %s slave %s",
				emu_now, speed, frames, worst, top(pcs_m), top(pcs_s))
		print(line)
		if out then
			out:write(string.format("%.2f,%.2f,%.1f,%d,%.1f,%s,%s\n", emu_now, wall, speed, frames, worst, top(pcs_m), top(pcs_s)))
			out:flush()
		end
		last_wall, last_emu, frames, worst = now, emu_now, 0, 0
		pcs_m, pcs_s = {}, {}
	end
end)

emu.add_machine_stop_notifier(function()
	if out then out:close() end
end)
