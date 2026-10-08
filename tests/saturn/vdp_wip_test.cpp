// license:BSD-3-Clause
// Rel.2.5 VDP2 6.3 and Table 8.1 regression fixtures. Link the real renderer.
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <memory>
#define private public
#include "saturn_vdp2_render.h"
#undef private

using namespace saturn_vdp2_render;

struct blank_sprites : sprite_source {
	uint16_t sprite_word(unsigned, unsigned) const override { return 0; }
};

void test_windows()
{
	std::array<uint16_t, 256> regs{};
	auto vram = std::make_unique<uint32_t[]>(0x20000);
	std::array<uint32_t, 1024> cram{};
	blank_sprites sprites;
	for (unsigned mode = 0; mode < 8; ++mode) {
		bool const hires = mode & 2, exclusive = mode & 4;
		screen_config cfg;
		cfg.hires = hires;
		cfg.exclusive = exclusive;
		cfg.hreso = mode;
		cfg.width = ((mode & 1) ? 352 : 320) * (hires ? 2 : 1);
		for (bool line_window : {false, true}) {
			regs.fill(0);
			// Exclusive registers discard bit 9; normal low resolution discards bit 0.
			unsigned const start = exclusive ? 0x207 : 14;
			unsigned const end = exclusive ? 0x20a : 20;
			regs[0xc0 / 2] = start;
			regs[0xc4 / 2] = end;
			if (line_window) {
				regs[0xd8 / 2] = 0x8000;
				regs[0xda / 2] = 0x800; // table at byte address 0x1000
				vram[0x1000 / 4] = (start << 16) | end;
			}
			auto r = std::make_unique<renderer>();
			r->begin_frame({regs.data(), vram.get(), cram.data()}, cfg);
			std::array<uint32_t, 704> pixels{};
			r->render_line(0, sprites, pixels.data());
			for (unsigned x = 0; x < cfg.width; ++x)
				assert(r->m_w_hit[0][x] == (x >= (hires ? 14 : 7) && x <= (hires ? 20 : 10)));
		}
	}
}

void test_rotation()
{
	std::array<uint16_t, 256> regs{};
	auto vram = std::make_unique<uint32_t[]>(0x20000);
	std::array<uint32_t, 1024> cram{};
	for (bool short_coefficients : {false, true}) {
		for (unsigned mode = 0; mode < 4; ++mode) {
			decoded d{};
			d.rpmd = mode;
			for (unsigned table = 0; table < 2; ++table) {
				unsigned const params = table * 0x80;
				unsigned const coefficients = 0x1000 + table * 0x1000;
				d.rot[table].kte = true;
				d.rot[table].kdbs = short_coefficients;
				d.rot[table].kmd = 3; // coefficient replaces Xp
				vram[(params + 0x54) / 4] = (coefficients / (short_coefficients ? 2 : 4)) << 16;
				vram[(params + 0x58) / 4] = 0x10000; // one coefficient per line
				vram[(params + 0x5c) / 4] = 0x10000; // one coefficient per dot
				for (unsigned x = 0; x < 8; ++x) {
					if (short_coefficients) {
						unsigned const shift = (x & 1) ? 0 : 16;
						uint32_t &word = vram[(coefficients + x * 2) / 4];
						word = (word & ~(0xffffU << shift)) | (((x + 1) * 4 | ((x & 1) ? 0x8000 : 0)) << shift);
					} else {
						vram[coefficients / 4 + x] = (x + 1) * 256 | ((x & 1) ? 0x80000000U : 0);
					}
				}
			}
			auto r = std::make_unique<renderer>();
			screen_config cfg;
			cfg.width = 4;
			r->begin_frame({regs.data(), vram.get(), cram.data()}, cfg);
			for (unsigned y = 0; y < 2; ++y) {
				r->calc_rotation(d, y, true);
				for (unsigned table = 0; table < 2; ++table)
					for (unsigned x = 0; x < 4; ++x) {
						unsigned const coefficient = y + ((mode == 2 && table == 1) ? 0 : x);
						assert(r->m_rot_line[table].x[x] == int(coefficient + 1));
						assert(r->m_rot_line[table].transparent[x] == bool(coefficient & 1));
					}
			}
		}
	}
}

int main(int argc, char **argv)
{
	assert(argc == 2);
	if (!std::strcmp(argv[1], "windows")) test_windows();
	else if (!std::strcmp(argv[1], "rotation")) test_rotation();
	else return 2;
	std::cout << argv[1] << " passed\n";
}
