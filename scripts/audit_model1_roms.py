#!/usr/bin/env python3
import os
import zipfile
import hashlib
import re

roms_dir = r"Z:\mame\roms"
games = ['vr', 'vformula', 'vf', 'swa', 'swaj', 'wingwar', 'wingwaru', 'wingwarj', 'wingwar360', 'netmerc']

with open("src/mame/sega/model1.cpp", "r", encoding="utf-8") as f:
    cpp = f.read()

report = {}

for game in games:
    zip_path = os.path.join(roms_dir, f"{game}.zip")
    if not os.path.exists(zip_path):
        print(f"[-] {game}: ZIP NOT FOUND at {zip_path}")
        report[game] = {"status": "missing_zip", "path": zip_path}
        continue
    zf = zipfile.ZipFile(zip_path)
    file_map = {name.lower(): info for name, info in zip(zf.namelist(), zf.infolist())}
    print(f"\n=== {game} ({len(file_map)} files in zip) ===")
    
    m = re.search(r"ROM_START\(\s*" + game + r"\s*\)(.*?)ROM_END", cpp, re.DOTALL)
    if not m:
        print(f"  No ROM_START found in model1.cpp for {game}")
        continue
    block = m.group(1)
    
    pattern = re.compile(r'ROM_LOAD\w*\(\s*"([^"]+)"[^,]*,\s*[^,]*,\s*([^,]+),\s*CRC\(([0-9a-fA-F]+)\)\s+SHA1\(([0-9a-fA-F]+)\)(.*?)\)')
    entries = []
    for match in pattern.finditer(block):
        rom = match.group(1)
        size = match.group(2).strip()
        crc = match.group(3).lower()
        sha1 = match.group(4).lower()
        extra = match.group(5)
        is_bad = "BAD_DUMP" in extra
        is_opt = "OPTIONAL" in extra
        
        rom_lower = rom.lower()
        if rom_lower in file_map:
            info = file_map[rom_lower]
            actual_crc = f"{info.CRC:08x}".lower()
            actual_data = zf.read(info.filename)
            actual_sha1 = hashlib.sha1(actual_data).hexdigest().lower()
            crc_match = (actual_crc == crc)
            sha1_match = (actual_sha1 == sha1)
            
            if not crc_match or not sha1_match:
                status = "mismatch"
                print(f"  [MISMATCH] {rom}: expected CRC({crc}) SHA1({sha1}), found CRC({actual_crc}) SHA1({actual_sha1}) BAD_DUMP={is_bad}")
            elif is_bad:
                status = "bad_dump_matched"
                print(f"  [BAD_DUMP] {rom}: matched CRC({actual_crc}) SHA1({actual_sha1})")
            else:
                status = "ok"
                # print(f"  [OK] {rom}")
            entries.append({"rom": rom, "status": status, "expected": {"crc": crc, "sha1": sha1}, "actual": {"crc": actual_crc, "sha1": actual_sha1}, "bad_dump": is_bad})
        else:
            status = "missing_optional" if is_opt else "missing_required"
            print(f"  [{status.upper()}] {rom}: expected size {size}, CRC({crc}), SHA1({sha1})")
            entries.append({"rom": rom, "status": status, "expected": {"crc": crc, "sha1": sha1}, "bad_dump": is_bad, "optional": is_opt})
    report[game] = {"status": "ok", "entries": entries}

import json
os.makedirs("build", exist_ok=True)
with open("build/rom_audit_report.json", "w") as out:
    json.dump(report, out, indent=2)
print("\n[+] Audit report written to build/rom_audit_report.json")
