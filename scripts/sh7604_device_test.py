#!/usr/bin/env python3
# license:BSD-3-Clause
"""Run SH7604 real-device tests sequentially without retail ROMs.

The Saturn machine supplies the device graph; our generated SH2 ROM only parks
execution until Lua installs its diagnostic guest. The generated SH-1 ROM also parks execution; it does not implement CD commands. MAME's expected retail
checksum warnings are intentional. This harness does not test BIOS/game boot.
"""
import argparse
import os
from pathlib import Path
import struct
import subprocess
import zipfile


def diagnostic_roms(root):
    root.mkdir()
    rom = bytearray(0x80000)
    struct.pack_into('>IIII', rom, 0, 0x100, 0x26090000, 0x100, 0x26090000)
    struct.pack_into('>HH', rom, 0x100, 0xaffe, 0x0009)  # BRA self; NOP
    with zipfile.ZipFile(root/'saturnjp.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('sega_101.bin', rom)
    with zipfile.ZipFile(root/'satcdb.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        cdrom = bytearray(0x10000)
        struct.pack_into('>II', cdrom, 0, 0x100, 0x0ffffe00)
        struct.pack_into('>HH', cdrom, 0x100, 0xaffe, 0x0009)
        archive.writestr('cdb106.bin', cdrom)  # parked SH-1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, default=Path('saturn'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ideal-bus', action='store_true', help='disable bus wait timing while retaining functional bus observers')
    parser.add_argument('--dma', action='store_true', help='also test all seven legacy DMA burst counts')
    parser.add_argument('--only', choices=('power', 'sci-state', 'pll', 'reset', 'dma', 'pins', 'ubc', 'frt', 'dma-errors', 'bsc', 'wdt', 'divu'), help='run one test group')
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parent.parent
    output = args.output.resolve()
    output.mkdir(exist_ok=False, parents=True)
    diagnostic_roms(output/'roms')
    tests = [('power', 'sh7604_power_test.lua', 'SH7604_POWER_STATE_PATH', 'SH7604_POWER_PASS', None),
             ('sci-state', 'sh7604_sci_state_test.lua', 'SH7604_SCI_STATE_PATH', 'SH7604_SCI_STATE_PASS', None)]
    tests.append(('pll', 'sh7604_pll_test.lua', 'SH7604_PLL_STATE_PATH', 'SH7604_PLL_PASS', None))
    tests.append(('reset', 'sh7604_reset_test.lua', 'SH7604_RESET_STATE_PATH', 'SH7604_RESET_PASS', None))
    tests.append(('pins', 'sh7604_sci_pin_test.lua', 'SH7604_PIN_STATE_PATH', 'SH7604_PIN_PASS', None))
    tests.append(('ubc', 'sh7604_ubc_test.lua', 'SH7604_UBC_STATE_PATH', 'SH7604_UBC_PASS', None))
    tests.append(('dma-errors', 'sh7604_dma_error_test.lua', 'SH7604_DMA_ERROR_STATE_PATH', 'SH7604_DMA_ERROR_PASS', None))
    tests.append(('wdt', 'sh7604_wdt_active_test.lua', 'SH7604_WDT_STATE_PATH', 'SH7604_WDT_PASS', None))
    tests.append(('bsc', 'sh7604_bsc_test.lua', 'SH7604_BSC_STATE_PATH', 'SH7604_BSC_PASS', None))
    tests.append(('frt', 'sh7604_frt_test.lua', 'SH7604_FRT_STATE_PATH', 'SH7604_FRT_PASS', None))
    tests.append(('divu', 'sh7604_divu_register_test.lua', 'SH7604_DIVU_STATE_PATH', 'SH7604_DIVU_PASS', None))
    if args.dma or args.only == 'dma':
        tests += [(f'dma-{n}', 'sh7604_dma_test.lua', 'SH7604_TEST_BURST_COUNT', 'SH7604_REAL_DMA_PASS', n)
                  for n in range(1, 8)]
    if args.only:
        tests = [test for test in tests if test[0] == args.only or (args.only == 'dma' and test[0].startswith('dma-'))]
    for core in ('drc', 'interpreter'):
        for name, script, variable, token, count in tests:
            run = output/(core+'-'+name)
            run.mkdir()
            if args.ideal_bus:
                (run/'cfg').mkdir()
                (run/'cfg'/'saturnjp.cfg').write_text('<mameconfig version="10"><system name="saturnjp"><input><port tag=":CONFIG" type="CONFIG" mask="1" defvalue="1" value="0"/></input></system></mameconfig>')
            env = os.environ.copy()
            if args.ideal_bus:
                env['SH7604_TEST_IDEAL_BUS']='1'
            env[variable] = str(count if count is not None else run/'test.sta')
            command = ['nice', '-n', '10', str(args.binary.resolve()), 'saturnjp',
                       '-noreadconfig', '-rompath', str(output/'roms'),
                       '-video', 'none', '-sound', 'none', '-nothrottle', '-seconds_to_run', '5',
                       '-skip_gameinfo', '-autoboot_delay', '0', '-autoboot_script', str(workspace/'scripts'/script),
                       '-cfg_directory', str(run/'cfg'), '-nvram_directory', str(run/'nvram'),
                       '-diff_directory', str(run/'diff'), '-state_directory', str(run/'sta')]
            if core == 'interpreter':
                command.append('-nodrc')
            with (run/'run.log').open('w') as log:
                result = subprocess.run(command, cwd=workspace, env=env, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=90)
            text = (run/'run.log').read_text(errors='replace')
            if result.returncode or token not in text or 'FAIL' in text or '[LUA ERROR]' in text:
                raise RuntimeError(f'{core} {name}: see {run / "run.log"}\n{text}')
            print(f'{core} {name} PASS', flush=True)


if __name__ == '__main__':
    main()
