param([string]$c, [string]$cases)
# cases: semicolon separated mutation lines; each pair is applied alone
$y = "C:\Users\jkind\AppData\Local\Temp\claude\C--Users-jkind-mameSaturn-Saturn\a1a2ccb8-05e6-42b0-a91a-65b3d5f8f5b9\scratchpad\yoracle"
$env:PATH = "C:\msys64\ucrt64\bin;" + $env:PATH
Set-Location C:\Users\jkind\mameSaturn\Saturn
$base = "120=0 121=0 122=0 123=0"
$lines = @($base)
foreach ($l in $cases.Split(";")) {
    foreach ($p in $l.Trim().Split(" ")) {
        if ($p -match "^(\d+)=") { $i = $matches[1]; if ($i -notin 120,121,122,123) { $lines += "$base $p".Replace("$i=0 ", "") ; $lines[-1] = "$base $p" } }
    }
}
$mut = "$y\vf\iso_m.txt"
Set-Content $mut $lines -Encoding ascii
$cap = "$y\caps\$c.bin"
& "$y\build\vd2fuzz.exe" $cap $mut "$y\vf\iso_y.bin"
$env:VF_CAP = $cap; $env:VF_MUT = $mut; $env:VF_OUT = "$y\vf\iso_a.bin"
& .\saturn.exe saturnjp -rompath "Z:/mame/roms" -nothrottle -video none -sound none -seconds_to_run 3000 -autoboot_script "$y\vd2fuzz.lua" 2>&1 | Select-Object -Last 1 | Out-Null
python "$y\vd2tools.py" cmp $mut "$y\vf\iso_y.bin" "$y\vf\iso_a.bin"
