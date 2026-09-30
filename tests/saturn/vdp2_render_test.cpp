// license:BSD-3-Clause
// Standalone checks of the VDP2 line renderer on hand-built memory images.
// g++ -std=c++17 -I src/mame/sega tests/saturn/vdp2_render_test.cpp src/mame/sega/saturn_vdp2_render.cpp && ./a.out
#include "saturn_vdp2_render.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

using namespace saturn_vdp2_render;

#define CHECK_EQ(a, b) do { unsigned long long va = (a), vb = (b); if (va != vb) { std::printf("FAIL line %d: %s = %llx, expected %llx\n", __LINE__, #a, va, vb); std::exit(1); } } while (0)

struct machine {
	uint16_t regs[0x100] = {};
	std::vector<uint32_t> vram = std::vector<uint32_t>(0x20000);
	uint32_t cram[0x400] = {};

	void w16(uint32_t addr, uint16_t v)
	{
		unsigned const sh = 16 - 16 * ((addr >> 1) & 1);
		uint32_t &w = vram[addr >> 2];
		w = (w & ~(0xffffU << sh)) | (uint32_t(v) << sh);
	}
	void w8(uint32_t addr, uint8_t v)
	{
		unsigned const sh = 24 - 8 * (addr & 3);
		uint32_t &w = vram[addr >> 2];
		w = (w & ~(0xffU << sh)) | (uint32_t(v) << sh);
	}
	void c15(unsigned index, unsigned r, unsigned g, unsigned b) // RAM mode 0 colour
	{
		uint16_t const c = r | (g << 5) | (b << 10);
		unsigned const sh = 16 - 16 * (index & 1);
		cram[index >> 1] = (cram[index >> 1] & ~(0xffffU << sh)) | (uint32_t(c) << sh);
	}
	memory mem() const
	{
		memory m;
		m.regs = regs; m.vram = vram.data(); m.cram = cram; m.vram_mask = 0x7ffff;
		return m;
	}
};

struct sprite_fb : sprite_source {
	uint16_t value = 0;
	uint16_t sprite_word(unsigned, unsigned) const override { return value; }
};

static uint32_t rgb555(unsigned r, unsigned g, unsigned b) { return (r << 19) | (g << 11) | (b << 3); }

// NBG0: 16 colour cells, 1 word pattern names, one 64x64 page at VRAM 0
static void setup_nbg0(machine &m)
{
	m.regs[0x20 / 2] = 0x0001;      // BGON: NBG0 on
	m.regs[0x28 / 2] = 0x0000;      // CHCTLA: 16 colours, 1x1 cells, tile mode
	m.regs[0x30 / 2] = 0x8000;      // PNCN0: 1 word patterns
	m.regs[0xf8 / 2] = 0x0004;      // PRINA: NBG0 priority 4
	m.regs[0x78 / 2] = 1;           // ZMXIN0: 1.0
	m.regs[0x7c / 2] = 1;           // ZMYIN0: 1.0
	m.regs[0x0e / 2] = 0x0000;      // RAMCTL: CRMD 0
	m.regs[0xac / 2] = 0;
	m.regs[0xae / 2] = 0x8000 >> 1; // BKTA -> 0x8000
	// tile 1 at 0x20: dot value == x (0..7) on each row, packed two per byte
	for (unsigned row = 0; row < 8; row++)
		for (unsigned px = 0; px < 4; px++)
			m.w8(0x20 + row * 4 + px, ((2 * px) << 4) | (2 * px + 1));
	// page 0 (plane A at address 0 with all map regs 0) uses character 1 everywhere
	for (unsigned i = 0; i < 64 * 64; i++)
		m.w16(0x2000 * 0 + i * 2, 1);
	// tile data must not overlap the name table: move tiles above it (0x2000 + )
}

int main()
{
	// 1. back screen only
	{
		machine m;
		m.regs[0xae / 2] = 0x8000 >> 1;
		m.w16(0x8000, 0x7c00 | 0x1f); // blue 31 + red 31
		screen_config cfg;
		renderer r;
		r.begin_frame(m.mem(), cfg);
		sprite_fb sp;
		uint32_t line[704];
		r.render_line(0, sp, line);
		CHECK_EQ(line[0], rgb555(31, 0, 31));
		CHECK_EQ(line[319], rgb555(31, 0, 31));
	}

	// 2. NBG0 tile: colours from CRAM, transparent dot 0 shows the back screen
	{
		machine m;
		setup_nbg0(m);
		// relocate character 1 data: pattern name char number 0x100 -> data at 0x100*32 = 0x2000+ (past the page)
		for (unsigned i = 0; i < 64 * 64; i++)
			m.w16(i * 2, 0x100);
		for (unsigned row = 0; row < 8; row++)
			for (unsigned px = 0; px < 4; px++)
				m.w8(0x100 * 32 + row * 4 + px, ((2 * px) << 4) | (2 * px + 1));
		m.w16(0x8000, 0x03e0);         // back: green 31
		for (unsigned i = 1; i < 16; i++)
			m.c15(i, i * 2, 0, 0);     // palette entry i: red i*2
		screen_config cfg;
		renderer r;
		r.begin_frame(m.mem(), cfg);
		sprite_fb sp;
		uint32_t line[704];
		r.render_line(0, sp, line);
		CHECK_EQ(line[0], rgb555(0, 31, 0));      // dot 0 transparent
		CHECK_EQ(line[1], rgb555(2, 0, 0));
		CHECK_EQ(line[7], rgb555(14, 0, 0));
		CHECK_EQ(line[8], rgb555(0, 31, 0));      // next cell starts with dot 0 again
		CHECK_EQ(line[9], rgb555(2, 0, 0));
	}

	// helper: NBG0 with the gradient tile everywhere (dot c has colour c = red 2c)
	auto make = [](machine &m) {
		setup_nbg0(m);
		for (unsigned i = 0; i < 64 * 64; i++)
			m.w16(i * 2, 0x100);
		for (unsigned row = 0; row < 8; row++)
			for (unsigned px = 0; px < 4; px++)
				m.w8(0x100 * 32 + row * 4 + px, ((2 * px) << 4) | (2 * px + 1));
		m.w16(0x8000, 0x03e0);
		for (unsigned i = 1; i < 16; i++)
			m.c15(i, i * 2, 0, 0);
	};
	auto run = [](machine &m, sprite_fb &sp, uint32_t *line, unsigned y = 0) {
		screen_config cfg;
		renderer r;
		r.begin_frame(m.mem(), cfg);
		for (unsigned i = 0; i <= y; i++)
			r.render_line(i, sp, line);
	};

	// 3. horizontal scroll
	{
		machine m;
		make(m);
		m.regs[0x70 / 2] = 3;                 // SCXIN0 = 3
		sprite_fb sp;
		uint32_t line[704];
		run(m, sp, line);
		CHECK_EQ(line[0], rgb555(6, 0, 0));   // map x 3 -> dot 3 -> red 6
		CHECK_EQ(line[4], rgb555(14, 0, 0));  // map x 7
		CHECK_EQ(line[5], rgb555(0, 31, 0));  // map x 8 -> dot 0: transparent
	}

	// 4. sprite against NBG0 priority; sprite type 0 word 0x0002 = colour 2, priority slot 0
	{
		machine m;
		make(m);
		m.regs[0xf0 / 2] = 5;                 // PRISA: S0PRIN = 5 (above NBG0's 4)
		sprite_fb sp;
		sp.value = 0x0002;
		uint32_t line[704];
		run(m, sp, line);
		CHECK_EQ(line[1], rgb555(4, 0, 0));   // sprite wins over NBG0 dot 1
		CHECK_EQ(line[0], rgb555(4, 0, 0));
		m.regs[0xf0 / 2] = 3;                 // sprite below NBG0
		run(m, sp, line);
		CHECK_EQ(line[1], rgb555(2, 0, 0));   // NBG0 wins
		CHECK_EQ(line[0], rgb555(4, 0, 0));   // NBG0 transparent: sprite shows
		m.regs[0xf0 / 2] = 4;                 // tie: earlier layer (sprite) wins
		run(m, sp, line);
		CHECK_EQ(line[1], rgb555(4, 0, 0));
	}

	// 5. colour calculation of NBG0 over the back screen: ratio register 0
	{
		machine m;
		make(m);
		m.regs[0xec / 2] = 0x0001;            // CCCTL: NBG0 colour calculation
		m.regs[0x108 / 2] = 0;                // CCRNA: NBG0 ratio 0
		sprite_fb sp;
		uint32_t line[704];
		run(m, sp, line);
		// top screen weighs (31 - 0)/32, second (0 + 1)/32
		unsigned const r = (16 * 31) >> 5, g = (248 * 1) >> 5;
		CHECK_EQ(line[1], (r << 16) | (g << 8));
	}

	// 6. window 0 hides NBG0 outside/inside as configured
	{
		machine m;
		make(m);
		m.regs[0xc0 / 2] = 8 * 2;             // W0SX = 8 (half dots)
		m.regs[0xc4 / 2] = 15 * 2;            // W0EX = 15
		m.regs[0xc2 / 2] = 0;                 // W0SY
		m.regs[0xc6 / 2] = 100;               // W0EY
		m.regs[0xd0 / 2] = 0x0002;            // WCTLA: NBG0 window 0 enabled, area 0
		sprite_fb sp;
		uint32_t line[704];
		run(m, sp, line);
		CHECK_EQ(line[1], rgb555(2, 0, 0));   // outside the window: shown
		CHECK_EQ(line[9], rgb555(0, 31, 0));  // inside: hidden (back screen)
		CHECK_EQ(line[17], rgb555(2, 0, 0));
	}

	// 7. two word pattern names with horizontal flip
	{
		machine m;
		make(m);
		m.regs[0x30 / 2] = 0x0000;            // PNCN0: 2 word patterns
		for (unsigned i = 0; i < 64 * 64; i++) {
			m.w16(i * 4, 0x4000);             // HF, palette 0
			m.w16(i * 4 + 2, 0x200);          // character 0x200 (past the 16KB name table)
		}
		for (unsigned row = 0; row < 8; row++)
			for (unsigned px = 0; px < 4; px++)
				m.w8(0x200 * 32 + row * 4 + px, ((2 * px) << 4) | (2 * px + 1));
		sprite_fb sp;
		uint32_t line[704];
		run(m, sp, line);
		CHECK_EQ(line[0], rgb555(14, 0, 0));  // flipped: first dot is dot 7
		CHECK_EQ(line[7], rgb555(0, 31, 0));  // last dot is dot 0: transparent
	}

	// 8. vertical zoom stepping: 2.0 advances two map lines per screen line
	{
		machine m;
		make(m);
		// give every tile row a distinct value: row r uses colour r+1 for all dots
		for (unsigned row = 0; row < 8; row++)
			for (unsigned px = 0; px < 4; px++)
				m.w8(0x100 * 32 + row * 4 + px, ((row + 1) << 4) | (row + 1));
		m.regs[0x7c / 2] = 2;                 // ZMYIN0 = 2.0
		sprite_fb sp;
		uint32_t line[704];
		run(m, sp, line, 0);
		CHECK_EQ(line[0], rgb555(2, 0, 0));   // line 0 -> row 0 -> colour 1
		run(m, sp, line, 1);
		CHECK_EQ(line[0], rgb555(6, 0, 0));   // line 1 -> row 2 -> colour 3
		run(m, sp, line, 3);
		CHECK_EQ(line[0], rgb555(14, 0, 0));  // line 3 -> row 6 -> colour 7
	}

	std::puts("ok");
	return 0;
}
