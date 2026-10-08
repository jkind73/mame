-- license:BSD-3-Clause
-- Fixed-frame screenshots and CPU PCs; does not read status registers or inject input.
local machine = manager.machine
local screen = machine.screens[":screen"]
local directory = machine.options.entries["snapshot_directory"]:value()
local frame = 0
local targets = {[60]=true,[600]=true,[1800]=true,[3600]=true}
for number in (os.getenv('SATURN_SURVEY_CAPTURE_FRAMES') or ''):gmatch('%d+') do
    targets[tonumber(number)] = true
end
saturn_game_survey_subscription = emu.add_machine_frame_notifier(function()
    frame = frame + 1
    if not targets[frame] then return end
    local path = string.format("%s/frame-%04d.png", directory, frame)
    screen:snapshot(path)
    local master, slave = machine.devices[":maincpu"], machine.devices[":slave"]
    print(string.format("SURVEY frame=%d time=%.6f master=%08x slave=%08x image=%s",
        frame, machine.time:as_double(), master.state["PC"].value,
        slave and slave.state["PC"].value or 0, path))
end)
