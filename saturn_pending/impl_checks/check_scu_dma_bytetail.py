#!/usr/bin/env python3
"""Method-level extraction check for the SCU DMA byte-unit head/tail rule.

Extracts dma_read_word / dma_read_byte / dma_transfer_direct_default /
dma_transfer_direct_cbus_write from src/mame/sega/saturn_scu.cpp into a
standalone harness with a fake big-endian host space, and checks against a
reference byte-stream model:

  1. every transfer of size 1..17 from source offsets 0..5 to destination
     offsets 0..5 moves exactly `size` source bytes in stream order,
  2. the bytes before and after the destination region are untouched,
  3. even/aligned transfers produce the same memory as word-unit writes,
  4. fixed-destination (dst_add=0) transfers keep overwriting one address.

Method-level, unvalidated: this does not build or run MAME and is not
acceptance evidence.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/mame/sega/saturn_scu.cpp"
text = SRC.read_text()


def grab(name: str, kind: str = r"\w+") -> str:
    m = re.search(
        r"^(?:inline )?" + kind + r" saturn_scu_device::" + name
        + r"\(([^)]*)\)[^\n{]*\n?\{.*?^\}",
        text,
        re.M | re.S,
    )
    if not m:
        raise SystemExit(f"function {name} not found")
    body = m.group(0)
    body = body[body.index("{"):]
    return f"{kind} {name}({m.group(1)})\n" + body


HEAD = r"""
#include <cstdint>
#include <cstdio>
#include <cstring>
using u8 = std::uint8_t;
using u16 = std::uint16_t;
using u32 = std::uint32_t;
using u64 = std::uint64_t;
static int g_fail = 0;
#define CHECK(expr) do { if (!(expr)) { std::printf("FAIL %d: %s\n", __LINE__, #expr); ++g_fail; } } while (0)

// fake big-endian host space, 8 MiB, write-guarded
struct space_t
{
    static constexpr u32 SIZE = 0x800000;
    u8 mem[SIZE] = {0};
    u8 guard[SIZE] = {0}; // 1 = written at least once
    u32 rd = 0, wr = 0;   // access counters
    u32 mask(u32 a) const { return a & 0x07ffffff & (SIZE - 1); }
    u32 read_dword(u32 a) { ++rd; a = mask(a); return (u32(mem[a]) << 24) | (u32(mem[a+1]) << 16) | (u32(mem[a+2]) << 8) | mem[a+3]; }
    void write_word(u32 a, u16 d) { ++wr; a = mask(a); mem[a] = d >> 8; mem[a+1] = d & 0xff; guard[a] = guard[a+1] = 1; }
    void write_byte(u32 a, u8 d) { ++wr; a = mask(a); mem[a] = d; guard[a] = 1; }
};

struct saturn_scu_device
{
    space_t *m_hostspace = nullptr;
    struct dma_channel_t
    {
        u32 live_src = 0, live_dst = 0, live_size = 0, live_count = 0;
        u32 src_add = 4, dst_add = 2;
        u32 read_buffer = 0, read_address = 0;
        u8 read_offset = 0;
        bool read_buffer_valid = false;
    } ch;

    // ==== extracted production code ====
"""

TAIL = r"""
    // ==== end extracted production code ====
};

static space_t space;
static saturn_scu_device dev;

static void run_transfer(u32 src, u32 dst, u32 size, u32 dst_add, bool cbus_mode)
{
    space = space_t{}; // zero all
    // source pattern: mem[i] = (i * 7 + 3) & 0xff
    for (u32 i = 0; space_t::SIZE > i; ++i)
        space.mem[i] = u8((i * 7 + 3) & 0xff);
    auto &ch = dev.ch;
    ch = saturn_scu_device::dma_channel_t{};
    ch.live_src = src;
    ch.live_dst = dst;
    ch.live_size = size;
    ch.live_count = 0;
    ch.src_add = 4;
    ch.dst_add = dst_add;
    u64 budget = 4096;
    while (ch.live_count < ch.live_size && budget--)
    {
        if (cbus_mode)
            dev.dma_transfer_direct_cbus_write(ch);
        else
            dev.dma_transfer_direct_default(ch);
    }
    CHECK(ch.live_count == size);
    CHECK(budget != 0);
}

int main()
{
    dev.m_hostspace = &space;
    const u32 SRC_BASE = 0x06000000, DST_BASE = 0x00200000;

    // 1+2. reference byte-stream model over size/offset sweep
    for (u32 size = 1; 17 >= size; ++size)
    {
        for (u32 soff = 0; 5 >= soff; ++soff)
        {
            for (u32 doff = 0; 5 >= doff; ++doff)
            {
                for (int cbus = 0; 2 > cbus; ++cbus)
                {
                    run_transfer(SRC_BASE + soff, DST_BASE + doff, size, 2, cbus != 0);
                    u8 const *m = space.mem;
                    for (u32 i = 0; size > i; ++i)
                    {
                        u8 expect = u8(((SRC_BASE + soff + i) * 7 + 3) & 0xff);
                        if (m[DST_BASE + doff + i] != expect)
                        {
                            std::printf("FAIL stream size=%u soff=%u doff=%u cbus=%d i=%u got %02x want %02x\n",
                                        size, soff, doff, cbus, i, m[DST_BASE + doff + i], expect);
                            ++g_fail;
                        }
                    }
                    if (space.guard[DST_BASE + doff - 1])
                    {
                        std::printf("FAIL pre-guard written size=%u doff=%u cbus=%d\n", size, doff, cbus);
                        ++g_fail;
                    }
                    if (space.guard[DST_BASE + doff + size])
                    {
                        std::printf("FAIL post-guard written size=%u doff=%u cbus=%d\n", size, doff, cbus);
                        ++g_fail;
                    }
                }
            }
        }
    }
    if (!g_fail)
        std::printf("sweep 1: 6x6x17x2 byte-stream cases passed\n");

    // 3. even/aligned path stays word-based: 16 bytes in 8 word writes
    {
        run_transfer(SRC_BASE, DST_BASE, 16, 2, false);
        u8 expect[16];
        for (u32 i = 0; 16 > i; ++i)
            expect[i] = u8(((SRC_BASE + i) * 7 + 3) & 0xff);
        CHECK(std::memcmp(&space.mem[DST_BASE], expect, 16) == 0);
        CHECK(space.wr == 8);
        std::printf("sweep 2: aligned 16-byte case passed (8 word writes)\n");
    }

    // 4. fixed destination (dst_add=0): every unit overwrites the same word
    {
        run_transfer(SRC_BASE, DST_BASE + 4, 6, 0, false);
        u8 b4 = u8(((SRC_BASE + 4) * 7 + 3) & 0xff);
        u8 b5 = u8(((SRC_BASE + 5) * 7 + 3) & 0xff);
        CHECK(space.mem[DST_BASE + 4] == b4 && space.mem[DST_BASE + 5] == b5);
        std::printf("sweep 3: fixed-destination case passed\n");
    }

    if (g_fail)
    {
        std::printf("FAILED %d checks\n", g_fail);
        return 1;
    }
    std::printf("all checks passed\n");
    return 0;
}
"""

extracted = "\n".join(
    grab(name, kind).replace("saturn_scu_device::", "")
    for name, kind in (
        ("dma_read_word", "uint16_t"),
        ("dma_read_byte", "uint8_t"),
        ("dma_transfer_direct_default", "void"),
        ("dma_transfer_direct_cbus_write", "void"),
    )
)

harness = HEAD + extracted + TAIL
srcpath = "/tmp/impl_scudma_check.cpp"
binpath = "/tmp/impl_scudma_check"
Path(srcpath).write_text(harness)
r = subprocess.run(["g++", "-std=c++20", "-g", "-o", binpath, srcpath], capture_output=True, text=True)
if r.returncode:
    print(r.stderr)
    sys.exit("harness compile failed")
r = subprocess.run([binpath], capture_output=True, text=True)
print(r.stdout, end="")
print(r.stderr, end="")
sys.exit(r.returncode)
