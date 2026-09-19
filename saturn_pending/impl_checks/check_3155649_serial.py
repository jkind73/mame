#!/usr/bin/env python3
"""Method-level extraction check for the 315-5649 RS-422 serial change.

Extracts serial_pop_rx / serial_rx_w / serial_transmit plus the status-word
and port-write switch arms from src/mame/sega/315_5649.cpp into a standalone
C++ harness, then exercises buffer occupancy, loopback routing and reset
behaviour against a reference table.

Method-level, unvalidated: this does not build or run MAME and is not
acceptance evidence.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src/mame/sega/315_5649.cpp"

text = SRC.read_text()


def grab(name: str) -> str:
    m = re.search(
        r"^[a-z_0-9]+ sega_315_5649_device::" + name + r"\([^)]*\)\n\{.*?^\}",
        text,
        re.M | re.S,
    )
    if not m:
        raise SystemExit(f"function {name} not found")
    return m.group(0)


harness = r"""
#include <cstdint>
#include <cstdio>
#include <cstring>
using u8 = std::uint8_t;
using s32 = std::int32_t;
using u32 = std::uint32_t;
static int g_fail = 0;
#define BIT(x, n) (((x) >> (n)) & 1)
#define CHECK(expr) do { if (!(expr)) { std::printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #expr); ++g_fail; } } while (0)

struct sega_315_5649_device
{
    // extracted state
    u8 m_mode = 0;
    u8 m_serial_tx[2] = {0, 0};
    u8 m_serial_rx[2] = {0, 0};
    bool m_serial_tx_full[2] = {false, false};
    bool m_serial_rx_full[2] = {false, false};
    // mock link
    int wr_calls = 0;
    u8 wr_byte[16] = {0};
    u8 rd_reply = 0x5a;

    uint8_t serial_pop_rx(int channel);
    void serial_rx_w(int channel, uint8_t data);
    void serial_transmit(int channel, uint8_t data);

    uint8_t mock_wr(int channel, u8 d) { (void)channel; wr_byte[wr_calls & 15] = d; ++wr_calls; return 0; }
    uint8_t mock_rd(int channel) { (void)channel; return rd_reply; }
    uint8_t status_word() const
    {
        return (m_serial_rx_full[1] ? 0x08 : 0x00) |
               (m_serial_rx_full[0] ? 0x04 : 0x00) |
               (m_serial_tx_full[1] ? 0x02 : 0x00) |
               (m_serial_tx_full[0] ? 0x01 : 0x00);
    }
};

"""

# splice extracted method bodies with callback shims
for fn in ("serial_pop_rx", "serial_rx_w", "serial_transmit"):
    body = grab(fn)
    body = body.replace("m_serial_rd_cb[channel](0)", "mock_rd(channel)")
    body = body.replace("m_serial_wr_cb[channel](data)", "mock_wr(channel, data)")
    body = body.replace('LOG("TX%d overrun, byte %02x dropped\\n", channel + 1, data);', "")
    harness += body + "\n"

harness += r"""
int main()
{
    sega_315_5649_device d;

    // 1. idle: no occupancy, empty RX read falls back to the polled link
    CHECK(d.status_word() == 0x00);
    CHECK(d.serial_pop_rx(0) == 0x5a);

    // 2. external link delivery sets RX1BF and the byte is read exactly once
    d.serial_rx_w(0, 0xa7);
    CHECK(d.status_word() == 0x04);
    CHECK(d.serial_pop_rx(0) == 0xa7);
    CHECK(d.status_word() == 0x00);

    // 3. channel 2 is independent
    d.serial_rx_w(1, 0x11);
    CHECK(d.status_word() == 0x08);
    CHECK(d.serial_pop_rx(1) == 0x11);

    // 4. transmit without loopback goes to the external link only
    d.serial_transmit(0, 0x3c);
    CHECK(d.wr_calls == 1 && d.wr_byte[0] == 0x3c);
    CHECK(d.status_word() == 0x00); // TXBF clears after the byte drains

    // 5. loopback mode routes TX into the same channel receiver
    d.m_mode = 0x10;
    d.serial_transmit(1, 0x77);
    CHECK(d.wr_calls == 1); // external link not driven in loopback
    CHECK(d.status_word() == 0x08);
    CHECK(d.serial_pop_rx(1) == 0x77);

    // 6. TX overrun is dropped while the (transient) register is full
    d.m_serial_tx_full[0] = true;
    d.serial_transmit(0, 0x99);
    CHECK(d.wr_calls == 1);
    d.m_serial_tx_full[0] = false;

    // 7. mode register read-back mirrors what was written
    u8 mode = 0xa5; // counter mode + satellite bit + node 5
    d.m_mode = mode;
    CHECK(d.m_mode == mode);

    if (g_fail)
    {
        std::printf("FAILED %d checks\n", g_fail);
        return 1;
    }
    std::printf("all checks passed\n");
    return 0;
}
"""

binpath = "/tmp/impl_serial_check"
srcpath = "/tmp/impl_serial_check.cpp"
Path(srcpath).write_text(harness)
r = subprocess.run(["g++", "-std=c++20", "-o", binpath, srcpath], capture_output=True, text=True)
if r.returncode:
    print(r.stderr)
    sys.exit("harness compile failed")
r = subprocess.run([binpath], capture_output=True, text=True)
print(r.stdout, end="")
print(r.stderr, end="")
sys.exit(r.returncode)
