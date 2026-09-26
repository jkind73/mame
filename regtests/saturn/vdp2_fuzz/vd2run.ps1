param([string]$caps = "bios_1,bios_2,ab2_1,daytona_1,outrun_1", [int]$n = 400, [int]$seed = 1)
$y = "C:\Users\jkind\AppData\Local\Temp\claude\C--Users-jkind-mameSaturn-Saturn\a1a2ccb8-05e6-42b0-a91a-65b3d5f8f5b9\scratchpad\yoracle"
$env:PATH = "C:\msys64\ucrt64\bin;" + $env:PATH
Set-Location C:\Users\jkind\mameSaturn\Saturn
foreach ($c in $caps.Split(",")) {
    $cap = "$y\caps\$c.bin"
    $mut = "$y\vf\${c}_m.txt"
    python "$y\vd2tools.py" gen $cap $n $seed $mut
    & "$y\build\vd2fuzz.exe" $cap $mut "$y\vf\${c}_y.bin"
    $env:VF_CAP = $cap; $env:VF_MUT = $mut; $env:VF_OUT = "$y\vf\${c}_a.bin"
    & .\saturn.exe saturnjp -rompath "Z:/mame/roms" -nothrottle -video none -sound none -seconds_to_run 3000 -autoboot_script "$y\vd2fuzz.lua" 2>&1 | Select-Object -Last 1
    python "$y\vd2tools.py" cmp $mut "$y\vf\${c}_y.bin" "$y\vf\${c}_a.bin" | Out-File "$y\vf\${c}_res.txt" -Encoding ascii
    "== $c"
    Get-Content "$y\vf\${c}_res.txt" | Select-Object -First 3
}
