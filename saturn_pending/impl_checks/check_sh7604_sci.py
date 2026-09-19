#!/usr/bin/env python3
"""Method-level extraction check for the SH7604 SCI transfer engine.

Extracts the SCI register write paths and the TX/RX shift engines from
src/devices/cpu/sh/sh7604.cpp into a standalone C++ harness driven by a
virtual clock, then checks:

  1. an 8N1 frame for 0x55 emits start+LSB-first data+stop at the
     documented bit period (N+1)*2^7 phi ticks for CKS=0 (Tables 13.3/13.6),
  2. TDRE write-0 triggers the TDR->TSR load and re-sets TDRE (p.372),
  3. a full TX->RX round trip at 16x oversampling delivers the byte and
     sets RDRF,
  4. SSR write-0-to-clear flag semantics and TE=0 locking,
  5. the bit-period formulas for both clock sources.

Method-level, unvalidated: this does not build or run MAME and is not
acceptance evidence.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/devices/cpu/sh/sh7604.cpp"
text = SRC.read_text()


def grab(name: str, kind: str = r"\w+") -> str:
    m = re.search(
        r"^" + kind + r" sh7604_device::" + name + r"\(([^)]*)\)[^\n{]*\n?\{.*?^\}",
        text,
        re.M | re.S,
    )
    if not m:
        raise SystemExit(f"function {name} not found")
    return f"{kind} {name}({m.group(1)})\n" + m.group(0)[m.group(0).index("{"):]


def grab_cb(name: str) -> str:
    m = re.search(
        r"^TIMER_CALLBACK_MEMBER\(sh7604_device::" + name + r"\)\n\{.*?^\}",
        text,
        re.M | re.S,
    )
    if not m:
        raise SystemExit(f"callback {name} not found")
    return f"void {name}(s32 param)\n" + m.group(0)[m.group(0).index("{"):]


extracted = "\n".join(
    grab(fn, kind).replace("sh7604_device::", "")
    for fn, kind in (
        ("smr_w", "void"), ("brr_w", "void"), ("scr_w", "void"), ("tdr_w", "void"),
        ("ssr_w", "void"), ("ssr_r", "uint8_t"), ("rdr_r", "uint8_t"), ("tdr_r", "uint8_t"),
        ("sci_bit_period", "attotime"), ("sci_recalc_rates", "void"),
        ("sci_transmit_start", "void"), ("sci_rx_complete", "void"),
    )
) + "\n" + "\n".join(
    grab_cb(cb).replace("sh7604_device::", "") for cb in ("sci_tx_tick", "sci_rx_tick")
)

HEAD = r"""
#include <bit>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
using u8 = std::uint8_t;
using s32 = std::int32_t;
using u32 = std::uint32_t;
using u64 = std::uint64_t;
static int g_fail = 0;
#define CHECK(expr) do { if (!(expr)) { std::printf("FAIL %d: %s\n", __LINE__, #expr); ++g_fail; } } while (0)
#define BIT(x, n) (((x) >> (n)) & 1)
static u64 g_now = 0;
static u64 bitns = 0;
static const u32 PHI = 28636363;
struct attotime
{
    u64 t = 0;
    static const attotime never;
    static attotime from_ticks(u64 ticks, u32 hz) { return attotime{ticks * 1000000000ull / hz}; }
    attotime operator/(unsigned d) const { return attotime{t / d}; }
};
const attotime attotime::never{~0ull};
struct emu_timer
{
    u64 due = ~0ull; s32 param = 0;
    void adjust(attotime p, s32 par = -1) { due = g_now + p.t; param = par; }
    void cancel() { due = ~0ull; }
};

struct sh7604_device
{
    u8 m_smr = 0, m_brr = 0xff, m_scr = 0, m_tdr = 0xff, m_ssr = 0x84;
    u8 m_rdr = 0, m_tsr = 0, m_rsr = 0;
    u8 m_sci_tx_bit = 0;
    bool m_sci_tx_active = false, m_sci_rx_enabled = false;
    u8 m_sci_rx_state = 0, m_sci_rx_shift = 0, m_sci_rx_bitcnt = 0;
    u8 m_sci_rx_phase = 0, m_sci_rx_vote = 0;
    emu_timer *m_sci_tx_timer = new emu_timer;
    emu_timer *m_sci_rx_timer = new emu_timer;
    u64 tx_time[512]; int tx_bit[512]; int tx_count = 0; int tx_edges = 0; int tx_last = 1;
    u32 clock() const { return PHI; }
    void m_write_txd(int bit)
    {
        if (bit != tx_last) ++tx_edges;
        tx_last = bit;
        tx_time[tx_count & 511] = g_now; tx_bit[tx_count & 511] = bit; ++tx_count;
    }
    int m_read_rxd(int) const
    {
        int bit = 1;
        for (int i = 0; tx_count > i; ++i)
            if (tx_time[i & 511] <= g_now) bit = tx_bit[i & 511];
        return bit;
    }
    void sh2_recalc_irq() {}
    static constexpr u8 SSR_TDRE = 0x80, SSR_RDRF = 0x40, SSR_ORER = 0x20,
        SSR_FER = 0x10, SSR_PER = 0x08, SSR_TEND = 0x04, SSR_MPB = 0x02;

    // ==== extracted production code ====
"""

TAIL = r"""
    // ==== end extracted production code ====
};

static sh7604_device d;

static void run_until(u64 ns)
{
    for (;;)
    {
        u64 t1 = d.m_sci_tx_timer->due, t2 = d.m_sci_rx_timer->due;
        u64 next = t1 < t2 ? t1 : t2;
        if (next > ns || next == ~0ull) { g_now = ns; return; }
        g_now = next;
        if (t1 <= t2)
        {
            d.m_sci_tx_timer->due = ~0ull;
            if (getenv("SCI_DEBUG"))
                std::printf("TX t=%-5lld param=%d\n", (long long)(g_now * 16 / bitns), d.m_sci_tx_timer->param);
            d.sci_tx_tick(d.m_sci_tx_timer->param);
        }
        else
        {
            d.m_sci_rx_timer->due = ~0ull;
            if (getenv("SCI_DEBUG"))
                std::printf("RX t=%-5lld phase=%d bitcnt=%d line=%d state=%d\n",
                            (long long)(g_now * 16 / bitns), d.m_sci_rx_phase,
                            d.m_sci_rx_bitcnt, d.m_read_rxd(0), d.m_sci_rx_state);
            d.sci_rx_tick(d.m_sci_rx_timer->param);
        }
    }
}

int main()
{
    bitns = (u64)(12 + 1) * 128 * 1000000000ull / PHI; // BRR=12 CKS=0

    // --- 1. 8N1 frame for 0x55: start 0, data 1,0,1,0,1,0,1,0, stop 1 ---
    d.smr_w(0x00);
    d.brr_w(12);
    d.scr_w(0x20); // TE=1, internal clock
    CHECK((d.ssr_r() & 0x84) == 0x84); // TDRE|TEND idle
    d.tdr_w(0x55);
    d.ssr_w(0x7f); // clear TDRE: hardware loads TDR->TSR and starts the frame
    CHECK(d.ssr_r() & 0x80); // TDRE set again after the load (p.372 step 2)
    run_until(bitns * 10 + bitns / 2);
    CHECK(d.tx_edges == 10);
    int expect[10] = {0, 1, 0, 1, 0, 1, 0, 1, 0, 1};
    for (int i = 0; 10 > i; ++i)
        CHECK(d.tx_bit[i] == expect[i]);
    CHECK(d.tx_time[1] - d.tx_time[0] == bitns);
    CHECK(d.tx_time[9] - d.tx_time[0] == bitns * 9);
    CHECK(d.ssr_r() & 0x04); // TEND: nothing chained

    // --- 2. TX -> RX round trip (RE=1 starts the 16x oversample receiver) ---
    u64 start = g_now;
    d.scr_w(0x30);
    d.tdr_w(0xa7); // 10100111
    d.ssr_w(0x7f);
    run_until(start + bitns * 12);
    CHECK(d.tx_edges == 16);
    CHECK(d.ssr_r() & 0x40);  // RDRF
    CHECK(d.rdr_r() == 0xa7);
    CHECK(!(d.ssr_r() & 0x18)); // no FER/PER
    if (getenv("SCI_DEBUG"))
        std::printf("after roundtrip: ssr=%02x rdr=%02x tx_count=%d rx_state=%d bitcnt=%d phase=%d\n",
                    d.ssr_r(), d.rdr_r(), d.tx_count, d.m_sci_rx_state,
                    d.m_sci_rx_bitcnt, d.m_sci_rx_phase);

    // --- 3. SSR write-0-to-clear (TE off, so no transfer can restart) ---
    d.scr_w(0x00);
    CHECK((d.ssr_r() & 0x84) == 0x84); // TE=0 locks TDRE and sets TEND
    d.ssr_w((unsigned)~0x40 & 0xff);
    CHECK(!(d.ssr_r() & 0x40));
    d.ssr_w(0x01); // MPBT store; write-0 to TDRE with TE=0 starts nothing
    CHECK((d.ssr_r() & 0x01) == 0x01);

    // --- 4. TE=0: TDR write + TDRE clear emit no frame ---
    d.tdr_w(0x5a);
    d.ssr_w(0x7f);
    CHECK(d.ssr_r() & 0x80);
    CHECK(d.tx_edges == 16);

    // --- 5. bit period formulas: async CKS=2 => (N+1)*2^11, sync CKS=1 => (N+1)*2^6 ---
    d.smr_w(0x02);
    CHECK(d.sci_bit_period().t == (u64)(12 + 1) * 2048 * 1000000000ull / PHI);
    d.smr_w(0x82);
    CHECK(d.sci_bit_period().t == (u64)(12 + 1) * 256 * 1000000000ull / PHI); // 0x82: C/A=1, CKS=2
    d.smr_w(0x00);

    if (g_fail)
    {
        std::printf("FAILED %d checks\n", g_fail);
        return 1;
    }
    std::printf("all checks passed\n");
    return 0;
}
"""

harness = HEAD + extracted + TAIL
srcpath = "/tmp/impl_sci_check.cpp"
binpath = "/tmp/impl_sci_check"
Path(srcpath).write_text(harness)
r = subprocess.run(["g++", "-std=c++20", "-o", binpath, srcpath], capture_output=True, text=True)
if r.returncode:
    print(r.stderr)
    sys.exit("harness compile failed")
r = subprocess.run([binpath], capture_output=True, text=True)
print(r.stdout, end="")
print(r.stderr, end="")
sys.exit(r.returncode)
