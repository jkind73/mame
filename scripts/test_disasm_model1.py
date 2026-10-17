"""Focused integrity tests for the bounded Model 1 extraction helper."""
import importlib.util
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
import zlib

spec = importlib.util.spec_from_file_location('model1_extract', Path(__file__).with_name('disasm_model1.py'))
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)


class ExtractionTests(unittest.TestCase):
    def test_lanes(self):
        for mode, offset, expected in [
            ('plain', 0, [1, 2, 3, 4, 0, 0, 0, 0]),
            ('load16_byte', 1, [0, 1, 0, 2, 0, 3, 0, 4]),
            ('load32_word', 2, [0, 0, 1, 2, 0, 0, 3, 4]),
            ('load16_word_swap', 0, [2, 1, 4, 3, 0, 0, 0, 0]),
        ]:
            buf = bytearray(8)
            m.apply_rom_part(buf, m.RomPart('test', offset, 4, '', mode), bytes([1, 2, 3, 4]))
            self.assertEqual(list(buf), expected)
        buf = bytearray(8)
        m.apply_rom_part(buf, m.RomPart('test', 3, 2, '', 'load32_byte'), b'AB')
        self.assertEqual(buf, b'\0\0\0A\0\0\0B')

    def test_invalid_lengths_and_bounds(self):
        for part, raw in [(m.RomPart('x', 0, 4, ''), b'abc'),
                          (m.RomPart('x', 7, 2, ''), b'ab'),
                          (m.RomPart('x', 0, 3, '', 'load32_word'), b'abc')]:
            with self.assertRaises(ValueError):
                m.apply_rom_part(bytearray(8), part, raw)

    def test_filename_match_does_not_bypass_checksum(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'build') as folder:
            Path(folder, 'test').write_bytes(b'bad')
            repo = m.RomRepository(Path(folder))
            crc = f'{zlib.crc32(b"yes"):08x}'
            with self.assertRaises(ValueError):
                repo.load_rom_bytes(m.RomPart('test', 0, 3, crc), [])

    def test_reload(self):
        class Repo:
            def load_rom_bytes(self, part, candidates):
                return b'AB'
        region = m.RegionSpec('x', 6, parts=[m.RomPart('x', 0, 2, '')], reloads=[(0, 4, 2)])
        buf, missing = m.assemble_region(Repo(), region, [])
        self.assertFalse(missing)
        self.assertEqual(buf, b'AB\xff\xffAB')

    def test_definitions_match_source_loads(self):
        root = Path(__file__).resolve().parents[1]
        source = '\n'.join((root / 'src/mame/sega' / file).read_text() for file in
                           ['model1.cpp', 'model1io.cpp', 'model1io2.cpp', 'm1comm.cpp'])
        for game in m.build_game_specs().values():
            for region in game.regions:
                for part in region.parts:
                    pattern = (r'ROM(?:X_LOAD|_LOAD\w*)\s*\(\s*"' + re.escape(part.filename)
                               + r'"\s*,\s*(0x[\da-fA-F]+|\d+)\s*,\s*(0x[\da-fA-F]+|\d+)[^\n]*CRC\(([a-fA-F0-9]+)\)')
                    matches = list(re.finditer(pattern, source))
                    self.assertTrue(matches, part.filename)
                    part_crcs = [c.strip().lower() for c in part.crc32.split(",") if c.strip()]
                    self.assertTrue(any(int(x[1], 0) == part.offset and int(x[2], 0) == part.length and (not part_crcs or x[3].lower() in part_crcs) for x in matches), part.filename)

    def test_vformula_is_not_vr_program(self):
        specs = m.build_game_specs()
        names = lambda game: {p.filename for r in specs[game].regions for p in r.parts}
        self.assertIn('epr-15638.14', names('vformula'))
        self.assertNotIn('epr-14882.14', names('vformula'))
        self.assertIn('epr-14882.14', names('vr'))

    def test_missing_tool_or_rom_fails_cli(self):
        import contextlib
        import io
        root = Path(__file__).resolve().parents[1]
        for have_rom in (False, True):
            with tempfile.TemporaryDirectory(dir=root / 'build') as folder:
                folder = Path(folder)
                if have_rom:
                    (folder / 'test.bin').write_bytes(b'AB')
                part = m.RomPart('test.bin', 0, 2, f'{zlib.crc32(b"AB"):08x}')
                target = m.DisasmTarget('test', 'z80', 0, 2, 0, 'fixture')
                game = m.GameSpec('vr', 'fixture', None, [], [m.RegionSpec('test', 2, parts=[part], disasm_targets=[target])])
                with patch.object(m, 'build_game_specs', return_value={'vr': game}), contextlib.redirect_stdout(io.StringIO()):
                    result = m.main(['--game', 'vr', '--roms-dir', str(folder),
                                     '--out-dir', str(folder / 'out'), '--unidasm', str(folder / 'missing.exe')])
                self.assertEqual(result, 1)


if __name__ == '__main__':
    unittest.main()
