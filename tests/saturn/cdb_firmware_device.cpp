// license:BSD-3-Clause
// Isolated enabled CD block: main CPU only supplies the host register window.
#include "emu.h"

#include "../sega/saturn_cdb.h"
#include "../sega/saturn_scu.h"
#include "cpu/scudsp/scudsp.h"
#include "cpu/sh/sh7604.h"
#include "sound/cdda.h"
#include "speaker.h"
namespace
{
class cdbdiag_state : public driver_device
{
  public:
	cdbdiag_state(const machine_config &c, device_type t, const char *n)
		: driver_device(c, t, n), m_cdrom(*this, "cdrom"), m_cdb(*this, "cdb"), m_scu(*this, "scu")
	{
	}
	void config(machine_config &config)
	{
		sh7604_device &host(SH7604(config, "maincpu", 28636363));
		host.set_addrmap(AS_PROGRAM, &cdbdiag_state::map);
		sh7604_device &slave(SH7604(config, "slave", 28636363));
		slave.set_addrmap(AS_PROGRAM, &cdbdiag_state::map);
		SATURN_SCU(config, m_scu, 57272727);
		m_scu->set_hostcpu("^maincpu");
		SATURN_CDB(config, m_cdb, 20000000);
		m_cdb->set_lle(true);
		m_cdb->set_host_wait_callback(
			[&host, &slave](bool on)
			{
				host.set_bus_wait_active(on);
				slave.set_bus_wait_active(on);
			});
		m_cdb->set_host_notify_callback(
			[&host, &slave]()
			{
				host.sh2_notify_dma_data_available();
				slave.sh2_notify_dma_data_available();
			});
		host.set_bus_ready_callback(NAME([this](u32 a, unsigned size, bool write)
										 { return m_scu->cpu_bus_ready(a) && m_cdb->host_bus_ready(a, size, write); }));
		slave.set_bus_ready_callback(
			NAME([this](u32 a, unsigned size, bool write)
				 { return m_scu->cpu_bus_ready(a) && m_cdb->host_bus_ready(a, size, write); }));
		host.set_dma_fifo_data_available_callback(NAME(
			[this](u32 src, u32 dst, u32 data, int size)
			{
				unsigned const bytes = size == 3 ? 4 : 1U << size;
				return m_cdb->host_bus_ready(src, bytes, false) && m_cdb->host_bus_ready(dst, bytes, true);
			}));
		slave.set_dma_fifo_data_available_callback(NAME(
			[this](u32 src, u32 dst, u32 data, int size)
			{
				unsigned const bytes = size == 3 ? 4 : 1U << size;
				return m_cdb->host_bus_ready(src, bytes, false) && m_cdb->host_bus_ready(dst, bytes, true);
			}));
		m_scu->set_host_ready_callback([this](u32 a, unsigned size, bool write)
									   { return m_cdb->host_bus_ready(a, size, write); });
		CDROM(config, "cdrom").set_interface("cdrom");
		m_cdb->set_cdrom_tag("^cdrom");
		SPEAKER(config, "lspeaker").front_left();
		SPEAKER(config, "rspeaker").front_right();
		cdda_device &audio(CDDA(config, "cdda"));
		audio.set_cdrom_tag("cdrom");
		audio.add_route(0, "lspeaker", 1.0);
		audio.add_route(1, "rspeaker", 1.0);
		m_cdb->set_cdda_tag("^cdda");
	}

  protected:
	void machine_reset() override
	{
		m_reference.fill(0);
		if (m_cdrom->exists())
		{
			unsigned type = m_cdrom->get_track_type(0);
			m_reference_size = type == cdrom_file::CD_TRACK_MODE2_FORM2 ? 2324 : 2048;
			m_cdrom->read_data(0, m_reference.data(),
							   (type == cdrom_file::CD_TRACK_MODE2_FORM1 || type == cdrom_file::CD_TRACK_MODE2_FORM2)
								   ? type
								   : cdrom_file::CD_TRACK_MODE1);
		}
	}

  private:
	required_device<cdrom_image_device> m_cdrom;
	std::array<u8, 2560> m_reference{};
	u32 m_reference_size = 2048;
	required_device<saturn_cdb_device> m_cdb;
	required_device<saturn_scu_device> m_scu;
	void map(address_map &map)
	{
		map(0x06000000, 0x0600ffff).ram().share("hostram");
		map(0x05c00000, 0x05c0ffff).ram();
		map(0x05fe0000, 0x05fe00ff).m(m_scu, FUNC(saturn_scu_device::regs_map));
		map(0x05901010, 0x05901013)
			.lw32(NAME(
				[this](u32 data)
				{
					if (data)
						m_cdb->set_tray_open();
					else
						m_cdb->set_tray_close();
				}));
		map(0x05901000, 0x0590100f)
			.lr32(NAME(
				[this](offs_t offset) -> u32
				{
					if (offset == 0)
						return m_reference_size;
					if (offset == 1)
						return m_cdrom->get_track_start(1) + 150;
					if (offset == 2)
						return m_cdrom->get_track_start(2) + 150;
					return m_cdrom->get_last_track();
				}));
		map(0x05900000, 0x059009ff)
			.lr32(NAME(
				[this](offs_t offset) -> u32
				{
					unsigned i = offset * 4;
					return (u32(m_reference[i]) << 24) | (u32(m_reference[i + 1]) << 16) |
						   (u32(m_reference[i + 2]) << 8) | m_reference[i + 3];
				}));
		map(0, 0x1ff).rom().region("maincpu", 0);
		map(0x05800000, 0x0589ffff).m(m_cdb, FUNC(saturn_cdb_device::amap));
	}
};
ROM_START(cdbdiag)
ROM_REGION(0x200, "maincpu", 0)
ROM_LOAD("host.bin", 0, 0x200, CRC(987bc9f7) SHA1(aa4178e79c70d717c2bd5c1a0277e1c589641065))
ROM_END
} // namespace
CONS(2026, cdbdiag, 0, 0, config, 0, cdbdiag_state, empty_init, "Diagnostic", "Saturn CD firmware diagnostic",
	 MACHINE_SUPPORTS_SAVE)
