#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Execute the production Saturn cart accessors against a mock slot.

Covers CART-01: the Data RAM and Battery RAM cart handlers extracted verbatim
from src/devices/bus/saturn/{dram,bram}.cpp.  The point of the fixture is the
guard added this session - the console maps a fixed 2 MiB window per DRAM chip
and an 8 MiB window for battery RAM whatever the fitted capacity is, so a cart
whose region was never allocated used to compute `offset % 0`.

MUTATE_CART=1 restores the pre-fix handlers (hard-coded 0x80000 bound, no
empty-region check, popmessage) and must fail.
"""
from pathlib import Path
import os, subprocess, tempfile

ROOT = Path(__file__).resolve().parents[2]
dram = (ROOT / 'src/devices/bus/saturn/dram.cpp').read_text()
bram = (ROOT / 'src/devices/bus/saturn/bram.cpp').read_text()


def extract(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


functions = '\n'.join([
    extract(dram, 'uint32_t saturn_dram_device::read_ext_dram0(offs_t offset)'),
    extract(dram, 'uint32_t saturn_dram_device::read_ext_dram1(offs_t offset)'),
    extract(dram, 'void saturn_dram_device::write_ext_dram0(offs_t offset, uint32_t data, uint32_t mem_mask)'),
    extract(dram, 'void saturn_dram_device::write_ext_dram1(offs_t offset, uint32_t data, uint32_t mem_mask)'),
    extract(bram, 'uint32_t saturn_bram_device::read_ext_bram(offs_t offset)'),
    extract(bram, 'void saturn_bram_device::write_ext_bram(offs_t offset, uint32_t data, uint32_t mem_mask)'),
])

if os.environ.get('MUTATE_CART') == '1':
    # pre-fix DRAM handlers: constant bound, unguarded modulo, popmessage
    for n in ('0', '1'):
        functions = functions.replace(
            f'\tif (m_ext_dram{n}.empty())\n'
            '\t{\n'
            f'\t\tlogerror("%s: DRAM{n} read with no region allocated (offs %X)\\n", machine().describe_context(), offset);\n'
            '\t\treturn 0xffffffff;\n'
            '\t}\n'
            f'\treturn m_ext_dram{n}[offset % m_ext_dram{n}.size()];',
            f'\tif (offset < (0x400000/2)/4)\n'
            f'\t\treturn m_ext_dram{n}[offset % m_ext_dram{n}.size()];\n'
            '\telse\n'
            '\t\treturn 0xffffffff;')

harness = r'''
#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

using u8 = uint8_t;
using u32 = uint32_t;
using offs_t = uint32_t;

#define COMBINE_DATA(_ptr) (*(_ptr) = (*(_ptr) & ~mem_mask) | (data & mem_mask))
#define ACCESSING_BITS_16_23 (mem_mask & 0x00ff0000)
#define ACCESSING_BITS_0_7   (mem_mask & 0x000000ff)

struct machine_t { const char *describe_context() const { return "cart-test"; } };
static void logerror(const char *, ...) {}

// ---- Data RAM cart ---------------------------------------------------------
struct saturn_dram_device {
	std::vector<u32> m_ext_dram0, m_ext_dram1;
	machine_t m_machine;
	machine_t &machine() { return m_machine; }
	u32 read_ext_dram0(offs_t offset);
	u32 read_ext_dram1(offs_t offset);
	void write_ext_dram0(offs_t offset, u32 data, u32 mem_mask);
	void write_ext_dram1(offs_t offset, u32 data, u32 mem_mask);
};

// ---- Battery RAM cart ------------------------------------------------------
struct saturn_bram_device {
	std::vector<u8> m_ext_bram;
	machine_t m_machine;
	machine_t &machine() { return m_machine; }
	u32 read_ext_bram(offs_t offset);
	void write_ext_bram(offs_t offset, u32 data, u32 mem_mask);
};
// FUNCTIONS
int main()
{
	unsigned cases = 0;

	// ---- 8 Mbit Data RAM cart (ID 5a): 4 Mbit = 0x20000 words per chip ----
	{
		saturn_dram_device c;
		c.m_ext_dram0.resize(0x20000);
		c.m_ext_dram1.resize(0x20000);

		c.write_ext_dram0(0x00000, 0xdeadbeef, ~0u);
		c.write_ext_dram0(0x1ffff, 0x12345678, ~0u);
		assert(c.read_ext_dram0(0x00000) == 0xdeadbeef);
		assert(c.read_ext_dram0(0x1ffff) == 0x12345678);

		// the console window is 2 MiB = 0x80000 words, four times this chip,
		// so the upper three quarters alias - that is the retained modelling
		// choice, asserted here so a silent change to it is noticed
		assert(c.read_ext_dram0(0x20000) == 0xdeadbeef);
		assert(c.read_ext_dram0(0x7ffff) == 0x12345678);

		// byte lanes
		c.write_ext_dram1(0x100, 0xffff0000, 0xffff0000);
		assert(c.read_ext_dram1(0x100) == 0xffff0000);
		c.write_ext_dram1(0x100, 0x0000aaaa, 0x0000ffff);
		assert(c.read_ext_dram1(0x100) == 0xffffaaaa);
		cases += 6;
	}

	// ---- 32 Mbit Data RAM cart (ID 5c): 0x80000 words per chip, no alias --
	{
		saturn_dram_device c;
		c.m_ext_dram0.resize(0x80000);
		c.write_ext_dram0(0x00000, 0x11111111, ~0u);
		c.write_ext_dram0(0x20000, 0x22222222, ~0u);
		c.write_ext_dram0(0x7ffff, 0x33333333, ~0u);
		assert(c.read_ext_dram0(0x00000) == 0x11111111);
		assert(c.read_ext_dram0(0x20000) == 0x22222222);
		assert(c.read_ext_dram0(0x7ffff) == 0x33333333);
		cases += 3;
	}

	// ---- the guard: no region allocated -----------------------------------
	// This is the case that used to divide by zero.  It is reachable when the
	// slot holds a DRAM cart but the software list entry supplied no region.
	{
		saturn_dram_device c;
		assert(c.m_ext_dram0.empty() && c.m_ext_dram1.empty());
		assert(c.read_ext_dram0(0) == 0xffffffff);
		assert(c.read_ext_dram0(0x7ffff) == 0xffffffff);
		assert(c.read_ext_dram1(0x1234) == 0xffffffff);
		c.write_ext_dram0(0, 0xdeadbeef, ~0u);      // must be a no-op, not a crash
		c.write_ext_dram1(0x55, 0xdeadbeef, ~0u);
		assert(c.m_ext_dram0.empty() && c.m_ext_dram1.empty());
		cases += 5;
	}

	// ---- Battery RAM cart --------------------------------------------------
	{
		// 4 Mbit cart: 512 KiB, so the 8 MiB window runs off the end of it
		saturn_bram_device c;
		c.m_ext_bram.resize(0x80000);

		// the cart is 16-bit: each longword access writes data bits 16-23 to
		// the even byte and bits 0-7 to the odd byte, and the read puts them
		// back in the same two lanes, so the value comes back byte-spread
		c.write_ext_bram(0x00000, 0xaabbccdd, ~0u);
		assert(c.m_ext_bram[0] == 0xbb && c.m_ext_bram[1] == 0xdd);
		assert(c.read_ext_bram(0x00000) == 0x00bb00dd);
		c.write_ext_bram(0x00000, 0x11223344, 0x00ff0000);   // high lane only
		assert(c.m_ext_bram[0] == 0x22 && c.m_ext_bram[1] == 0xdd);
		assert(c.read_ext_bram(0x00000) == 0x002200dd);
		c.write_ext_bram(0x00000, 0x11223344, 0x000000ff);   // low lane only
		assert(c.m_ext_bram[0] == 0x22 && c.m_ext_bram[1] == 0x44);
		assert(c.read_ext_bram(0x00000) == 0x00220044);

		// last addressable pair
		offs_t last = c.m_ext_bram.size() / 2 - 1;
		c.write_ext_bram(last, 0x0000beef, 0x0000ffff);
		assert(c.m_ext_bram[last * 2 + 1] == 0xef);
		assert(c.read_ext_bram(last) == 0x000000ef);

		// past the end: open bus, logged, and the array must not be touched
		assert(c.read_ext_bram(last + 1) == 0xffffffff);
		assert(c.read_ext_bram(0x1fffff) == 0xffffffff);
		c.write_ext_bram(last + 1, 0xdeadbeef, ~0u);
		assert(c.read_ext_bram(last) == 0x000000ef);
		cases += 8;

		// empty cart: every access is out of range, none may trap
		saturn_bram_device e;
		assert(e.read_ext_bram(0) == 0xffffffff);
		e.write_ext_bram(0, 0xdeadbeef, ~0u);
		assert(e.m_ext_bram.empty());
		cases += 2;
	}

	std::cout << "Saturn carts: " << cases << " access cases passed\n";
}
'''.replace('// FUNCTIONS', functions)

with tempfile.TemporaryDirectory(prefix='saturn-cart-') as tmp:
    src = Path(tmp) / 'test.cpp'
    exe = Path(tmp) / 'test'
    src.write_text(harness)
    subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++20', '-O1', '-g',
                    '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                    str(src), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
