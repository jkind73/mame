// vdp1fuzz <seed> <count> <out_prefix>
// Generates <count> single-command VDP1 cases, draws each in Ymir and writes:
//   <prefix>_cases.bin : per case 0x10000 bytes of VDP1 VRAM as big-endian (CPU view) words + u16 TVMR + u16 pad
//   <prefix>_ymir.bin  : per case 0x40000 bytes of the displayed frame buffer (byte order as Ymir stores it)
//   <prefix>_desc.txt  : one line per case describing the command
#define private public
#define protected public
#include <ymir/hw/vdp/vdp.hpp>
#include <ymir/core/scheduler.hpp>
#include <ymir/core/configuration.hpp>
#include <ymir/sys/bus.hpp>
#undef private
#undef protected

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <random>
#include <string>
#include <vector>

static std::mt19937 rng;
static int rnd(int lo, int hi) { return lo + int(rng() % unsigned(hi - lo + 1)); }
static bool chance(int pct) { return rnd(0, 99) < pct; }

struct Case
{
	std::vector<uint16_t> vram = std::vector<uint16_t>(0x8000, 0); // 64 KiB
	uint16_t tvmr = 0;
	std::string desc;
};

static void put(Case &c, unsigned cmd, unsigned word, uint16_t v) { c.vram[cmd * 16 + word] = v; }

static Case make_case()
{
	Case c;
	char buf[512];
	// TVMR: 0 = 16 bpp frame buffer, 1 = 8 bpp
	c.tvmr = chance(15) ? 1 : 0;
	int const bpp8 = c.tvmr & 1;

	// textures at 0x8000.., CLUT at 0xE000, gouraud table at 0xF000 (byte addresses)
	for (unsigned i = 0; i < 0x2000; i++) // 0x8000..0xBFFF words? keep byte range 0x8000..0xEFFF
	{
		uint16_t v = uint16_t(rng());
		int k = rnd(0, 9);
		if (k == 0) v = 0x0000;
		else if (k == 1) v = 0x7FFF;
		else if (k == 2) v = 0xFFFF;
		else if (k == 3) v = 0x8000 | uint16_t(rng() & 0x7FFF);
		c.vram[0x4000 + i] = v;
	}
	for (unsigned i = 0; i < 0x400; i++) // CLUT (16-bit colours)
		c.vram[0x7000 + i] = uint16_t(rng()) | (chance(50) ? 0x8000 : 0);
	for (unsigned i = 0; i < 0x40; i++) // gouraud tables
		c.vram[0x7800 + i] = uint16_t(rng()) & 0x7FFF;

	unsigned n = 0;
	// system clip
	int sx2 = chance(70) ? 319 : rnd(8, 319), sy2 = chance(70) ? 223 : rnd(8, 223);
	put(c, n, 0, 0x0009); put(c, n, 10, sx2); put(c, n, 11, sy2); n++;
	// user clip
	int ux1 = rnd(0, 200), uy1 = rnd(0, 150), ux2 = ux1 + rnd(1, 180), uy2 = uy1 + rnd(1, 130);
	put(c, n, 0, 0x0008);
	put(c, n, 6, ux1); put(c, n, 7, uy1); put(c, n, 10, ux2); put(c, n, 11, uy2); n++;
	// local coordinates
	int lx = rnd(-16, 200), ly = rnd(-16, 150);
	if (chance(50)) { lx = 0; ly = 0; }
	put(c, n, 0, 0x000A); put(c, n, 6, uint16_t(lx)); put(c, n, 7, uint16_t(ly)); n++;

	static const int kinds[] = {0, 1, 2, 4, 5, 6};
	int kind = kinds[rnd(0, 5)];
	unsigned flip = chance(50) ? unsigned(rnd(0, 3)) : 0;
	uint16_t ctrl = uint16_t(kind | (flip << 4));
	int zp = 0;
	if (kind == 1) { static const int zps[] = {0, 5, 6, 7, 9, 10, 11, 13, 14, 15}; zp = zps[rnd(0, 9)]; ctrl |= uint16_t(zp << 8); }

	// PMOD
	unsigned cm = rnd(0, 5);
	unsigned ccb = rnd(0, 7);
	unsigned pmod = ccb | (cm << 3);
	if (chance(35)) pmod |= 0x40; // SPD
	if (chance(35)) pmod |= 0x80; // ECD
	if (chance(25)) pmod |= 0x100; // mesh
	if (chance(35)) pmod |= 0x200; // user clip enable
	if (chance(25)) pmod |= 0x400; // outside clip
	if (chance(15)) pmod |= 0x1000; // HSS
	if (chance(10)) pmod |= 0x8000; // MON
	if (bpp8 && chance(60)) pmod &= ~0x8000; // keep some 8bpp MSB-on cases too
	if (getenv("FZ_ECD")) pmod |= 0x80;
	bool gour = (ccb & 4);
	if (kind >= 4 && kind <= 6) { cm = 5; pmod = (pmod & ~0x38u) | (5u << 3); }
	// polygons/lines take their colour from CMDCOLR; make it random 16-bit
	uint16_t colr = uint16_t(rng());
	if (kind < 3)
	{
		if (cm == 0) colr = uint16_t((rng() & 0xFFF0) | 0);
		if (cm == 1) colr = uint16_t(0x7000 * 2 / 2) & 0xFFF8; // CLUT table address /8 (byte 0xE000)
		if (cm == 1) colr = uint16_t(0xE000 / 8);
	}
	if (chance(30)) colr = uint16_t(colr & 0x7FFF);

	int w8 = rnd(1, 6), h = rnd(1, 40);
	if (chance(30)) { w8 = 1; }
	unsigned srca = 0x8000 / 8 + unsigned(rnd(0, 0x100)); // words 0x4000+ (byte 0x8000+)

	auto coord = [&](int base, int span) { return uint16_t(int16_t(base + rnd(-span, span))); };
	int cx = rnd(-20, 340), cy = rnd(-20, 240);
	put(c, n, 0, ctrl); put(c, n, 2, uint16_t(pmod)); put(c, n, 3, colr);
	put(c, n, 4, uint16_t(srca)); put(c, n, 5, uint16_t((w8 << 8) | h));
	if (gour) put(c, n, 7 + 7, uint16_t(0xF000 / 8)); // CMDGRDA at word 7 (offset 0x0E)
	int sw = rnd(1, 90), sh = rnd(1, 90);
	switch (kind)
	{
	case 0: // normal sprite: A is the top-left
		put(c, n, 6, uint16_t(cx)); put(c, n, 7, uint16_t(cy));
		break;
	case 1: // scaled sprite
		put(c, n, 6, uint16_t(cx)); put(c, n, 7, uint16_t(cy));
		if (zp == 0)
		{
			// two-point form: A upper-left, C lower-right
			put(c, n, 10, uint16_t(cx + rnd(-90, 90))); put(c, n, 11, uint16_t(cy + rnd(-90, 90)));
		}
		else
		{
			// zoom-point form: B holds the display width and height
			put(c, n, 8, uint16_t(sw)); put(c, n, 9, uint16_t(sh));
		}
		break;
	default: // quads / lines
		put(c, n, 6, uint16_t(cx)); put(c, n, 7, uint16_t(cy));
		put(c, n, 8, uint16_t(cx + rnd(-60, 100))); put(c, n, 9, uint16_t(cy + rnd(-60, 60)));
		put(c, n, 10, uint16_t(cx + rnd(-60, 100))); put(c, n, 11, uint16_t(cy + rnd(-60, 100)));
		put(c, n, 12, uint16_t(cx + rnd(-60, 60))); put(c, n, 13, uint16_t(cy + rnd(-60, 100)));
		if (kind == 6) { /* line uses A,B only; C,D ignored */ }
		break;
	}
	n++;
	// end
	put(c, n, 0, 0x8000);

	snprintf(buf, sizeof buf,
	         "kind=%d ctrl=%04x pmod=%04x colr=%04x srca=%04x size=%04x tvmr=%d sclip=(%d,%d) uclip=(%d,%d)-(%d,%d) local=(%d,%d) zp=%d",
	         kind, ctrl, pmod, colr, srca, (w8 << 8) | h, c.tvmr, sx2, sy2, ux1, uy1, ux2, uy2, lx, ly, zp);
	c.desc = buf;
	return c;
}

int main(int argc, char **argv)
{
	if (argc < 5) { fprintf(stderr, "usage: vdp1fuzz seed count prefix\n"); return 1; }
	unsigned const seed = unsigned(atoi(argv[1]));
	int const first = atoi(argv[2]);
	int const count = atoi(argv[3]);
	std::string prefix = argv[4];

	ymir::core::Scheduler scheduler{};
	ymir::core::Configuration config{};
	config.swRenderer.threadedVDP1 = false;
	config.swRenderer.threadedVDP2 = false;
	config.swRenderer.threadedDeinterlacer = false;
	config.system.videoStandard = ymir::core::config::sys::VideoStandard::NTSC;
	auto vdp = std::make_unique<ymir::vdp::VDP>(scheduler, config);
	int frames = 0;
	vdp->SetSoftwareRenderCallback({&frames, [](uint32_t *, uint32_t, uint32_t, void *c) { ++*static_cast<int *>(c); }});
	static int draws = 0;
	vdp->GetRenderer().Callbacks.VDP1DrawFinished = {nullptr, [](void *) { ++draws; }};
	vdp->Reset(true);
	static ymir::sys::SH2Bus bus;
	vdp->MapMemory(bus);

	auto run_frames = [&](int n) {
		int target = frames + n;
		uint64_t g = 0;
		while (frames < target && g++ < 6000 * (uint64_t)n)
		{
			uint64_t cycles = scheduler.NextCount();
			vdp->Advance(cycles);
			scheduler.Advance(cycles);
		}
	};

	FILE *fc = fopen((prefix + "_cases.bin").c_str(), "wb");
	FILE *fy = fopen((prefix + "_ymir.bin").c_str(), "wb");
	FILE *fd = fopen((prefix + "_desc.txt").c_str(), "w");
	for (int i = first; i < first + count; i++)
	{
		rng.seed(seed * 1000003u + unsigned(i));
		Case c = make_case(); if (getenv("FZ_RESET")) vdp->Reset(true);
		fprintf(fd, "%d %s\n", i, c.desc.c_str()); fflush(fd);
		// VRAM image
		for (unsigned w = 0; w < c.vram.size(); w++)
		{
			bus.Write<uint16_t>(0x5C00000 + w * 2, c.vram[w]);
			uint16_t be = uint16_t((c.vram[w] >> 8) | (c.vram[w] << 8));
			fwrite(&be, 2, 1, fc);
		}
		uint16_t tail[2] = {c.tvmr, 0};
		fwrite(tail, 2, 2, fc);
		fflush(fc);

		// erase both frame buffers with the erase-write registers, then draw
		bus.Write<uint16_t>(0x5D00000, c.tvmr);
		bus.Write<uint16_t>(0x5D00006, 0x0000); // EWDR
		bus.Write<uint16_t>(0x5D00008, 0x0000); // EWLR
		bus.Write<uint16_t>(0x5D0000A, 0x50DF); // EWRR: full 512x256 (X=0x50*8, Y=0xDF)
		bus.Write<uint16_t>(0x5D00002, 0x0003);
		fprintf(stderr,"c%d erase\n",i);run_frames(3);fprintf(stderr,"erased\n");
		draws = 0;
		bus.Write<uint16_t>(0x5D00004, 0x0001);
		int guard = 0;
		while (draws == 0 && guard++ < 40) run_frames(1);
		if (guard > 10) fprintf(stderr, "case %d slow draw guard=%d\n", i, guard);
		bus.Write<uint16_t>(0x5D00002, 0x0003);
		fprintf(stderr,"swap\n");run_frames(3);fprintf(stderr,"done\n");
		auto fb = vdp->VDP1GetDisplayFramebuffer();
		fwrite(fb.data(), 1, 0x40000, fy);
	}
	fclose(fc); fclose(fy); fclose(fd);
	return 0;
}
