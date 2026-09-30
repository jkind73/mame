// license:BSD-3-Clause
// Standalone check of saturn_vdp2_compose.h against the MiSTer arithmetic.
// g++ -std=c++17 -I src/mame/sega tests/saturn/vdp2_compose_test.cpp && ./a.out
#include "saturn_vdp2_compose.h"
#include <cstdio>
#include <cstdlib>

using namespace saturn_vdp2_compose;

#define CHECK(x) do { if (!(x)) { std::printf("FAIL line %d: %s\n", __LINE__, #x); std::exit(1); } } while (0)

static layer_input mk(uint8_t pri, uint32_t dc)
{
	layer_input l; l.on = true; l.priority = pri; l.dot.dc = dc; return l;
}

int main()
{
	// Earlier layers win ties; later strictly-higher ones displace.
	dot_stack s;
	insert_layer(s, layer_kind::sprite, mk(3, 1));
	insert_layer(s, layer_kind::rbg0, mk(3, 2));   // tie: goes second
	insert_layer(s, layer_kind::nbg, mk(3, 3));    // tie with both: third
	CHECK(s.dot[0].dc == 1 && s.dot[1].dc == 2 && s.dot[2].dc == 3);
	insert_layer(s, layer_kind::nbg, mk(5, 4));    // displaces all
	CHECK(s.dot[0].dc == 4 && s.dot[1].dc == 1 && s.dot[2].dc == 2);
	insert_layer(s, layer_kind::rbg0, mk(1, 9));   // rbg0 cannot take the third slot
	CHECK(s.dot[2].dc == 2);
	insert_layer(s, layer_kind::nbg, mk(0, 9));    // priority 0 hidden
	CHECK(s.dot[0].dc == 4);

	// Colour calc: ratio 0 -> 31/32 first + 1/32 second; additive saturates.
	rgb a{200, 100, 0}, b{100, 100, 255};
	rgb m = color_calc(a, b, 0, true, false);
	CHECK(m.r == ((200 * 31 + 100 * 1) >> 5));
	rgb add = color_calc(a, b, 0, true, true);
	CHECK(add.r == 255 && add.g == 200 && add.b == 255);
	CHECK(color_calc(a, b, 5, false, false).r == 200);

	// Colour offset clamps both ways; shadow halves.
	CHECK(color_offset(250, 20, true) == 255);
	CHECK(color_offset(10, 0x1f0, true) == 0);   // -16
	CHECK(color_offset(100, 0x1ff, true) == 99); // -1
	CHECK(color_offset(100, 0x1ff, false) == 100);
	CHECK(shadow(255, true) == 127);

	// Extended: sec/2 + thd/4 + fth/4 with both ratios, sec/2 + thd/2 with one.
	rgb w{255, 0, 0};
	CHECK(ext_color_calc(w, true, w, false, true, w, true, false, 0, true).r == 127 + 63 + 63);
	CHECK(ext_color_calc(w, true, w, false, false, w, false, false, 0, true).r == 127 + 127);
	CHECK(ext_color_calc(w, false, w, false, false, w, false, false, 0, true).r == 255);
	std::puts("ok");
	return 0;
}
