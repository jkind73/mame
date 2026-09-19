#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Exercise production SH delay-slot compiler state propagation.

A recording instruction emitter models SR writes; the production slot helper
must propagate the interrupt-check request to its caller. This is not a linked
DRC execution test. --old-state drops the new propagation and must fail.
"""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--old-state', action='store_true')
args = parser.parse_args()
source = (ROOT / 'src/devices/cpu/sh/sh.cpp').read_text()
start = source.index('void sh_common_execution::generate_delay_slot(')
end = source.index('\n}', start) + 2
function = source[start:end]
if args.old_state:
    statement = '\tcompiler.checkints = compiler_temp.checkints;'
    assert function.count(statement) == 1
    function = function.replace(statement, '')
harness = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <vector>
struct drcuml_block { std::vector<int> operations; };
struct compiler_state { int cycles = 0, labelnum = 0; bool checkints = false; };
struct opcode_desc {
    struct delay_list {
        const opcode_desc *instruction = nullptr;
        const opcode_desc *first() const { return instruction; }
    } delay;
    int kind = 0; // NOP, LDC Rm,SR, LDC.L @Rm+,SR
};
struct sh_common_execution {
    void generate_sequence_instruction(drcuml_block &block, compiler_state &c,
                                       const opcode_desc *desc, uint32_t ovrpc) {
        assert(ovrpc == 0x6001000);
        c.cycles += desc->kind == 2 ? 3 : 1;
        c.labelnum += 2;
        if (desc->kind) {
            c.checkints = true;
            block.operations.push_back(1); // write SR, without accepting IRQ in slot
        }
    }
    void generate_delay_slot(drcuml_block &, compiler_state &, const opcode_desc *, uint32_t);
};
// PRODUCTION
int main() {
    unsigned cases = 0;
    for (int kind = 0; kind < 3; ++kind)
        for (bool before : {false, true})
            for (int cycles : {0, 1, 12, 100})
                for (int label : {0, 7, 100}) {
                    sh_common_execution cpu;
                    drcuml_block block;
                    compiler_state compiler{cycles, label, before};
                    opcode_desc slot; slot.kind = kind;
                    opcode_desc branch; branch.delay.instruction = &slot;
                    cpu.generate_delay_slot(block, compiler, &branch, 0x6001000);
                    assert(compiler.checkints == (before || kind != 0));
                    assert(compiler.cycles == cycles + (kind == 2 ? 3 : 1));
                    assert(compiler.labelnum == label + 2);
                    // Caller emits check after the slot, before returning to
                    // ordinary code. SR writes must not be checked mid-slot.
                    if (compiler.checkints) block.operations.push_back(2);
                    block.operations.push_back(3); // next code masks BIOS shadow
                    if (kind) assert((block.operations == std::vector<int>{1,2,3}));
                    else if (before) assert((block.operations == std::vector<int>{2,3}));
                    else assert((block.operations == std::vector<int>{3}));
                    ++cases;
                }
    std::cout << cases << " SH delay-slot compiler-state cases passed\n";
}
'''
with tempfile.TemporaryDirectory(prefix='sh-delay-irq-') as temp:
    cpp, exe = Path(temp) / 'test.cpp', Path(temp) / 'test'
    cpp.write_text(harness.replace('// PRODUCTION', function))
    subprocess.run([os.environ.get('CXX', 'c++'), '-std=c++17', '-O1',
                    '-Wall', '-Wextra', '-Werror', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
