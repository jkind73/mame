#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Execute the production 315-5649 register read/write code against a mock bus.

Covers the two gaps closed this session (STV-03 port G counter reset, STV-05
RS-422 loopback) plus the unchanged paths they sit next to, so a regression in
the shared Model 2/3 behaviour is caught as well as a break in the new code.

This is a linked fixture, not a cabinet: it drives sega_315_5649_device::read
and ::write verbatim from src/mame/sega/315_5649.cpp, but the callbacks are
mocks, so it proves the register semantics and not any real link timing.

MUTATE_IOGA=1 restores the pre-fix behaviour (constant 0x0c status, no
loopback, no counter reset) and must fail.
"""
from pathlib import Path
import os, subprocess, tempfile

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / 'src/mame/sega/315_5649.cpp').read_text()


def extract(signature):
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


functions = '\n'.join(extract(s) for s in (
    'uint8_t sega_315_5649_device::read(offs_t offset)',
    'void sega_315_5649_device::write(offs_t offset, uint8_t data)',
))

if os.environ.get('MUTATE_IOGA') == '1':
    # the pre-fix register file: constant status, no loopback, no counter reset
    functions = functions.replace(
        '\t\tdata = (m_serial_rx_valid[1] ? 0x08 : 0x00)\n'
        '\t\t\t| (m_serial_rx_valid[0] ? 0x04 : 0x00);\n'
        '\t\tif (!(m_mode & 0x10))\n'
        '\t\t\tdata |= 0x0c;',
        '\t\tdata = 0x0c;')
    functions = functions.replace('\t\t\tif (m_mode & 0x10)\n'
                                  '\t\t\t{\n'
                                  '\t\t\t\tm_serial_rx_data[ch] = data;\n'
                                  '\t\t\t\tm_serial_rx_valid[ch] = 1;\n'
                                  '\t\t\t}', '')
    functions = functions.replace('\t\tif ((m_mode & 0x80) && !(data & 0x80))\n'
                                  '\t\t{\n'
                                  '\t\t\tfor (int i = 0; i < 4; i++)\n'
                                  '\t\t\t\tm_cnt_reset_cb[i](ASSERT_LINE);\n'
                                  '\t\t}', '')

harness = r'''
#include <array>
#include <cassert>
#include <cstdint>
#include <iostream>

using u8 = uint8_t;
using u16 = uint16_t;
using offs_t = uint32_t;
constexpr int ASSERT_LINE = 1;
#define BIT(x, n) (((x) >> (n)) & 1)
#define LOG(...) ((void)0)

struct machine_t {
	bool side_effects = true;
	bool side_effects_disabled() const { return !side_effects; }
};

struct sega_315_5649_device {
	// mock callbacks: ports read back a fixed pattern, serial reads back the
	// channel index so a delegate answer is distinguishable from a latched one
	std::array<u8, 7> in_value{0xa0, 0xa1, 0xa2, 0xa3, 0xa4, 0xa5, 0xa6};
	std::array<u8, 7> out_value{};
	std::array<u8, 8> an_value{0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17};
	std::array<u8, 2> serial_value{0xd0, 0xd1};
	std::array<u8, 2> serial_sent{};
	std::array<u16, 4> cnt_value{0x1111, 0x2222, 0x3333, 0x4444};
	std::array<int, 4> cnt_resets{};

	struct rd8 {
		sega_315_5649_device *d; const u8 *src;
		u8 operator()(int) const { return *src; }
	};
	struct wr8 {
		sega_315_5649_device *d; u8 *dst;
		void operator()(u8 v) const { *dst = v; }
	};
	struct rd16 {
		sega_315_5649_device *d; const u16 *src;
		u16 operator()(int) const { return *src; }
	};
	struct wrline {
		sega_315_5649_device *d; int *dst;
		void operator()(int v) const { if (v) ++*dst; }
	};

	// one indirection per index, matching devcb_*::array semantics
	struct in_cb { sega_315_5649_device *d; rd8 operator[](unsigned n) const { return {d, &d->in_value[n]}; } } m_in_port_cb{this};
	struct out_cb { sega_315_5649_device *d; wr8 operator[](unsigned n) const { return {d, &d->out_value[n]}; } } m_out_port_cb{this};
	struct an_cb { sega_315_5649_device *d; rd8 operator[](unsigned n) const { return {d, &d->an_value[n]}; } } m_an_port_cb{this};
	struct srd_cb { sega_315_5649_device *d; rd8 operator[](unsigned n) const { return {d, &d->serial_value[n]}; } } m_serial_rd_cb{this};
	struct swr_cb { sega_315_5649_device *d; wr8 operator[](unsigned n) const { return {d, &d->serial_sent[n]}; } } m_serial_wr_cb{this};
	struct cnt_cb { sega_315_5649_device *d; rd16 operator[](unsigned n) const { return {d, &d->cnt_value[n]}; } } m_cnt_cb{this};
	struct rst_cb { sega_315_5649_device *d; wrline operator[](unsigned n) const { return {d, &d->cnt_resets[n]}; } } m_cnt_reset_cb{this};

	uint8_t m_port_value[7] = {0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff};
	uint8_t m_port_config = 0xff;
	uint8_t m_mode = 0;
	int m_analog_channel = 0;
	uint8_t m_serial_rx_data[2] = {};
	uint8_t m_serial_rx_valid[2] = {};

	machine_t m_machine;
	machine_t &machine() { return m_machine; }

	uint8_t read(offs_t offset);
	void write(offs_t offset, uint8_t data);
};
// FUNCTIONS
int main()
{
	unsigned cases = 0;

	// ---- unchanged paths must not regress -------------------------------
	{
		sega_315_5649_device io;
		// every port reads back its callback value while configured as input
		for (unsigned p = 0; p < 7; ++p)
			assert(io.read(p) == 0xa0 + p);
		// direction register: 0 = output, so the port reads its own latch
		io.write(0x08, 0x00);
		assert(io.m_port_config == 0x00);
		io.write(0x03, 0x5c);
		assert(io.m_port_value[3] == 0x5c && io.out_value[3] == 0x5c);
		assert(io.read(0x03) == 0x5c);
		// analog mux auto-increments through the eight channels
		for (unsigned n = 0; n < 8; ++n) {
			assert(io.read(0x0f) == 0x10 + n);
			++cases;
		}
		assert(io.read(0x0f) == 0x10);          // wrapped
		io.write(0x0f, 0x05);
		assert(io.m_analog_channel == 5);
		io.write(0x0f, 0xff);                   // only bits 0-2 select
		assert(io.m_analog_channel == 7);
		++cases;
	}

	// ---- STV-03: port G counter mode ------------------------------------
	{
		sega_315_5649_device io;
		// counter mode off: port G behaves like any other port
		io.write(0x06, 0x00);
		assert(io.read(0x06) == 0xa6);
		for (int i = 0; i < 4; ++i)
			assert(io.cnt_resets[i] == 0);

		// counter mode on: reads walk the four 16-bit counters MSB byte first,
		// and the low 3 bits of the latch pick the counter/byte pair
		io.write(0x0e, 0x80);
		assert(io.m_mode == 0x80);
		io.write(0x06, 0x80);                   // select counter 0, high byte
		assert(io.read(0x06) == 0x11);          // counter 0 high
		assert(io.m_port_value[6] == 0x81);     // auto-incremented
		assert(io.read(0x06) == 0x11);          // counter 0 low
		assert(io.m_port_value[6] == 0x82);
		assert(io.read(0x06) == 0x22);          // counter 1 high
		assert(io.m_port_value[6] == 0x83);
		assert(io.read(0x06) == 0x22);          // counter 1 low
		assert(io.m_port_value[6] == 0x84);
		assert(io.read(0x06) == 0x33);          // counter 2 high
		assert(io.m_port_value[6] == 0x85);
		assert(io.read(0x06) == 0x33);          // counter 2 low
		assert(io.m_port_value[6] == 0x86);
		assert(io.read(0x06) == 0x44);          // counter 3 high
		assert(io.m_port_value[6] == 0x87);
		assert(io.read(0x06) == 0x44);          // counter 3 low
		assert(io.m_port_value[6] == 0x80);     // wrapped, bit 7 preserved
		io.m_machine.side_effects = false;      // peeking must not advance it
		assert(io.read(0x06) == 0x11);
		assert(io.m_port_value[6] == 0x80);
		io.m_machine.side_effects = true;
		++cases;

		// writing bit 7 low in counter mode resets all four counters
		io.write(0x06, 0x7f);
		for (int i = 0; i < 4; ++i)
			assert(io.cnt_resets[i] == 1);
		// writing bit 7 high must not
		io.write(0x06, 0xff);
		for (int i = 0; i < 4; ++i)
			assert(io.cnt_resets[i] == 1);
		++cases;

		// with counter mode off the same write is just a port write
		sega_315_5649_device io2;
		io2.write(0x06, 0x00);
		for (int i = 0; i < 4; ++i)
			assert(io2.cnt_resets[i] == 0);
		++cases;
	}

	// ---- STV-05: RS-422 --------------------------------------------------
	{
		// no loopback: status keeps the historical "both buffers full" value
		// and reads come from the driver callback
		sega_315_5649_device io;
		assert(io.read(0x0d) == 0x0c);
		assert(io.read(0x0b) == 0xd0);
		assert(io.read(0x0c) == 0xd1);
		assert(io.read(0x0d) == 0x0c);          // reading does not clear it
		++cases;

		// loopback on: a transmitted byte lands in its own receiver
		io.write(0x0e, 0x10);
		assert(io.m_mode == 0x10);
		io.write(0x09, 0x77);
		assert(io.serial_sent[0] == 0x77);      // the driver still sees the TX
		assert(io.serial_sent[1] == 0x00);
		assert(io.read(0x0d) == 0x04);          // RX1BF only
		assert(io.read(0x0b) == 0x77);          // latched byte, not 0xd0
		assert(io.read(0x0d) == 0x00);          // consumed -> buffer empty
		assert(io.read(0x0b) == 0xd0);          // falls back to the callback
		++cases;

		// channel 2 is independent
		io.write(0x0a, 0x99);
		assert(io.serial_sent[1] == 0x99);
		assert(io.read(0x0d) == 0x08);          // RX2BF only
		assert(io.read(0x0c) == 0x99);
		assert(io.read(0x0d) == 0x00);
		++cases;

		// a byte that was never read is dropped when loopback is switched off
		io.write(0x09, 0x11);
		assert(io.read(0x0d) == 0x04);
		io.write(0x0e, 0x00);
		assert(io.read(0x0d) == 0x0c);
		assert(io.read(0x0b) == 0xd0);
		++cases;

		// side-effect-free peeking must not consume the latched byte
		io.write(0x0e, 0x10);
		io.write(0x0a, 0x22);
		io.m_machine.side_effects = false;
		assert(io.read(0x0c) == 0x22);
		io.m_machine.side_effects = true;
		assert(io.read(0x0d) == 0x08);          // still pending
		assert(io.read(0x0c) == 0x22);
		assert(io.read(0x0d) == 0x00);          // now consumed
		++cases;
	}

	// ---- exhaustive register sweep: no path may trap ----------------------
	{
		for (unsigned mode = 0; mode < 256; ++mode) {
			sega_315_5649_device io;
			io.write(0x0e, mode);
			for (unsigned off = 0; off < 0x10; ++off) {
				io.write(off, mode ^ off);
				(void)io.read(off);
				++cases;
			}
		}
	}

	std::cout << "315-5649: " << cases << " register cases passed\n";
}
'''.replace('// FUNCTIONS', functions)

with tempfile.TemporaryDirectory(prefix='saturn-ioga-') as tmp:
    src = Path(tmp) / 'test.cpp'
    exe = Path(tmp) / 'test'
    src.write_text(harness)
    subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++20', '-O1', '-g',
                    '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                    str(src), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
