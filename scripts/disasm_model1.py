#!/usr/bin/env python3
"""Extract selected Model 1 firmware windows and run unidasm.

Definitions are a bounded selection, not a complete MAME ROM loader. Supported
games: vf, vr, vformula, swa, wingwar, netmerc; subboards exports selected BIOSes.
Other clones, banked data and motor firmware are not covered. CRC and length
are checked for every input; hashes and transforms are recorded in manifest.json.
Missing/invalid inputs or failed disassembly produce a nonzero exit status.
Use a new output directory. Linear instruction scans and same-PC ROM differences
are research aids, not hardware/protocol verification or proof of bad dump bits.

Example:
  python scripts/disasm_model1.py --game vformula --roms-dir Z:/mame/roms \
      --unidasm ./unidasm.exe --out-dir build/model1-fresh-start/disasm-vformula
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import zipfile
import zlib
from typing import Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# Data Structures Matching MAME's ROM_LOAD Macros in src/mame/sega/model1.cpp
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RomPart:
    """Single ROM chip file entry inside a MAME ROM region."""
    filename: str
    offset: int
    length: int
    crc32: str
    mode: str = "plain"  # "plain", "load16_byte", "load16_word_swap", "load32_word", "load32_byte"


@dataclass(frozen=True)
class DisasmTarget:
    """A contiguous binary slice within an unpacked region to pass to `unidasm`."""
    name: str
    arch: str
    region_offset: int
    length: int
    base_pc: int
    description: str


@dataclass
class RegionSpec:
    """A MAME memory region constructed from one or more ROM chips."""
    name: str
    size: int
    fill_byte: int = 0xFF
    parts: List[RomPart] = field(default_factory=list)
    reloads: List[Tuple[int, int, int]] = field(default_factory=list)  # (src_off, dst_off, length)
    disasm_targets: List[DisasmTarget] = field(default_factory=list)


@dataclass
class GameSpec:
    """Complete ROM and disassembly specification for a Sega Model 1 game or device."""
    shortname: str
    description: str
    parent: Optional[str]
    zip_candidates: List[str]
    regions: List[RegionSpec]


# ---------------------------------------------------------------------------
# Shared Model 1 CPU & Video Board ROM Specifications (`MODEL1_CPU_BOARD`)
# ---------------------------------------------------------------------------

def get_shared_cpu_board_regions() -> List[RegionSpec]:
    """Returns the shared DSP and math lookup table regions on the Model 1 CPU/Video PCBs."""
    return [
        RegionSpec(
            name="315_5571_geometrizer1",
            size=0x2000,
            fill_byte=0x00,
            parts=[
                RomPart("315-5571.bin", 0x0000, 0x2000, "1233db2a", "plain"),
            ],
            disasm_targets=[
                DisasmTarget(
                    name="315_5571_geometrizer1",
                    arch="mb86233",
                    region_offset=0x0000,
                    length=0x2000,
                    base_pc=0x0000,
                    description="Fujitsu MB86233 Geometrizer 1 (IC57/IC58) internal 2Kx32 ROM",
                )
            ],
        ),
        RegionSpec(
            name="315_5572_geometrizer2",
            size=0x2000,
            fill_byte=0x00,
            parts=[
                RomPart("315-5572.bin", 0x0000, 0x2000, "66785906", "plain"),
            ],
            disasm_targets=[
                DisasmTarget(
                    name="315_5572_geometrizer2",
                    arch="mb86233",
                    region_offset=0x0000,
                    length=0x2000,
                    base_pc=0x0000,
                    description="Fujitsu MB86233 Geometrizer 2 (IC60/IC66) internal 2Kx32 ROM",
                )
            ],
        ),
        RegionSpec(
            name="copro_tables",
            size=0x40000,
            fill_byte=0x00,
            parts=[
                RomPart("opr14742.bin", 0x000000, 0x20000, "446a1085", "load32_word"),
                RomPart("opr14743.bin", 0x000002, 0x20000, "e8953554", "load32_word"),
            ],
        ),
        RegionSpec(
            name="other_data_math_tables",
            size=0x80000,
            fill_byte=0x00,
            parts=[
                # 1/x reciprocal table
                RomPart("opr-14744.58", 0x000000, 0x20000, "730ea9e0", "load32_word"),
                RomPart("opr-14745.59", 0x000002, 0x20000, "4c934d96", "load32_word"),
                # 1/sqrt(x) reciprocal square-root table
                RomPart("opr-14746.62", 0x040000, 0x20000, "2a266cbd", "load32_word"),
                RomPart("opr-14747.63", 0x040002, 0x20000, "a4ad5e19", "load32_word"),
            ],
        ),
        RegionSpec(
            name="video_lighting_table_opr14748",
            size=0x20000,
            fill_byte=0x00,
            parts=[
                RomPart("opr14748.bin", 0x000000, 0x20000, "4a532cb8", "plain"),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Game-Specific ROM Definitions (from src/mame/sega/model1.cpp)
# ---------------------------------------------------------------------------

def build_game_specs() -> Dict[str, GameSpec]:
    """Build selected firmware extraction windows; this is not full ROM coverage."""
    specs: Dict[str, GameSpec] = {}

    # 1. Virtua Fighter (vf)
    specs["vf"] = GameSpec(
        shortname="vf",
        description="Virtua Fighter (Sega Model 1, 1993)",
        parent=None,
        zip_candidates=["vf", "model1io"],
        regions=get_shared_cpu_board_regions() + [
            RegionSpec(
                name="tgp_copro_315_5724",
                size=0x2000,
                fill_byte=0x00,
                parts=[RomPart("315-5724.bin", 0x0000, 0x2000, "4b4f330e", "plain")],
                disasm_targets=[
                    DisasmTarget(
                        name="vf_tgp_315_5724",
                        arch="mb86233",
                        region_offset=0x0000,
                        length=0x2000,
                        base_pc=0x0000,
                        description="Virtua Fighter TGP Coprocessor (315-5724, flagged BAD_DUMP in MAME)",
                    )
                ],
            ),
            RegionSpec(
                name="maincpu_v60",
                size=0x1000000,
                parts=[
                    RomPart("epr-16082.14", 0x200000, 0x80000, "b23f22ee", "load16_byte"),
                    RomPart("epr-16083.15", 0x200001, 0x80000, "d12c77f8", "load16_byte"),
                    RomPart("epr-16080.4", 0xFC0000, 0x20000, "3662e1a5", "plain"),
                    RomPart("epr-16081.5", 0xFE0000, 0x20000, "6dec06ce", "plain"),
                ],
                disasm_targets=[
                    DisasmTarget("vf_v60_boot_fc0000", "v60", 0xFC0000, 0x40000, 0xFC0000, "VF V60 Fixed Boot/Main ROM (0xFC0000-0xFFFFFF)"),
                    DisasmTarget("vf_v60_code_200000", "v60", 0x200000, 0x100000, 0x200000, "VF V60 Extended Code/Data ROM (0x200000-0x2FFFFF)"),
                ],
            ),
            RegionSpec(
                name="audiocpu_m68k",
                size=0xA0000,
                parts=[
                    RomPart("epr-16120.7", 0x00000, 0x20000, "2bff8378", "load16_word_swap"),
                    RomPart("epr-16121.8", 0x20000, 0x20000, "ff6723f9", "load16_word_swap"),
                ],
                reloads=[(0x20000, 0x80000, 0x20000)],
                disasm_targets=[
                    DisasmTarget("vf_m68k_sound", "m68000", 0x00000, 0x40000, 0x00000, "VF 68000 Sound Driver (epr-16120.7 + epr-16121.8)"),
                ],
            ),
        ],
    )

    # 2. Virtua Racing (vr)
    specs["vr"] = GameSpec(
        shortname="vr",
        description="Virtua Racing (Sega Model 1, 1992)",
        parent=None,
        zip_candidates=["vr", "model1io", "m1comm"],
        regions=get_shared_cpu_board_regions() + [
            RegionSpec(
                name="tgp_copro_315_5573",
                size=0x2000,
                fill_byte=0x00,
                parts=[RomPart("315-5573.bin", 0x0000, 0x2000, "3335a19b", "plain")],
                disasm_targets=[
                    DisasmTarget(
                        name="vr_tgp_315_5573",
                        arch="mb86233",
                        region_offset=0x0000,
                        length=0x2000,
                        base_pc=0x0000,
                        description="Virtua Racing / Virtua Formula TGP Coprocessor (315-5573)",
                    )
                ],
            ),
            RegionSpec(
                name="maincpu_v60",
                size=0x1000000,
                parts=[
                    RomPart("epr-14882.14", 0x200000, 0x80000, "547d75ad", "load16_byte"),
                    RomPart("epr-14883.15", 0x200001, 0x80000, "6bfad8b1", "load16_byte"),
                    RomPart("epr-14878a.4", 0xFC0000, 0x20000, "6d69e695", "plain"),
                    RomPart("epr-14879a.5", 0xFE0000, 0x20000, "d45af9dd", "plain"),
                ],
                disasm_targets=[
                    DisasmTarget("vr_v60_boot_fc0000", "v60", 0xFC0000, 0x40000, 0xFC0000, "VR V60 Fixed Boot/Main ROM (0xFC0000-0xFFFFFF)"),
                    DisasmTarget("vr_v60_code_200000", "v60", 0x200000, 0x100000, 0x200000, "VR V60 Extended Code/Data ROM (0x200000-0x2FFFFF)"),
                ],
            ),
            RegionSpec(
                name="audiocpu_m68k",
                size=0x40000,
                parts=[
                    RomPart("epr-14870a.7", 0x00000, 0x20000, "919d9b75", "load16_word_swap"),
                ],
                disasm_targets=[
                    DisasmTarget("vr_m68k_sound", "m68000", 0x00000, 0x20000, 0x00000, "VR 68000 Sound Driver (epr-14870a.7)"),
                ],
            ),
        ],
    )

    # 3. Star Wars (swa)
    specs["swa"] = GameSpec(
        shortname="swa",
        description="Star Wars (Sega Model 1, 1994 US)",
        parent=None,
        zip_candidates=["swa", "model1io"],
        regions=get_shared_cpu_board_regions() + [
            RegionSpec(
                name="tgp_copro_315_5711",
                size=0x2000,
                fill_byte=0x00,
                parts=[RomPart("315-5711.bin", 0x0000, 0x2000, "6a21f304", "plain")],
                disasm_targets=[
                    DisasmTarget(
                        name="swa_tgp_315_5711",
                        arch="mb86233",
                        region_offset=0x0000,
                        length=0x2000,
                        base_pc=0x0000,
                        description="Star Wars / Wing War / NetMerc TGP Coprocessor (315-5711)",
                    )
                ],
            ),
            RegionSpec(
                name="maincpu_v60",
                size=0x1000000,
                parts=[
                    RomPart("epr-16669.14", 0x200000, 0x80000, "52e5e7e4", "load16_byte"),
                    RomPart("epr-16670.15", 0x200001, 0x80000, "1e7ecabd", "load16_byte"),
                    RomPart("epr-16668.5", 0xF80000, 0x80000, "9e112425", "plain"),
                ],
                reloads=[
                    (0xF80000, 0x000000, 0x80000),
                    (0xF80000, 0x080000, 0x80000),
                ],
                disasm_targets=[
                    DisasmTarget("swa_v60_boot_f80000", "v60", 0xF80000, 0x80000, 0xF80000, "SWA V60 Fixed Boot/Main ROM (0xF80000-0xFFFFFF, mirrored at 0x000000)"),
                    DisasmTarget("swa_v60_code_200000", "v60", 0x200000, 0x100000, 0x200000, "SWA V60 Extended Code/Data ROM (0x200000-0x2FFFFF)"),
                ],
            ),
            RegionSpec(
                name="audiocpu_m68k",
                size=0xA0000,
                parts=[
                    RomPart("epr-16470.7", 0x00000, 0x20000, "7da18cf7", "load16_word_swap"),
                ],
                reloads=[(0x00000, 0x80000, 0x20000)],
                disasm_targets=[
                    DisasmTarget("swa_m68k_sound", "m68000", 0x00000, 0x20000, 0x00000, "SWA 68000 Sound Driver (epr-16470.7)"),
                ],
            ),
            RegionSpec(
                name="dsbz80_mpegcpu",
                size=0x20000,
                parts=[
                    RomPart("epr-16471.2", 0x00000, 0x20000, "f4ee84a4", "plain"),
                ],
                disasm_targets=[
                    DisasmTarget("swa_dsbz80_mpeg", "z80", 0x00000, 0x20000, 0x0000, "SWA Digital Sound Board Z80 MPEG Controller Firmware (epr-16471.2)"),
                ],
            ),
        ],
    )

    # 4. Wing War (wingwar)
    specs["wingwar"] = GameSpec(
        shortname="wingwar",
        description="Wing War (Sega Model 1, 1994 World)",
        parent=None,
        zip_candidates=["wingwar", "model1io2", "m1comm"],
        regions=get_shared_cpu_board_regions() + [
            RegionSpec(
                name="tgp_copro_315_5711",
                size=0x2000,
                fill_byte=0x00,
                parts=[RomPart("315-5711.bin", 0x0000, 0x2000, "6a21f304", "plain")],
                disasm_targets=[
                    DisasmTarget(
                        name="wingwar_tgp_315_5711",
                        arch="mb86233",
                        region_offset=0x0000,
                        length=0x2000,
                        base_pc=0x0000,
                        description="Wing War TGP Coprocessor (315-5711)",
                    )
                ],
            ),
            RegionSpec(
                name="maincpu_v60",
                size=0x1000000,
                parts=[
                    RomPart("epr-16729.14", 0x200000, 0x80000, "7edec2cc", "load16_byte"),
                    RomPart("epr-16730.15", 0x200001, 0x80000, "bab24dee", "load16_byte"),
                    RomPart("epr-16953.4", 0xFC0000, 0x20000, "c821a920", "plain"),
                    RomPart("epr-16952.5", 0xFE0000, 0x20000, "03a3ecc5", "plain"),
                ],
                reloads=[
                    (0xFC0000, 0x000000, 0x20000),
                    (0xFE0000, 0x020000, 0x20000),
                ],
                disasm_targets=[
                    DisasmTarget("wingwar_v60_boot_fc0000", "v60", 0xFC0000, 0x40000, 0xFC0000, "Wing War V60 Fixed Boot/Main ROM (0xFC0000-0xFFFFFF)"),
                    DisasmTarget("wingwar_v60_code_200000", "v60", 0x200000, 0x100000, 0x200000, "Wing War V60 Extended Code/Data ROM (0x200000-0x2FFFFF)"),
                ],
            ),
            RegionSpec(
                name="audiocpu_m68k",
                size=0xA0000,
                parts=[
                    RomPart("epr-17126.7", 0x00000, 0x20000, "50178e40", "load16_word_swap"),
                    RomPart("epr-16752.8", 0x20000, 0x20000, "6541c48f", "load16_word_swap"),
                ],
                reloads=[(0x20000, 0x80000, 0x20000)],
                disasm_targets=[
                    DisasmTarget("wingwar_m68k_sound", "m68000", 0x00000, 0x40000, 0x00000, "Wing War 68000 Sound Driver (epr-17126.7 + epr-16752.8)"),
                ],
            ),
        ],
    )

    # 5. Sega NetMerc / TecWar (netmerc)
    specs["netmerc"] = GameSpec(
        shortname="netmerc",
        description="Sega NetMerc / TecWar (Sega & Virtuality Model 1 VR Pod, 1993)",
        parent=None,
        zip_candidates=["netmerc", "model1io2"],
        regions=get_shared_cpu_board_regions() + [
            RegionSpec(
                name="tgp_copro_315_5711",
                size=0x2000,
                fill_byte=0x00,
                parts=[RomPart("315-5711.bin", 0x0000, 0x2000, "6a21f304", "plain")],
                disasm_targets=[
                    DisasmTarget(
                        name="netmerc_tgp_315_5711",
                        arch="mb86233",
                        region_offset=0x0000,
                        length=0x2000,
                        base_pc=0x0000,
                        description="Sega NetMerc TGP Coprocessor (315-5711)",
                    )
                ],
            ),
            RegionSpec(
                name="maincpu_v60",
                size=0x1000000,
                parts=[
                    RomPart("epr-18120.ic5", 0xF80000, 0x80000, "de489762", "plain"),
                ],
                reloads=[(0xF80000, 0x000000, 0x80000)],
                disasm_targets=[
                    DisasmTarget("netmerc_v60_boot_f80000", "v60", 0xF80000, 0x80000, 0xF80000, "NetMerc V60 Main ROM (epr-18120.ic5 at 0xF80000 / 0x000000)"),
                ],
            ),
            RegionSpec(
                name="polhemus_i386sx",
                size=0x8000,
                parts=[
                    RomPart("u1", 0x0000, 0x4000, "7073a312", "load16_byte"),
                    RomPart("u2", 0x0001, 0x4000, "c589f428", "load16_byte"),
                ],
                disasm_targets=[
                    DisasmTarget(
                        name="netmerc_polhemus_i386sx_f8000",
                        arch="x86_16",
                        region_offset=0x0000,
                        length=0x8000,
                        base_pc=0xF8000,
                        description="NetMerc Polhemus 3SPACE VR Head-Tracker i386SX Firmware (mapped at 0xF8000-0xFFFFF)",
                    )
                ],
            ),
            RegionSpec(
                name="audiocpu_m68k",
                size=0xA0000,
                parts=[
                    RomPart("epr-18121.ic7", 0x00000, 0x80000, "113285b5", "load16_word_swap"),
                ],
                reloads=[(0x00000, 0x80000, 0x20000)],
                disasm_targets=[
                    DisasmTarget("netmerc_m68k_sound", "m68000", 0x00000, 0x80000, 0x00000, "NetMerc 68000 Sound Driver (epr-18121.ic7)"),
                ],
            ),
        ],
    )

    # 6. Sub-Board Devices (model1io, model1io2, m1comm)
    specs["subboards"] = GameSpec(
        shortname="subboards",
        description="Sega Model 1 Z80 I/O & Link Communication Sub-Boards (model1io, model1io2, m1comm)",
        parent=None,
        zip_candidates=["model1io", "model1io2", "m1comm", "vr", "vformula", "wingwar", "netmerc"],
        regions=[
            RegionSpec(
                name="model1io_z80",
                size=0x10000,
                parts=[RomPart("epr-14869b.25", 0x0000, 0x10000, "2d093304", "plain")],
                disasm_targets=[
                    DisasmTarget("model1io_epr14869b", "z80", 0x0000, 0x10000, 0x0000, "Sega Model 1 Standard I/O Board Z80 Firmware (epr-14869b)"),
                ],
            ),
            RegionSpec(
                name="model1io2_wingwar_z80",
                size=0x10000,
                parts=[RomPart("epr-16891.6", 0x0000, 0x10000, "a33f84d1", "plain")],
                disasm_targets=[
                    DisasmTarget("model1io2_wingwar_epr16891", "z80", 0x0000, 0x10000, 0x0000, "Sega Model 1 Advanced I/O Board TMPZ84C015 Firmware - Wing War (epr-16891.6)"),
                ],
            ),
            RegionSpec(
                name="model1io2_netmerc_z80",
                size=0x10000,
                parts=[RomPart("epr-18021.6", 0x0000, 0x10000, "5551837e", "plain")],
                disasm_targets=[
                    DisasmTarget("model1io2_netmerc_epr18021", "z80", 0x0000, 0x10000, 0x0000, "Sega Model 1 Advanced I/O Board TMPZ84C015 Firmware - NetMerc (epr-18021.6)"),
                ],
            ),
            RegionSpec(
                name="m1comm_vr_wingwar_z80",
                size=0x20000,
                parts=[RomPart("epr-15112.17", 0x0000, 0x20000, "4950e771", "plain")],
                disasm_targets=[
                    DisasmTarget("m1comm_epr15112", "z80", 0x0000, 0x10000, 0x0000, "Sega Model 1 Communication Board Z80 Firmware (epr-15112.17)"),
                ],
            ),
            RegionSpec(
                name="m1comm_vformula_z80",
                size=0x20000,
                parts=[RomPart("epr-15624.17", 0x0000, 0x20000, "9b3ba315", "plain")],
                disasm_targets=[
                    DisasmTarget("m1comm_epr15624", "z80", 0x0000, 0x10000, 0x0000, "Sega Model 1 Communication Board Z80 Firmware - Virtua Formula (epr-15624.17)"),
                ],
            ),
        ],
    )

    # Selected VFormula firmware windows, not an alias of the VR main program.
    vf = copy.deepcopy(specs["vr"])
    vf.shortname = "vformula"
    vf.description = "Virtua Formula (selected firmware windows)"
    vf.parent = "vr"
    vf.zip_candidates = ["vformula", "vr", "model1io", "m1comm"]
    replacements = {
        "epr-14882.14": ("epr-15638.14", "b9db21a2"),
        "epr-14883.15": ("epr-15639.15", "4c3796f5"),
        "epr-14878a.4": ("epr-15623.4", "155fa5be"),
        "epr-14879a.5": ("epr-15622.5", "18007f6f"),
    }
    from dataclasses import replace
    for region in vf.regions:
        region.parts = [replace(p, filename=replacements[p.filename][0],
                                crc32=replacements[p.filename][1])
                        if p.filename in replacements else p for p in region.parts]
        region.disasm_targets = [replace(t, name=t.name.replace("vr_", "vformula_"),
                                        description=t.description.replace("VR ", "VFormula "))
                                 for t in region.disasm_targets]
    specs["vformula"] = vf
    return specs


# ---------------------------------------------------------------------------
# ROM Loader & Byte-Interleaving Engine
# ---------------------------------------------------------------------------

class RomRepository:
    """Locates ROM files by name or CRC32 across extracted folders or `.zip` archives."""

    def __init__(self, roms_dir: Path):
        self.roms_dir = roms_dir
        self._zip_cache: Dict[str, Optional[zipfile.ZipFile]] = {}
        self.provenance: List[dict] = []

    def checked(self, part: RomPart, raw: bytes, source: str) -> bytes:
        crc = f"{zlib.crc32(raw) & 0xffffffff:08x}"
        if len(raw) != part.length or crc != part.crc32.lower():
            raise ValueError(f"{source}: expected {part.length} bytes/CRC {part.crc32}, "
                             f"got {len(raw)} bytes/CRC {crc}")
        self.provenance.append({"file": part.filename, "source": source,
                                "length": len(raw), "crc32": crc,
                                "sha1": hashlib.sha1(raw).hexdigest()})
        return raw

    def _get_zip(self, candidate: str) -> Optional[zipfile.ZipFile]:
        if candidate not in self._zip_cache:
            zip_path = self.roms_dir / f"{candidate}.zip"
            if zip_path.is_file():
                try:
                    self._zip_cache[candidate] = zipfile.ZipFile(zip_path, "r")
                except Exception:
                    self._zip_cache[candidate] = None
            else:
                self._zip_cache[candidate] = None
        return self._zip_cache.get(candidate)

    def load_rom_bytes(self, part: RomPart, zip_candidates: Sequence[str]) -> Optional[bytes]:
        target_crc = int(part.crc32, 16) if part.crc32 else None
        target_name_lower = part.filename.lower()

        # 1. Check .zip archives first (cached ZipFile handles, fast in-memory directory lookup)
        for candidate in zip_candidates:
            zf = self._get_zip(candidate)
            if zf is None:
                continue
            # Match by exact CRC32 first (handles renamed dumps across MAME versions)
            if target_crc is not None:
                for info in zf.infolist():
                    if info.CRC == target_crc:
                        return self.checked(part, zf.read(info.filename), f"{zf.filename}:{info.filename}")
            # Fallback to case-insensitive basename match
            for info in zf.infolist():
                if Path(info.filename).name.lower() == target_name_lower:
                    return self.checked(part, zf.read(info.filename), f"{zf.filename}:{info.filename}")

        # 2. Check candidate subfolder or root folder by direct path lookup
        for candidate in list(zip_candidates) + [""]:
            folder = self.roms_dir / candidate if candidate else self.roms_dir
            direct_file = folder / part.filename
            if direct_file.is_file():
                return self.checked(part, direct_file.read_bytes(), str(direct_file))

        return None


def apply_rom_part(buffer: bytearray, part: RomPart, raw: bytes) -> None:
    """Applies a ROM chip's bytes into a region buffer using MAME's ROM_LOAD semantics."""
    if len(raw) != part.length:
        raise ValueError(f"Wrong length for {part.filename}")
    unit, stride = {"plain": (1, 1), "load16_byte": (1, 2),
                    "load16_word_swap": (2, 2), "load32_word": (2, 4),
                    "load32_byte": (1, 4)}[part.mode]
    if not raw or len(raw) % unit or part.offset < 0:
        raise ValueError(f"Invalid layout for {part.filename}")
    end = part.offset + (len(raw) // unit - 1) * stride + unit
    if end > len(buffer):
        raise ValueError(f"ROM exceeds region: {part.filename}")
    data = raw
    if part.mode == "plain":
        buffer[part.offset : part.offset + len(data)] = data
    elif part.mode == "load16_byte":
        # ROM_LOAD16_BYTE: write each byte at stride 2 starting at part.offset
        end_offset = part.offset + len(data) * 2
        if end_offset <= len(buffer):
            buffer[part.offset : end_offset : 2] = data
        else:
            for i, b in enumerate(data):
                dst = part.offset + (i * 2)
                if dst < len(buffer):
                    buffer[dst] = b
    elif part.mode == "load16_word_swap":
        # ROM_LOAD16_WORD_SWAP: swap even/odd bytes of each 16-bit word
        swapped = bytearray(len(data))
        swapped[0::2] = data[1::2]
        swapped[1::2] = data[0::2]
        buffer[part.offset : part.offset + len(swapped)] = swapped
    elif part.mode == "load32_word":
        # ROM_LOAD32_WORD: write 16-bit words at stride 4 starting at part.offset
        for i in range(0, len(data), 2):
            dst = part.offset + (i * 2)
            if dst + 2 <= len(buffer):
                buffer[dst : dst + 2] = data[i : i + 2]
    elif part.mode == "load32_byte":
        # ROM_LOAD32_BYTE: write each byte at stride 4 starting at part.offset
        end_offset = part.offset + len(data) * 4
        if end_offset <= len(buffer):
            buffer[part.offset : end_offset : 4] = data
        else:
            for i, b in enumerate(data):
                dst = part.offset + (i * 4)
                if dst < len(buffer):
                    buffer[dst] = b
    else:
        raise ValueError(f"Unsupported ROM load mode: {part.mode}")


def assemble_region(repo: RomRepository, region: RegionSpec, zip_candidates: Sequence[str]) -> Tuple[bytearray, List[str]]:
    """Assembles a complete memory region buffer and returns (buffer, missing_files)."""
    buf = bytearray([region.fill_byte] * region.size)
    missing: List[str] = []

    for part in region.parts:
        try:
            raw = repo.load_rom_bytes(part, zip_candidates)
        except ValueError as error:
            missing.append(str(error))
            continue
        if raw is None:
            missing.append(f"{part.filename} (CRC {part.crc32})")
            continue
        apply_rom_part(buf, part, raw)

    for src_off, dst_off, length in region.reloads:
        if min(src_off, dst_off, length) < 0 or max(src_off, dst_off) + length > len(buf):
            raise ValueError(f"Reload outside region {region.name}")
        buf[dst_off : dst_off + length] = buf[src_off : src_off + length]

    return buf, missing


# ---------------------------------------------------------------------------
# Disassembly & Automated Diagnostic Auditors (Phases 2, 3, 4, and 6)
# ---------------------------------------------------------------------------

def run_unidasm(unidasm_bin: str, bin_path: Path, asm_path: Path, arch: str, base_pc: int) -> bool:
    """Runs MAME's `unidasm` on `bin_path` and writes the annotated listing to `asm_path`."""
    exe = shutil.which(unidasm_bin) or (unidasm_bin if Path(unidasm_bin).is_file() else None)
    if exe is None:
        return False

    cmd = [
        str(exe),
        str(bin_path),
        "-arch",
        arch,
        "-basepc",
        f"{base_pc:X}",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if res.returncode != 0 or not res.stdout.strip():
        asm_path.write_text(f"; ERROR running {' '.join(cmd)}:\n; {res.stderr}\n", encoding="utf-8")
        return False

    header = (
        f"; ===========================================================================\n"
        f"; Binary : {bin_path.name}\n"
        f"; Arch   : {arch}\n"
        f"; BasePC : 0x{base_pc:08X}\n"
        f"; Command: {' '.join(cmd)}\n"
        f"; ===========================================================================\n\n"
    )
    asm_path.write_text(header + res.stdout, encoding="utf-8")
    return True


def audit_tgp_coprocessor_roms(out_dir: Path) -> Dict[str, object]:
    """Report same-PC differences; no functional alignment or dump diagnosis."""
    tgp_files = {
        "315-5573": out_dir / "vr" / "bins" / "vr_tgp_315_5573.bin",
        "315-5711": out_dir / "swa" / "bins" / "swa_tgp_315_5711.bin",
        "315-5724": out_dir / "vf" / "bins" / "vf_tgp_315_5724.bin",
    }
    loaded: Dict[str, List[int]] = {}
    for label, path in tgp_files.items():
        if path.is_file() and path.stat().st_size == 0x2000:
            raw = path.read_bytes()
            loaded[label] = list(struct.unpack("<2048I", raw))

    report: Dict[str, object] = {"loaded_roms": list(loaded.keys()), "same_pc_small_differences": [],
                                "limitation": "Different programs; same-PC Hamming distance is not evidence of a dump error."}
    if "315-5724" in loaded and "315-5711" in loaded:
        words_vf = loaded["315-5724"]
        words_swa = loaded["315-5711"]
        suspects = []
        for pc in range(len(words_vf)):
            xor_val = words_vf[pc] ^ words_swa[pc]
            if xor_val != 0 and bin(xor_val).count("1") <= 2:
                suspects.append({
                    "word_pc": f"0x{pc:03X}",
                    "byte_offset": f"0x{pc * 4:04X}",
                    "vf_315_5724": f"0x{words_vf[pc]:08X}",
                    "swa_315_5711": f"0x{words_swa[pc]:08X}",
                    "xor_mask": f"0x{xor_val:08X}",
                    "hamming_distance": bin(xor_val).count("1"),
                })
        report["same_pc_small_differences"] = suspects
    return report


def audit_polhemus_i386_io(asm_path: Path) -> Dict[str, object]:
    """
    Phase 4 Auditor: Scans the disassembled `netmerc` Polhemus `i386sx` listing for
    `in`, `out`, and `int` instructions so an AI agent can wire up `polhemus_map` /
    `polhemus_io` in `src/mame/sega/model1.cpp`.
    """
    if not asm_path.is_file():
        return {"status": "missing_asm"}

    io_instructions: List[str] = []
    imm_ports: set[str] = set()
    in_out_re = re.compile(r"\b(in|out|insb|insw|outsb|outsw|int)\b", re.IGNORECASE)
    imm_port_re = re.compile(r"\b(?:in|out)\s+(?:al|ax|eax),\s*(0x[0-9a-fA-F]+|[0-9a-fA-F]+h?)\b", re.IGNORECASE)

    for line in asm_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(";"):
            continue
        if in_out_re.search(line):
            io_instructions.append(line.strip())
            m = imm_port_re.search(line)
            if m:
                imm_ports.add(m.group(1))

    return {
        "status": "ok",
        "total_io_and_int_sites": len(io_instructions),
        "immediate_io_ports": sorted(imm_ports),
        "sample_sites": io_instructions[:50],
    }


def audit_z80_subboard_io(asm_path: Path, board_label: str) -> Dict[str, object]:
    """
    Phase 6 Auditor: Scans a disassembled Z80 sub-board listing (`dsbz80` MPEG board
    or `m1comm` link board) for `in`/`out`/`otir`/`inir` I/O port accesses and
    memory-mapped control registers (`0x8000-0xFFFF`).
    """
    if not asm_path.is_file():
        return {"board": board_label, "status": "missing_asm"}

    io_sites: List[str] = []
    ports_seen: set[str] = set()
    mmio_seen: set[str] = set()

    z80_io_re = re.compile(r"\b(in|out|ini|inir|ind|indr|outi|otir|outd|otdr)\b", re.IGNORECASE)
    port_imm_re = re.compile(r"\(\s*(\$[0-9a-fA-F]+|0x[0-9a-fA-F]+|[0-9a-fA-F]+h)\s*\)", re.IGNORECASE)
    mmio_re = re.compile(r"\(\s*(\$[89a-fA-F][0-9a-fA-F]{3}|0x[89a-fA-F][0-9a-fA-F]{3})\s*\)")

    for line in asm_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(";"):
            continue
        if z80_io_re.search(line):
            io_sites.append(line.strip())
            for pm in port_imm_re.findall(line):
                ports_seen.add(pm)
        for mm in mmio_re.findall(line):
            mmio_seen.add(mm)

    return {
        "board": board_label,
        "status": "ok",
        "total_z80_io_sites": len(io_sites),
        "io_ports_accessed": sorted(ports_seen),
        "high_mmio_addresses_sample": sorted(mmio_seen)[:64],
        "sample_io_instructions": io_sites[:60],
    }


def export_math_tables_summary(out_dir: Path, region_name: str, buf: bytes) -> None:
    """Phase 3 Auditor: Exports a JSON sample of the Model 1 hardware math/lighting LUTs."""
    summary_path = out_dir / f"{region_name}_sample.json"
    if region_name == "video_lighting_table_opr14748" and len(buf) >= 512:
        words = struct.unpack("<256H", buf[:512])
        summary_path.write_text(
            json.dumps(
                {
                    "table": "OPR-14748 raw little-endian u16 sample; hardware indexing not established",
                    "first_64_entries_hex": [f"0x{w:04X}" for w in words[:64]],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    elif region_name == "other_data_math_tables" and len(buf) >= 0x80000:
        inv_floats = struct.unpack("<32f", buf[:128])
        isqrt_floats = struct.unpack("<32f", buf[0x40000 : 0x40000 + 128])
        summary_path.write_text(
            json.dumps(
                {
                    "table": "OPR-14744..14747 (Geometrizer 1/x and 1/sqrt(x) 32-bit LUTs)",
                    "inv_first_32_floats": [round(x, 8) for x in inv_floats],
                    "isqrt_first_32_floats": [round(x, 8) for x in isqrt_floats],
                },
                indent=2,
            ),
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract selected Model 1 firmware windows and produce provenance plus linear listings."
    )
    parser.add_argument(
        "--roms-dir",
        type=Path,
        default=Path("roms"),
        help="Path to MAME ROMs directory containing Model 1 .zip archives or folders (default: ./roms)",
    )
    parser.add_argument(
        "--unidasm",
        type=str,
        default="unidasm",
        help="Path to MAME's `unidasm` executable (default: unidasm in PATH)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("build/model1_disasm"),
        help="Output directory for unpacked binaries, .asm listings, and JSON audit reports",
    )
    parser.add_argument(
        "--game",
        type=str,
        default="all",
        choices=["all", "vf", "vr", "vformula", "swa", "wingwar", "netmerc", "subboards"],
        help="Target game or sub-board set to unpack and disassemble (default: all)",
    )
    args = parser.parse_args(argv)

    specs = build_game_specs()
    selected = list(specs.values()) if args.game == "all" else [specs[args.game]]
    repo = RomRepository(args.roms_dir)
    if args.out_dir.exists() and any(args.out_dir.iterdir()):
        parser.error("Use a new/empty output directory; stale listings are not accepted")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    failed = False

    manifest: Dict[str, object] = {"roms_dir": str(args.roms_dir), "games": {}, "phase6_audits": {},
        "scope": "Selected firmware windows only; not all regions, banks, BIOSes or variants",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    tool = shutil.which(args.unidasm) or (str(Path(args.unidasm).resolve()) if Path(args.unidasm).is_file() else None)
    manifest["unidasm"] = {"path": tool, "sha256": hashlib.sha256(Path(tool).read_bytes()).hexdigest() if tool else None}
    root = Path(__file__).resolve().parents[1]
    manifest["source_sha256"] = {
        f"src/mame/sega/{name}": hashlib.sha256((root / "src/mame/sega" / name).read_bytes()).hexdigest()
        for name in ("model1.cpp", "model1io.cpp", "model1io2.cpp", "m1comm.cpp")
    }

    for game in selected:
        print(f"[*] Processing {game.shortname}: {game.description}")
        game_dir = args.out_dir / game.shortname
        bins_dir = game_dir / "bins"
        asm_dir = game_dir / "asm"
        bins_dir.mkdir(parents=True, exist_ok=True)
        asm_dir.mkdir(parents=True, exist_ok=True)

        game_report: Dict[str, object] = {"regions": {}, "disassembled": []}

        for region in game.regions:
            buf, missing = assemble_region(repo, region, game.zip_candidates)
            if missing:
                failed = True
                print(f"    [!] Region {region.name}: missing {len(missing)} ROM part(s): {', '.join(missing)}")
                game_report["regions"][region.name] = {"status": "incomplete", "missing": missing}
                continue

            region_sha1 = hashlib.sha1(buf).hexdigest()
            game_report["regions"][region.name] = {"status": "ok", "size": len(buf), "sha1": region_sha1,
                "parts": [vars(p) for p in region.parts], "reloads": region.reloads,
                "fill_byte": region.fill_byte}
            export_math_tables_summary(game_dir, region.name, buf)

            for target in region.disasm_targets:
                if target.region_offset < 0 or target.length <= 0 or target.region_offset + target.length > len(buf):
                    raise ValueError(f"Invalid target window: {target.name}")
                slice_bytes = buf[target.region_offset : target.region_offset + target.length]
                # The load16_word_swap ROM definitions already produce the
                # big-endian sound CPU stream used by unidasm. Do not swap twice.
                transform = "none"
                bin_path = bins_dir / f"{target.name}.bin"
                asm_path = asm_dir / f"{target.name}.asm"
                bin_path.write_bytes(slice_bytes)

                ok = run_unidasm(args.unidasm, bin_path, asm_path, target.arch, target.base_pc)
                if not ok:
                    failed = True
                status_str = "disassembled" if ok else "unpacked_only (tool absent or failed)"
                print(f"    [+] {target.name} ({target.arch} @ 0x{target.base_pc:X}): {status_str}")
                game_report["disassembled"].append({
                    "name": target.name,
                    "arch": target.arch,
                    "base_pc": f"0x{target.base_pc:X}",
                    "bin_path": str(bin_path),
                    "asm_path": str(asm_path) if ok else None,
                    "status": status_str,
                    "sha1": hashlib.sha1(slice_bytes).hexdigest(),
                    "region_offset": target.region_offset,
                    "length": target.length,
                    "transform": transform,
                })

                if target.name == "netmerc_polhemus_i386sx_f8000" and ok:
                    polhemus_audit = audit_polhemus_i386_io(asm_path)
                    (game_dir / "polhemus_io_audit.json").write_text(
                        json.dumps(polhemus_audit, indent=2), encoding="utf-8"
                    )

                if target.name in ("swa_dsbz80_mpeg", "m1comm_epr15112", "m1comm_epr15624") and ok:
                    z80_audit = audit_z80_subboard_io(asm_path, target.name)
                    (game_dir / f"{target.name}_phase6_audit.json").write_text(
                        json.dumps(z80_audit, indent=2), encoding="utf-8"
                    )
                    manifest["phase6_audits"][target.name] = z80_audit

        manifest["games"][game.shortname] = game_report

    # Descriptive cross-ROM comparison only; not a decapping audit
    tgp_audit = audit_tgp_coprocessor_roms(args.out_dir)
    manifest["tgp_decapping_audit"] = tgp_audit
    manifest["input_roms"] = repo.provenance
    manifest["success"] = not failed

    manifest_path = args.out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[+] Wrote disassembly manifest and audit report to {manifest_path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
