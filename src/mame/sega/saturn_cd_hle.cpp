// license:BSD-3-Clause
// copyright-holders:R. Belmont, Angelo Salese
/**************************************************************************************************

  sega/saturn_cd_hle.cpp - Sega Saturn and ST-V CD-ROM handling

  Another tilt at the windmill in 2011 by R. Belmont.

  Status: All known discs at least load their executable, and many load
          some data files successfully, but there are other problems.

  Information sources:
  - Tyranid's document
  - A commented disassembly I made of the Saturn BIOS's CD code
  - Yabuse's cs2.c
  - The ISO/IEC "Yellow Book" CD-ROM standard, 1995 version

  Address is mostly in terms of FAD (Frame ADdress).
  FAD is absolute number of frames from the start of the disc.
  In other words, FAD = LBA + 150; FAD is the same units as
  LBA except it counts starting at absolute zero instead of
  the first sector (00:02:00 in MSF format).

===================================================================================================

TODO:
- fix DRDY behaviour, several softwares gets to the point of filling the buffer
  (and probably don't know what to do);
- fix startup not really reading the initial ID setup in device_reset, cfr.
cdblock branch;
- derive MPEG commands in a subdevice;
- startup with NODISC/OPEN states currently takes a bit too much wall clock time
  (should be rather instant not take ~14 seconds);

DASM notes:
* whizzj:
- wpset 0x605e4b8,4,w,wpdata==0x4e
  (second trigger)
- write to 0x605e498 -> 1
  (PUBLISH.CPK tries to playback a few frames then keeps looping)

**************************************************************************************************/

#include "saturn_cd_hle.h"
#include "emu.h"


#include "coreutil.h"
#include "multibyte.h"

#define LOG_WARN (1U << 1)
#define LOG_CMD (1U << 2)
#define LOG_SEEK (1U << 3)
#define LOG_XFER (1U << 4)
#define LOG_STATUS (1U << 5) // log CD status changes
#define LOG_CMDV (1U << 6)   // raw command output (verbose)

#define VERBOSE (LOG_CMD | LOG_WARN | LOG_STATUS)
// #define LOG_OUTPUT_FUNC osd_printf_info

#include "logmacro.h"

#define LOGWARN(...) LOGMASKED(LOG_WARN, __VA_ARGS__)
#define LOGCMD(...) LOGMASKED(LOG_CMD, __VA_ARGS__)
#define LOGSEEK(...) LOGMASKED(LOG_SEEK, __VA_ARGS__)
#define LOGXFER(...) LOGMASKED(LOG_XFER, __VA_ARGS__)
#define LOGSTATUS(...) LOGMASKED(LOG_STATUS, __VA_ARGS__)
#define LOGCMDV(...) LOGMASKED(LOG_CMDV, __VA_ARGS__)

#define LIVE_CD_VIEW 0

// HIRQ definitions
#define CMOK 0x0001 // command dispatch possible
#define DRDY 0x0002 // data transfer preparations complete
#define CSCT 0x0004 // finished reading 1 sector
#define BFUL 0x0008 // CD buffer full
#define PEND 0x0010 // CD playback completed
#define DCHG 0x0020 // disc change / tray open
#define ESEL 0x0040 // selector settings processing complete
#define EHST 0x0080 // host input/output processing complete
#define ECPY 0x0100 // duplication/move processing complete
#define EFLS 0x0200 // file system processing complete
#define SCDQ 0x0400 // subcode Q update completed
#define MPED 0x0800 // MPEG-related processing complete
#define MPCM 0x1000 // MPEG action uncertain
#define MPST 0x2000 // MPEG interrupt status report

// CD status (hi byte of CR1) definitions:
// (these defines are shifted up 8)
#define CD_STAT_BUSY 0x0000    // status change in progress
#define CD_STAT_PAUSE 0x0100   // CD block paused (temporary stop)
#define CD_STAT_STANDBY 0x0200 // CD drive stopped
#define CD_STAT_PLAY 0x0300    // CD play in progress
#define CD_STAT_SEEK 0x0400    // drive seeking
#define CD_STAT_SCAN 0x0500    // drive scanning
#define CD_STAT_OPEN 0x0600    // tray is open
#define CD_STAT_NODISC 0x0700  // no disc present
#define CD_STAT_RETRY 0x0800   // read retry in progress
#define CD_STAT_ERROR 0x0900   // read data error occurred
#define CD_STAT_FATAL 0x0a00   // fatal error (hard reset required)
#define CD_STAT_PERI 0x2000  // periodic response if set, else command response
#define CD_STAT_TRANS 0x4000 // data transfer request if set
#define CD_STAT_WAIT                                                           \
  0x8000 // waiting for command if set, else executed immediately
#define CD_STAT_REJECT 0xff00 // ultra-fatal error.

DEFINE_DEVICE_TYPE(SATURN_CD_HLE, saturn_cd_hle_device, "saturn_cd_hle",
                   "Sega Saturn/ST-V CD Block HLE")

ALLOW_SAVE_TYPE(saturn_cd_hle_device::transT);
ALLOW_SAVE_TYPE(saturn_cd_hle_device::trans32T);

saturn_cd_hle_device::saturn_cd_hle_device(const machine_config &mconfig,
                                           const char *tag, device_t *owner,
                                           uint32_t clock)
    : device_t(mconfig, SATURN_CD_HLE, tag, owner, clock),
      device_mixer_interface(mconfig, *this), m_cdrom_image(*this, "cdrom"),
      m_cdda(*this, "cdda"), m_host_irq_cb(*this) {}

void saturn_cd_hle_device::device_add_mconfig(machine_config &config) {
  CDROM(config, "cdrom").set_interface("cdrom");

  CDDA(config, m_cdda);
  m_cdda->add_route(0, *this, 1.0, 0);
  m_cdda->add_route(1, *this, 1.0, 1);
  m_cdda->set_cdrom_tag("cdrom");
}

void saturn_cd_hle_device::device_start() {
  m_sh1_timer = timer_alloc(FUNC(saturn_cd_hle_device::sh1_command_cb), this);
  m_sector_timer = timer_alloc(FUNC(saturn_cd_hle_device::cd_sector_cb), this);

  // initialize at power on only
  tray_is_closed = 1;

  save_item(NAME(sectlenin));
  save_item(NAME(sectlenout));
  save_item(NAME(lastbuf));
  save_item(NAME(playtype));
  save_item(NAME(xfercount));
  save_item(NAME(calcsize));
  save_item(NAME(xferoffs));
  save_item(NAME(xfersect));
  save_item(NAME(xfersectpos));
  save_item(NAME(xfersectnum));
  save_item(NAME(xferdnum));
  save_item(NAME(cddevicenum));
  save_item(NAME(cr1));
  save_item(NAME(cr2));
  save_item(NAME(cr3));
  save_item(NAME(cr4));
  save_item(NAME(hirqmask));
  save_item(NAME(hirqreg));
  save_item(NAME(cd_stat));
  save_item(NAME(cd_next_stat));
  save_item(NAME(cd_seek_stat));
  save_item(NAME(cd_curfad));
  save_item(NAME(cd_fad_seek));
  save_item(NAME(fadstoplay));
  save_item(NAME(buffull));
  save_item(NAME(m_seek_ticks_left));
  save_item(NAME(sectorstore));
  save_item(NAME(freeblocks));
  save_item(NAME(cur_track));
  save_item(NAME(cmd_pending));
  save_item(NAME(cd_speed));
  save_item(NAME(cdda_maxrepeat));
  save_item(NAME(cdda_repeat_count));
  save_item(NAME(tray_is_closed));
  save_item(NAME(m_status_change_in_progress));
  save_item(NAME(numfiles));
  save_item(NAME(firstfile));
  // the transfer type gives the saved xfercount/xferoffs/xfersect* positions
  // their meaning, so it has to travel with them
  save_item(NAME(xfertype));
  save_item(NAME(xfertype32));
}

void saturn_cd_hle_device::device_reset() {
  int32_t i, j;

  hirqmask = 0x0000;
  // FIXME: should be zero but CD auto load and azelpanztai breaks otherwise
  // (what's the origin of this CMOK?)
  hirqreg = 0x0001;
  update_hirq();
  cr1 = 'C';
  cr2 = ('D' << 8) | 'B';
  cr3 = ('L' << 8) | 'O';
  cr4 = ('C' << 8) | 'K';

  //	cd_stat = CD_STAT_PAUSE;
  //	cd_stat |= CD_STAT_PERI;
  //	cd_next_stat = CD_STAT_PAUSE;
  // clear, not supposed to be used until actual command issued
  cd_seek_stat = CD_STAT_BUSY;
  cur_track = 0xff;
  calcsize = 0;
  playtype = 0;
  buffull_temp_pause = false;
  m_status_change_in_progress = false;
  m_seek_in_progress = false;
  m_seek_ticks_left = 0;

  curdir.clear();

  xfertype = XFERTYPE_INVALID;
  xfertype32 = XFERTYPE32_INVALID;
  xfercount = 0;
  xferoffs = 0;

  // reset flag vars
  buffull = sectorstore = 0;

  freeblocks = MAX_BLOCKS;

  sectlenin = sectlenout = 2048;

  lastbuf = 0xff;

  // reset buffer partitions
  for (i = 0; i < MAX_FILTERS; i++) {
    partitions[i].size = -1;
    partitions[i].numblks = 0;

    for (j = 0; j < MAX_BLOCKS; j++) {
      partitions[i].blocks[j] = (blockT *)nullptr;
      partitions[i].bnum[j] = 0xff;
    }
  }

  // reset blocks
  for (i = 0; i < MAX_BLOCKS; i++) {
    blocks[i].size = -1;
    memset(&blocks[i].data, 0, cdrom_file::MAX_SECTOR_DATA);
  }

  // open device
  if (m_cdrom_image->exists()) {
    LOG("Opened CD-ROM successfully, reading root directory\n");
    read_new_dir(0xffffff); // read root directory
    cd_curfad = 150;
    fadstoplay = -1;
    cd_change_status(CD_STAT_PAUSE);
  } else {
    cd_change_status(tray_is_closed ? CD_STAT_NODISC : CD_STAT_OPEN);
  }

  buffull = 0;
  cd_speed = 2;
  cdda_repeat_count = 0;

  // the MPEG state is not registered for save states, following the convention
  // of the filter, partition and block arrays above; reset re-establishes it
  mpeg_reset();

  m_sector_timer->adjust(
      attotime::from_hz(150)); // 150 sectors / second = 300kBytes/second
}

/*
 * Block interface
 */

// base 0x05800000
void saturn_cd_hle_device::amap(address_map &map) {
  map(0x18000, 0x18003)
      .rw(FUNC(saturn_cd_hle_device::datatrns_r),
          FUNC(saturn_cd_hle_device::datatrns_w));
  // normally read at $58900xx, test1f probes $58800xx instead
  map(0x80000, 0x80003)
      .mirror(0x18000)
      .rw(FUNC(saturn_cd_hle_device::datatrns_r),
          FUNC(saturn_cd_hle_device::datatrns_w));
  map(0x80008, 0x8000b)
      .mirror(0x18000)
      .rw(FUNC(saturn_cd_hle_device::hirq_r),
          FUNC(saturn_cd_hle_device::hirq_w));
  map(0x8000c, 0x8000f)
      .mirror(0x18000)
      .rw(FUNC(saturn_cd_hle_device::hirqmask_r),
          FUNC(saturn_cd_hle_device::hirqmask_w));
  map(0x80018, 0x8001b)
      .mirror(0x18000)
      .rw(FUNC(saturn_cd_hle_device::dr1_r), FUNC(saturn_cd_hle_device::cr1_w));
  map(0x8001c, 0x8001f)
      .mirror(0x18000)
      .rw(FUNC(saturn_cd_hle_device::dr2_r), FUNC(saturn_cd_hle_device::cr2_w));
  map(0x80020, 0x80023)
      .mirror(0x18000)
      .rw(FUNC(saturn_cd_hle_device::dr3_r), FUNC(saturn_cd_hle_device::cr3_w));
  map(0x80024, 0x80027)
      .mirror(0x18000)
      .rw(FUNC(saturn_cd_hle_device::dr4_r), FUNC(saturn_cd_hle_device::cr4_w));

  // NetLink/ Sega Saturn modem access
  // dragndrm expects this value, most likely for status
  // TODO: move out of here, breaks daytoncej boot
  map(0x85029, 0x85029).lr8(NAME([]() -> u8 { return 0x11; }));
}

u32 saturn_cd_hle_device::datatrns_r(offs_t offset, uint32_t mem_mask) {
  u32 rv;

  if (mem_mask == 0xffffffff) {
    rv = dataxfer_long_r();
  } else if (mem_mask == 0xffff0000) {
    rv = dataxfer_word_r() << 16;
  } else if (mem_mask == 0x0000ffff) {
    rv = dataxfer_word_r();
  } else {
    if (!machine().side_effects_disabled())
      LOGWARN("CD: Unknown data buffer read with mask = %08x\n", mem_mask);
    rv = 0;
  }
  return rv;
}

void saturn_cd_hle_device::datatrns_w(offs_t offset, uint32_t data,
                                      uint32_t mem_mask) {
  if (mem_mask == 0xffffffff)
    dataxfer_long_w(data);
  else
    LOGWARN("CD: Unknown data buffer write with mask = %08x\n", mem_mask);
}

inline u32 saturn_cd_hle_device::dataxfer_long_r() {
  uint32_t rv = 0xffff'ffff;

  if (machine().side_effects_disabled())
    return rv;

  switch (xfertype32) {
  case XFERTYPE32_GETSECTOR:
  case XFERTYPE32_GETDELETESECTOR:
    // make sure we have sectors left
    if (xfersect < xfersectnum) {
      blockT *const blk = transpart->blocks[xfersectpos + xfersect];

      // a hole in the partition has nothing to hand over; leave the port at
      // its idle value and move on to the next sector rather than chasing a
      // null pointer or running off a block with a nonsense size
      if (blk == nullptr || blk->size < 0 ||
          uint32_t(blk->size) > sizeof(blk->data)) {
        LOGWARN("CD: Get Sector Data skipping invalid block %d of %d\n",
                xfersect + 1, xfersectnum);

        xferoffs = 0;
        xfersect++;
        break;
      }

      // get next longword
      rv = get_u32be(&blk->data[xferoffs]);

      xferdnum += 4;
      xferoffs += 4;

      // did we run out of sector? (this tested blocks[xfersect], missing the
      // partition offset the data read above uses)
      if (xferoffs >= blk->size) {
        LOG("Finished xfer of block %d of %d\n", xfersect + 1, xfersectnum);

        xferoffs = 0;
        xfersect++;
      }
    } else // sectors are done, kill 'em all if we can
    {
      if (xfertype32 == XFERTYPE32_GETDELETESECTOR) {
        int32_t i;

        LOG("Killing sectors in done\n");

        // deallocate the blocks
        for (i = xfersectpos; i < xfersectpos + xfersectnum; i++) {
          cd_free_block(transpart->blocks[i]);
          transpart->blocks[i] = (blockT *)nullptr;
          transpart->bnum[i] = 0xff;
        }

        // defrag what's left
        cd_defragblocks(transpart);

        // clean up our state
        transpart->size -= xferdnum;
        transpart->numblks -= xfersectnum;

        // TODO: is this correct?
        xfertype32 = XFERTYPE32_INVALID;
      }
    }
    break;

  default:
    // punt in particular if SH-2 or SCU DMA try to go overboard ...
    throw emu_fatalerror(
        "CD: attempting to read 32-bit data port with invalid transfer mode %d",
        (int)xfertype32);
  }

  return rv;
}

inline void saturn_cd_hle_device::dataxfer_long_w(u32 data) {
  switch (xfertype32) {
  case XFERTYPE32_PUTSECTOR:
    // make sure we have sectors left
    if (xfersect < xfersectnum) {
      blockT *const blk = transpart->blocks[xfersectpos + xfersect];

      // as above: skip anything we cannot safely write into
      if (blk == nullptr || blk->size < 0 ||
          uint32_t(blk->size) > sizeof(blk->data)) {
        LOGWARN("CD: Put Sector Data skipping invalid block %d of %d\n",
                xfersect + 1, xfersectnum);

        xferoffs = 0;
        xfersect++;
        break;
      }

      // get next longword
      put_u32be(&blk->data[xferoffs], data);

      xferdnum += 4;
      xferoffs += 4;

      // did we run out of sector?
      if (xferoffs >= blk->size) {
        LOG("Finished xfer of block %d of %d\n", xfersect + 1, xfersectnum);

        xferoffs = 0;
        xfersect++;
      }
    } else // sectors are done
    {
      /* Virtual On doesnt want this to be resetted. */
      // xfertype32 = XFERTYPE32_INVALID;
    }
    break;

  default:
    LOGWARN("CD: unhandled 32-bit transfer type write %d\n", (int)xfertype32);
    break;
  }
}

inline u16 saturn_cd_hle_device::dataxfer_word_r() {
  u16 rv;

  rv = 0xffff;
  switch (xfertype) {
  case XFERTYPE_TOC:
    rv = get_u16be(&tocbuf[xfercount]);

    xfercount += 2;
    xferdnum += 2;

    if (xfercount >= 102 * 4) {
      xfercount = 0;
      xfertype = XFERTYPE_INVALID;
    }
    break;

  case XFERTYPE_FILEINFO_1:
    rv = get_u16be(&finfbuf[xfercount]);
    xfercount += 2;
    xferdnum += 2;

    if (xfercount > 6 * 2) {
      xfercount = 0;
      xfertype = XFERTYPE_INVALID;
    }
    break;

  case XFERTYPE_FILEINFO_254: // Lunar 2
    if ((xfercount % (6 * 2)) == 0) {
      uint32_t temp = 2 + (xfercount / (0x6 * 2));

      /* this transfer promises 254 records no matter how many entries
         make_dir_current() actually parsed, so temp runs past the end of
         curdir on any disc with fewer than 257 of them - and curdir is empty
         until a directory has been read at all.  Report the entries that are
         not there as an absent file, which is how this protocol already
         spells "not found", instead of reading past the allocation.
         Deliberately no warning here: this is the normal case, so one would
         fire per record on every title that asks for the whole directory. */
      direntryT const entry =
          (size_t(temp) < curdir.size()) ? curdir[temp] : direntryT{};

      // first 4 bytes = FAD
      put_u32be(&finfbuf[0], entry.firstfad);
      // second 4 bytes = length of file
      put_u32be(&finfbuf[4], entry.length);
      finfbuf[8] = entry.interleave_gap_size;
      finfbuf[9] = entry.file_unit_size;
      finfbuf[10] = temp;
      finfbuf[11] = entry.flags;
    }

    rv = get_u16be(&finfbuf[xfercount % (6 * 2)]);

    xfercount += 2;
    xferdnum += 2;

    if (xfercount > (254 * 6 * 2)) {
      xfercount = 0;
      xfertype = XFERTYPE_INVALID;
    }
    break;

  case XFERTYPE_SUBQ:
    rv = get_u16be(&subqbuf[xfercount]);

    xfercount += 2;
    xferdnum += 2;

    if (xfercount >= 5 * 2) {
      xfercount = 0;
      xfertype = XFERTYPE_INVALID;
    }
    break;

  case XFERTYPE_SUBRW:
    rv = get_u16be(&subrwbuf[xfercount]);

    xfercount += 2;
    xferdnum += 2;

    if (xfercount >= 12 * 2) {
      xfercount = 0;
      xfertype = XFERTYPE_INVALID;
    }
    break;

  default:
    LOGWARN("SATURN_CD_HLE: Unhandled xfer type %d\n", (int)xfertype);
    rv = 0;
    break;
  }

  return rv;
}

// the HIRQ line to the host is asserted while any unmasked CD interrupt is
// pending; the SCU latches it as A-Bus external interrupt 0
void saturn_cd_hle_device::update_hirq() {
  if (m_host_irq_cb.isunset())
    return;

  m_host_irq_cb((hirqreg & hirqmask) ? ASSERT_LINE : CLEAR_LINE);
}

uint16_t saturn_cd_hle_device::hirq_r() {
  // TODO: this member must return the register only
  u16 rv;

  //  LOG("RW HIRQ: %04x\n", rv);

  rv = hirqreg;

  rv &= ~DCHG; // always clear bit 6 (tray open)

  if (buffull)
    rv |= BFUL;
  else
    rv &= ~BFUL;
  if (sectorstore)
    rv |= CSCT;
  else
    rv &= ~CSCT;

  hirqreg = rv;
  update_hirq();

  return rv;
}

void saturn_cd_hle_device::hirq_w(uint16_t data) {
  hirqreg &= data;
  update_hirq();
}

// TODO: these two are actually never read or written to by host?
uint16_t saturn_cd_hle_device::hirqmask_r() {
  if (!machine().side_effects_disabled())
    LOGWARN("RW HIRM: %04x\n", hirqmask);
  return hirqmask;
}

void saturn_cd_hle_device::hirqmask_w(offs_t offset, uint16_t data,
                                      uint16_t mem_mask) {
  LOGWARN("WW HIRM: %04x => %04x\n", hirqmask, data);
  COMBINE_DATA(&hirqmask);
  update_hirq();
}

uint16_t saturn_cd_hle_device::dr1_r() { return cr1; }
uint16_t saturn_cd_hle_device::dr2_r() { return cr2; }
uint16_t saturn_cd_hle_device::dr3_r() { return cr3; }
uint16_t saturn_cd_hle_device::dr4_r() {
  if (!machine().side_effects_disabled()) {
    cmd_pending = 0;
    cd_stat |= CD_STAT_PERI;
  }
  return cr4;
}

// TODO: understand how dual-port interface really works out
void saturn_cd_hle_device::cr1_w(uint16_t data) {
  cr1 = data;
  cd_stat &= ~CD_STAT_PERI;
  cmd_pending |= 1;
  m_sh1_timer->adjust(attotime::never);
}

void saturn_cd_hle_device::cr2_w(uint16_t data) {
  cr2 = data;
  cmd_pending |= 2;
}

void saturn_cd_hle_device::cr3_w(uint16_t data) {
  cr3 = data;
  cmd_pending |= 4;
}

void saturn_cd_hle_device::cr4_w(uint16_t data) {
  cr4 = data;
  cmd_pending |= 8;
  m_sh1_timer->adjust(attotime::from_hz(get_timing_command()));
}

/*
 * CDC command helpers
 */
int saturn_cd_hle_device::get_timing_command(void) {
  // TODO: calculate timings based off command params
  // given the CMOK returns it looks like SH2 expects way slower responses
  // (loops for 0x7xx times at most, max number of iterations is 0x240000)
  return 16667;
}

/* FIXME: assume Saturn CD-ROMs to have a 2 secs pre-gap for now. */
int saturn_cd_hle_device::get_track_index(uint32_t fad) {
  uint32_t rel_fad;
  uint8_t track;

  if (m_cdrom_image->get_track_type(m_cdrom_image->get_track(fad)) !=
      cdrom_file::CD_TRACK_AUDIO)
    return 1;

  track = m_cdrom_image->get_track(fad);

  rel_fad = fad - m_cdrom_image->get_track_start(track);

  if (rel_fad < 150)
    return 0;

  return 1;
}

int saturn_cd_hle_device::sega_cdrom_get_adr_control(int track) {
  return bitswap<8>(m_cdrom_image->get_adr_control(track), 3, 2, 1, 0, 7, 6, 5,
                    4);
}

void saturn_cd_hle_device::cr_standard_return(uint16_t cur_status) {
  if (!m_cdrom_image->exists()) {
    // preserve whatever command is currently set
    cr1 = cd_stat | (cr1 & 0xff);
    // cr2 = 0;
    // cr3 = 0;
    // cr4 = 0;
  } else if ((cd_stat & 0x0f00) == CD_STAT_SEEK) {
    /* During seek state, values returned are from the target position */
    uint8_t seek_track = m_cdrom_image->get_track(cd_fad_seek - 150);

    cr1 = cur_status | (playtype << 7) | 0x00 | (cdda_repeat_count & 0xf);
    cr2 = (seek_track == 0xff)
              ? 0xffff
              : ((sega_cdrom_get_adr_control(seek_track) << 8) | seek_track);
    cr3 = (get_track_index(cd_fad_seek) << 8) |
          (cd_fad_seek >> 16); // index & 0xff00
    cr4 = cd_fad_seek;
  } else {
    cr1 = cur_status | (playtype << 7) | 0x00 |
          (cdda_repeat_count & 0xf); // options << 4 | repeat & 0xf
    cr2 = (cur_track == 0xff)
              ? 0xffff
              : ((sega_cdrom_get_adr_control(cur_track) << 8) |
                 (m_cdrom_image->get_track(cd_curfad - 150) + 1));
    cr3 =
        (get_track_index(cd_curfad) << 8) | (cd_curfad >> 16); // index & 0xff00
    cr4 = cd_curfad;
  }
}

void saturn_cd_hle_device::cd_change_status(u16 new_status) {
  // BUSY over BUSY is an unexpected condition hence the !
  // The "???" are just to avoid making a division in this hot path
  char const *const status_names[16] = {
      "BUSY (!)", "PAUSE", "STANDBY", "PLAY", "SEEK", "SCAN", "OPEN", "NODISC",
      "RETRY",    "ERROR", "FATAL",   "???",  "???",  "???",  "???",  "???"};
  LOGSTATUS("Status change: %s (%04x) -> BUSY -> %s (%04x)\n",
            status_names[(cd_stat >> 8) & 0xf], cd_stat,
            status_names[(new_status >> 8) & 0xf], new_status);
  // it would make more sense with mask & 0xf0ff
  // - houkago will chain 0x21 commands due of PERI hook (leading to a crash)
  cd_stat = CD_STAT_BUSY;
  cd_next_stat = new_status;
  m_status_change_in_progress = true;
  if (new_status == CD_STAT_SEEK)
    m_seek_ticks_left = 0; // retarget: re-measure the travel on the next tick
  // we are changing the status, definitely don't want PERI to interfere
  cd_stat &= ~CD_STAT_PERI;
}

/*
 * CDC commands
 */

void saturn_cd_hle_device::cmd_get_status() {
  // LOGCMD("%s: Get Status\n", machine().describe_context();
  hirqreg |= CMOK;
  update_hirq();
  cr_standard_return(cd_stat);
  // LOG("   = %04x %04x %04x %04x %04x\n", hirqreg, cr1, cr2, cr3, cr4);
}

void saturn_cd_hle_device::cmd_get_hw_info() {
  LOGCMD("%s: Get Hardware Info\n", machine().describe_context());
  hirqreg |= CMOK;
  update_hirq();
  cr1 = cd_stat;
  cr2 = 0x0201;
  cr3 = 0x0000;
  cr4 = 0x0400;
}

void saturn_cd_hle_device::cmd_get_toc() {
  LOGCMD("%s: Get TOC\n", machine().describe_context());
  cd_readTOC();
  // nope, hisspach wants just the DTREQ, otherwise hangs at Sega logo
  // cd_stat = CD_STAT_TRANS | CD_STAT_PAUSE;
  cd_stat |= CD_STAT_TRANS;
  cr1 = cd_stat;
  cr2 = 102 * 2; // TOC length in words (102 entries @ 2 words/4bytes each)
  cr3 = 0;
  cr4 = 0;
  xferdnum = 0;
  hirqreg |= (CMOK | DRDY);
  update_hirq();
}

void saturn_cd_hle_device::cmd_get_session_info() {
  // get session info (lower byte = session # to get?)
  // bios is interested in returns in cr3 and cr4
  // cr3 should be data track #
  // cr4 must be > 1 and < 100 or bios gets angry.
  LOGCMD("%s: Get Session Info\n", machine().describe_context());
  // TODO: shouldn't really read from TOC
  cd_readTOC();
  switch (cr1 & 0xff) {
  case 0: // get total session info / disc end
    // TODO: shouldn't require a status change
    cd_change_status(CD_STAT_PAUSE);
    cr1 = cd_stat;
    cr2 = 0;
    cr3 = 0x0100 | tocbuf[(101 * 4) + 1];
    cr4 = get_u16be(&tocbuf[(101 * 4) + 2]);
    break;

  case 1: // get total session info / disc start
    // TODO: as above
    cd_change_status(CD_STAT_PAUSE);
    cr1 = cd_stat;
    cr2 = 0;
    cr3 = 0x0100; // sessions in high byte, session start in lower
    cr4 = 0;
    break;

  default:
    LOGWARN("CD: Unknown request to Get Session Info %x\n", cr1 & 0xff);
    cr1 = cd_stat;
    cr2 = 0;
    cr3 = 0;
    cr4 = 0;
    break;
  }

  hirqreg |= (CMOK);
  update_hirq();
}

void saturn_cd_hle_device::cmd_init_cdsystem() {
  // TODO: double check this
  // initialize CD system
  // CR1 & 1 = reset software
  // CR1 & 2 = decode RW subcode
  // CR1 & 4 = don't confirm mode 2 subheader
  // CR1 & 8 = retry reading mode 2 sectors
  // CR1 & 10 = force single-speed
  // CR1 & 80 = no change flag (done by Assault Suit Leynos 2)
  LOGCMD("%s: Initialize CD system %02x\n", machine().describe_context(), cr1);

  // if((cr1 & 0x81) == 0x00) //guess TODO: nope, Choice Cuts doesn't like it,
  // it crashes if you try to skip the FMV otherwise.
  {
    if (((cd_stat & 0x0f00) != CD_STAT_NODISC) &&
        ((cd_stat & 0x0f00) != CD_STAT_OPEN)) {
      cd_fad_seek = 150;
      cd_change_status(CD_STAT_SEEK);
      cd_seek_stat = CD_STAT_PAUSE;
      // cur_track = 1;
      fadstoplay = 0;
    }
    buffull = 0;
    buffull_temp_pause = false;
    hirqreg &= 0xffe5;
    update_hirq();
    cd_speed = (cr1 & 0x10) ? 1 : 2;

/* reset filter connections */
/* Guess: X-Men COTA sequence is 0x48->0x48->0x04(01)->0x04(00)->0x30 then 0x10,
 * without this game throws a FAD reject error */
/* X-Men vs. SF is even fussier, sequence is  0x04 (1) 0x04 (0) 0x03 (0) 0x03
 * (1) 0x30 */
#if 0
		for(int i=0;i<MAX_FILTERS;i++)
		{
			filters[i].fad = 0;
			filters[i].range = 0xffffffff;
			filters[i].mode = 0;
			filters[i].chan = 0;
			filters[i].smmask = 0;
			filters[i].cimask = 0;
			filters[i].fid = 0;
			filters[i].smval = 0;
			filters[i].cival = 0;
		}
#endif

    /* reset CD device connection */
    // cddevice = (filterT *)nullptr;
  }

  // TODO: ESEL happens at the end of the actual reset phase
  hirqreg |= (CMOK | ESEL | EFLS | ECPY | EHST);
  update_hirq();
  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_end_data_transfer() {
  // end data transfer (TODO: needs to be worked on!)
  // returns # of bytes transferred (24 bits) in
  // low byte of cr1 (MSB) and cr2 (middle byte, LSB)
  LOGXFER("%s: End data transfer (%d bytes xfer'd)\n",
          machine().describe_context(), xferdnum);

  // clear the "transfer" flag
  cd_stat &= ~CD_STAT_TRANS;

  if (xferdnum) {
    cr1 = (cd_stat) | ((xferdnum >> 17) & 0xff);
    cr2 = (xferdnum >> 1) & 0xffff;
    cr3 = 0;
    cr4 = 0;
  } else {
    LOGWARN("No xferdnum error\n");
    cr1 = (cd_stat) | (0xff); // is this right?
    cr2 = 0xffff;
    cr3 = 0;
    cr4 = 0;
  }

  // try to clean up any transfers still in progress
  switch (xfertype32) {
  case XFERTYPE32_GETSECTOR:
  case XFERTYPE32_PUTSECTOR:
    hirqreg |= EHST;
    update_hirq();
    break;

  case XFERTYPE32_GETDELETESECTOR:
    if (transpart->size > 0) {
      int32_t i;

      xfertype32 = XFERTYPE32_INVALID;

      // deallocate the blocks
      for (i = xfersectpos; i < xfersectpos + xfersectnum; i++) {
        cd_free_block(transpart->blocks[i]);
        transpart->blocks[i] = (blockT *)nullptr;
        transpart->bnum[i] = 0xff;
      }

      // defrag what's left
      cd_defragblocks(transpart);

      // clean up our state
      transpart->size -= xferdnum;
      transpart->numblks -= xfersectnum;

      if (freeblocks == MAX_BLOCKS) {
        sectorstore = 0;
      }

      hirqreg |= EHST;
      update_hirq();
    }
    break;

  default:
    break;
  }

  xferdnum = 0;
  hirqreg |= CMOK;
  update_hirq();

  LOGXFER("\t%04x %04x %04x %04x %04x\n", hirqreg, cr1, cr2, cr3, cr4);
}

void saturn_cd_hle_device::cmd_play_disc() {
  // Play Disc. FAD is in lowest 7 bits of cr1 and all of cr2.
  uint32_t start_pos, end_pos;
  uint8_t play_mode;

  LOGCMD("%s: Play Disc\n", machine().describe_context());

  play_mode = (cr3 >> 8) & 0x7f;

  // preserve current position if bit 7 set
  if (!(cr3 & 0x8000)) {
    start_pos = ((cr1 & 0xff) << 16) | cr2;
    end_pos = ((cr3 & 0xff) << 16) | cr4;

    if (start_pos & 0x800000) {
      if (start_pos != 0xffffff) {
        cd_fad_seek = start_pos & 0x7f'ffff;
        cd_change_status(CD_STAT_SEEK);
        cd_seek_stat = CD_STAT_PLAY;
      }

      LOGCMD("\tFAD mode\n");
      cur_track = m_cdrom_image->get_track(cd_curfad - 150);
    } else {
      // track mode
      if ((start_pos >> 8) != 0) {
        cur_track = start_pos >> 8;
        cd_fad_seek = m_cdrom_image->get_track_start(cur_track - 1);
        cd_change_status(CD_STAT_SEEK);
        cd_seek_stat = CD_STAT_PLAY;
        // m_cdda->pause_audio(0);
      } else {
        // FIXME: Waku Waku 7 sets up track 0, that basically doesn't make any
        // sense. Just skip it for now.
        popmessage("Warning: track mode == 0");
        cr_standard_return(cd_stat);
        hirqreg |= (CMOK);
        update_hirq();
        return;
      }

      LOGCMD("\ttrack mode %d\n", cur_track);
    }

    if (end_pos & 0x800000) {
      if (end_pos != 0xffffff)
        fadstoplay = end_pos & 0x7f'ffff;
    } else {
      uint8_t end_track;

      end_track = (end_pos) >> 8;
      fadstoplay = m_cdrom_image->get_track_start(end_track) - cd_fad_seek;
    }
  } else // play until the end of the disc
  {
    start_pos = ((cr1 & 0xff) << 16) | cr2;
    end_pos = ((cr3 & 0xff) << 16) | cr4;

    if (start_pos != 0xffffff) {
      /* Madou Monogatari sets 0xff80xxxx as end position, needs investigation
       * ... */
      if (end_pos & 0x800000)
        fadstoplay = end_pos & 0xfffff;
      else {
        if (end_pos == 0)
          fadstoplay = (m_cdrom_image->get_track_start(0xaa)) - cd_curfad;
        else
          fadstoplay =
              (m_cdrom_image->get_track_start((end_pos & 0xff00) >> 8)) -
              cd_curfad;
      }
      LOGCMD("\ttrack mode %08x %08x -> %08x %08x\n", start_pos, end_pos,
             cd_curfad, fadstoplay);
      // make sure to SEEK anyway:
      // - Multiplayer Audio CD would otherwise override a previous track seek
      // command
      cd_change_status(CD_STAT_SEEK);
      cd_seek_stat = CD_STAT_PLAY;
    } else {
      /* resume from a pause state */
      // FIXME: verify implementation with Galaxy Fight
      // it calls 10ff ffff ffff ffff, but then it follows up with
      // 0x04->0x02->0x06->0x11->0x04->0x02->0x06 command sequence
      // (and current implementation nukes start/end FAD addresses at 0x04).
      // I'm sure that this doesn't work like this, but there could
      // be countless possible combinations ...
      if (fadstoplay == 0) {
        // don't override FAD start, Multiplayer Audio CD needs this
        // (testable by pausing then play again current track)
        // TODO: need to preserve previous fadstoplay
        // (in said case, by playing until the end of disc rather than just one
        // track)
        // cd_curfad = m_cdrom_image->get_track_start(cur_track);
        fadstoplay = m_cdrom_image->get_track_start(cur_track + 1) - cd_curfad;
        cd_change_status(CD_STAT_SEEK);
        cd_seek_stat = CD_STAT_PLAY;
      }
      LOGCMD("\ttrack resume %08x %08x (%06x %06x)\n", cd_curfad, fadstoplay,
             start_pos, end_pos);
    }
  }

  LOGCMD("\tPlay Disc: current %06x -> start %06x length %06x\n", cd_curfad,
         cd_fad_seek, fadstoplay);

  cr_standard_return(cd_stat);
  hirqreg |= (CMOK);
  update_hirq();

  playtype = 0;

  // cdda
  // if(m_cdrom_image->get_track_type(m_cdrom_image->get_track(cd_curfad)) ==
  // cdrom_file::CD_TRACK_AUDIO)
  //{
  //	m_cdda->pause_audio(0);
  //	//m_cdda->start_audio(cd_curfad, fadstoplay);
  //	//cdda_repeat_count = 0;
  //}

  if (play_mode != 0x7f)
    cdda_maxrepeat = play_mode & 0xf;
  else
    cdda_maxrepeat = 0;

  cdda_repeat_count = 0;
}

void saturn_cd_hle_device::cmd_seek_disc() {
  uint32_t temp;

  // clear any pending transfer
  // - asenna when playing back a video and going back in main menu
  fadstoplay = 0;
  cdda_repeat_count = 0;
  playtype = 0;

  LOGCMD("%s: Disc seek\n", machine().describe_context());
  LOGCMD("\t%04x %04x %04x %04x\n", cr1, cr2, cr3, cr4);
  if (cr1 & 0x80) {
    temp = (cr1 & 0xff) << 16; // get FAD to seek to
    temp |= cr2;

    // cd_curfad = temp;

    if (temp == 0xffffff) {
      /* A seek to 0xFFFFFF is a pause, not a stop: mednafen's command
         decode ("0xFFFFFF=pause, 0=stop") and its DRIVEPHASE_STOPPED ->
         STATUS_STANDBY path put the pause-to-standby transition on a
         seek to 0 instead, which is why the standby variant sketched
         here never shipped and is now removed. */
      {
        // chain a seek over the same position for delaying pausing a bit
        // - amagishi
        // - asenna
        // - batmanfu (batmobile GFX at intro)
        // - jungrhyt (restarting a failed stage)
        cd_fad_seek = cd_curfad;
        cd_change_status(CD_STAT_SEEK);
        cd_seek_stat = CD_STAT_PAUSE;
        m_cdda->pause_audio(1);
      }
    } else if (temp == 0) {
      // a seek to 0 stops the drive, which leaves it in standby
      cd_fad_seek = 150;
      cd_change_status(CD_STAT_SEEK);
      cd_seek_stat = CD_STAT_STANDBY;
      m_cdda->stop_audio();
      LOGCMD("\tdisc seek to 0: stop\n");
    } else {
      // Area 51 sets this up (TODO: retest me out)
      cd_fad_seek = ((cr1 & 0x7f) << 16) | cr2;
      cd_change_status(CD_STAT_SEEK);
      cd_seek_stat = CD_STAT_PAUSE;
      LOGCMD("\tdisc seek with params %04x %04x\n", cr1, cr2);
    }
  } else {
    // is it a valid track?
    if (cr2 >> 8) {
      cur_track = cr2 >> 8;
      cd_fad_seek = m_cdrom_image->get_track_start(cur_track - 1);
      cd_change_status(CD_STAT_SEEK);
      cd_seek_stat = CD_STAT_PAUSE;

      m_cdda->pause_audio(1);
      // (index is cr2 low byte)
    } else // error!
    {
      cd_change_status(CD_STAT_STANDBY);
      cd_curfad = 0xffffffff;
      cur_track = 0xff;
      m_cdda->stop_audio(); // stop any pending CD-DA
    }
  }

  hirqreg |= CMOK;
  update_hirq();
  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_ffwd_rew_disc() {
  // FFWD / REW
  // cr1 bit 0 determines if this is a Fast Forward (0) or a Rewind (1) command
  // TODO: the pickup is not actually moved, can be triggered thru Multiplayer
  // by holding on relevant keys
  LOGCMD("%s: %s disc\n", machine().describe_context(),
         (cr1 & 1) ? "Rewind" : "Fast forward");

  /* the drive reports scanning for as long as the command is in effect and
     stays there until the program asks for something else, so this is the
     status to move to even though the read position does not change yet.
     Without it the command also never completed: the handler returned
     without raising CMOK, leaving anything waiting on the interrupt stuck */
  cd_change_status(CD_STAT_SCAN);

  hirqreg |= CMOK;
  update_hirq();
  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_get_subcode_q_rw_channel() {
  // untested, assume it should set DTREQ
  cd_stat |= CD_STAT_TRANS;
  cd_stat &= 0xff00;
  // Get SubCode Q / RW Channel
  switch (cr1 & 0xff) {
  case 0: // Get Q
  {
    uint32_t msf_abs, msf_rel;
    uint8_t track;
    cr1 = cd_stat | 0;
    cr2 = 10 / 2;
    cr3 = 0;
    cr4 = 0;

    /*
    Subcode Q info should be:
    ---- --x- S0
    ---- ---x S1
    xxxx ---- [0] Control (bit 7 Pre-emphasis, bit 6: copy permitted, bit 5
    undefined, bit 4 number of channels)
    ---- xxxx [0] address (0x0001 Mode 1)
    xxxx xxxx [1] track number (1-99, AA lead-out), BCD format
    xxxx xxxx [2] index (01 lead-out), BCD format
    xxxx xxxx [3] Time within' track M
    xxxx xxxx [4] Time within' track S
    xxxx xxxx [5] Time within' track F
    xxxx xxxx [6] Zero
    xxxx xxxx [7] Absolute M
    xxxx xxxx [8] Absolute S
    xxxx xxxx [9] Absolute F
    xxxx xxxx [10] CRCC - (omitted in this implementation)
    xxxx xxxx [11] CRCC /
    */

    msf_abs = cdrom_file::lba_to_msf_alt(cd_curfad - 150);
    track = m_cdrom_image->get_track(cd_curfad);
    msf_rel = cdrom_file::lba_to_msf_alt(cd_curfad - 150 -
                                         m_cdrom_image->get_track_start(track));

    xfertype = XFERTYPE_SUBQ;
    xfercount = 0;
    subqbuf[0] =
        0x01 |
        ((m_cdrom_image->get_track_type(m_cdrom_image->get_track(track + 1)) ==
          cdrom_file::CD_TRACK_AUDIO)
             ? 0x00
             : 0x40);
    subqbuf[1] = dec_2_bcd(track + 1);
    subqbuf[2] = dec_2_bcd(get_track_index(cd_curfad));
    subqbuf[3] = dec_2_bcd((msf_rel >> 16) & 0xff);
    subqbuf[4] = dec_2_bcd((msf_rel >> 8) & 0xff);
    subqbuf[5] = dec_2_bcd((msf_rel >> 0) & 0xff);
    subqbuf[6] = 0;
    subqbuf[7] = dec_2_bcd((msf_abs >> 16) & 0xff);
    subqbuf[8] = dec_2_bcd((msf_abs >> 8) & 0xff);
    subqbuf[9] = dec_2_bcd((msf_abs >> 0) & 0xff);
  } break;

  case 1: // Get RW
    cr1 = cd_stat | 0;
    cr2 = 12;
    cr3 = 0;
    cr4 = 0;

    xfertype = XFERTYPE_SUBRW;
    xfercount = 0;

    /* return null data for now */
    {
      int i;

      for (i = 0; i < 12 * 2; i++)
        subrwbuf[i] = 0xff;
    }
    break;
  }
  hirqreg |= CMOK | DRDY;
  update_hirq();
}

void saturn_cd_hle_device::cmd_set_cddevice_connection() {
  uint8_t param;

  // get operation
  param = cr3 >> 8;

  LOGCMD("%s: Set CD Device Connection filter # %x\n",
         machine().describe_context(), param);

  cddevicenum = param;

  // a param of 0xff disconnects
  if (param == 0xff) {
    cddevice = (filterT *)nullptr;
  } else {
    if (param < MAX_FILTERS) {
      cddevice = &filters[param];
    } else {
      // TODO: should just require a rejection
      popmessage(
          "saturn_cd_hle.cpp: cmd_set_cddevice_connection() with param %02x",
          param);
    }
  }

  hirqreg |= (CMOK | ESEL);
  update_hirq();
  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_get_cddevice_connection() {
  LOGCMD("%s: Get CD Device Connection filter\n", machine().describe_context());
  cr1 = cd_stat | 0;
  cr2 = 0;
  cr3 = cddevicenum << 8;
  cr4 = 0;

  // TODO: unverified
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_last_buffer_destination() {
  cr1 = cd_stat | 0;
  cr2 = 0;
  cr3 = lastbuf << 8;
  cr4 = 0;
  hirqreg |= (CMOK);
  update_hirq();
}

void saturn_cd_hle_device::cmd_set_filter_range() {
  // cr1 low + cr2 = FAD0, cr3 low + cr4 = FAD1
  // cr3 hi = filter num.
  uint8_t fnum = (cr3 >> 8) & 0xff;

  LOGCMD("%s: Set Filter Range\n", machine().describe_context());
  if (fnum >= MAX_FILTERS) {
    LOGWARN("CD: invalid filter number %02x\n", fnum);
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | ESEL);
    update_hirq();
    return;
  }

  filters[fnum].fad = ((cr1 & 0xff) << 16) | cr2;
  filters[fnum].range = ((cr3 & 0xff) << 16) | cr4;

  LOGCMD("\t%08x %08x %d\n", filters[fnum].fad, filters[fnum].range, fnum);

  hirqreg |= (CMOK | ESEL);
  update_hirq();
  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_get_filter_range() {
  // Get Filter Range
  // cr1 low + cr2 = FAD0, cr3 low + cr4 = FAD1, cr3 hi = filter num.
  uint8_t fnum = (cr3 >> 8) & 0xff;

  if (fnum >= MAX_FILTERS) {
    LOGWARN("CD: invalid filter number %02x\n", fnum);
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | ESEL);
    update_hirq();
    return;
  }

  LOGCMD("%s: Get Filter Range fnum %x => %08x %08x\n",
         machine().describe_context(), fnum, filters[fnum].fad,
         filters[fnum].range);

  cr1 = cd_stat | ((filters[fnum].fad >> 16) & 0xff);
  cr2 = filters[fnum].fad & 0xffff;
  cr3 = (filters[fnum].range >> 16) & 0xff;
  cr4 = filters[fnum].range & 0xffff;

  hirqreg |= (CMOK | ESEL);
  update_hirq();
}

void saturn_cd_hle_device::cmd_set_filter_subheader_conditions() {
  uint8_t fnum = (cr3 >> 8) & 0xff;

  LOGCMD("%s: Set Filter Subheader conditions %x => chan %x masks %x fid %x "
         "vals %x\n",
         machine().describe_context(), fnum, cr1 & 0xff, cr2, cr3 & 0xff, cr4);
  if (fnum >= MAX_FILTERS) {
    LOGWARN("CD: invalid filter number %02x\n", fnum);
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | ESEL);
    update_hirq();
    return;
  }

  filters[fnum].chan = cr1 & 0xff;
  filters[fnum].smmask = (cr2 >> 8) & 0xff;
  filters[fnum].cimask = cr2 & 0xff;
  filters[fnum].fid = cr3 & 0xff;
  filters[fnum].smval = (cr4 >> 8) & 0xff;
  filters[fnum].cival = cr4 & 0xff;

  hirqreg |= (CMOK | ESEL);
  update_hirq();
  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_get_filter_subheader_conditions() {
  // Get Filter Subheader conditions
  uint8_t fnum = (cr3 >> 8) & 0xff;

  LOGCMD("%s: Get Filter Subheader conditions %x => chan %x masks %x fid %x "
         "vals %x\n",
         machine().describe_context(), fnum, cr1 & 0xff, cr2, cr3 & 0xff, cr4);
  if (fnum >= MAX_FILTERS) {
    LOGWARN("CD: invalid filter number %02x\n", fnum);
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | ESEL);
    update_hirq();
    return;
  }

  cr1 = cd_stat | (filters[fnum].chan & 0xff);
  cr2 = (filters[fnum].smmask << 8) | (filters[fnum].cimask & 0xff);
  cr3 = filters[fnum].fid;
  cr4 = (filters[fnum].smval << 8) | (filters[fnum].cival & 0xff);

  hirqreg |= (CMOK | ESEL);
  update_hirq();
}

void saturn_cd_hle_device::cmd_set_filter_mode() {
  // Set Filter Mode
  uint8_t fnum = (cr3 >> 8) & 0xff;
  uint8_t mode = (cr1 & 0xff);

  if (fnum >= MAX_FILTERS) {
    LOGWARN("CD: invalid filter number %02x\n", fnum);
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | ESEL);
    update_hirq();
    return;
  }

  // initialize filter?
  if (mode & 0x80) {
    memset(&filters[fnum], 0, sizeof(filterT));
  } else {
    filters[fnum].mode = mode;
  }

  LOGCMD("%s: Set Filter Mode filt %x mode %x\n", machine().describe_context(),
         fnum, mode);
  hirqreg |= (CMOK | ESEL);
  update_hirq();
  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_get_filter_mode() {
  uint8_t fnum = (cr3 >> 8) & 0xff;

  LOGCMD("%s: Get Filter Mode fnum %x\n", machine().describe_context(), fnum);
  if (fnum >= MAX_FILTERS) {
    LOGWARN("CD: invalid filter number %02x\n", fnum);
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | ESEL);
    update_hirq();
    return;
  }

  cr1 = cd_stat | (filters[fnum].mode & 0xff);
  cr2 = 0;
  cr3 = 0;
  cr4 = 0;

  hirqreg |= (CMOK | ESEL);
  update_hirq();
}

void saturn_cd_hle_device::cmd_set_filter_connection() {
  // Set Filter Connection
  // FIXME: verify usage of cr3 LSB
  // (false condition?)
  uint8_t fnum = (cr3 >> 8) & 0xff;

  LOGCMD("%s: Set Filter Connection %x => mode %x parm %04x\n",
         machine().describe_context(), fnum, cr1 & 0xf, cr2);
  if (fnum >= MAX_FILTERS) {
    LOGWARN("CD: invalid filter number %02x\n", fnum);
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | ESEL);
    update_hirq();
    return;
  }

  if (cr1 & 1) // set true condition
    filters[fnum].condtrue = (cr2 >> 8) & 0xff;

  if (cr1 & 2) // set false condition
    filters[fnum].condfalse = cr2 & 0xff;

  hirqreg |= (CMOK | ESEL);
  update_hirq();
  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_reset_selector() {
  int i, j;
  // Reset Selector

  LOGCMD("%s: Reset Selector %02x\n", machine().describe_context(), cr1);

  // reset defined buffer partition data, in cr3
  if ((cr1 & 0xff) == 0x00) {
    uint8_t bufnum = cr3 >> 8;
    LOGCMD("\tbufnum %02x\n", bufnum);

    if (bufnum < MAX_FILTERS) {
      for (i = 0; i < MAX_BLOCKS; i++) {
        cd_free_block(partitions[bufnum].blocks[i]);
        partitions[bufnum].blocks[i] = (blockT *)nullptr;
        partitions[bufnum].bnum[i] = 0xff;
      }

      partitions[bufnum].size = -1;
      partitions[bufnum].numblks = 0;
    }

    // TODO: buffer full flag

    if (freeblocks == MAX_BLOCKS) {
      sectorstore = 0;
    }

    hirqreg |= (CMOK | ESEL);
    update_hirq();
    cr_standard_return(cd_stat);
    return;
  }

  // TODO: what follows should delay a bit
  // cfr. indepdayu

  // reset all buffer partitions
  if (BIT(cr1, 2)) {
    for (i = 0; i < MAX_FILTERS; i++) {
      for (j = 0; j < MAX_BLOCKS; j++) {
        cd_free_block(partitions[i].blocks[j]);
        partitions[i].blocks[j] = (blockT *)nullptr;
        partitions[i].bnum[j] = 0xff;
      }

      partitions[i].size = -1;
      partitions[i].numblks = 0;
    }

    buffull = sectorstore = 0;
    buffull_temp_pause = false;
  }

  // TODO: bit 3, initialize all partition output connectors

  // reset all filter conditions
  if (BIT(cr1, 4)) {
    for (i = 0; i < MAX_FILTERS; i++) {
      filters[i].fad = 0;
      filters[i].range = 0xffffffff;
      filters[i].mode = 0;
      filters[i].chan = 0;
      filters[i].smmask = 0;
      filters[i].cimask = 0;
      filters[i].fid = 0;
      filters[i].smval = 0;
      filters[i].cival = 0;
    }
  }

  // reset all filter input connectors
  if (BIT(cr1, 5)) {
    for (i = 0; i < MAX_FILTERS; i++) {
      if (i == cddevicenum)
        cddevice = (filterT *)nullptr;

      if (filters[i].condfalse < MAX_FILTERS)
        filters[i].condfalse = 0xff;
    }
  }

  // reset all true filter output connectors
  if (BIT(cr1, 6)) {
    for (i = 0; i < MAX_FILTERS; i++)
      filters[i].condtrue = i;
  }

  // reset all false filter output connectors
  if (BIT(cr1, 7)) {
    for (i = 0; i < MAX_FILTERS; i++)
      filters[i].condfalse = 0xff;
  }

  hirqreg |= (CMOK | ESEL);
  update_hirq();
  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_get_buffer_size() {
  // get Buffer Size
  cr1 = cd_stat;
  cr2 = (freeblocks > MAX_BLOCKS) ? MAX_BLOCKS : freeblocks;
  cr3 = 0x1800;
  cr4 = 200;
  LOGCMD("%s: Get Buffer Size = %d\n", machine().describe_context(), cr2);
  hirqreg |= (CMOK);
  update_hirq();
}

void saturn_cd_hle_device::cmd_get_buffer_partition_sector_number() {
  // get # sectors used in a buffer

  uint32_t bufnum = cr3 >> 8;

  if (bufnum >= MAX_FILTERS) {
    LOGWARN("CD: invalid buffer number\n");
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK);
    update_hirq();
    return;
  }

  cr1 = cd_stat;
  cr2 = 0;
  cr3 = 0;
  if (cr1 & 0xff || cr2 || cr3 & 0xff || cr4)
    LOGWARN("Get Sector Number issued with params %04x %04x %04x %04x\n", cr1,
            cr2, cr3, cr4);

  // is the partition empty?
  if (partitions[bufnum].size == -1) {
    cr4 = 0;
  } else {
    cr4 = partitions[bufnum].numblks;
    // LOGWARN("Partition %08x %04x\n",bufnum,cr4);
  }

  LOGCMD("%s: Get Sector Number (bufno %d) = %d blocks\n",
         machine().describe_context(), bufnum, cr4);

  // LOGWARN("%04x\n",cr4);
  hirqreg |= (CMOK);
  update_hirq();
}

void saturn_cd_hle_device::cmd_calculate_actual_data_size() {
  // calculate actual size
  uint32_t bufnum = cr3 >> 8;
  uint32_t sectoffs = cr2;
  uint32_t numsect = cr4;

  if (bufnum >= MAX_FILTERS) {
    LOGWARN("CD: invalid buffer number\n");
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | ESEL);
    update_hirq();
    return;
  }

  LOGCMD("%s: Calculate actual size: buf %x offs %x numsect %x\n",
         machine().describe_context(), bufnum, sectoffs, numsect);

  /* cr2 and cr4 are the same offset / sector count pair that the other sector
     commands take, and the loop below walks blocks[] with them, so bound them
     the same way: cr2 is used unmasked here, so an offset of up to 0xffff
     indexed a MAX_BLOCKS (200) entry array and dereferenced whatever pointer
     it found there, and a large cr4 kept the loop walking past the end even
     from a valid offset. */
  cd_getsectoroffsetnum(bufnum, &sectoffs, &numsect);

  calcsize = 0;
  if (partitions[bufnum].size != -1) {
    int32_t i;

    for (i = 0; i < numsect; i++) {
      if (partitions[bufnum].blocks[sectoffs + i]) {
        calcsize += (partitions[bufnum].blocks[sectoffs + i]->size / 2);
      }
    }
  }

  hirqreg |= (CMOK | ESEL);
  update_hirq();
  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_get_actual_data_size() {
  // get actual block size
  cr1 = cd_stat | ((calcsize >> 16) & 0xff);
  cr2 = (calcsize & 0xffff);
  cr3 = 0;
  cr4 = 0;
  LOGCMD("%s: Get actual block size %06x\n", machine().describe_context(),
         calcsize);
  hirqreg |= (CMOK);
  update_hirq();
}

// falcom2
void saturn_cd_hle_device::cmd_get_sector_information() {
  // get sector info
  uint32_t sectoffs = cr2 & 0xff;
  uint32_t bufnum = cr3 >> 8;

  /* sectoffs is masked to 8 bits but blocks[] only holds MAX_BLOCKS (200)
     entries, so 200..255 read past the array and then dereferenced whatever
     was found there; reject those through the existing path. */
  if (bufnum >= MAX_FILTERS || sectoffs >= MAX_BLOCKS ||
      !partitions[bufnum].blocks[sectoffs]) {
    cr1 |= CD_STAT_REJECT & 0xff00;
    hirqreg |= (CMOK | ESEL);
    update_hirq();
    LOGWARN("Get sector info reject\n");
  } else {
    cr1 = cd_stat | ((partitions[bufnum].blocks[sectoffs]->FAD >> 16) & 0xff);
    cr2 = partitions[bufnum].blocks[sectoffs]->FAD & 0xffff;
    cr3 = ((partitions[bufnum].blocks[sectoffs]->fnum & 0xff) << 8) |
          (partitions[bufnum].blocks[sectoffs]->chan & 0xff);
    cr4 = ((partitions[bufnum].blocks[sectoffs]->subm & 0xff) << 8) |
          (partitions[bufnum].blocks[sectoffs]->cinf & 0xff);
    hirqreg |= (CMOK | ESEL);
    update_hirq();
  }
}

void saturn_cd_hle_device::cmd_set_sector_length() {
  // set sector length
  LOGCMD("%s: Set sector length\n", machine().describe_context());

  switch (cr1 & 0xff) {
  case 0:
    sectlenin = 2048;
    break;
  case 1:
    sectlenin = 2336;
    break;
  case 2:
    sectlenin = 2340;
    break;
  case 3:
    sectlenin = 2352;
    break;
  }

  switch ((cr2 >> 8) & 0xff) {
  case 0:
    sectlenout = 2048;
    break;
  case 1:
    sectlenout = 2336;
    break;
  case 2:
    sectlenout = 2340;
    break;
  case 3:
    sectlenout = 2352;
    break;
  }
  hirqreg |= (CMOK | ESEL);
  update_hirq();
  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_get_sector_data() {
  // get sector data
  uint32_t sectnum = cr4;
  uint32_t sectofs = cr2;
  uint32_t bufnum = cr3 >> 8;

  LOGCMD("%s: Get sector data (SN %d SO %d BN %d)\n",
         machine().describe_context(), sectnum, sectofs, bufnum);

  if (bufnum >= MAX_FILTERS) {
    // TODO: find actual SW that does this
    // (may conceal a bigger issue)
    LOGWARN("CD: invalid buffer number\n");
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | EHST);
    update_hirq();
    return;
  }

  cd_getsectoroffsetnum(bufnum, &sectofs, &sectnum);

  if (partitions[bufnum].numblks < sectnum) {
    LOGWARN("CD: buffer is not full %08x %08x\n", partitions[bufnum].numblks,
            sectnum);
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | EHST);
    update_hirq();
    return;
  }

  xfertype32 = XFERTYPE32_GETSECTOR;
  xferoffs = 0;
  xfersect = 0;
  xferdnum = 0;
  xfersectpos = sectofs;
  xfersectnum = sectnum;
  transpart = &partitions[bufnum];

  cd_stat |= CD_STAT_TRANS;
  cr_standard_return(cd_stat);
  hirqreg |= (CMOK | EHST | DRDY);
  update_hirq();
}

void saturn_cd_hle_device::cmd_delete_sector_data() {
  // delete sector data
  uint32_t sectnum = cr4;
  uint32_t sectofs = cr2;
  uint32_t bufnum = cr3 >> 8;
  int32_t i;

  LOGCMD("%s: Delete sector data (SN %d SO %d BN %d)\n",
         machine().describe_context(), sectnum, sectofs, bufnum);

  if (bufnum >= MAX_FILTERS) {
    // TODO: mustn't happen
    LOGWARN("CD: invalid buffer number\n");
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | EHST);
    update_hirq();
    return;
  }

  // pstarcol PS2 does this
  // TODO: verify if implementation is correct
  if (partitions[bufnum].numblks == 0) {
    LOGWARN("CD: buffer is already empty\n");
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | EHST);
    update_hirq();
    return;
  }

  cd_getsectoroffsetnum(bufnum, &sectofs, &sectnum);

  for (i = sectofs; i < (sectofs + sectnum); i++) {
    // pstarcol PS2 tries to delete partial partitions,
    // need to guard against it (otherwise it would crash after first attract
    // cycle) a partition can also hold holes, so check the block pointer as
    // well
    if ((partitions[bufnum].size > 0) &&
        (partitions[bufnum].blocks[i] != nullptr)) {
      partitions[bufnum].size -= partitions[bufnum].blocks[i]->size;
      cd_free_block(partitions[bufnum].blocks[i]);
      partitions[bufnum].blocks[i] = (blockT *)nullptr;
      partitions[bufnum].bnum[i] = 0xff;
    }
  }

  cd_defragblocks(&partitions[bufnum]);

  partitions[bufnum].numblks -= sectnum;

  if (freeblocks == MAX_BLOCKS) {
    sectorstore = 0;
  }

  cd_stat &= ~CD_STAT_TRANS;
  cr_standard_return(cd_stat);
  hirqreg |= (CMOK | EHST);
  update_hirq();
}

void saturn_cd_hle_device::cmd_get_and_delete_sector_data() {
  // get then delete sector data

  uint32_t sectnum = cr4;
  uint32_t sectofs = cr2;
  uint32_t bufnum = cr3 >> 8;

  LOGCMD("%s: Get and delete sector data (SN %d SO %d BN %d)\n",
         machine().describe_context(), sectnum, sectofs, bufnum);

  if (bufnum >= MAX_FILTERS) {
    // TODO: mustn't happen
    LOGWARN("CD: invalid buffer number\n");
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | EHST);
    update_hirq();
    return;
  }

  // we need to calculate this before REJECT condition
  // - shadtusk at startup
  cd_getsectoroffsetnum(bufnum, &sectofs, &sectnum);

  /* yoshimj uses the REJECT status to verify when the data is ready. */
  // TODO: verify again if it's really REJECT or something else
  if (partitions[bufnum].numblks < sectnum) {
    LOGWARN("CD: buffer is not full %08x %08x\n", partitions[bufnum].numblks,
            sectnum);
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | EHST);
    update_hirq();
    return;
  }

  xfertype32 = XFERTYPE32_GETDELETESECTOR;
  xferoffs = 0;
  xfersect = 0;
  xferdnum = 0;
  xfersectpos = sectofs;
  xfersectnum = sectnum;
  transpart = &partitions[bufnum];

  cd_stat |= CD_STAT_TRANS;
  cr_standard_return(cd_stat);
  hirqreg |= (CMOK | EHST | DRDY);
  update_hirq();
}

void saturn_cd_hle_device::cmd_put_sector_data() {
  // aburner2, outrun, fantzone and dmastnx needs this
  // TODO: transfer shouldn't be here

  uint32_t sectnum = cr4 & 0xff;
  uint32_t sectofs = cr2;
  uint32_t bufnum = cr3 >> 8;

  LOGCMD("%s: Put sector data (SN %d SO %d BN %d)\n",
         machine().describe_context(), sectnum, sectofs, bufnum);

  if (bufnum >= MAX_FILTERS) {
    LOGWARN("CD: invalid buffer number\n");
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | EHST);
    update_hirq();
    return;
  }

  xfertype32 = XFERTYPE32_PUTSECTOR;

  /*TODO: eventual errors? */

  cd_getsectoroffsetnum(bufnum, &sectofs, &sectnum);

  cd_stat |= CD_STAT_TRANS;

  xferoffs = 0;
  xfersect = 0;
  xferdnum = 0;
  xfersectpos = sectofs;
  xfersectnum = sectnum;
  transpart = &partitions[bufnum];

  // allocate the blocks
  for (int i = xfersectpos; i < xfersectpos + xfersectnum; i++) {
    transpart->blocks[i] = cd_alloc_block(&transpart->bnum[i]);

    /* cd_alloc_block() returns null once every block is in use. Both the host
       transfer and the deallocation that follows it walk xfersectnum blocks, so
       shorten the transfer instead of dereferencing it - cd_filterdata() gives
       up the same way when the buffer fills up while the disc is being read */
    if (transpart->blocks[i] == nullptr) {
      transpart->bnum[i] = 0xff;
      xfersectnum = i - xfersectpos;
      LOGWARN("CD: put sector data, buffer full after %d sectors\n",
              xfersectnum);
      break;
    }

    if (transpart->size == -1)
      transpart->size = 0;
    transpart->size += transpart->blocks[i]->size;
    transpart->numblks++;
  }

  hirqreg |= (CMOK | DRDY);
  update_hirq();
  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_move_sector_data() {
  // Move Sector Data
  // swordsor and riglord2 use the copy variant of this command
  uint32_t src_filter = (cr3 >> 8) & 0xff;
  uint32_t dst_filter = cr1 & 0xff;
  uint32_t sectnum = cr4 & 0xff;

  LOGCMD("%s: Move sector data (SN %d SO %d BN %d -> %d)\n",
         machine().describe_context(), sectnum, cr2, src_filter, dst_filter);

  if ((src_filter >= MAX_FILTERS) || (dst_filter >= MAX_FILTERS)) {
    LOGWARN("CD: invalid buffer number\n");
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | ECPY);
    update_hirq();
    return;
  }

  /* the count comes from CR4 but a partition only holds MAX_BLOCKS sectors */
  if (sectnum > MAX_BLOCKS) {
    LOGWARN("CD: move sector data, count %d truncated to %d\n", sectnum,
            MAX_BLOCKS);
    sectnum = MAX_BLOCKS;
  }

  for (int i = 0; i < sectnum; i++) {
    blockT *const srcblock = partitions[src_filter].blocks[i];

    // the source partition can hold fewer sectors than we were asked to move
    if (srcblock == nullptr) {
      LOGWARN("CD: move sector data, no source block %d in partition %02x\n", i,
              src_filter);
      break;
    }

    // allocate the dst blocks
    partitions[dst_filter].blocks[i] =
        cd_alloc_block(&partitions[dst_filter].bnum[i]);

    // cd_alloc_block() returns null once every block is in use
    if (partitions[dst_filter].blocks[i] == nullptr) {
      partitions[dst_filter].bnum[i] = 0xff;
      LOGWARN("CD: move sector data, buffer full after %d sectors\n", i);
      break;
    }

    if (partitions[dst_filter].size == -1)
      partitions[dst_filter].size = 0;
    partitions[dst_filter].size += srcblock->size;
    partitions[dst_filter].numblks++;

    /* unlike cmd_copy_sector_data(), which only copies the sector payload and
       leaves the block's FAD and subheader at whatever the recycled block held,
       move the whole block across: Get Sector Information reports those fields
       and the hardware relocates the block rather than re-reading it */
    *partitions[dst_filter].blocks[i] = *srcblock;

    // release the source block, which is what makes this a move and not a copy
    partitions[src_filter].size -= srcblock->size;
    cd_free_block(srcblock);
    partitions[src_filter].blocks[i] = (blockT *)nullptr;
    partitions[src_filter].bnum[i] = 0xff;
    partitions[src_filter].numblks--;
  }

  cd_defragblocks(&partitions[src_filter]);

  hirqreg |= (CMOK | ECPY);
  update_hirq();
  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_copy_sector_data() {
  // swordsor and riglord2 uses this
  // TODO: incomplete
  uint32_t src_filter = (cr3 >> 8) & 0xff;
  uint32_t dst_filter = cr1 & 0xff;
  uint32_t sectnum = cr4 & 0xff;

  if (src_filter >= MAX_FILTERS) {
    LOGWARN("CD: invalid buffer number\n");
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | ECPY);
    update_hirq();
    return;
  }
  if (dst_filter >= MAX_FILTERS) {
    LOGWARN("CD: invalid buffer number\n");
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | ECPY);
    update_hirq();
    return;
  }

  // cd_stat |= CD_STAT_TRANS;
  // transpart = &partitions[dst_filter];

  /* the count comes from CR4 but a partition only holds MAX_BLOCKS sectors */
  if (sectnum > MAX_BLOCKS) {
    LOGWARN("CD: copy sector data, count %d truncated to %d\n", sectnum,
            MAX_BLOCKS);
    sectnum = MAX_BLOCKS;
  }

  for (int i = 0; i < sectnum; i++) {
    blockT *const srcblock = partitions[src_filter].blocks[i];

    // the source partition can hold fewer sectors than we were asked to copy
    if (srcblock == nullptr) {
      LOGWARN("CD: copy sector data, no source block %d in partition %02x\n", i,
              src_filter);
      break;
    }

    // allocate the dst blocks
    partitions[dst_filter].blocks[i] =
        cd_alloc_block(&partitions[dst_filter].bnum[i]);

    // cd_alloc_block() returns null once every block is in use
    if (partitions[dst_filter].blocks[i] == nullptr) {
      partitions[dst_filter].bnum[i] = 0xff;
      LOGWARN("CD: copy sector data, buffer full after %d sectors\n", i);
      break;
    }

    if (partitions[dst_filter].size == -1)
      partitions[dst_filter].size = 0;
    partitions[dst_filter].size += partitions[dst_filter].blocks[i]->size;
    partitions[dst_filter].numblks++;

    // copy data
    for (int j = 0; j < sectlenin; j++)
      partitions[dst_filter].blocks[i]->data[j] = srcblock->data[j];

    // deallocate the src blocks
    // partitions[src_filter].size -= partitions[src_filter].blocks[i]->size;
    // cd_free_block(partitions[src_filter].blocks[i]);
    // partitions[src_filter].blocks[i] = (blockT *)nullptr;
    // partitions[src_filter].bnum[i] = 0xff;
  }

  hirqreg |= (CMOK | ECPY);
  update_hirq();
  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_get_sector_data_copy_or_move_error() {
  // get copy error
  LOGCMD("%s: Get copy error\n", machine().describe_context());
  cr1 = cd_stat;
  cr2 = 0;
  cr3 = 0;
  cr4 = 0;
  hirqreg |= (CMOK);
  update_hirq();
}

void saturn_cd_hle_device::cmd_change_directory() {
  uint32_t temp;
  // change directory
  LOGCMD("%s: Change Directory\n", machine().describe_context());
  hirqreg |= (CMOK | EFLS);
  update_hirq();

  temp = (cr3 & 0xff) << 16;
  temp |= cr4;

  read_new_dir(temp);
  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_read_directory() {
  // Read directory entry
  LOGCMD("%s: Read Directory Entry\n", machine().describe_context());
  //  uint32_t read_dir;

  //  read_dir = ((cr3&0xff)<<16)|cr4;

  if ((cr3 >> 8) < MAX_FILTERS)
    cddevice = &filters[cr3 >> 8];
  else
    cddevice = (filterT *)nullptr;

  // TODO: how to actually read?
  // read_new_dir(read_dir - 2);

  cr_standard_return(cd_stat);
  hirqreg |= (CMOK | EFLS);
  update_hirq();
}

void saturn_cd_hle_device::cmd_get_file_scope() {
  // Get file system scope
  LOGCMD("%s: Get file system scope\n", machine().describe_context());
  hirqreg |= (CMOK | EFLS);
  update_hirq();
  cr1 = cd_stat;
  cr2 = numfiles;  // # of files in directory
  cr3 = 0x0100;    // report directory held
  cr4 = firstfile; // first file id
  LOGWARN("%04x %04x %04x %04x\n", cr1, cr2, cr3, cr4);
}

void saturn_cd_hle_device::cmd_get_target_file_info() {
  uint32_t temp;

  // Get File Info
  LOGCMD("%s: Get File Info\n", machine().describe_context());
  cd_stat |= CD_STAT_TRANS;
  cd_stat &= 0xff00; // clear top byte of return value

  playtype = 0;
  cdda_repeat_count = 0;
  hirqreg |= (CMOK | DRDY);
  update_hirq();

  temp = (cr3 & 0xff) << 16;
  temp |= cr4;

  if (temp == 0xffffff) // special
  {
    xfertype = XFERTYPE_FILEINFO_254;
    xfercount = 0;

    cr1 = cd_stat;
    cr2 = 0x5f4;
    cr3 = 0;
    cr4 = 0;
  } else {
    cr1 = cd_stat;
    cr2 = 6; // 6 words for single file
             // first 4 bytes = FAD address
             // second 4 bytes = length
             // last 4 bytes:
             // - unit size
             // - gap size
             // - file #
             // attributes flags

    cr3 = 0;
    cr4 = 0;

    /* temp is the 24-bit value from CR3/CR4 while curdir only ever holds
       as many entries as make_dir_current() parsed, so validate it before
       indexing: an out-of-range read here lands hundreds of megabytes past
       the allocation.  An ID beyond the directory is reported as an absent
       file rather than joining the not-found path below, because the ISO
       9660 parser here is incomplete and a real title can legitimately ask
       for an ID past it; killing the machine over that would be worse than
       what the unchecked read used to return. */
    bool const found = size_t(temp) < curdir.size();
    direntryT const entry = found ? curdir[temp] : direntryT{};
    if (!found)
      LOGWARN("CD: Get File Info %06x beyond directory (%u entries)\n", temp,
              unsigned(curdir.size()));
    else if (entry.firstfad == 0 || entry.length == 0)
      throw emu_fatalerror("File ID not found in XFERTYPE_FILEINFO_1");
    //      LOGWARN("%08x %08x\n",curdir[temp].firstfad,curdir[temp].length);
    // first 4 bytes = FAD
    put_u32be(&finfbuf[0], entry.firstfad);
    // second 4 bytes = length of file
    put_u32be(&finfbuf[4], entry.length);
    finfbuf[8] = entry.interleave_gap_size;
    finfbuf[9] = entry.file_unit_size;
    finfbuf[10] = temp;
    finfbuf[11] = entry.flags;

    xfertype = XFERTYPE_FILEINFO_1;
    xfercount = 0;
  }
  LOG("   = %04x %04x %04x %04x %04x\n", hirqreg, cr1, cr2, cr3, cr4);
}

void saturn_cd_hle_device::cmd_read_file() {
  // Read File
  LOGCMD("%s: Read File\n", machine().describe_context());
  uint16_t file_offset, file_filter, file_id, file_size;

  file_offset = ((cr1 & 0xff) << 8) | (cr2 & 0xff); /* correct? */
  file_filter = cr3 >> 8;
  file_id = ((cr3 & 0xff) << 16) | (cr4);

  /* curdir is only ever sized by make_dir_current(), so a Read File issued
     before a directory has been parsed - the vector is cleared on reset and
     on stop - or with a file ID beyond the parsed one has no entry to read.
     The index comes straight from CR3/CR4 and curdir is read with unchecked
     operator[], so validate it here; file_filter is validated the same way
     just below.  Acknowledge the command either way, so that software
     waiting on HIRQ is not left hanging, but start no bogus playback. */
  if (size_t(file_id) >= curdir.size()) {
    LOGWARN("CD: Read File %04x beyond directory (%u entries)\n", file_id,
            unsigned(curdir.size()));
    cr_standard_return(cd_stat);
    hirqreg |= (CMOK | EHST);
    update_hirq();
    return;
  }

  file_size =
      ((curdir[file_id].length + sectlenin - 1) / sectlenin) - file_offset;

  cd_change_status(CD_STAT_PLAY | 0x80); // set "cd-rom" bit
  cd_curfad = (curdir[file_id].firstfad + file_offset);
  fadstoplay = file_size;
  if (file_filter < MAX_FILTERS)
    cddevice = &filters[file_filter];
  else
    cddevice = (filterT *)nullptr;

  LOGWARN("Read file %08x (%08x %08x) %02x %d\n", curdir[file_id].firstfad,
          cd_curfad, fadstoplay, file_filter, sectlenin);

  cr_standard_return(cd_stat);

  playtype = 1;

  hirqreg |= (CMOK | EHST);
  update_hirq();
}

void saturn_cd_hle_device::cmd_abort_file() {
  LOGCMD("%s: Abort File\n", machine().describe_context());
  // bios expects "2bc" mask to work against this
  hirqreg |= (CMOK | EFLS);
  update_hirq();
  sectorstore = 0;
  xfertype32 = XFERTYPE32_INVALID;
  xferdnum = 0;
  if (((cd_stat & 0x0f00) != CD_STAT_NODISC) &&
      ((cd_stat & 0x0f00) != CD_STAT_OPEN))
    cd_change_status(CD_STAT_PAUSE); // force to pause

  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_check_copy_protection() {
  // appears to be copy protection check.  needs only to return OK.
  LOGCMD("%s: Verify copy protection\n", machine().describe_context());
  if (((cd_stat & 0x0f00) != CD_STAT_NODISC) &&
      ((cd_stat & 0x0f00) != CD_STAT_OPEN))
    cd_change_status(CD_STAT_PAUSE);

  //   cr1 = cd_stat;  // necessary to pass
  //   cr2 = 0x4;
  //   hirqreg |= (CMOK|EFLS|CSCT);
  if (cr2 == 0x0001) // MPEG card
  {
    hirqreg |= (CMOK | MPED);
    update_hirq();
  } else {
    sectorstore = 1;
    hirqreg = 0x7c5;
    update_hirq();
  }
  cr_standard_return(cd_stat);
}

void saturn_cd_hle_device::cmd_get_disc_region() {
  // get disc region
  LOGCMD("%s: Get disc region\n", machine().describe_context());
  if (cd_stat != CD_STAT_NODISC && cd_stat != CD_STAT_OPEN)
    cd_change_status(CD_STAT_PAUSE);

  cr1 = cd_stat;     // necessary to pass
  if (cr2 == 0x0001) // MPEG card
    cr2 = 0x2;
  else
    cr2 = 0x4; // 0 = No CD, 1 = Audio CD, 2 Regular Data disk (not Saturn), 3
               // pirate disc, 4 Saturn disc
  cr3 = 0;
  cr4 = 0;
  hirqreg |= (CMOK);
  update_hirq();
  //  cr_standard_return(cd_stat);
}

/* ------------------------------------------------------------------------
   MPEG (Video CD / Movie Card) cartridge

   The card is driven entirely through CD block host commands $90-$AF: the
   SH-2 writes parameters into CR1-CR4 and reads decoder status back out of
   the same registers, so from the host side the card is the state in mpegT
   plus this response contract.  The CDB-106 firmware itself does no
   decoding - it relays commands to the two decoder LSIs on the cartridge
   (register windows $0A100000 / $0A180000 on the SH-1 bus) and aggregates
   their status back.

   What is modelled here is that host-visible contract: the command set, the
   parameter encodings, the status report layout and the interrupt causes.
   What is not modelled is the decoding - the raw decoder-LSI register
   encoding is not documented, and MAME has neither a dump of the card's own
   firmware image nor a Video CD data path, so no picture is produced and the
   timecode/PTS counters never advance.
   ------------------------------------------------------------------------ */

void saturn_cd_hle_device::mpeg_bringup() {
  /* Bring-up service hook 34 ($A500), which the cartridge's own firmware image
     supplies.  The image is loaded and run at boot - the CD block reads a
     length and image from the window at $0E000000, copies it to buffer DRAM
     $0907B000 and calls its entry point - so on a unit with a card fitted this
     has already run before the host issues a single MPEG command.  MpegInit
     ($93) runs it again. */
  mpeg.subsys_state = 0x67818022;
  mpeg.lsi_b_control = 0x8209;
  mpeg.lsi_a_event = 0xffffffff;
  mpeg.lsi_a_param[0] = 0x88fe;

  /* the subsystem state long is big-endian at $0F000890, so $0F000891 is its
     bits 23-16 and $0F000892 its bits 15-8: derive both documented flags from
     the constant rather than restating them */
  mpeg.active = ((mpeg.subsys_state >> 8) & 0x80) != 0; // $0F000892 bit 7
  mpeg.decode_stopped =
      ((mpeg.subsys_state >> 16) & 0x01) != 0; // $0F000891 bit 0
}

void saturn_cd_hle_device::mpeg_reset() {
  memset(&mpeg, 0, sizeof(mpeg));

  /* MAME has no MPEG cartridge device and no dump of the card's firmware image,
     so there is nothing to probe.  The interface is modelled as fitted and
     loaded, which is what this driver has always assumed when it answered
     $90-$94; clear these to reproduce a stock unit, on which the firmware's
     extension dispatch table is empty and every MPEG command rejects. */
  mpeg.present = true;
  mpeg.image_loaded = true;

  mpeg_bringup();

  // idle report: both run states stopped, nothing decoded, both buffers empty
  mpeg.video_run = 1;
  mpeg.audio_run = 1;
  mpeg.video_status = 0x1000; // video buffer-partition empty
  mpeg.audio_status = 0x10;   // audio buffer empty
  mpeg.audio_mute = 0x04;     // default, unmuted
  mpeg.pause_time = 1;        // normal playback
  mpeg.freeze_time = 1;       // normal playback

  // NTSC normal-resolution picture geometry until Set Mode says otherwise
  mpeg.scan_mode = 0;
  mpeg.operation_mode = 0;
  mpeg.pic_width = 352;
  mpeg.pic_height = 240;

  // partition $FF disconnects a layer
  for (int i = 0; i < 2; i++) {
    mpeg.layer[i].partition = 0xff;
    mpeg.next_layer[i].partition = 0xff;
  }
}

/* The dispatcher gates every MPEG command on the hardware being present and the
   subsystem being active; MpegInit ($93) is the one exception and skips the
   active check.  A gated-off command still answers with CMOK - only the status
   byte says it was refused. */
bool saturn_cd_hle_device::mpeg_gate(bool need_active) {
  if (mpeg.present && (!need_active || mpeg.active))
    return true;

  LOGWARN("CD: MPEG command %02x refused, %s\n", cr1 >> 8,
          mpeg.present ? "subsystem not initialised" : "no MPEG hardware");

  cr1 = CD_STAT_REJECT;
  cr2 = cr3 = cr4 = 0;
  hirqreg |= CMOK;
  update_hirq();
  return false;
}

void saturn_cd_hle_device::mpeg_standard_return(uint16_t cur_status) {
  /* GetStatus service (ROM index 68, $AEB4), which nearly every MPEG command
     tail-calls.  It seeds CR1:CR2 from the drive's own status responder and
     then ORs in the MPEG fields, which lands on this layout: CR1 high byte is
     the CD status code and its low byte the MPEG operation status, CR2 holds
     the picture-info and audio-status bytes, CR3 the video status word and CR4
     the operation-interval (VSYNC) counter.

     The operation status byte packs the two run states either side of the
     decode-stopped flag: bits 0-2 video, bit 3 stopped, bits 4-6 audio. */
  const uint8_t op_status = (mpeg.video_run & 0x07) |
                            (mpeg.decode_stopped ? 0x08 : 0x00) |
                            ((mpeg.audio_run & 0x07) << 4);

  cr1 = cur_status | op_status;
  cr2 = (mpeg.picture_info << 8) | mpeg.audio_status;
  cr3 = mpeg.video_status;
  cr4 = mpeg.interval;
}

void saturn_cd_hle_device::cmd_get_mpeg_card_boot_rom() {
  // Get MPEG Card Boot ROM ($E2)
  LOGCMD("%s: Get MPEG Card Boot ROM\n", machine().describe_context());

  /* requires MPEG hardware present and a loaded cartridge image.  The firmware
     also requires the subsystem to be active and validates the requested
     address and length against a $07FF window, but it does not document which
     CR holds which, so that check is not implemented here. */
  if (!mpeg.present || !mpeg.image_loaded) {
    LOGWARN("CD: Get MPEG Card Boot ROM with no MPEG cartridge\n");
    cr1 = CD_STAT_REJECT;
    cr2 = cr3 = cr4 = 0;
    hirqreg |= CMOK;
    update_hirq();
    return;
  }

  // TODO: incomplete, needs to actually retrieve from MPEG ROM, just silence
  // popmessage for now.

  cr_standard_return(cd_stat);
  hirqreg |= (CMOK | MPED);
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_get_status() {
  // MPEG Get Status ($90) - read the decoder status and return it
  LOGCMD("%s: MPEG Get Status\n", machine().describe_context());
  if (!mpeg_gate(true))
    return;

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_get_irq() {
  // MPEG Get Interrupt ($91) - read and clear the interrupt-status long
  LOGCMD("%s: MPEG Get Interrupt\n", machine().describe_context());
  if (!mpeg_gate(true))
    return;

  /* the interrupt-status long ($0F000848) is merged into the response and then
     cleared, so build the status report first and let the pending causes take
     over CR3:CR4, which is where the report puts the MPEG status longword */
  mpeg_standard_return(cd_stat);
  cr3 = mpeg.irq_status >> 16;
  cr4 = mpeg.irq_status & 0xffff;
  mpeg.irq_status = 0;

  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_set_irq_mask() {
  // MPEG Set Interrupt Mask ($92) - write CR to the interrupt mask ($0F00084C)
  LOGCMD("%s: MPEG Set Interrupt Mask %04x%04x\n", machine().describe_context(),
         cr3, cr4);
  if (!mpeg_gate(true))
    return;

  mpeg.irq_mask = (uint32_t(cr3) << 16) | cr4;

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_init() {
  // MPEG Init ($93)
  /* the one MPEG command the dispatcher does not gate on the subsystem already
     being active, since this is what activates it - but it still refuses with
     status $FF unless the cartridge's own image is loaded, because that is
     where the command logic lives. */
  const uint16_t param = cr2; // read before the response overwrites the CRs

  LOGCMD("%s: MPEG Init (%04x)\n", machine().describe_context(), param);
  if (!mpeg_gate(false))
    return;

  if (!mpeg.image_loaded) {
    LOGWARN("CD: MPEG Init with no cartridge image loaded\n");
    cr1 = CD_STAT_REJECT;
    cr2 = cr3 = cr4 = 0;
    hirqreg |= CMOK;
    update_hirq();
    return;
  }

  mpeg_bringup();

  hirqreg |= (CMOK | MPED);
  if (param == 0x0001)
    hirqreg |= MPCM;
  update_hirq();

  cr1 = cd_stat;
  cr2 = cr3 = cr4 = 0;
}

void saturn_cd_hle_device::cmd_mpeg_set_mode() {
  /* MPEG Set Mode ($94) - CR1 low byte operation mode (0 normal movie, 1 still
     picture, 2 hi-res movie (unsupported), 3 hi-res still, 4 MPEG sector-buffer
     mode), CR2 high byte decode timing (0 VSYNC-synchronised, 1 host-
     synchronised), CR2 low byte output destination (0 VDP2, 1 host transfer),
     CR3 high byte scan mode.  $FF in any byte keeps the current value. */
  const uint8_t op = cr1 & 0xff;
  const uint8_t timing = cr2 >> 8;
  const uint8_t dest = cr2 & 0xff;
  const uint8_t scan = cr3 >> 8;

  LOGCMD("%s: MPEG Set Mode (op %02x timing %02x dest %02x scan %02x)\n",
         machine().describe_context(), op, timing, dest, scan);
  if (!mpeg_gate(true))
    return;

  if (op != 0xff)
    mpeg.operation_mode = op;
  if (timing != 0xff)
    mpeg.decode_timing = timing;
  if (dest != 0xff)
    mpeg.output_dest = dest;
  if (scan != 0xff)
    mpeg.scan_mode = scan;

  /* picture geometry follows the scan mode: 0/1 are NTSC (352x240 normal,
     704x480 hi-res) and 2/3 are PAL (352x288 / 704x576).  These are the
     per-scan-mode maxima - a stream's encoded picture can be smaller. */
  const bool pal = (mpeg.scan_mode & 0x02) != 0;
  const bool hires = (mpeg.operation_mode == 2) || (mpeg.operation_mode == 3);

  mpeg.pic_width = hires ? 704 : 352;
  mpeg.pic_height = hires ? (pal ? 576 : 480) : (pal ? 288 : 240);

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_play() {
  /* MPEG Play ($95) - CR1 low byte playback mode (0 A/V-synchronised, 1
     independent with no A/V sync), CR2 high byte audio-decoder transfer mode,
     CR2 low byte video-decoder transfer mode (0 automatic, 1 forced), CR3 = 0,
     CR4 low byte a fourth parameter whose meaning is untraced (the host library
     always sends $FF for it).  Same $FF keep-current convention as Set Mode.
     This is the start of decoding. */
  const uint8_t mode = cr1 & 0xff;
  const uint8_t axfer = cr2 >> 8;
  const uint8_t vxfer = cr2 & 0xff;
  const uint8_t param4 = cr4 & 0xff;

  LOGCMD("%s: MPEG Play (mode %02x audio %02x video %02x param4 %02x)\n",
         machine().describe_context(), mode, axfer, vxfer, param4);
  if (!mpeg_gate(true))
    return;

  if (mode != 0xff)
    mpeg.playback_mode = mode;
  if (axfer != 0xff)
    mpeg.audio_xfer = axfer;
  if (vxfer != 0xff)
    mpeg.video_xfer = vxfer;
  if (param4 != 0xff)
    mpeg.play_param4 = param4;

  // both run states move to transferring/playing and decoding is no longer
  // stopped
  mpeg.video_run = 4;
  mpeg.audio_run = 4;
  mpeg.decode_stopped = false;
  mpeg.video_status |= 0x0001;  // decoding
  mpeg.audio_status |= 0x01;    // decoding
  mpeg.video_status &= ~0x1000; // video partition no longer empty
  mpeg.audio_status &= ~0x10;   // audio buffer no longer empty

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_set_decode() {
  /* MPEG Set Decode ($96) - CR1 low byte audio mute ($04 default/unmuted, $01
     mute right, $02 mute left), CR2 pause-time word, CR4 freeze-time word,
     CR3 = 0.  Pause time 0 = pause (frame advance), 1 = normal playback, other
     values = slow-playback interval; freeze time 0 = freeze, 1 = normal
     playback, other values = strobe-playback interval. */
  const uint8_t mute = cr1 & 0xff;
  const uint16_t pause = cr2;
  const uint16_t freeze = cr4;

  LOGCMD("%s: MPEG Set Decode (mute %02x pause %04x freeze %04x)\n",
         machine().describe_context(), mute, pause, freeze);
  if (!mpeg_gate(true))
    return;

  if (mute != 0xff)
    mpeg.audio_mute = mute;
  mpeg.pause_time = pause;
  mpeg.freeze_time = freeze;

  mpeg.video_status &= ~0x000c;
  if (pause == 0)
    mpeg.video_status |= 0x0004; // paused
  if (freeze == 0)
    mpeg.video_status |= 0x0008; // frozen

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_out_decoding_sync() {
  /* MPEG Out Decoding Sync ($97) - CR2 low byte frame bank number.  In
     host-synchronised decode timing (Set Mode decode timing 1) the decoder
     advances one picture per command; stream identification, the sequence
     header and the first picture proceed without it. */
  const uint8_t bank = cr2 & 0xff;

  LOGCMD("%s: MPEG Out Decoding Sync (bank %02x)\n",
         machine().describe_context(), bank);
  if (!mpeg_gate(true))
    return;

  mpeg.display_bank = bank;
  mpeg.tc_frame++;
  mpeg.video_status |= 0x0040; // picture updated

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_get_timecode() {
  // MPEG Get Timecode ($98)
  LOGCMD("%s: MPEG Get Timecode\n", machine().describe_context());
  if (!mpeg_gate(true))
    return;

  /* the record is hour, minute, second and picture (frame) number, plus the
     buffer bank, the picture type (1=I, 2=P, 3=B, 4=D) and the track number.
     The reference does not give the CR packing for those seven bytes, so they
     go out in that order two to a word; with no decoder running they stay at
     whatever the last picture left behind. */
  mpeg_standard_return(cd_stat);
  cr1 = (mpeg.tc_hour << 8) | mpeg.tc_min;
  cr2 = (mpeg.tc_sec << 8) | mpeg.tc_frame;
  cr3 = (mpeg.tc_bank << 8) | mpeg.tc_pic_type;
  cr4 = mpeg.tc_track << 8;

  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_get_pts() {
  // MPEG Get PTS ($99) - the audio presentation timestamp, a 32-bit count
  LOGCMD("%s: MPEG Get PTS\n", machine().describe_context());
  if (!mpeg_gate(true))
    return;

  mpeg_standard_return(cd_stat);
  cr3 = mpeg.pts >> 16;
  cr4 = mpeg.pts & 0xffff;

  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_set_connection() {
  /* MPEG Set Connection ($9A) - CR1 low byte audio connection mode, CR2 audio
     layer:partition, CR3 high byte record selector (0 = current, 1 = next),
     CR3 low byte video connection mode, CR4 video layer:partition.  Connection
     mode bits: $01 switch on EOR, $02 switch on system-end, $04 delete sector,
     $08 ignore PTS, $10 clear VBV, $20 clear VBV + write-back cache, $40
     evaluate the end condition before the back aperture.  Layer 0 = system,
     1 = audio/video.  Picture search $00 off, $80 video, $C0 video plus discard
     audio.  Partition $FF disconnects the layer. */
  const bool next = (cr3 >> 8) != 0;
  const uint8_t amode = cr1 & 0xff;
  const uint16_t arec = cr2;
  const uint8_t vmode = cr3 & 0xff;
  const uint16_t vrec = cr4;

  LOGCMD("%s: MPEG Set Connection (%s audio %02x %04x video %02x %04x)\n",
         machine().describe_context(), next ? "next" : "current", amode, arec,
         vmode, vrec);
  if (!mpeg_gate(true))
    return;

  mpegT::layerT *const dst = next ? mpeg.next_layer : mpeg.layer;

  dst[MPEG_LAYER_AUDIO].conn_mode = amode;
  dst[MPEG_LAYER_AUDIO].layer_search = arec >> 8;
  dst[MPEG_LAYER_AUDIO].partition = arec & 0xff;
  dst[MPEG_LAYER_VIDEO].conn_mode = vmode;
  dst[MPEG_LAYER_VIDEO].layer_search = vrec >> 8;
  dst[MPEG_LAYER_VIDEO].partition = vrec & 0xff;

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_get_connection() {
  // MPEG Get Connection ($9B) - reads the selected records back in the $9A
  // layout
  const bool next = (cr3 >> 8) != 0;

  LOGCMD("%s: MPEG Get Connection (%s)\n", machine().describe_context(),
         next ? "next" : "current");
  if (!mpeg_gate(true))
    return;

  const mpegT::layerT *const src = next ? mpeg.next_layer : mpeg.layer;

  mpeg_standard_return(cd_stat);
  cr1 = (cr1 & 0xff00) | src[MPEG_LAYER_AUDIO].conn_mode;
  cr2 = (src[MPEG_LAYER_AUDIO].layer_search << 8) |
        src[MPEG_LAYER_AUDIO].partition;
  cr3 = (uint16_t(next ? 1 : 0) << 8) | src[MPEG_LAYER_VIDEO].conn_mode;
  cr4 = (src[MPEG_LAYER_VIDEO].layer_search << 8) |
        src[MPEG_LAYER_VIDEO].partition;

  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_change_connection() {
  /* MPEG Change Connection ($9C) - commits the staged next-slot records rather
     than carrying full ones.  CR2 holds the two per-layer selector bytes, low
     byte video and high byte audio; CR3/CR4 carry no field the handler
     evaluates.  Per selector bit 7 set skips the layer and keeps its current
     binding, bit 7 clear commits the layer's next-slot record, and bit 0 set
     additionally requires the layer's busy flag to be clear first.  Committing
     a layer requires its run state to be 4 (playing) and advances it to 5
     (switching). */
  const uint8_t vsel = cr2 & 0xff;
  const uint8_t asel = cr2 >> 8;

  LOGCMD("%s: MPEG Change Connection (video %02x audio %02x)\n",
         machine().describe_context(), vsel, asel);
  if (!mpeg_gate(true))
    return;

  /* beyond the dispatcher's active gate the handler refuses the whole command
     unless $0F000892 bits 1-3 are clear - those are the LSI A/B packet-DMA
     completion bits, and $0F000892 is bits 15-8 of the subsystem state long */
  if (mpeg.subsys_state & 0x0e00) {
    LOGWARN(
        "CD: MPEG Change Connection refused, LSI packet DMA still running\n");
    cr1 = CD_STAT_REJECT;
    cr2 = cr3 = cr4 = 0;
    hirqreg |= CMOK;
    update_hirq();
    return;
  }

  const uint8_t sel[2] = {vsel, asel};

  for (int i = 0; i < 2; i++) {
    if (sel[i] & 0x80)
      continue; // layer skipped, current binding kept

    uint8_t &run = (i == MPEG_LAYER_VIDEO) ? mpeg.video_run : mpeg.audio_run;

    if (run != 4) {
      LOGWARN(
          "CD: MPEG Change Connection, layer %d not playing (run state %d)\n",
          i, run);
      continue;
    }

    mpeg.layer[i] = mpeg.next_layer[i];
    run = 5; // switching
  }

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_set_stream() {
  /* MPEG Set Stream ($9D) - wire layout mirrors Set Connection: CR1 low byte
     audio stream mode, CR2 audio stream:channel, CR3 high byte record selector,
     CR3 low byte video stream mode, CR4 video stream:channel.  Stream mode
     bits: $01 set stream number, $02 identify stream number, $10 set channel
     number, $20 identify channel number.  The stream number validates as <= 31.
   */
  const bool next = (cr3 >> 8) != 0;
  const uint8_t amode = cr1 & 0xff;
  const uint16_t arec = cr2;
  const uint8_t vmode = cr3 & 0xff;
  const uint16_t vrec = cr4;

  LOGCMD("%s: MPEG Set Stream (%s audio %02x %04x video %02x %04x)\n",
         machine().describe_context(), next ? "next" : "current", amode, arec,
         vmode, vrec);
  if (!mpeg_gate(true))
    return;

  if (((arec >> 8) > 31) || ((vrec >> 8) > 31)) {
    LOGWARN("CD: MPEG Set Stream, stream number %d/%d out of range\n",
            arec >> 8, vrec >> 8);
    cr1 = CD_STAT_REJECT;
    cr2 = cr3 = cr4 = 0;
    hirqreg |= CMOK;
    update_hirq();
    return;
  }

  mpegT::layerT *const dst = next ? mpeg.next_layer : mpeg.layer;

  if (amode & 0x01)
    dst[MPEG_LAYER_AUDIO].stream_number = arec >> 8;
  if (amode & 0x10)
    dst[MPEG_LAYER_AUDIO].channel = arec & 0xff;
  if (vmode & 0x01)
    dst[MPEG_LAYER_VIDEO].stream_number = vrec >> 8;
  if (vmode & 0x10)
    dst[MPEG_LAYER_VIDEO].channel = vrec & 0xff;

  dst[MPEG_LAYER_AUDIO].stream_mode = amode;
  dst[MPEG_LAYER_VIDEO].stream_mode = vmode;

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_get_stream() {
  // MPEG Get Stream ($9E) - reads back the Set Stream layout, per layer
  const bool next = (cr3 >> 8) != 0;

  LOGCMD("%s: MPEG Get Stream (%s)\n", machine().describe_context(),
         next ? "next" : "current");
  if (!mpeg_gate(true))
    return;

  const mpegT::layerT *const src = next ? mpeg.next_layer : mpeg.layer;

  mpeg_standard_return(cd_stat);
  cr1 = (cr1 & 0xff00) | src[MPEG_LAYER_AUDIO].stream_mode;
  cr2 = (src[MPEG_LAYER_AUDIO].stream_number << 8) |
        src[MPEG_LAYER_AUDIO].channel;
  cr3 = (uint16_t(next ? 1 : 0) << 8) | src[MPEG_LAYER_VIDEO].stream_mode;
  cr4 = (src[MPEG_LAYER_VIDEO].stream_number << 8) |
        src[MPEG_LAYER_VIDEO].channel;

  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_get_picture_size() {
  // MPEG Get Picture Size ($9F) - horizontal and vertical pixel size
  LOGCMD("%s: MPEG Get Picture Size\n", machine().describe_context());
  if (!mpeg_gate(true))
    return;

  mpeg_standard_return(cd_stat);
  cr3 = mpeg.pic_width;
  cr4 = mpeg.pic_height;

  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_display() {
  // MPEG Display ($A0) - CR2 high byte display switch (0 off, nonzero on),
  // CR2 low byte frame bank number
  const bool on = (cr2 >> 8) != 0;
  const uint8_t bank = cr2 & 0xff;

  LOGCMD("%s: MPEG Display (%s bank %02x)\n", machine().describe_context(),
         on ? "on" : "off", bank);
  if (!mpeg_gate(true))
    return;

  mpeg.display_on = on;
  mpeg.display_bank = bank;

  if (on)
    mpeg.video_status |= 0x0002; // displaying
  else
    mpeg.video_status &= ~0x0002;

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_set_window() {
  /* MPEG Set Window ($A1) - CR1 low byte selects the sub-parameter, and all
     five selectors go through this one command: 0 frame-buffer position, 1
     frame- buffer ratio, 2 display position, 3 display size (an exclusive
     extent), 4 display offset.  CR2 low byte is a change flag, CR3 the X value
     and CR4 the Y value.  Display position places the picture's top-left on
     screen in the decoder's output-raster coordinates, where the X origin sits
     one dot left of the visible frame and the Y origin at the top of the full
     raster, 8 lines above a 224-line frame. */
  const uint8_t sel = cr1 & 0xff;
  const uint8_t flag = cr2 & 0xff;

  LOGCMD("%s: MPEG Set Window (sel %02x flag %02x x %04x y %04x)\n",
         machine().describe_context(), sel, flag, cr3, cr4);
  if (!mpeg_gate(true))
    return;

  if (sel >= 5) {
    LOGWARN("CD: MPEG Set Window, unknown sub-parameter %02x\n", sel);
    cr1 = CD_STAT_REJECT;
    cr2 = cr3 = cr4 = 0;
    hirqreg |= CMOK;
    update_hirq();
    return;
  }

  mpeg.win[sel][0] = cr3;
  mpeg.win[sel][1] = cr4;

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_set_border_color() {
  // MPEG Set Border Color ($A2) - written to LSI shadow +18.  The reference
  // does not give the CR position, so the colour is taken from CR4, the
  // word-sized value register the neighbouring display commands use.
  LOGCMD("%s: MPEG Set Border Color (%04x)\n", machine().describe_context(),
         cr4);
  if (!mpeg_gate(true))
    return;

  mpeg.border_color = cr4;

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_set_fade() {
  /* MPEG Set Fade ($A3) - Y gain and C gain, gated on the LSI-ready flag at
     $0F000890 bit 1, which is bits 31-24 of the subsystem state long.  The
     reference gives the two gains but not their CR positions; they are taken
     from CR2 high and low, the byte pair the other display commands use. */
  const uint8_t ygain = cr2 >> 8;
  const uint8_t cgain = cr2 & 0xff;

  LOGCMD("%s: MPEG Set Fade (Y %02x C %02x)\n", machine().describe_context(),
         ygain, cgain);
  if (!mpeg_gate(true))
    return;

  if (!((mpeg.subsys_state >> 24) & 0x02)) {
    LOGWARN("CD: MPEG Set Fade refused, LSI not ready\n");
    cr1 = CD_STAT_REJECT;
    cr2 = cr3 = cr4 = 0;
    hirqreg |= CMOK;
    update_hirq();
    return;
  }

  mpeg.fade_y = ygain;
  mpeg.fade_c = cgain;

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_set_video_effect() {
  /* MPEG Set Video Effect ($A4) - written to LSI shadow +24.  Interpolation
     bits $01 Y-horizontal, $02 C-horizontal, $04 Y-vertical, $08 C-vertical;
     transparent-bit mode 0 off, 1 luma 64, 2 luma 96, 3 luma 128, $04 magnify
     the transparent area; blur (soft-switch) $01 on.  The CR positions are not
     documented, so the interpolation and transparent bytes are taken from CR2
     and the blur flag from CR4 low. */
  const uint8_t interp = cr2 >> 8;
  const uint8_t transparent = cr2 & 0xff;
  const uint8_t blur = cr4 & 0xff;

  LOGCMD("%s: MPEG Set Video Effect (interp %02x transparent %02x blur %02x)\n",
         machine().describe_context(), interp, transparent, blur);
  if (!mpeg_gate(true))
    return;

  mpeg.video_effect = (interp << 8) | transparent;
  mpeg.display_attr = blur;

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_set_display_attr() {
  // MPEG $A5 - an additional display attribute, a window sub-parameter. Neither
  // the command name nor its parameters were individually confirmed against the
  // host-side command builders, so the CRs are recorded as given.
  LOGCMD("%s: MPEG Set Display Attribute (%04x %04x %04x)\n",
         machine().describe_context(), cr2, cr3, cr4);
  if (!mpeg_gate(true))
    return;

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_get_picture_info() {
  // MPEG $A6 - get image / picture info.  Not individually confirmed; the
  // picture info byte is already carried in CR2 high of every status report.
  LOGCMD("%s: MPEG Get Picture Info\n", machine().describe_context());
  if (!mpeg_gate(true))
    return;

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_read_lsi() {
  /* MPEG $AE - raw read of an LSI shadow register rather than of the decoder
     itself: $0F000854 for the LSI A parameter block and $0F000884 for the LSI B
     control shadow.  CR1 bit 1 selects the window, matching $AF. */
  const bool lsi_b = (cr1 & 0x02) != 0;
  const uint8_t reg = (cr2 & 0xff) & ~1;

  LOGCMD("%s: MPEG Read LSI %s register %02x\n", machine().describe_context(),
         lsi_b ? "B" : "A", reg);
  if (!mpeg_gate(true))
    return;

  uint16_t value = 0;

  if (lsi_b)
    value = mpeg.lsi_b_control;
  else if ((reg >> 1) <
           (sizeof(mpeg.lsi_a_param) / sizeof(mpeg.lsi_a_param[0])))
    value = mpeg.lsi_a_param[reg >> 1];
  else
    LOGWARN("CD: MPEG Read LSI A register %02x outside the parameter block\n",
            reg);

  mpeg_standard_return(cd_stat);
  cr4 = value;

  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_mpeg_write_lsi() {
  /* MPEG $AF - raw write of CR4 into window[CR2 low byte & ~1].  CR1 bit 1
     selects the window (LSI A at $0A100000, LSI B at $0A180000) and CR1 bit 0
     is read-back mode.  This is the escape hatch a cartridge image or a
     diagnostic uses to poke the decoder LSIs directly; with no decoder modelled
     the value lands in the shadow the read-back command reports. */
  const bool lsi_b = (cr1 & 0x02) != 0;
  const bool readback = (cr1 & 0x01) != 0;
  const uint8_t reg = (cr2 & 0xff) & ~1;
  const uint16_t value = cr4;

  LOGCMD("%s: MPEG Write LSI %s register %02x = %04x%s\n",
         machine().describe_context(), lsi_b ? "B" : "A", reg, value,
         readback ? " (read-back)" : "");
  if (!mpeg_gate(true))
    return;

  if (lsi_b)
    mpeg.lsi_b_control = value;
  else if ((reg >> 1) <
           (sizeof(mpeg.lsi_a_param) / sizeof(mpeg.lsi_a_param[0])))
    mpeg.lsi_a_param[reg >> 1] = value;
  else
    LOGWARN("CD: MPEG Write LSI A register %02x outside the parameter block\n",
            reg);

  mpeg_standard_return(cd_stat);
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cd_exec_command() {
  if (cr1 != 0 && ((cr1 & 0xff00) != 0x5100) && ((cr1 & 0xff00) != 0x5200) &&
      ((cr1 & 0xff00) != 0x5300) && 1)
    LOGCMDV("Command exec %04x %04x %04x %04x %04x (stat %04x)\n", hirqreg, cr1,
            cr2, cr3, cr4, cd_stat);

  // execute the command even if CD isn't in tray
  // - BIOS will otherwise draw VDP2 garbage if tray is closed (seen commands:
  // 0x01, 0x75, 0x67)
  // if(!m_cdrom_image->exists() && ((cr1 >> 8) & 0xff) != 0x00) {
  //	hirqreg |= (CMOK);
  //	return;
  //}

  switch ((cr1 >> 8) & 0xff) {
  case 0x00:
    cmd_get_status();
    break;
  case 0x01:
    cmd_get_hw_info();
    break;
  case 0x02:
    cmd_get_toc();
    break;
  case 0x03:
    cmd_get_session_info();
    break;
  case 0x04:
    cmd_init_cdsystem();
    break;
  case 0x06:
    cmd_end_data_transfer();
    break;

  case 0x10:
    cmd_play_disc();
    break;
  case 0x11:
    cmd_seek_disc();
    break;
  case 0x12:
    cmd_ffwd_rew_disc();
    break;

  case 0x20:
    cmd_get_subcode_q_rw_channel();
    break;

  case 0x30:
    cmd_set_cddevice_connection();
    break;
  case 0x31:
    cmd_get_cddevice_connection();
    break;
  case 0x32:
    cmd_last_buffer_destination();
    break;

  case 0x40:
    cmd_set_filter_range();
    break;
  case 0x41:
    cmd_get_filter_range();
    break;
  case 0x42:
    cmd_set_filter_subheader_conditions();
    break;
  case 0x43:
    cmd_get_filter_subheader_conditions();
    break;
  case 0x44:
    cmd_set_filter_mode();
    break;
  case 0x45:
    cmd_get_filter_mode();
    break;
  case 0x46:
    cmd_set_filter_connection();
    break;
  case 0x48:
    cmd_reset_selector();
    break;

  case 0x50:
    cmd_get_buffer_size();
    break;
  case 0x51:
    cmd_get_buffer_partition_sector_number();
    break;
  case 0x52:
    cmd_calculate_actual_data_size();
    break;
  case 0x53:
    cmd_get_actual_data_size();
    break;
  case 0x54:
    cmd_get_sector_information();
    break;
    //      case 0x55: cmd_execute_frame_address_search()
    //      case 0x56: cmd_get_frame_address_search_results()

  case 0x60:
    cmd_set_sector_length();
    break;
  case 0x61:
    cmd_get_sector_data();
    break;
  case 0x62:
    cmd_delete_sector_data();
    break;
  case 0x63:
    cmd_get_and_delete_sector_data();
    break;
  case 0x64:
    cmd_put_sector_data();
    break;
  case 0x65:
    cmd_move_sector_data();
    break;
  case 0x66:
    cmd_copy_sector_data();
    break;
  case 0x67:
    cmd_get_sector_data_copy_or_move_error();
    break;

  case 0x70:
    cmd_change_directory();
    break;
  case 0x71:
    cmd_read_directory();
    break;
  case 0x72:
    cmd_get_file_scope();
    break;
  case 0x73:
    cmd_get_target_file_info();
    break;
  case 0x74:
    cmd_read_file();
    break;
  case 0x75:
    cmd_abort_file();
    break;

  // following are MPEG commands, enough to get Sport Fishing to do something
  case 0x90:
    cmd_mpeg_get_status();
    break;
  case 0x91:
    cmd_mpeg_get_irq();
    break;
  case 0x92:
    cmd_mpeg_set_irq_mask();
    break;
  case 0x93:
    cmd_mpeg_init();
    break;
  case 0x94:
    cmd_mpeg_set_mode();
    break;
  case 0x95:
    cmd_mpeg_play();
    break;
  case 0x96:
    cmd_mpeg_set_decode();
    break;
  case 0x97:
    cmd_mpeg_out_decoding_sync();
    break;
  case 0x98:
    cmd_mpeg_get_timecode();
    break;
  case 0x99:
    cmd_mpeg_get_pts();
    break;
  case 0x9a:
    cmd_mpeg_set_connection();
    break;
  case 0x9b:
    cmd_mpeg_get_connection();
    break;
  case 0x9c:
    cmd_mpeg_change_connection();
    break;
  case 0x9d:
    cmd_mpeg_set_stream();
    break;
  case 0x9e:
    cmd_mpeg_get_stream();
    break;
  case 0x9f:
    cmd_mpeg_get_picture_size();
    break;
  case 0xa0:
    cmd_mpeg_display();
    break;
  case 0xa1:
    cmd_mpeg_set_window();
    break;
  case 0xa2:
    cmd_mpeg_set_border_color();
    break;
  case 0xa3:
    cmd_mpeg_set_fade();
    break;
  case 0xa4:
    cmd_mpeg_set_video_effect();
    break;
  case 0xa5:
    cmd_mpeg_set_display_attr();
    break;
  case 0xa6:
    cmd_mpeg_get_picture_info();
    break;

  /* $A7-$AD have no ROM default handler, so the dispatcher rejects them until
     a cartridge extension image installs one - they are not unknown commands
     and must not fall through to the unknown-command path */
  case 0xa7:
  case 0xa8:
  case 0xa9:
  case 0xaa:
  case 0xab:
  case 0xac:
  case 0xad:
    LOGWARN("CD: MPEG command %02x has no handler\n", cr1 >> 8);
    cr1 = CD_STAT_REJECT;
    cr2 = cr3 = cr4 = 0;
    hirqreg |= CMOK;
    update_hirq();
    break;

  // $AE/$AF are the raw decoder-LSI escape hatch
  case 0xae:
    cmd_mpeg_read_lsi();
    break;
  case 0xaf:
    cmd_mpeg_write_lsi();
    break;

  case 0xe0:
    cmd_check_copy_protection();
    break;
  case 0xe1:
    cmd_get_disc_region();
    break;
  case 0xe2:
    cmd_get_mpeg_card_boot_rom();
    break;

  default:
    LOG("Unknown command %04x\n", cr1 >> 8);
    popmessage("saturn_cd_hle.cpp: Unknown command %02x", cr1 >> 8);

    hirqreg |= (CMOK);
    update_hirq();
    break;
  }
}

TIMER_CALLBACK_MEMBER(saturn_cd_hle_device::sh1_command_cb) {
  // yield current command until we managed to handle the new status change
  // - cnc* definitely wants former at FMV playbacks
  // TODO: do we need to yield for seek as well? asenna dislikes the idea
  if (m_status_change_in_progress) {
    m_sh1_timer->adjust(attotime::from_hz(get_timing_command()));
    return;
  }

  if ((cmd_pending == 0xf) && (!(hirqreg & CMOK)))
    cd_exec_command();
}

TIMER_CALLBACK_MEMBER(saturn_cd_hle_device::cd_sector_cb) {
  // m_sector_timer->reset();

  // popmessage("%08x %08x %d %d",cd_curfad,fadstoplay,cmd_pending,cd_speed);

  cd_playdata();

  // pickup travel is physical, so a SEEK always ticks at the real sector
  // rate; only streaming follows the cd_speed multiplier
  if ((cd_stat & 0x0f00) == CD_STAT_SEEK)
    m_sector_timer->adjust(attotime::from_hz(75));
  else if (m_cdrom_image->get_track_type(m_cdrom_image->get_track(cd_curfad)) ==
           cdrom_file::CD_TRACK_AUDIO)
    m_sector_timer->adjust(
        attotime::from_hz(75)); // 75 sectors / second = 150kBytes/second (cdda
                                // track ignores cd_speed setting)
  else
    m_sector_timer->adjust(attotime::from_hz(
        75 * cd_speed)); // 75 / 150 sectors / second = 150 / 300kBytes/second

  /* The subcode Q buffer is refreshed and SCDQ raised on every periodic
     update, exactly as mednafen's CDB does at the end of its periodic
     handler; it is not gated on the data buffer having room (daytonau needs
     the flag while the buffer is full, and clearing a pending SCDQ could
     drop an update the host has not read yet).  The existence guard stays
     out: with no disc the status reports NODISC and the host masks SCDQ. */
  hirqreg |= SCDQ;
  update_hirq();

  if (cd_stat & CD_STAT_PERI) {
    cr_standard_return(cd_stat);
  }
}

saturn_cd_hle_device::blockT *
saturn_cd_hle_device::cd_alloc_block(uint8_t *blknum) {
  int32_t i;

  // search the 200 available blocks for a free one
  for (i = 0; i < MAX_BLOCKS; i++) {
    if (blocks[i].size == -1) {
      freeblocks--;
      if (freeblocks <= 0) {
        buffull = 1;
        LOGWARN("buffull in cd_alloc_block\n");
      }

      blocks[i].size = sectlenin;
      *blknum = i;

      LOG("Allocating block %d, size %x\n", i, sectlenin);

      return &blocks[i];
    }
  }

  buffull = 1;
  return (blockT *)nullptr;
}

void saturn_cd_hle_device::cd_free_block(blockT *blktofree) {
  int32_t i;

  LOG("cd_free_block: %x\n", (uint32_t)(uintptr_t)blktofree);

  if (blktofree == nullptr) {
    return;
  }

  for (i = 0; i < MAX_BLOCKS; i++) {
    if (&blocks[i] == blktofree) {
      LOG("Freeing block %d\n", i);
    }
  }

  blktofree->size = -1;
  freeblocks++;
  buffull = 0;
  hirqreg &= ~BFUL;
  update_hirq();
}

void saturn_cd_hle_device::cd_getsectoroffsetnum(uint32_t bufnum,
                                                 uint32_t *sectoffs,
                                                 uint32_t *sectnum) {
  /* Two sentinel values are defined for the sector commands: a sector offset of
     0xffff means "the last sector in the partition", and a sector count of
     0xffff means "from the offset to the end of the partition".  Both are
     resolved here so that every caller can walk blocks[] with plain indices.

     They are independent rather than mutually exclusive, so the count has to be
     expanded *after* the offset: a command asking for the last sector through
     to the end then correctly resolves to a single sector instead of leaving
     the 0xffff count to be truncated by the range check below.  Callers
     validate the buffer number against MAX_FILTERS before getting here, and
     numblks is capped at MAX_BLOCKS by cd_alloc_block(), so numblks - 1 is
     always a valid index. */
  const uint32_t numblks = partitions[bufnum].numblks;

  if (*sectoffs == 0xffff)
    *sectoffs = (numblks > 0) ? (numblks - 1) : 0;

  if (*sectnum == 0xffff)
    *sectnum = (numblks > *sectoffs) ? (numblks - *sectoffs) : 0;

  /* both values come straight out of the command registers and every caller
     walks blocks[] with them, so keep them inside the array; an offset past the
     end of the partition is out of range and the request is ignored */
  if (*sectoffs >= MAX_BLOCKS) {
    LOGWARN("CD: sector offset %04x out of range, ignoring the request\n",
            *sectoffs);
    *sectnum = 0;
  } else if (*sectnum > MAX_BLOCKS - *sectoffs) {
    LOGWARN("CD: sector count %04x truncated to %d\n", *sectnum,
            MAX_BLOCKS - *sectoffs);
    *sectnum = MAX_BLOCKS - *sectoffs;
  }
}

void saturn_cd_hle_device::cd_defragblocks(partitionT *part) {
  uint32_t i, j;
  blockT *temp;
  uint8_t temp2;

  for (i = 0; i < (MAX_BLOCKS - 1); i++) {
    for (j = i + 1; j < MAX_BLOCKS; j++) {
      if ((part->blocks[i] == (blockT *)nullptr) &&
          (part->blocks[j] != (blockT *)nullptr)) {
        temp = part->blocks[i];
        part->blocks[i] = part->blocks[j];
        part->blocks[j] = temp;

        temp2 = part->bnum[i];
        part->bnum[i] = part->bnum[j];
        part->bnum[j] = temp2;
      }
    }
  }
}

// iso9660 parsing
void saturn_cd_hle_device::read_new_dir(uint32_t fileno) {
  int foundpd, i;
  uint32_t cfad; //, dirfad;
  uint8_t sect[2048];

  if (fileno == 0xffffff) {
    cfad = 166; // first sector of directory as per iso9660 specs

    foundpd = 0; // search for primary vol. desc
    while ((!foundpd) && (cfad < 200)) {
      if (sectlenin != 2048)
        popmessage("saturn_cd_hle.cpp: read_new_dir with Sector Length %d (0)",
                   sectlenin);

      memset(sect, 0, 2048);
      cd_readblock(cfad++, sect);

      if ((sect[1] == 'C') && (sect[2] == 'D') && (sect[3] == '0') &&
          (sect[4] == '0') && (sect[5] == '1')) {
        switch (sect[0]) {
        case 0: // boot record
          break;

        case 1: // primary volume descriptor
          foundpd = 1;
          break;

        case 2: // secondary volume descriptor
          break;

        case 3: // volume section descriptor
          break;

        case 0xff:
          cfad = 200;
          break;
        }
      }
    }

    // got primary volume descriptor
    if (foundpd) {
      // dirfad = get_u32le(&sect[140]);
      // dirfad += 150;

      // parse root entry
      curroot.firstfad = get_u32le(&sect[158]);
      curroot.firstfad += 150;
      curroot.length = get_u32le(&sect[166]);
      curroot.flags = sect[181];
      /* the identifier length comes off the disc and ISO 9660 allows up to
         255 bytes there - a Joliet name of 64 UCS-2 characters plus its
         ";1" version suffix is already 132 - so clamp it to what name[]
         holds, leaving room for the terminator that follows the loop.
         Unclamped this overran curroot, a device member, by up to 128
         bytes. */
      int const idlen =
          std::min<int>(sect[188], int(std::size(curroot.name)) - 1);
      for (i = 0; i < idlen; i++) {
        curroot.name[i] = sect[189 + i];
      }
      curroot.name[i] = '\0'; // terminate

      // easy to fix, but make sure we *need* to first
      if (curroot.length > MAX_DIR_SIZE) {
        LOGWARN("ERROR: root directory too big (%d)\n", curroot.length);
      }

      // done with all that, read the root directory now
      make_dir_current(curroot.firstfad);
    }
  } else {
    /* fileno is the 24-bit value from CR3/CR4 while curdir only ever holds
       as many entries as make_dir_current() parsed, so an out-of-range one
       would read hundreds of megabytes past the allocation.  Leave the
       current directory alone: cmd_change_directory() has already reported
       CMOK|EFLS and calls cr_standard_return() on the way out. */
    if (size_t(fileno) >= curdir.size()) {
      LOGWARN("CD: Change Directory %06x beyond directory (%u entries)\n",
              fileno, unsigned(curdir.size()));
      return;
    }

    if (curdir[fileno].length > MAX_DIR_SIZE) {
      LOGWARN("ERROR: new directory too big (%d)!\n", curdir[fileno].length);
    }
    make_dir_current(curdir[fileno].firstfad);
  }
}

// makes the directory pointed to by FAD current
// https://wiki.osdev.org/ISO_9660 for a detailed reference
void saturn_cd_hle_device::make_dir_current(uint32_t fad) {
  uint32_t i;
  uint32_t nextent, numentries;
  std::vector<uint8_t> sect(MAX_DIR_SIZE);
  direntryT *curentry;

  memset(&sect[0], 0, MAX_DIR_SIZE);
  if (sectlenin != 2048)
    popmessage("saturn_cd_hle.cpp: make_dir_current Sector Length %d (1)",
               sectlenin);

  for (i = 0; i < (curroot.length / 2048); i++) {
    cd_readblock(fad + i, &sect[2048 * i]);
  }

  nextent = 0;
  numentries = 0;

  // on directories bigger than 1 FAD we have to keep track of gaps
  // i.e. a sector will end with a 0 marker but continues in the next sector.
  // cfr. chaossd and sengblad
  u32 sector_number = 0;
  while (nextent < MAX_DIR_SIZE) {
    if (sect[nextent]) {
      nextent += sect[nextent];
      numentries++;
    } else {
      if (sector_number < curroot.length) {
        sector_number += 0x800;
        nextent = sector_number;
      } else
        nextent = MAX_DIR_SIZE;
    }
  }

  curdir.resize(numentries);
  curentry = &curdir[0];
  numfiles = numentries;

  sector_number = 0;
  nextent = 0;
  while (numentries) {
    // [0] record size
    // [1] xa record size
    // [2-5] lba
    // [6-9] (lba?)
    // [10-13] size
    // [14-17] (size?)
    // [18] year
    // [19] month
    // [20] day
    // [21] hour
    // [22] minute
    // [23] second
    // [24] gmt offset
    // [25] flags
    // [26] file unit size
    // [27] interleave gap size
    // [28-29] volume sequencer number
    // [30-31] (volume sequencer number?)
    // [32] name character size
    // [33+ ...] file name

    if (!sect[nextent + 0] && sector_number < curroot.length) {
      sector_number += 0x800;
      nextent = sector_number;
      continue;
    }

    curentry->record_size = sect[nextent + 0];
    curentry->xa_record_size = sect[nextent + 1];
    curentry->firstfad = get_u32le(&sect[nextent + 2]);
    curentry->firstfad += 150;
    curentry->length = get_u32le(&sect[nextent + 10]);
    curentry->year = sect[nextent + 18];
    curentry->month = sect[nextent + 19];
    curentry->day = sect[nextent + 20];
    curentry->hour = sect[nextent + 21];
    curentry->minute = sect[nextent + 22];
    curentry->second = sect[nextent + 23];
    curentry->gmt_offset = sect[nextent + 24];
    curentry->flags = sect[nextent + 25];
    curentry->file_unit_size = sect[nextent + 26];
    curentry->interleave_gap_size = sect[nextent + 27];
    curentry->volume_sequencer_number = get_u16le(&sect[nextent + 28]);

    /* as above, and also stop the source read at the end of sect[] - a record
       starting in the last bytes of a maximum size directory would otherwise
       read up to 287 bytes past the allocation.  Unclamped, the copy overran
       name[] into the fields of the next curdir element, or past the end of
       the vector's allocation for the last one. */
    uint32_t const nameroom =
        (nextent + 33 < MAX_DIR_SIZE) ? (MAX_DIR_SIZE - (nextent + 33)) : 0;
    uint32_t const idlen = std::min<uint32_t>(
        sect[nextent + 32],
        std::min<uint32_t>(uint32_t(std::size(curentry->name)) - 1, nameroom));
    for (i = 0; i < idlen; i++) {
      curentry->name[i] = sect[nextent + 33 + i];
    }
    curentry->name[i] = '\0'; // terminate
    // printf("%d: %08x %08x %s %d/%d/%d\n", nextent,
    // curentry->firstfad,curentry->length,curentry->name,curentry->year,curentry->month,curentry->day);

    nextent += sect[nextent];
    curentry++;
    numentries--;
  }

  for (i = 0; i < numfiles; i++) {
    if (!(curdir[i].flags & 0x02)) {
      firstfile = i;
      i = numfiles;
    }
  }
}

void saturn_cd_hle_device::device_stop() { curdir.clear(); }

void saturn_cd_hle_device::cd_readTOC(void) {
  int i, ntrks, tocptr, fad;

  xfertype = XFERTYPE_TOC;
  xfercount = 0;

  if (m_cdrom_image->exists()) {
    ntrks = m_cdrom_image->get_last_track();
  } else {
    ntrks = 0;
  }

  // data format for Saturn TOC:
  // no header.
  // 4 bytes per track
  // top nibble of first byte is CTRL info
  // low nibble is ADR
  // next 3 bytes are FAD address (LBA + 150)
  // there are always 99 track entries (0-98)
  // unused tracks are ffffffff.
  // entries 99-101 are metadata

  tocptr = 0; // starting point of toc entries

  for (i = 0; i < ntrks; i++) {
    if (m_cdrom_image->exists()) {
      tocbuf[tocptr] = sega_cdrom_get_adr_control(i);
    } else {
      tocbuf[tocptr] = 0xff;
    }

    if (m_cdrom_image->exists()) {
      fad = m_cdrom_image->get_track_start(i) + 150;

      put_u24be(&tocbuf[tocptr + 1], fad);
    } else {
      tocbuf[tocptr + 1] = 0xff;
      tocbuf[tocptr + 2] = 0xff;
      tocbuf[tocptr + 3] = 0xff;
    }

    tocptr += 4;
  }

  // fill in the rest
  for (; i < 99; i++) {
    tocbuf[tocptr] = 0xff;
    tocbuf[tocptr + 1] = 0xff;
    tocbuf[tocptr + 2] = 0xff;
    tocbuf[tocptr + 3] = 0xff;

    tocptr += 4;
  }

  // tracks 99-101 are special metadata
  // $$$FIXME: what to do with the address info for these?
  tocptr = 99 * 4;
  tocbuf[tocptr] = tocbuf[0]; // get ctrl/adr from first track
  tocbuf[tocptr + 1] = 1;     // first track's track #
  tocbuf[tocptr + 2] = 0;
  tocbuf[tocptr + 3] = 0;

  /* get_last_track() returns a track count, so (ntrks-1)*4 is the last
     track's entry - but the count is 0 with no disc present, and both
     cmd_get_toc() and cmd_get_session_info() call this without checking for
     one, which made the index -4 and read four bytes in front of tocbuf.
     Report the 0xff filler this format already uses for unused track
     entries, which is what every entry is when there are no tracks. */
  tocbuf[tocptr + 4] =
      (ntrks > 0) ? tocbuf[(ntrks - 1) * 4] : 0xff; // ditto for last track
  tocbuf[tocptr + 5] = ntrks;                       // last track's track #
  tocbuf[tocptr + 6] = 0;
  tocbuf[tocptr + 7] = 0;

  // get total disc length (start of lead-out)
  fad = m_cdrom_image->get_track_start(0xaa) + 150;

  tocbuf[tocptr + 8] = tocbuf[0];
  put_u24be(&tocbuf[tocptr + 9], fad);
}

saturn_cd_hle_device::partitionT *
saturn_cd_hle_device::cd_filterdata(filterT *flt, int trktype, uint8_t *p_ok) {
  int match, keepgoing;
  partitionT *filterprt;

  LOG("cd_filterdata, trktype %d\n", trktype);
  match = 1;
  keepgoing = 2;
  lastbuf = flt->condtrue;

  // loop on the filters
  do {
    // FAD range check?
    // reject and try on the other filter connection
    // - sfz2 and sonicjamj wouldn't repeat BGMs properly
    // - timegal, falcom2 also uses this at very least
    if (flt->mode & 0x40) {
      if ((cd_curfad < flt->fad) || (cd_curfad >= (flt->fad + flt->range))) {
        LOGWARN("curfad reject %08x %08x %08x %08x\n", cd_curfad, fadstoplay,
                flt->fad, flt->fad + flt->range);
        match = 0;
        // lastbuf = flt->condfalse;
        // flt = &filters[lastbuf];
      }
    }

    if ((trktype != cdrom_file::CD_TRACK_AUDIO) && (curblock.data[15] == 2)) {
      if (flt->mode & 1) // file number
      {
        if (curblock.fnum != flt->fid) {
          LOGWARN("fnum reject\n");
          match = 0;
        }
      }

      if (flt->mode & 2) // channel number
      {
        if (curblock.chan != flt->chan) {
          LOGWARN("channel number reject\n");
          match = 0;
        }
      }

      if (flt->mode & 4) // sub mode
      {
        if ((curblock.subm & flt->smmask) != flt->smval) {
          LOGWARN("sub mode reject\n");
          match = 0;
        }
      }

      if (flt->mode & 8) // coding information
      {
        if ((curblock.cinf & flt->cimask) != flt->cival) {
          LOGWARN("coding information reject\n");
          match = 0;
        }
      }

      if (flt->mode & 0x10) // reverse subheader conditions
      {
        // TODO: this may not play well with curfad rejection
        match ^= 1;
      }
    }

    if (match) {
      // lastbuf = flt->condtrue;
      // filterprt = &partitions[lastbuf];
      //  we're done
      keepgoing = 0;
    } else {
      lastbuf = flt->condfalse;

      // reject sector if no match on either connector
      if ((lastbuf == 0xff) || (keepgoing == 0)) {
        *p_ok = 0;
        return (partitionT *)nullptr;
      }

      // try again using the filter that was on the "false" connector
      flt = &filters[lastbuf];
      match = 1;

      // and exit if we fail
      keepgoing--;
    }
  } while (keepgoing);

  filterprt = &partitions[lastbuf];

  // a partition holds at most MAX_BLOCKS blocks, and blocks[]/bnum[] are
  // indexed here before cd_alloc_block() gets any chance to report
  // exhaustion - bnum[MAX_BLOCKS] is followed immediately by numblks, so an
  // overfull partition would scribble on its own block count and then on the
  // next partition. cmd_move_sector_data() and cmd_copy_sector_data() already
  // bail out when the buffer fills, and software does get there: see the DRDY
  // note at the top of this file.
  if (filterprt->numblks >= MAX_BLOCKS) {
    LOGWARN("CD: filter buffer full after %d blocks\n", MAX_BLOCKS);
    *p_ok = 0;
    return (partitionT *)nullptr;
  }

  // try to allocate a block
  filterprt->blocks[filterprt->numblks] =
      cd_alloc_block(&filterprt->bnum[filterprt->numblks]);

  // did the allocation succeed?
  if (filterprt->blocks[filterprt->numblks] == (blockT *)nullptr) {
    *p_ok = 0;
    return (partitionT *)nullptr;
  }

  // copy working block to the newly allocated one
  memcpy(filterprt->blocks[filterprt->numblks], &curblock, sizeof(blockT));

  // and massage the data format a bit
  switch (curblock.size) {
  case 2048: // user data
    if (curblock.data[15] == 2) {
      // mode 2
      memcpy(&filterprt->blocks[filterprt->numblks]->data[0],
             &curblock.data[24], curblock.size);
    } else {
      // mode 1
      memcpy(&filterprt->blocks[filterprt->numblks]->data[0],
             &curblock.data[16], curblock.size);
    }
    break;

  case 2324: // Mode 2 Form 2 data
    memcpy(&filterprt->blocks[filterprt->numblks]->data[0], &curblock.data[24],
           curblock.size);
    break;

  case 2336: // Mode 2 Form 2 skip sync/header
    memcpy(&filterprt->blocks[filterprt->numblks]->data[0], &curblock.data[16],
           curblock.size);
    break;

  case 2340: // Mode 2 Form 2 skip sync only
    memcpy(&filterprt->blocks[filterprt->numblks]->data[0], &curblock.data[12],
           curblock.size);
    break;

  case 2352: // want all data, it's already done, so don't do it again :)
    break;
  }

  // update the status of the partition
  if (filterprt->size == -1)
    filterprt->size = 0;

  filterprt->size += filterprt->blocks[filterprt->numblks]->size;
  filterprt->numblks++;

  *p_ok = 1;
  return filterprt;
}

// read a single sector off the CD, applying the current filter(s) as necessary
saturn_cd_hle_device::partitionT *
saturn_cd_hle_device::cd_read_filtered_sector(int32_t fad, uint8_t *p_ok) {
  int trktype;

  if ((cddevice != nullptr) && (!buffull)) {
    // find out the track's type
    trktype =
        m_cdrom_image->get_track_type(m_cdrom_image->get_track(fad - 150));

    // now get a raw 2352 byte sector - if it's mode 1, get mode1_raw
    if ((trktype == cdrom_file::CD_TRACK_MODE1) ||
        (trktype == cdrom_file::CD_TRACK_MODE1_RAW)) {
      m_cdrom_image->read_data(fad - 150, curblock.data,
                               cdrom_file::CD_TRACK_MODE1_RAW);
    } else if (trktype != cdrom_file::CD_TRACK_AUDIO) // if not audio it must be
                                                      // mode 2 so get mode2_raw
    {
      m_cdrom_image->read_data(fad - 150, curblock.data,
                               cdrom_file::CD_TRACK_MODE2_RAW);
    } else {
      m_cdrom_image->read_data(fad - 150, curblock.data,
                               cdrom_file::CD_TRACK_AUDIO);
    }

    curblock.size = sectlenin;
    curblock.FAD = fad;

    // if track is Mode 2, get the subheader values
    if ((trktype != cdrom_file::CD_TRACK_AUDIO) && (curblock.data[15] == 2)) {
      curblock.chan = curblock.data[17];
      curblock.fnum = curblock.data[16];
      curblock.subm = curblock.data[18];
      curblock.cinf = curblock.data[19];

      // if it's Form 2, the length is actually 2324 bytes
      if (curblock.subm & 0x20) {
        curblock.size = 2324;
      }
    }

    return cd_filterdata(cddevice, trktype, &*p_ok);
  }

  *p_ok = 0;
  return (partitionT *)nullptr;
}

// loads in data set up by a CD-block PLAY command
void saturn_cd_hle_device::cd_playdata() {
  if (LIVE_CD_VIEW)
    popmessage("%04x %d %d %04x (%d)", cd_stat, cd_curfad, fadstoplay, hirqreg,
               buffull);

  switch (cd_stat & 0x0f00) {
  case CD_STAT_BUSY: {
    // accept the previously chained command
    // amagishi wants this at startup
    LOGSTATUS("Change to new status %04x -> %04x\n", cd_stat, cd_next_stat);
    cd_stat = cd_next_stat;
    m_status_change_in_progress = false;
    break;
  }
  case CD_STAT_SEEK: {
    if (!m_cdrom_image->exists())
      return;

    m_seek_in_progress = true;

    /* The pickup travel budget is measured once, on the first tick of
       this SEEK, with mednafen's approximation (ss/cdb.cpp,
       DRIVEPHASE_SEEK_START3): a fixed 12-sector startup latency, then
       26 units per sector of forward travel or 28 per sector backwards
       against the 75296 units of one sector period, plus one extra
       sector period when moving backwards or jumping 150 sectors or
       more.  The startup latency is what makes back-to-back Play
       commands discard the first request (Digital Dance Mix vol.1
       seeks away from a resume point and immediately re-plays), and
       the distance term is what keeps long FMV seeks from completing
       in a couple of sector ticks. */
    if (m_seek_ticks_left == 0) {
      int32_t const fad_delta = int32_t(cd_fad_seek - cd_curfad);
      int64_t units = 12 * 75296 + int64_t(std::abs(fad_delta)) *
                                       ((fad_delta < 0) ? 28 : 26);
      if (fad_delta < 0 || fad_delta >= 150)
        units += 75296;
      m_seek_ticks_left = int32_t(units / 75296) + 1;
      LOGSEEK("PRE %08x %08x %08x %d -> %d sector periods\n", cd_curfad,
              cd_fad_seek, cd_stat, fad_delta, m_seek_ticks_left);
    }

    if (--m_seek_ticks_left > 0) {
      // still travelling; position reports already come from the
      // seek target while the status is SEEK (cr_standard_return)
      break;
    }

    cur_track = m_cdrom_image->get_track(cd_fad_seek);
    LOGSEEK("Ready (track %d)\n", cur_track + 1);
    cd_curfad = cd_fad_seek;
    cd_change_status(cd_seek_stat);
    if (cd_seek_stat == CD_STAT_PLAY &&
        m_cdrom_image->get_track_type(m_cdrom_image->get_track(cd_curfad)) ==
            cdrom_file::CD_TRACK_AUDIO)
      m_cdda->pause_audio(0);
    m_seek_in_progress = false;

    break;
  }
  case CD_STAT_PAUSE: {
    if (!m_cdrom_image->exists())
      return;

    if (buffull_temp_pause && !buffull && fadstoplay) {
      buffull_temp_pause = false;
      cd_change_status(CD_STAT_PLAY);
    }
    break;
  }
  case CD_STAT_PLAY: {
    if (!m_cdrom_image->exists())
      return;

    if (fadstoplay) {
      LOGXFER("SATURN_CD_HLE: Reading FAD %d\n", cd_curfad);

      if (m_cdrom_image->exists()) {
        uint8_t p_ok;

        if (m_cdrom_image->get_track_type(m_cdrom_image->get_track(
                cd_curfad)) != cdrom_file::CD_TRACK_AUDIO) {
          cd_read_filtered_sector(cd_curfad, &p_ok);
          m_cdda->stop_audio(); // stop any pending CD-DA
        } else {
          // TODO: pinpoint cases when this isn't okay
          // (out of bounds disc for example)
          p_ok = 1;
          m_cdda->start_audio(cd_curfad, 1);
        }

        if (p_ok) {
          cd_curfad++;
          fadstoplay--;
          hirqreg |= CSCT;
          update_hirq();
          sectorstore = 1;

          if (!fadstoplay) {
            if (cdda_repeat_count >= cdda_maxrepeat) {
              LOG("cd_playdata: playback ended\n");
              cd_change_status(CD_STAT_PAUSE);

              hirqreg |= PEND;
              update_hirq();

              if (playtype == 1) {
                LOG("cd_playdata: setting EFLS\n");
                hirqreg |= EFLS;
                update_hirq();
              }
            } else {
              // a cdda_maxrepeat of 0xf means keep repeating same track
              // indefinitely
              if (cdda_repeat_count < 0xe)
                cdda_repeat_count++;

              // TODO: untested with cur_track == 0xaa (lead-out)
              // - dendego (tries to) playback redbook track 3 on title screen
              // after seek
              // - girlpuz1 is an easy test case, on both title and Himekuri
              // mode NOTE: cur_track is -1 at this point vs. redbook spec
              assert(cur_track >= 0 && cur_track != 0xff);
              // cd_curfad = m_cdrom_image->get_track_start(cur_track);
              cd_fad_seek = m_cdrom_image->get_track_start(cur_track);
              fadstoplay =
                  m_cdrom_image->get_track_start(cur_track + 1) - cd_fad_seek;
              cd_change_status(CD_STAT_SEEK);
              cd_seek_stat = CD_STAT_PLAY;
              LOGCMD("Repeat hit track %d count %d/%d FAD %06x -> start %06x "
                     "end %06x\n",
                     cur_track + 1, cdda_repeat_count, cdda_maxrepeat,
                     cd_curfad, cd_fad_seek, fadstoplay);
            }
          }
        } else if (buffull) {
          // TODO: should be correct but somehow still doesn't work
          buffull_temp_pause = true;
          // sectorstore = 0;
          cd_change_status(CD_STAT_PAUSE);
        }
      }
    }

    break;
  }
  }
}

// loads a single sector off the CD, anywhere from FAD 150 on up
void saturn_cd_hle_device::cd_readblock(uint32_t fad, uint8_t *dat) {
  if (m_cdrom_image->exists()) {
    m_cdrom_image->read_data(fad - 150, dat, cdrom_file::CD_TRACK_MODE1);
  }
}

void saturn_cd_hle_device::set_tray_open() {
  if (!tray_is_closed)
    return;

  hirqreg |= DCHG;
  update_hirq();

  cd_change_status(CD_STAT_OPEN);

  // unmount the existing image, pretend that's what user wants if we are there.
  m_cdrom_image->unload();

  tray_is_closed = 0;

  popmessage("Tray Open");
}

void saturn_cd_hle_device::set_tray_close() {
  /* avoid user attempts to load a CD-ROM without opening the tray first
   * (emulation asserts anyway with current framework) */
  if (tray_is_closed)
    return;

  hirqreg |= DCHG;
  update_hirq();

  if (m_cdrom_image->exists()) {
    LOG("Opened CD-ROM successfully, reading root directory\n");
    // read_new_dir(0xffffff);  // read root directory
    cd_change_status(CD_STAT_PAUSE);
  } else {
    cd_change_status(CD_STAT_NODISC);
  }

  cd_speed = 2;
  cdda_repeat_count = 0;
  tray_is_closed = 1;

  popmessage("Tray Close");
}
