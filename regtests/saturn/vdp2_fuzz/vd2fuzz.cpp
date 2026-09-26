// vd2fuzz
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
#include <fstream>
#include <map>
#include <string>
#include <vector>

struct Rec { uint32_t elem; std::vector<uint8_t> data; };

static uint32_t be32(const uint8_t *p) { return (uint32_t(p[0]) << 24) | (uint32_t(p[1]) << 16) | (uint32_t(p[2]) << 8) | p[3]; }

static std::map<std::string, Rec> load(const char *path)
{
	std::ifstream in(path, std::ios::binary);
	std::vector<uint8_t> all((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
	std::map<std::string, Rec> m;
	size_t p = 15;
	while (p + 4 <= all.size())
	{
		uint32_t nl = be32(&all[p]); p += 4;
		std::string name((char *)&all[p], nl); p += nl;
		uint32_t el = be32(&all[p]); p += 4;
		uint32_t len = be32(&all[p]); p += 4;
		m[name] = Rec{el, std::vector<uint8_t>(all.begin() + p, all.begin() + p + len)};
		p += len;
	}
	return m;
}

static void write_ppm(const std::string &path, const std::vector<uint32_t> &px, uint32_t w, uint32_t h, bool bgr)
{
	FILE *f = fopen(path.c_str(), "wb");
	fprintf(f, "P6\n%u %u\n255\n", w, h);
	for (uint32_t i = 0; i < w * h; i++)
	{
		uint32_t c = px[i];
		unsigned char rgb[3];
		if (bgr) { rgb[0] = c & 0xff; rgb[1] = (c >> 8) & 0xff; rgb[2] = (c >> 16) & 0xff; }
		else { rgb[0] = (c >> 16) & 0xff; rgb[1] = (c >> 8) & 0xff; rgb[2] = c & 0xff; }
		fwrite(rgb, 1, 3, f);
	}
	fclose(f);
}

// host-order uint32 words holding big-endian memory words -> big-endian bytes
static void words32_to_be(const std::vector<uint8_t> &src, uint8_t *dst, size_t bytes)
{
	for (size_t i = 0; i + 4 <= bytes && i + 4 <= src.size(); i += 4)
	{
		uint32_t v; memcpy(&v, &src[i], 4);
		dst[i] = v >> 24; dst[i + 1] = v >> 16; dst[i + 2] = v >> 8; dst[i + 3] = v;
	}
}
static void words16_to_be(const std::vector<uint8_t> &src, uint8_t *dst, size_t bytes)
{
	for (size_t i = 0; i + 2 <= bytes && i + 2 <= src.size(); i += 2)
	{
		uint16_t v; memcpy(&v, &src[i], 2);
		dst[i] = v >> 8; dst[i + 1] = v;
	}
}


// vd2fuzz <capture.bin> <mutations.txt> <out.bin> : for every mutation line ("idx=val idx=val ...", VDP2 register
// word indices) load the capture into a fresh Ymir VDP, apply the register overrides, run frames and append
// u32 w, u32 h, w*h u32 pixels (Ymir's 0xAABBGGRR) to <out.bin>.
int main(int argc, char **argv)
{
	if (argc < 4) { fprintf(stderr, "usage: vd2fuzz capture mut out\n"); return 1; }
	auto cap = load(argv[1]);
	std::ifstream mf(argv[2]);
	FILE *out = fopen(argv[3], "wb");
	std::string line;
	while (std::getline(mf, line))
	{
		std::vector<std::pair<int, uint16_t>> muts;
		{
			size_t p = 0;
			while (p < line.size())
			{
				int idx, val;
				if (sscanf(line.c_str() + p, "%d=%d", &idx, &val) == 2) muts.push_back({idx, uint16_t(val)});
				size_t sp = line.find(' ', p);
				if (sp == std::string::npos) break;
				p = sp + 1;
			}
		}
		ymir::core::Scheduler scheduler{};
		ymir::core::Configuration config{};
		config.swRenderer.threadedVDP1 = false;
		config.swRenderer.threadedVDP2 = false;
		config.swRenderer.threadedDeinterlacer = false;
		config.system.videoStandard = ymir::core::config::sys::VideoStandard::NTSC;
		auto vdp = std::make_unique<ymir::vdp::VDP>(scheduler, config);
		std::vector<uint32_t> px;
		uint32_t ow = 0, oh = 0;
		int frames = 0;
		struct Ctx { std::vector<uint32_t> *out; uint32_t *w, *h; int *frames; } ctx{&px, &ow, &oh, &frames};
		vdp->SetSoftwareRenderCallback({&ctx, [](uint32_t *fb, uint32_t w, uint32_t h, void *c) {
			auto *x = static_cast<Ctx *>(c);
			x->out->assign(fb, fb + w * h); *x->w = w; *x->h = h; (*x->frames)++;
		}});
		vdp->Reset(true);
		auto busp = std::make_unique<ymir::sys::SH2Bus>(); auto &bus = *busp;
		vdp->MapMemory(bus);
		{
			auto &vr = cap["m_vdp2_vram"].data;
			for (uint32_t i = 0; i + 4 <= vr.size() && i < 0x80000; i += 4)
			{
				uint32_t v; memcpy(&v, &vr[i], 4);
				bus.Write<uint16_t>(0x5E00000 + i, uint16_t(v >> 16));
				bus.Write<uint16_t>(0x5E00000 + i + 2, uint16_t(v));
			}
		}
		std::vector<uint16_t> regs(0x100, 0);
		{
			auto &r2 = cap["m_vdp2_regs"].data;
			for (uint32_t i = 0; i * 2 + 2 <= r2.size() && i < 0x100; i++) memcpy(&regs[i], &r2[i * 2], 2);
			auto rd = [&](const char *n) -> uint32_t { auto it = cap.find(n); if (it == cap.end()) return 0; uint32_t v = 0; memcpy(&v, it->second.data.data(), std::min<size_t>(4, it->second.data.size())); return v; };
			regs[0] = uint16_t(rd("vdp2.m_tvmd"));
			regs[1] = uint16_t(rd("vdp2.m_exten"));
			regs[3] = uint16_t((rd("vdp2.m_vramsz") & 1) << 15);
		}
		for (unsigned i = 0; i < 0x100; i++) bus.Write<uint16_t>(0x5F80000 + i * 2, regs[i]);
		{
			auto &cr = cap["m_vdp2_cram"].data;
			for (uint32_t i = 0; i + 4 <= cr.size() && i < 0x1000; i += 4)
			{
				uint32_t v; memcpy(&v, &cr[i], 4);
				bus.Write<uint16_t>(0x5F00000 + i, uint16_t(v >> 16));
				bus.Write<uint16_t>(0x5F00000 + i + 2, uint16_t(v));
			}
		}
		for (auto &m : muts) regs[m.first] = m.second;
		for (unsigned i = 0; i < 0x100; i++) bus.Write<uint16_t>(0x5F80000 + i * 2, regs[i]);
		int guard = 0;
		while (frames < 8 && guard++ < 4000000)
		{
			uint64_t cycles = scheduler.NextCount();
			vdp->Advance(cycles);
			scheduler.Advance(cycles);
		}
		uint32_t hdr[2] = {ow, oh};
		fwrite(hdr, 4, 2, out);
		fwrite(px.data(), 4, px.size(), out);
		fflush(out);
	}
	fclose(out);
	return 0;
}
