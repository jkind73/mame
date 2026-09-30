// license:BSD-3-Clause
// Standalone checks of the VDP1 drawing engine.
// g++ -std=c++17 -I src/mame/sega tests/saturn/vdp1_draw_test.cpp src/mame/sega/saturn_vdp1_draw.cpp && ./a.out
#include "saturn_vdp1_draw.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

using namespace saturn_vdp1;

#define CHECK_EQ(a, b) do { unsigned long long va = (a), vb = (b); if (va != vb) { std::printf("FAIL line %d: %s = %llx, expected %llx\n", __LINE__, #a, va, vb); std::exit(1); } } while (0)

struct rig {
	std::vector<uint16_t> vram = std::vector<uint16_t>(VRAM_WORDS);
	std::vector<uint16_t> fb = std::vector<uint16_t>(FB_WORDS);
	draw_engine e;
	rig()
	{
		e.vram = vram.data();
		e.fb = fb.data();
		e.reset();
		e.sys_x = 319;
		e.sys_y = 223;
	}
	uint16_t px(int x, int y) const { return fb[((y & 0xff) << 9) + (x & 0x1ff)]; }
	unsigned count(uint16_t v) const
	{
		unsigned n = 0;
		for (int y = 0; y < 256; y++)
			for (int x = 0; x < 512; x++)
				n += px(x, y) == v;
		return n;
	}
};

static void cmd(uint16_t *c, unsigned ctrl, unsigned mode, unsigned colour, unsigned srca, unsigned size,
		int xa, int ya, int xb, int yb, int xc, int yc, int xd, int yd)
{
	c[0] = ctrl; c[1] = 0; c[2] = mode; c[3] = colour; c[4] = srca; c[5] = size;
	c[6] = xa & 0x1fff; c[7] = ya & 0x1fff; c[8] = xb & 0x1fff; c[9] = yb & 0x1fff;
	c[10] = xc & 0x1fff; c[11] = yc & 0x1fff; c[12] = xd & 0x1fff; c[13] = yd & 0x1fff;
	c[14] = 0; c[15] = 0;
}

int main()
{
	// 1. flat polygon: a 10x10 square covers exactly 100 pixels
	{
		rig r;
		uint16_t c[16];
		cmd(c, 4, 0x0000, 0x8123, 0, 0, 10, 20, 19, 20, 19, 29, 10, 29);
		r.e.execute(c);
		CHECK_EQ(r.count(0x8123), 100);
		CHECK_EQ(r.px(10, 20), 0x8123);
		CHECK_EQ(r.px(19, 29), 0x8123);
		CHECK_EQ(r.px(20, 20), 0);
		CHECK_EQ(r.px(10, 30), 0);
	}

	// 2. line: horizontal, 5 pixels
	{
		rig r;
		uint16_t c[16];
		cmd(c, 6, 0x0000, 0x8001, 0, 0, 5, 7, 9, 7, 0, 0, 0, 0);
		r.e.execute(c);
		CHECK_EQ(r.count(0x8001), 5);
		for (int x = 5; x <= 9; x++)
			CHECK_EQ(r.px(x, 7), 0x8001);
	}

	// 3. normal sprite, 16 colour bank mode: an 8x2 texture, texel value = x
	{
		rig r;
		for (int row = 0; row < 2; row++)
			for (int w = 0; w < 2; w++)   // 8 texels = 2 words
				r.vram[0x100 * 4 + row * 2 + w] = uint16_t((((w * 4 + 0) & 15) << 12) | (((w * 4 + 1) & 15) << 8) | (((w * 4 + 2) & 15) << 4) | ((w * 4 + 3) & 15));
		uint16_t c[16];
		// CMDSRCA = 0x100 (8 byte units -> word 0x400); size 8x2 => SX=1, SY=2; colour bank 0x0010
		cmd(c, 0, 0x0000 | 0x0000, 0x0010, 0x100, (1 << 8) | 2, 30, 40, 0, 0, 0, 0, 0, 0);
		r.e.execute(c);
		// texel 0 is transparent (SPD=0); texels 1..7 -> colour bank | value
		CHECK_EQ(r.px(30, 40), 0);
		for (int x = 1; x < 8; x++)
			CHECK_EQ(r.px(30 + x, 40), 0x0010 | x);
		CHECK_EQ(r.px(37, 41), 0x0010 | 7);
		CHECK_EQ(r.px(38, 40), 0);
	}

	// 4. scaled sprite: the 8x2 texture drawn as 16x4 doubles every texel
	{
		rig r;
		for (int row = 0; row < 2; row++)
			for (int w = 0; w < 2; w++)
				r.vram[0x100 * 4 + row * 2 + w] = uint16_t((((w * 4 + 0) & 15) << 12) | (((w * 4 + 1) & 15) << 8) | (((w * 4 + 2) & 15) << 4) | ((w * 4 + 3) & 15));
		uint16_t c[16];
		// ZP = 5 (upper left origin, width/height given): 0x0500 -> zp bits 11:8 = 5 => 0x0500 in ctrl
		cmd(c, 0x0101, 0x0040, 0x0010, 0x100, (1 << 8) | 2, 50, 60, 16, 4, 0, 0, 0, 0);
		c[0] = 0x0501;    // scaled sprite, ZP = 5 (top left origin, size given)
		r.e.execute(c);
		// The scaled sprite covers width + 1 by height + 1 dots (corner C = A + size),
		// the 8 texels are spread across the 17 dots; SPD=1 so texel 0 draws too.
		CHECK_EQ(r.px(50, 60), 0x0010);
		CHECK_EQ(r.px(66, 64), 0x0017);
		CHECK_EQ(r.px(67, 60), 0);
		CHECK_EQ(r.px(50, 65), 0);
		CHECK_EQ(r.px(49, 60), 0);
		CHECK_EQ(r.px(58, 62), 0x0013);           // the middle dot shows texel 3
	}

	// 5. horizontally flipped normal sprite
	{
		rig r;
		for (int row = 0; row < 2; row++)
			for (int w = 0; w < 2; w++)
				r.vram[0x100 * 4 + row * 2 + w] = uint16_t((((w * 4 + 0) & 15) << 12) | (((w * 4 + 1) & 15) << 8) | (((w * 4 + 2) & 15) << 4) | ((w * 4 + 3) & 15));
		uint16_t c[16];
		cmd(c, 0x0010, 0x0040, 0x0010, 0x100, (1 << 8) | 2, 30, 40, 0, 0, 0, 0, 0, 0);
		r.e.execute(c);
		CHECK_EQ(r.px(30, 40), 0x0017);
		CHECK_EQ(r.px(37, 40), 0x0010);
	}

	// 6. system clip: pixels beyond it are not drawn
	{
		rig r;
		r.e.sys_x = 14;
		r.e.sys_y = 14;
		uint16_t c[16];
		cmd(c, 4, 0x0000, 0x8002, 0, 0, 10, 10, 19, 10, 19, 19, 10, 19);
		r.e.execute(c);
		CHECK_EQ(r.count(0x8002), 25);
	}

	// 7. local coordinates offset everything
	{
		rig r;
		uint16_t c[16];
		cmd(c, 0xa, 0, 0, 0, 0, 100, 50, 0, 0, 0, 0, 0, 0);
		r.e.execute(c);
		cmd(c, 4, 0x0000, 0x8003, 0, 0, 0, 0, 4, 0, 4, 4, 0, 4);
		r.e.execute(c);
		CHECK_EQ(r.count(0x8003), 25);
		CHECK_EQ(r.px(100, 50), 0x8003);
		CHECK_EQ(r.px(104, 54), 0x8003);
	}

	// 8. half transparency against an opaque background halves the colour
	{
		rig r;
		for (int y = 0; y < 8; y++)
			for (int x = 0; x < 8; x++)
				r.fb[(y << 9) + x] = 0x8000 | (20 << 10) | (20 << 5) | 20;
		uint16_t c[16];
		cmd(c, 4, 0x0003, 0x8000 | (10 << 10) | (10 << 5) | 10, 0, 0, 0, 0, 3, 0, 3, 3, 0, 3);   // CCB = 3: half FG + half BG
		r.e.execute(c);
		CHECK_EQ(r.px(1, 1), 0x8000 | (15 << 10) | (15 << 5) | 15);
	}

	std::puts("ok");
	return 0;
}
