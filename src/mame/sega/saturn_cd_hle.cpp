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

#include "emu.h"
#include "emuopts.h"
#include "saturn_cd_hle.h"


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
  save_item(NAME(m_xfer_raw_offset));
  save_item(NAME(m_xfer_raw_size));
  save_item(NAME(m_xfer_raw_sector));
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
  save_item(NAME(buffull_temp_pause));
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
  save_item(NAME(m_seek_in_progress));
  save_item(NAME(numfiles));
  save_item(NAME(firstfile));
  save_item(NAME(m_file_scope_start));
  save_item(NAME(m_file_info_words));
  save_item(NAME(m_file_info_invalidated));
  // the transfer type gives the saved xfercount/xferoffs/xfersect* positions
  // their meaning, so it has to travel with them
  save_item(NAME(xfertype));
  save_item(NAME(xfertype32));
  save_item(NAME(m_host_transfer_active));

  // Word-transfer cursors must be restored with the staged response bytes.
  // Full-directory transfers also use the directory cache registered below.
  save_item(NAME(tocbuf));
  save_item(NAME(subqbuf));
  save_item(NAME(subrwbuf));
  save_item(NAME(finfbuf));

  // Never register the initially empty/resizable vector's allocation.
  save_item(NAME(m_saved_dir_count));
  save_item(STRUCT_MEMBER(curroot, record_size));
  save_item(STRUCT_MEMBER(curroot, xa_record_size));
  save_item(STRUCT_MEMBER(curroot, file_number));
  save_item(STRUCT_MEMBER(curroot, firstfad));
  save_item(STRUCT_MEMBER(curroot, length));
  save_item(STRUCT_MEMBER(curroot, year));
  save_item(STRUCT_MEMBER(curroot, month));
  save_item(STRUCT_MEMBER(curroot, day));
  save_item(STRUCT_MEMBER(curroot, hour));
  save_item(STRUCT_MEMBER(curroot, minute));
  save_item(STRUCT_MEMBER(curroot, second));
  save_item(STRUCT_MEMBER(curroot, gmt_offset));
  save_item(STRUCT_MEMBER(curroot, flags));
  save_item(STRUCT_MEMBER(curroot, file_unit_size));
  save_item(STRUCT_MEMBER(curroot, interleave_gap_size));
  save_item(STRUCT_MEMBER(curroot, volume_sequencer_number));
  save_item(STRUCT_MEMBER(curroot, name));
  save_item(STRUCT_MEMBER(m_saved_dir, record_size));
  save_item(STRUCT_MEMBER(m_saved_dir, xa_record_size));
  save_item(STRUCT_MEMBER(m_saved_dir, file_number));
  save_item(STRUCT_MEMBER(m_saved_dir, firstfad));
  save_item(STRUCT_MEMBER(m_saved_dir, length));
  save_item(STRUCT_MEMBER(m_saved_dir, year));
  save_item(STRUCT_MEMBER(m_saved_dir, month));
  save_item(STRUCT_MEMBER(m_saved_dir, day));
  save_item(STRUCT_MEMBER(m_saved_dir, hour));
  save_item(STRUCT_MEMBER(m_saved_dir, minute));
  save_item(STRUCT_MEMBER(m_saved_dir, second));
  save_item(STRUCT_MEMBER(m_saved_dir, gmt_offset));
  save_item(STRUCT_MEMBER(m_saved_dir, flags));
  save_item(STRUCT_MEMBER(m_saved_dir, file_unit_size));
  save_item(STRUCT_MEMBER(m_saved_dir, interleave_gap_size));
  save_item(STRUCT_MEMBER(m_saved_dir, volume_sequencer_number));
  save_item(STRUCT_MEMBER(m_saved_dir, name));
  machine().save().register_presave(save_prepost_delegate(FUNC(saturn_cd_hle_device::directory_pre_save), this));
  machine().save().register_postload(save_prepost_delegate(FUNC(saturn_cd_hle_device::directory_post_load), this));

  // Save ownership by indices, never process-local pointers.
  save_item(NAME(m_saved_transpart));
  save_item(NAME(m_saved_cddevice));
  save_item(NAME(m_put_filter));
  save_item(STRUCT_MEMBER(m_get_partition, size));
  save_item(STRUCT_MEMBER(m_get_partition, numblks));
  save_item(STRUCT_MEMBER(m_get_partition, bnum));
  save_item(STRUCT_MEMBER(m_put_partition, size));
  save_item(STRUCT_MEMBER(m_put_partition, numblks));
  save_item(STRUCT_MEMBER(m_put_partition, bnum));
  save_item(STRUCT_MEMBER(filters, mode));
  save_item(STRUCT_MEMBER(filters, chan));
  save_item(STRUCT_MEMBER(filters, smmask));
  save_item(STRUCT_MEMBER(filters, cimask));
  save_item(STRUCT_MEMBER(filters, fid));
  save_item(STRUCT_MEMBER(filters, smval));
  save_item(STRUCT_MEMBER(filters, cival));
  save_item(STRUCT_MEMBER(filters, condtrue));
  save_item(STRUCT_MEMBER(filters, condfalse));
  save_item(STRUCT_MEMBER(filters, fad));
  save_item(STRUCT_MEMBER(filters, range));
  save_item(STRUCT_MEMBER(partitions, size));
  save_item(STRUCT_MEMBER(partitions, bnum));
  save_item(STRUCT_MEMBER(partitions, numblks));
  save_item(STRUCT_MEMBER(blocks, size));
  save_item(STRUCT_MEMBER(blocks, FAD));
  save_item(STRUCT_MEMBER(blocks, data));
  save_item(STRUCT_MEMBER(blocks, chan));
  save_item(STRUCT_MEMBER(blocks, fnum));
  save_item(STRUCT_MEMBER(blocks, subm));
  save_item(STRUCT_MEMBER(blocks, cinf));
  save_item(STRUCT_MEMBER(blocks, raw_data));
  save_item(STRUCT_MEMBER(curblock, size));
  save_item(STRUCT_MEMBER(curblock, FAD));
  save_item(STRUCT_MEMBER(curblock, data));
  save_item(STRUCT_MEMBER(curblock, chan));
  save_item(STRUCT_MEMBER(curblock, fnum));
  save_item(STRUCT_MEMBER(curblock, subm));
  save_item(STRUCT_MEMBER(curblock, cinf));
  save_item(STRUCT_MEMBER(curblock, raw_data));
}

void saturn_cd_hle_device::device_pre_save() {
  m_saved_transpart = transpart == &m_get_partition ? MAX_FILTERS + 1 :
                      transpart == &m_put_partition ? MAX_FILTERS : -1;
  m_saved_cddevice = -1;
  for (unsigned i = 0; i < MAX_FILTERS; ++i) {
    if (transpart == &partitions[i])
      m_saved_transpart = i;
    if (cddevice == &filters[i])
      m_saved_cddevice = i;
  }
}

void saturn_cd_hle_device::device_post_load() {
  for (partitionT &part : partitions)
    for (unsigned i = 0; i < MAX_BLOCKS; ++i)
      part.blocks[i] = part.bnum[i] < MAX_BLOCKS ? &blocks[part.bnum[i]] : nullptr;
  for (unsigned i = 0; i < MAX_BLOCKS; ++i)
    m_put_partition.blocks[i] = m_put_partition.bnum[i] < MAX_BLOCKS ?
                                   &blocks[m_put_partition.bnum[i]] : nullptr;
  for (unsigned i = 0; i < MAX_BLOCKS; ++i)
    m_get_partition.blocks[i] = m_get_partition.bnum[i] < MAX_BLOCKS ?
                                   &blocks[m_get_partition.bnum[i]] : nullptr;
  transpart = m_saved_transpart == MAX_FILTERS + 1 ? &m_get_partition :
              m_saved_transpart == MAX_FILTERS ? &m_put_partition :
              m_saved_transpart >= 0 && m_saved_transpart < MAX_FILTERS ?
                  &partitions[m_saved_transpart] : nullptr;
  cddevice = m_saved_cddevice >= 0 && m_saved_cddevice < MAX_FILTERS ?
                 &filters[m_saved_cddevice] : nullptr;
  // Pointer repair neither reruns a transfer nor produces a new HIRQ edge.
}

void saturn_cd_hle_device::directory_pre_save() {
  // All cache entries produced by make_dir_current fit this staging array.
  assert(curdir.size() <= std::size(m_saved_dir));
  m_saved_dir_count = std::min<size_t>(curdir.size(), std::size(m_saved_dir));
  std::copy_n(curdir.begin(), m_saved_dir_count, std::begin(m_saved_dir));
  std::fill(std::begin(m_saved_dir) + m_saved_dir_count, std::end(m_saved_dir), direntryT{});
}

void saturn_cd_hle_device::directory_post_load() {
  const uint32_t count = std::min<uint32_t>(m_saved_dir_count, std::size(m_saved_dir));
  curdir.assign(std::begin(m_saved_dir), std::begin(m_saved_dir) + count);
  // Restore held information without rereading media, changing a connection,
  // restarting a host stream or manufacturing a filesystem/IRQ completion.
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
  curroot = {};
  numfiles = firstfile = 0;
  m_file_scope_start = 2;
  m_file_info_words = 0;
  m_file_info_invalidated = false;

  xfertype = XFERTYPE_INVALID;
  xfertype32 = XFERTYPE32_INVALID;
  m_host_transfer_active = false;
  xfercount = 0;
  xferoffs = xfersect = xfersectpos = xfersectnum = xferdnum = 0;

  // reset flag vars
  buffull = sectorstore = 0;

  freeblocks = MAX_BLOCKS;

  sectlenin = sectlenout = 2048;

  lastbuf = 0xff;
  cddevice = nullptr;
  cddevicenum = 0xff;
  transpart = nullptr;
  m_saved_transpart = m_saved_cddevice = -1;
  curblock = {};
  m_get_partition = {};
  m_get_partition.size = -1;
  std::fill(std::begin(m_get_partition.bnum), std::end(m_get_partition.bnum), 0xff);
  m_put_partition = {};
  m_put_partition.size = -1;
  std::fill(std::begin(m_put_partition.bnum), std::end(m_put_partition.bnum), 0xff);
  m_put_filter = 0xff;
  m_xfer_raw_offset = m_xfer_raw_size = 0;
  m_xfer_raw_sector = 0xffffffff;

  // reset buffer partitions
  for (i = 0; i < MAX_FILTERS; i++) {
    // ST-162 sections 5.3/5.5: reset conditions, connect each true output
    // to its own partition, and disconnect the remaining connectors.
    filters[i] = {};
    filters[i].condtrue = i;
    filters[i].condfalse = 0xff;
    partitions[i].size = -1;
    partitions[i].numblks = 0;

    for (j = 0; j < MAX_BLOCKS; j++) {
      partitions[i].blocks[j] = (blockT *)nullptr;
      partitions[i].bnum[j] = 0xff;
    }
  }

  // reset blocks
  for (i = 0; i < MAX_BLOCKS; i++) {
    blocks[i] = {};
    blocks[i].size = -1;
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
  cdda_maxrepeat = 0;
  cdda_repeat_count = 0;

  // MPEG state is still not registered for save states; reset re-establishes
  // it independently of the saved selector/sector-buffer state.
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
    if (transpart && xfersectpos < MAX_BLOCKS &&
        xfersect < xfersectnum && xfersect < MAX_BLOCKS - xfersectpos) {
      blockT *const blk = transpart->blocks[xfersectpos + xfersect];

      // Raw backing is a physical 2352-byte sector even after its allocation
      // is freed. A captured GET can still reference it until DataEnd; freeing
      // or compacting the public partition does not erase these bytes.
      const int32_t storage_size = !blk ? 0 :
          blk->raw_data ? int32_t(sizeof(blk->data)) : blk->size;
      int32_t payload_size = storage_size;
      uint32_t payload_offset = 0;
      if (blk && blk->raw_data) {
        // A Set Sector Length during a transfer takes effect on the next
        // sector, not halfway through the already selected host view.
        if (m_xfer_raw_sector != xfersect) {
          m_xfer_raw_offset = blk->host_offset(sectlenin);
          m_xfer_raw_size = blk->host_size(sectlenin);
          m_xfer_raw_sector = xfersect;
        }
        payload_size = m_xfer_raw_size;
        payload_offset = m_xfer_raw_offset;
      }

      // a hole in the partition has nothing to hand over; leave the port at
      // its idle value and move on to the next sector rather than chasing a
      // null pointer or running off a block with a nonsense size
      if (blk == nullptr || storage_size < 4 ||
          uint32_t(storage_size) > sizeof(blk->data) || payload_size < 4 ||
          payload_offset > sizeof(blk->data) ||
          uint32_t(payload_size) > sizeof(blk->data) - payload_offset ||
          xferoffs > uint32_t(payload_size) - 4) {
        LOGWARN("CD: Get Sector Data skipping invalid block %d of %d\n",
                xfersect + 1, xfersectnum);

        xferoffs = 0;
        xfersect++;
        break;
      }

      // get next longword
      rv = get_u32be(&blk->data[payload_offset + xferoffs]);

      xferdnum += 4;
      xferoffs += 4;

      // did we run out of sector? (this tested blocks[xfersect], missing the
      // partition offset the data read above uses)
      if (xferoffs >= payload_size) {
        LOG("Finished xfer of block %d of %d\n", xfersect + 1, xfersectnum);

        xferoffs = 0;
        xfersect++;
      }
    }
    // Exhaustion returns dummy data, but does not release GET+DELETE's
    // captured allocations. DataEnd owns completion, including unread data.
    break;

  default:
    // Inactive/wrong-direction accesses must not crash the emulator.  Keep
    // the existing idle/dummy value; its exact hardware value is unverified.
    break;
  }

  return rv;
}

inline void saturn_cd_hle_device::dataxfer_long_w(u32 data) {
  switch (xfertype32) {
  case XFERTYPE32_PUTSECTOR:
    // make sure we have sectors left
    if (transpart && xfersectpos < MAX_BLOCKS &&
        xfersect < xfersectnum && xfersect < MAX_BLOCKS - xfersectpos) {
      blockT *const blk = transpart->blocks[xfersectpos + xfersect];

      int32_t payload_size = blk ? blk->size : 0;
      uint32_t payload_offset = 0;
      if (blk && blk->raw_data) {
        // Writing length is independent of fetching length and of the mode
        // byte being written. Latch it once per logical input sector.
        if (m_xfer_raw_sector != xfersect) {
          m_xfer_raw_offset = sectlenout == 2048 ? 24 : 2352 - sectlenout;
          m_xfer_raw_size = sectlenout;
          m_xfer_raw_sector = xfersect;
        }
        payload_size = m_xfer_raw_size;
        payload_offset = m_xfer_raw_offset;
      }

      // as above: skip anything we cannot safely write into
      if (blk == nullptr || blk->size < 4 ||
          uint32_t(blk->size) > sizeof(blk->data) || payload_size < 4 ||
          payload_offset > sizeof(blk->data) ||
          uint32_t(payload_size) > sizeof(blk->data) - payload_offset ||
          xferoffs > uint32_t(payload_size) - 4) {
        LOGWARN("CD: Put Sector Data skipping invalid block %d of %d\n",
                xfersect + 1, xfersectnum);

        xferoffs = 0;
        xfersect++;
        break;
      }

      // get next longword
      put_u32be(&blk->data[payload_offset + xferoffs], data);

      xferdnum += 4;
      xferoffs += 4;

      // did we run out of sector?
      if (xferoffs >= payload_size) {
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

    if (xfercount >= 6 * 2) {
      xfercount = 0;
      xfertype = XFERTYPE_INVALID;
    }
    break;

  case XFERTYPE_FILEINFO_254:
    if ((xfercount % (6 * 2)) == 0) {
      const uint32_t temp = m_file_scope_start + xfercount / (6 * 2);
      // Keep the host read bounded even if a later filesystem operation
      // replaces the cache while the accepted transfer is outstanding.
      direntryT const entry =
          cd_file_info_held(temp) ? curdir[temp] : direntryT{};

      // first 4 bytes = FAD
      put_u32be(&finfbuf[0], entry.firstfad);
      // second 4 bytes = length of file
      put_u32be(&finfbuf[4], entry.length);
      finfbuf[8] = entry.file_unit_size;
      finfbuf[9] = entry.interleave_gap_size;
      finfbuf[10] = entry.file_number;
      finfbuf[11] = entry.flags;
    }

    rv = get_u16be(&finfbuf[xfercount % (6 * 2)]);

    xfercount += 2;
    xferdnum += 2;

    if (xfercount >= m_file_info_words * 2U) {
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

void saturn_cd_hle_device::trace_host_read(unsigned port, uint16_t value) {
  if (!machine().options().verbose() || machine().side_effects_disabled())
    return;
  ++m_trace_reads[port];
  m_trace_last_read[port] = value;
}

void saturn_cd_hle_device::trace_boot_state(const char *event, bool force) {
  if (!machine().options().verbose())
    return;
  const int64_t second = machine().time().seconds();
  if (!force && m_trace_second == second)
    return;
  if (!force)
    m_trace_second = second;
  auto *const maincpu = machine().root_device().subdevice<cpu_device>("maincpu");
  auto *const slave = machine().root_device().subdevice<cpu_device>("slave");
  logerror("CDBOOT t=%s event=%s mainpc=%08x slavepc=%08x status=%04x next=%04x "
           "HIRQ=%04x HIRM=%04x pending=%x CR=%04x,%04x,%04x,%04x "
           "fad=%06x remaining=%u free=%d full=%d store=%d playtype=%d "
           "xfer=%d bytes=%u sector=%u/%u\n",
           machine().time().as_string(), event,
           maincpu ? uint32_t(maincpu->state_int(STATE_GENPC)) : 0,
           slave ? uint32_t(slave->state_int(STATE_GENPC)) : 0,
           cd_stat, cd_next_stat, hirqreg, hirqmask, cmd_pending, cr1, cr2, cr3, cr4,
           cd_curfad, fadstoplay, freeblocks, buffull, sectorstore, playtype,
           int(xfertype32), xferdnum, xfersect, xfersectnum);
  logerror("CDBOOT reads HIRQ=%llu CR1=%llu CR2=%llu CR3=%llu CR4=%llu "
           "last=%04x,%04x,%04x,%04x,%04x\n",
           (unsigned long long)m_trace_reads[0], (unsigned long long)m_trace_reads[1],
           (unsigned long long)m_trace_reads[2], (unsigned long long)m_trace_reads[3],
           (unsigned long long)m_trace_reads[4], m_trace_last_read[0],
           m_trace_last_read[1], m_trace_last_read[2], m_trace_last_read[3], m_trace_last_read[4]);
}

uint16_t saturn_cd_hle_device::hirq_r() {
  // TODO: this member must return the register only
  u16 rv;

  //  LOG("RW HIRQ: %04x\n", rv);

  rv = hirqreg;

  // DCHG (bit 5) used to be force-cleared here on every read, which made the
  // tray-change condition unreadable: set_tray_open() raises it and drives the
  // interrupt line, but software polling HIRQ to find the cause saw bit 5
  // already gone. ST-136-R2 states that "a '1' value for the DCHG bit (bit 5) of
  // the interrupt factor register (HIRQREQ) of the CD block is also treated as a
  // tray open condition", i.e. reading it is the documented detection path, so
  // it must survive a read and be cleared only by hirq_w().

  if (buffull)
    rv |= BFUL;
  else
    rv &= ~BFUL;
  if (sectorstore)
    rv |= CSCT;
  else
    rv &= ~CSCT;

  // Debugger/inspection reads expose the live status without committing the
  // overlay or changing the host interrupt line.
  if (!machine().side_effects_disabled()) {
    hirqreg = rv;
    update_hirq();
  }

  trace_host_read(0, rv);
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

uint16_t saturn_cd_hle_device::dr1_r() { trace_host_read(1, cr1); return cr1; }
uint16_t saturn_cd_hle_device::dr2_r() { trace_host_read(2, cr2); return cr2; }
uint16_t saturn_cd_hle_device::dr3_r() { trace_host_read(3, cr3); return cr3; }
uint16_t saturn_cd_hle_device::dr4_r() {
  if (!machine().side_effects_disabled()) {
    cmd_pending = 0;
    cd_stat |= CD_STAT_PERI;
  }
  trace_host_read(4, cr4);
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

int saturn_cd_hle_device::get_track_index(uint32_t fad) {
  // The image owns the index table (including nonstandard pregaps and
  // indices above one). Its position argument is LBA, not Saturn FAD.
  return m_cdrom_image->get_track_index(fad - 150);
}

int saturn_cd_hle_device::sega_cdrom_get_adr_control(int track) {
  return bitswap<8>(m_cdrom_image->get_adr_control(track), 3, 2, 1, 0, 7, 6, 5,
                    4);
}

void saturn_cd_hle_device::cr_standard_return(uint16_t cur_status) {
  if (!m_cdrom_image->exists()) {
    // A missing image does not turn a REJECT/WAIT into a normal drive
    // status. Keep the legacy low response byte, but honor the caller's
    // command status just as the media-present paths below do.
    cr1 = cur_status | (cr1 & 0xff);
    // cr2 = 0;
    // cr3 = 0;
    // cr4 = 0;
  } else if ((cd_stat & 0x0f00) == CD_STAT_SEEK) {
    /* During seek state, values returned are from the target position */
    uint8_t seek_track = m_cdrom_image->get_track(cd_fad_seek - 150);

    cr1 = cur_status | (playtype << 7) | 0x00 | (cdda_repeat_count & 0xf);
    cr2 = (seek_track == 0xff)
              ? 0xffff
              : ((sega_cdrom_get_adr_control(seek_track) << 8) | (seek_track + 1));
    cr3 = (get_track_index(cd_fad_seek) << 8) |
          (cd_fad_seek >> 16); // index & 0xff00
    cr4 = cd_fad_seek;
  } else {
    cr1 = cur_status | (playtype << 7) | 0x00 |
          (cdda_repeat_count & 0xf); // options << 4 | repeat & 0xf
    // Track and CONTROL/ADR must describe the same reported position.
    // cur_track can still name the track where a multi-track play began.
    const uint8_t current_track = m_cdrom_image->get_track(cd_curfad - 150);
    cr2 = (cur_track == 0xff)
              ? 0xffff
              : ((sega_cdrom_get_adr_control(current_track) << 8) |
                 (current_track + 1));
    cr3 =
        (get_track_index(cd_curfad) << 8) | (cd_curfad >> 16); // index & 0xff00
    cr4 = cd_curfad;
  }
}

// The drive cursor names the next sector interval. Arm the converter when
// PLAY is entered, before that first interval elapses, rather than resetting
// its sample cache at every sector tick. Stop it before a non-audio interval.
void saturn_cd_hle_device::cd_update_cdda() {
  if ((cd_stat & 0x0f00) != CD_STAT_PLAY || !fadstoplay ||
      !m_cdrom_image->exists() || cd_curfad < 150 ||
      m_cdrom_image->get_track_type(m_cdrom_image->get_track(cd_curfad - 150)) !=
          cdrom_file::CD_TRACK_AUDIO) {
    if (m_cdda->audio_active())
      m_cdda->stop_audio();
    return;
  }

  const uint32_t lba = cd_curfad - 150;
  const uint32_t leadout = m_cdrom_image->get_track_start(0xaa);
  if (lba >= leadout) {
    if (m_cdda->audio_active())
      m_cdda->stop_audio();
    return;
  }
  if (!m_cdda->audio_active())
    m_cdda->start_audio(lba, std::min(fadstoplay, leadout - lba));
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
  // A new drive operation invalidates the old converter range. The PLAY
  // entry phase rearms it at the resulting pickup position if appropriate.
  if (m_cdda->audio_active())
    m_cdda->stop_audio();
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

// A drained FIFO/word response is still an outstanding host transfer until
// DataEnd. Do not let another command replace its cursors or backing bytes.
bool saturn_cd_hle_device::cd_transfer_wait() {
  if (!m_host_transfer_active && xfertype == XFERTYPE_INVALID &&
      xfertype32 == XFERTYPE32_INVALID && m_put_filter == 0xff)
    return false;
  cr_standard_return(cd_stat | CD_STAT_WAIT);
  hirqreg |= CMOK;
  update_hirq();
  return true;
}

void saturn_cd_hle_device::cmd_get_toc() {
  if (cd_transfer_wait())
    return;
  m_host_transfer_active = true;

  LOGCMD("%s: Get TOC\n", machine().describe_context());
  cd_readTOC();
  xfertype = XFERTYPE_TOC;
  xfercount = 0;
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

// Get-and-Delete detaches its range at acceptance. DataEnd releases all
// captured allocations, including sectors the host did not read (ST-162,
// p.96). Work on the private descriptor, not mutable public positions.
void saturn_cd_hle_device::finish_get_delete() {
  if (!transpart || xfersectpos >= MAX_BLOCKS)
    return;

  const u32 count = std::min<u32>(xfersectnum, MAX_BLOCKS - xfersectpos);
  if (!count)
    return;
  unsigned removed = 0;
  for (u32 i = xfersectpos; i < xfersectpos + count; ++i) {
    blockT *const blk = transpart->blocks[i];
    if (blk) {
      transpart->size -= std::max(blk->size, 0);
      cd_free_block(blk);
      ++removed;
    }
    transpart->blocks[i] = nullptr;
    transpart->bnum[i] = 0xff;
  }
  cd_defragblocks(transpart);
  transpart->numblks -= std::min<unsigned>(removed, transpart->numblks);
  if (freeblocks == MAX_BLOCKS)
    sectorstore = 0;
}

void saturn_cd_hle_device::cmd_end_data_transfer() {
  // end data transfer (TODO: needs to be worked on!)
  // returns # of bytes transferred (24 bits) in
  // low byte of cr1 (MSB) and cr2 (middle byte, LSB)
  LOGXFER("%s: End data transfer (%d bytes xfer'd)\n",
          machine().describe_context(), xferdnum);

  m_host_transfer_active = false;

  // clear the "transfer" flag
  cd_stat &= ~CD_STAT_TRANS;

  const bool pending_put = m_put_filter != 0xff;
  if (xferdnum || pending_put) {
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

  if (pending_put) {
    finish_put();
    hirqreg |= EHST;
  }

  // try to clean up any transfers still in progress
  switch (xfertype32) {
  case XFERTYPE32_GETSECTOR:
  case XFERTYPE32_PUTSECTOR:
    hirqreg |= EHST;
    update_hirq();
    break;

  case XFERTYPE32_GETDELETESECTOR:
    finish_get_delete();
    hirqreg |= EHST;
    break;

  default:
    break;
  }

  // DataEnd stops both transfer interfaces, including partial GET and PUT.
  xfertype = XFERTYPE_INVALID;
  xfertype32 = XFERTYPE32_INVALID;
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
      // Host tracks are one-based; image tracks are zero-based and their
      // start positions are LBA. Keep the drive position in FAD (LBA + 150).
      // Track/index 0/0 is the default disc-start position (ST-162 p.66),
      // not a command error. Index-specific positioning remains separate.
      cur_track = (start_pos >> 8) ? (start_pos >> 8) - 1 : 0;
      cd_fad_seek = m_cdrom_image->get_track_start(cur_track) + 150;
      cd_change_status(CD_STAT_SEEK);
      cd_seek_stat = CD_STAT_PLAY;

      LOGCMD("\ttrack mode %d\n", cur_track);
    }

    if (end_pos & 0x800000) {
      if (end_pos != 0xffffff)
        fadstoplay = end_pos & 0x7f'ffff;
    } else {
      uint8_t end_track;

      end_track = (end_pos) >> 8;
      // The default end is the last sector before lead-out, not the start
      // of image track zero. The image API uses AA for its lead-out entry.
      fadstoplay = m_cdrom_image->get_track_start(end_track ? end_track : 0xaa) +
                  150 - cd_fad_seek;
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
          fadstoplay = (m_cdrom_image->get_track_start(0xaa) + 150) - cd_curfad;
        else
          fadstoplay =
              (m_cdrom_image->get_track_start((end_pos & 0xff00) >> 8) + 150) -
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
        fadstoplay =
            m_cdrom_image->get_track_start(cur_track + 1) + 150 - cd_curfad;
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

  // ST-162 p.67: 7F retains the programmed maximum, independently of
  // bit 7 (pickup movement). The visible repeat counter is separate.
  if (play_mode != 0x7f)
    cdda_maxrepeat = play_mode & 0xf;

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
      cur_track = (cr2 >> 8) - 1;
      cd_fad_seek = m_cdrom_image->get_track_start(cur_track) + 150;
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
  if (cd_transfer_wait())
    return;
  if ((cr1 & 0xff) >= 2) {
    // No transfer was accepted: do not raise DRDY or acquire host ownership
    // for an unsupported subcode selector.
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= CMOK;
    update_hirq();
    return;
  }
  m_host_transfer_active = true;

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

// Filter inputs have one producer; partition inputs may have many true
// producers (ST-162 Table 5.1). Use the active pointer as authority when
// repairing legacy/inconsistent connection images.
void saturn_cd_hle_device::cd_disconnect_filter_input(uint8_t input) {
  if (input >= MAX_FILTERS)
    return;
  if (cddevice == &filters[input] || (!cddevice && cddevicenum == input)) {
    cddevice = nullptr;
    cddevicenum = 0xff;
  }
  for (filterT &filter : filters)
    if (filter.condfalse == input)
      filter.condfalse = 0xff;
}

void saturn_cd_hle_device::cd_connect_cddevice(uint8_t input) {
  assert(input < MAX_FILTERS || input == 0xff);
  cd_disconnect_filter_input(input);
  cddevice = input < MAX_FILTERS ? &filters[input] : nullptr;
  cddevicenum = input;
}

void saturn_cd_hle_device::cmd_set_cddevice_connection() {
  const uint8_t input = cr3 >> 8;
  if (input >= MAX_FILTERS && input != 0xff) {
    cr_standard_return(CD_STAT_REJECT);
  } else {
    cd_connect_cddevice(input);
    cr_standard_return(cd_stat);
  }
  hirqreg |= CMOK | ESEL;
  update_hirq();
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
    hirqreg |= CMOK;
    update_hirq();
    return;
  }

  LOGCMD("%s: Get Filter Range fnum %x => %08x %08x\n",
         machine().describe_context(), fnum, filters[fnum].fad,
         filters[fnum].range);

  cr1 = cd_stat | ((filters[fnum].fad >> 16) & 0xff);
  cr2 = filters[fnum].fad & 0xffff;
  cr3 = (uint16_t(fnum) << 8) | ((filters[fnum].range >> 16) & 0xff);
  cr4 = filters[fnum].range & 0xffff;

  hirqreg |= CMOK;
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
    hirqreg |= CMOK;
    update_hirq();
    return;
  }

  cr1 = cd_stat | (filters[fnum].chan & 0xff);
  cr2 = (filters[fnum].smmask << 8) | (filters[fnum].cimask & 0xff);
  cr3 = (uint16_t(fnum) << 8) | filters[fnum].fid;
  cr4 = (filters[fnum].smval << 8) | (filters[fnum].cival & 0xff);

  hirqreg |= CMOK;
  update_hirq();
}

// Initializing conditions is distinct from initializing connectors (ST-162
// functions 5.5 and 5.9). Preserve the selector graph in both command forms.
void saturn_cd_hle_device::cd_reset_filter_conditions(filterT &filter) {
  const uint8_t true_output = filter.condtrue;
  const uint8_t false_output = filter.condfalse;
  filter = {};
  filter.condtrue = true_output;
  filter.condfalse = false_output;
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
    cd_reset_filter_conditions(filters[fnum]);
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
    hirqreg |= CMOK;
    update_hirq();
    return;
  }

  cr1 = cd_stat | (filters[fnum].mode & 0xff);
  cr2 = 0;
  cr3 = uint16_t(fnum) << 8;
  cr4 = 0;

  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_set_filter_connection() {
  const uint8_t fnum = cr3 >> 8;
  const uint8_t true_output = cr2 >> 8;
  const uint8_t false_output = cr2;
  // Validate all selected outputs before changing any part of the graph.
  // Unselected command bytes have no effect, even if not valid selectors.
  if (fnum >= MAX_FILTERS ||
      ((cr1 & 1) && true_output >= MAX_FILTERS && true_output != 0xff) ||
      ((cr1 & 2) && false_output >= MAX_FILTERS && false_output != 0xff)) {
    cr_standard_return(CD_STAT_REJECT);
  } else {
    if (cr1 & 1)
      filters[fnum].condtrue = true_output;
    if (cr1 & 2) {
      cd_disconnect_filter_input(false_output);
      filters[fnum].condfalse = false_output;
    }
    cr_standard_return(cd_stat);
  }
  hirqreg |= CMOK | ESEL;
  update_hirq();
}

void saturn_cd_hle_device::cmd_get_filter_connection() {
  const uint8_t fnum = cr3 >> 8;
  if (fnum >= MAX_FILTERS) {
    cr_standard_return(CD_STAT_REJECT);
  } else {
    cr1 = cd_stat;
    cr2 = (uint16_t(filters[fnum].condtrue) << 8) | filters[fnum].condfalse;
    cr3 = uint16_t(fnum) << 8;
    cr4 = 0;
  }
  // A query completes the command, not a selector-setting operation.
  hirqreg |= CMOK;
  update_hirq();
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

    // Only released public blocks create free space; private host
    // reservations may still fill the pool. Keep the buffer-space pause
    // reason so the drive resumes when capacity actually becomes available.
    sectorstore = 0;
  }

  // TODO: bit 3, initialize all partition output connectors

  // reset all filter conditions
  if (BIT(cr1, 4)) {
    for (i = 0; i < MAX_FILTERS; i++)
      cd_reset_filter_conditions(filters[i]);
  }

  // reset all filter input connectors
  if (BIT(cr1, 5)) {
    cddevice = nullptr;
    cddevicenum = 0xff;
    for (filterT &filter : filters)
      filter.condfalse = 0xff;
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
  const unsigned input = cr3 >> 8;
  uint32_t offset = cr2;
  uint32_t count = cr4;
  auto const respond = [this](uint16_t status, bool completed) {
    cr_standard_return(status);
    hirqreg |= CMOK | (completed ? ESEL : 0);
    update_hirq();
  };
  if (input >= MAX_FILTERS) {
    respond(CD_STAT_REJECT, false);
    return;
  }

  const partitionT &part = partitions[input];
  if (offset == 0xffff)
    offset = part.numblks ? part.numblks - 1 : 0;
  if (count == 0xffff)
    count = offset < part.numblks ? part.numblks - offset : 0;
  // An unavailable range is not a shorter successful calculation. Host
  // writing also makes this command wait; an existing GET may continue.
  if (xfertype32 == XFERTYPE32_PUTSECTOR || !count ||
      part.numblks > MAX_BLOCKS || offset >= part.numblks ||
      count > part.numblks - offset) {
    respond(cd_stat | CD_STAT_WAIT, false);
    return;
  }

  uint32_t words = 0;
  for (unsigned i = 0; i < count; ++i) {
    const unsigned position = offset + i;
    const uint8_t id = part.bnum[position];
    const blockT *const sector = part.blocks[position];
    // Keep malformed saved/legacy ownership from becoming a bad read or a
    // partial replacement of the held result. Normal partitions have no holes.
    if (id >= MAX_BLOCKS || sector != &blocks[id] || sector->size <= 0 ||
        uint32_t(sector->size) > sizeof(sector->data)) {
      respond(cd_stat | CD_STAT_WAIT, false);
      return;
    }
    words += sector->host_size(sectlenin) / 2;
  }
  calcsize = words;
  respond(cd_stat, true);
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

void saturn_cd_hle_device::cmd_get_sector_information() {
  const uint8_t bufnum = cr3 >> 8;
  uint32_t position = cr2;
  const blockT *sector = nullptr;
  if (bufnum < MAX_FILTERS) {
    const partitionT &partition = partitions[bufnum];
    if (position == 0xffff && partition.numblks)
      position = partition.numblks - 1;
    if (position < partition.numblks && position < MAX_BLOCKS)
      sector = partition.blocks[position];
  }
  if (!sector) {
    cr_standard_return(CD_STAT_REJECT);
  } else {
    cr1 = cd_stat | ((sector->FAD >> 16) & 0xff);
    cr2 = sector->FAD & 0xffff;
    cr3 = (uint16_t(sector->fnum) << 8) | sector->chan;
    cr4 = (uint16_t(sector->subm) << 8) | sector->cinf;
  }
  // Sector information is a query, not a selector-setting operation.
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_set_sector_length() {
  LOGCMD("%s: Set sector length\n", machine().describe_context());

  const uint8_t get = cr1 & 0xff;
  const uint8_t put = cr2 >> 8;
  if ((get >= 4 && get != 0xff) || (put >= 4 && put != 0xff)) {
    // Validate both operands before changing either direction.
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= CMOK;
    update_hirq();
    return;
  }

  static constexpr int lengths[] = {2048, 2336, 2340, 2352};
  if (get != 0xff)
    sectlenin = lengths[get];
  if (put != 0xff)
    sectlenout = lengths[put];

  cr_standard_return(cd_stat);
  hirqreg |= (CMOK | ESEL);
  update_hirq();
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

  if (cd_transfer_wait())
    return;

  cd_getsectoroffsetnum(bufnum, &sectofs, &sectnum);

  if (partitions[bufnum].numblks < sectnum) {
    LOGWARN("CD: buffer is not full %08x %08x\n", partitions[bufnum].numblks,
            sectnum);
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= (CMOK | EHST);
    update_hirq();
    return;
  }

  m_host_transfer_active = true;
  xfertype32 = XFERTYPE32_GETSECTOR;
  xferoffs = 0;
  xfersect = 0;
  xferdnum = 0;
  xfersectpos = sectofs;
  xfersectnum = sectnum;
  // Capture the physical slot map at acceptance. A concurrent Delete may
  // compact the public partition, but must not retarget this GET to the
  // sectors that move into its old positions. This does not copy or pin data.
  m_get_partition = partitions[bufnum];
  transpart = &m_get_partition;
  // The first host view is selected when GET starts, before its first read.
  m_xfer_raw_sector = 0xffffffff;
  if (sectnum && sectofs < MAX_BLOCKS) {
    const blockT *const first = transpart->blocks[sectofs];
    if (first && first->raw_data) {
      m_xfer_raw_offset = first->host_offset(sectlenin);
      m_xfer_raw_size = first->host_size(sectlenin);
      m_xfer_raw_sector = 0;
    }
  }

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
  if (cd_transfer_wait())
    return;

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

  m_host_transfer_active = true;
  xfertype32 = XFERTYPE32_GETDELETESECTOR;
  xferoffs = 0;
  xfersect = 0;
  xferdnum = 0;
  xfersectpos = sectofs;
  xfersectnum = sectnum;
  m_get_partition = partitions[bufnum];
  transpart = &m_get_partition;

  // Detach at acceptance without freeing: the host owns these physical
  // buffers until DataEnd, not until its last port read. Public partition
  // operations must neither expose nor recycle this reserved range.
  partitionT &part = partitions[bufnum];
  if (sectnum) {
    for (uint32_t i = sectofs; i < sectofs + sectnum; ++i) {
      if (part.blocks[i])
        part.size -= std::max(part.blocks[i]->size, 0);
      part.blocks[i] = nullptr;
      part.bnum[i] = 0xff;
    }
    cd_defragblocks(&part);
    part.numblks -= sectnum;
  }
  // The first host view is selected when GET starts, before its first read.
  m_xfer_raw_sector = 0xffffffff;
  if (sectnum && sectofs < MAX_BLOCKS) {
    const blockT *const first = transpart->blocks[sectofs];
    if (first && first->raw_data) {
      m_xfer_raw_offset = first->host_offset(sectlenin);
      m_xfer_raw_size = first->host_size(sectlenin);
      m_xfer_raw_sector = 0;
    }
  }

  cd_stat |= CD_STAT_TRANS;
  cr_standard_return(cd_stat);
  hirqreg |= (CMOK | EHST | DRDY);
  update_hirq();
}

void saturn_cd_hle_device::cmd_put_sector_data() {
  const uint8_t input = cr3 >> 8;
  const uint32_t count = cr4;
  auto const respond = [this](uint16_t status, bool ready) {
    cr_standard_return(status);
    hirqreg |= CMOK | (ready ? DRDY : 0);
    update_hirq();
  };

  if (input >= MAX_FILTERS) {
    respond(CD_STAT_REJECT, false);
    return;
  }
  if (m_host_transfer_active || xfertype != XFERTYPE_INVALID ||
      xfertype32 != XFERTYPE32_INVALID ||
      m_put_partition.numblks || !count || count > MAX_BLOCKS || count > freeblocks) {
    respond(cd_stat | CD_STAT_WAIT, false);
    return;
  }

  // PUT names a filter, not a partition/sector offset. Reserve the complete
  // request privately so existing sectors cannot be overwritten and newly
  // written sectors do not become visible before DataEnd filters them.
  m_put_partition = {};
  std::fill(std::begin(m_put_partition.bnum), std::end(m_put_partition.bnum), 0xff);
  for (unsigned i = 0; i < count; ++i) {
    blockT *const sector = cd_alloc_block(&m_put_partition.bnum[i]);
    if (!sector) {
      // Counter/pool inconsistency: release only our own reservations.
      for (unsigned j = 0; j < m_put_partition.numblks; ++j)
        cd_free_block(m_put_partition.blocks[j]);
      m_put_partition = {};
      m_put_partition.size = -1;
      std::fill(std::begin(m_put_partition.bnum), std::end(m_put_partition.bnum), 0xff);
      respond(cd_stat | CD_STAT_WAIT, false);
      return;
    }
    // ST-162 section5.4: the absent header of host user data is zero.
    // Unwritten bytes are unspecified; zeroing them is deterministic.
    *sector = {};
    sector->size = cdrom_file::MAX_SECTOR_DATA;
    sector->raw_data = true;
    m_put_partition.blocks[i] = sector;
    ++m_put_partition.numblks;
    m_put_partition.size += sector->size;
  }

  m_put_filter = input;
  cd_disconnect_filter_input(input);
  transpart = &m_put_partition;
  xfertype32 = XFERTYPE32_PUTSECTOR;
  m_host_transfer_active = true;
  xferoffs = xfersect = xferdnum = xfersectpos = 0;
  xfersectnum = count;
  m_xfer_raw_offset = sectlenout == 2048 ? 24 : 2352 - sectlenout;
  m_xfer_raw_size = sectlenout;
  m_xfer_raw_sector = 0;
  cd_stat |= CD_STAT_TRANS;
  respond(cd_stat, true);
}

// All reserved sectors go through the designated filter at DataEnd, even
// after an interrupted/zero-byte PUT (ST-162 p.97, function7.5).
void saturn_cd_hle_device::finish_put() {
  if (m_put_filter >= MAX_FILTERS)
    return;

  cd_disconnect_filter_input(m_put_filter);
  for (unsigned i = 0; i < m_put_partition.numblks && i < MAX_BLOCKS; ++i) {
    blockT *const sector = m_put_partition.blocks[i];
    const uint8_t id = m_put_partition.bnum[i];
    m_put_partition.blocks[i] = nullptr;
    m_put_partition.bnum[i] = 0xff;
    if (id >= MAX_BLOCKS || sector != &blocks[id])
      continue;

    sector->FAD = (bcd_2_dec(sector->data[12]) * 60 +
                   bcd_2_dec(sector->data[13])) * 75 + bcd_2_dec(sector->data[14]);
    sector->fnum = sector->chan = sector->subm = sector->cinf = 0;
    if (sector->data[15] == 2) {
      sector->fnum = sector->data[16];
      sector->chan = sector->data[17];
      sector->subm = sector->data[18];
      sector->cinf = sector->data[19];
    }

    const uint8_t destination = cd_filter_destination(m_put_filter, *sector);
    if (destination == 0xff || partitions[destination].numblks >= MAX_BLOCKS) {
      cd_free_block(sector);
      continue;
    }
    partitionT &dst = partitions[destination];
    dst.blocks[dst.numblks] = sector;
    dst.bnum[dst.numblks++] = id;
    if (dst.size < 0)
      dst.size = 0;
    dst.size += sector->size;
  }
  m_put_partition.numblks = 0;
  m_put_partition.size = -1;
  m_put_filter = 0xff;
  if (transpart == &m_put_partition)
    transpart = nullptr;
  if (freeblocks == MAX_BLOCKS)
    sectorstore = 0;
}

void saturn_cd_hle_device::cmd_move_sector_data() {
  cd_copy_move_sector_data(true);
}

void saturn_cd_hle_device::cmd_copy_sector_data() {
  cd_copy_move_sector_data(false);
}

void saturn_cd_hle_device::cd_copy_move_sector_data(bool move) {
  const unsigned source = cr3 >> 8;
  const uint8_t input = cr1 & 0xff;
  uint32_t offset = cr2;
  uint32_t count = cr4;

  auto const respond = [this](uint16_t status, bool completed) {
    cr_standard_return(status);
    hirqreg |= CMOK | (completed ? ECPY : 0);
    if (!freeblocks)
      hirqreg |= BFUL;
    update_hirq();
  };
  if (source >= MAX_FILTERS || input >= MAX_FILTERS) {
    respond(CD_STAT_REJECT, false);
    return;
  }

  partitionT &src = partitions[source];
  // Resolve both sentinels against the original partition, before a self
  // copy/move can append anything. Do not truncate an unavailable range.
  if (offset == 0xffff)
    offset = src.numblks ? src.numblks - 1 : 0;
  if (count == 0xffff)
    count = offset < src.numblks ? src.numblks - offset : 0;
  if (m_host_transfer_active || xfertype != XFERTYPE_INVALID ||
      xfertype32 != XFERTYPE32_INVALID ||
      !count || offset >= src.numblks || count > src.numblks - offset ||
      src.numblks > MAX_BLOCKS || (!move && count > freeblocks)) {
    respond(cd_stat | CD_STAT_WAIT, false);
    return;
  }

  // Stable block identities let a selected range move back into its own
  // source partition without reprocessing the newly appended tail.
  uint8_t selected[MAX_BLOCKS];
  for (unsigned i = 0; i < count; ++i) {
    selected[i] = src.bnum[offset + i];
    if (selected[i] >= MAX_BLOCKS ||
        src.blocks[offset + i] != &blocks[selected[i]]) {
      respond(cd_stat | CD_STAT_WAIT, false);
      return;
    }
  }

  // A filter input has one producer (ST-162 Table 5.1). The temporary
  // partition-output connection replaces a CD/false-output connection.
  cd_disconnect_filter_input(input);

  if (move) {
    for (unsigned i = 0; i < count; ++i) {
      src.size -= src.blocks[offset + i]->size;
      src.blocks[offset + i] = nullptr;
      src.bnum[offset + i] = 0xff;
    }
    src.numblks -= count;
    cd_defragblocks(&src);
  }

  for (unsigned i = 0; i < count; ++i) {
    blockT *sector = &blocks[selected[i]];
    uint8_t id = selected[i];
    if (!move) {
      blockT *const copy = cd_alloc_block(&id);
      // Preflight reserves enough space in the synchronous model. Keep
      // malformed legacy buffer states from becoming a null dereference.
      if (!copy)
        break;
      *copy = *sector;
      sector = copy;
    }

    const uint8_t destination = cd_filter_destination(input, *sector);
    if (destination == 0xff || partitions[destination].numblks >= MAX_BLOCKS) {
      // An unconnected selector output discards its sector (section 5.3.1).
      // MOVE has already removed the complete selected source range.
      cd_free_block(sector);
      continue;
    }
    partitionT &dst = partitions[destination];
    dst.blocks[dst.numblks] = sector;
    dst.bnum[dst.numblks++] = id;
    if (dst.size < 0)
      dst.size = 0;
    dst.size += sector->size;
  }

  if (freeblocks == MAX_BLOCKS)
    sectorstore = 0;
  // Still synchronous: no invented copy rate, busy interval or intermediate
  // ECPY edge. The actual asynchronous command engine remains separate work.
  respond(cd_stat, true);
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

uint32_t saturn_cd_hle_device::cd_file_info_count() const {
  return m_file_scope_start < curdir.size()
             ? std::min<size_t>(254, curdir.size() - m_file_scope_start)
             : 0;
}

bool saturn_cd_hle_device::cd_file_info_held(uint32_t file_id) const {
  // This is a backing-cache lookup, not command admission. Tray invalidation
  // must not destroy the bytes of a previously accepted File Info transfer.
  return file_id < curdir.size() &&
         (file_id < 2 || (file_id >= m_file_scope_start &&
                         file_id - m_file_scope_start < 254));
}

void saturn_cd_hle_device::cd_setup_directory_filter(uint8_t input,
                                                     const direntryT &entry) {
  assert(input < MAX_FILTERS);
  // ST-162 section 6.2.3/Table 6.1: directory access selects only the FAD
  // range. File-number selection is enabled by Read File, not by a hold.
  filterT &filter = filters[input];
  filter = {};
  filter.mode = 0x40;
  filter.fad = entry.firstfad;
  filter.range = (uint64_t(entry.length) + 2047) / 2048;
  filter.fid = entry.file_number;
  filter.condtrue = input;
  filter.condfalse = 0xff;
}

void saturn_cd_hle_device::cmd_change_directory() {
  const uint8_t input = cr3 >> 8;
  const uint32_t file_id = (uint32_t(cr3 & 0xff) << 16) | cr4;
  // Only a held directory (or the special filesystem-root ID) designates
  // a directory move. In particular, a regular file is not a directory
  // byte stream and must not replace the current held information.
  if (input >= MAX_FILTERS ||
      (file_id != 0xffffff &&
       (m_file_info_invalidated || !cd_file_info_held(file_id) ||
        !(curdir[file_id].flags & 0x02)))) {
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= CMOK;
    update_hirq();
    return;
  }

  // ID zero names the current directory: acknowledge without restarting
  // its load or displacing the existing input connection/held window.
  if (file_id != 0) {
    cd_clear_partition(input);
    cd_connect_cddevice(input);
    read_new_dir(file_id, input);
  }
  cr_standard_return(cd_stat);
  hirqreg |= CMOK | EFLS;
  update_hirq();
}

void saturn_cd_hle_device::cmd_read_directory() {
  LOGCMD("%s: Read Directory Entry\n", machine().describe_context());
  const uint8_t input = cr3 >> 8;
  const uint32_t first =
      std::max<uint32_t>(2, (uint32_t(cr3 & 0xff) << 16) | cr4);
  // Holding another window requires an existing file-information table
  // and a real work selector; FF is not a filesystem disconnection command.
  if (input >= MAX_FILTERS || m_file_info_invalidated || curdir.empty()) {
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= CMOK;
    update_hirq();
    return;
  }
  // Clear the work partition for an ordinary held-window access. Leave
  // beyond-directory requests outside this still-unresolved error policy.
  if (first == 2 || first < curdir.size())
    cd_clear_partition(input);
  cd_connect_cddevice(input);
  cd_setup_directory_filter(input, curdir[0]);

  // The synchronous HLE already cached the parsed directory. Expose the
  // requested window without losing the always-held self/parent records.
  // Beyond-directory requests retain the prior window: their error policy
  // is not established by the ordinary, in-directory hold contract.
  if (first < curdir.size() || curdir.size() <= 2)
    m_file_scope_start = first;

  cr_standard_return(cd_stat);
  hirqreg |= (CMOK | EFLS);
  update_hirq();
}

void saturn_cd_hle_device::cmd_get_file_scope() {
  // Get file system scope
  LOGCMD("%s: Get file system scope\n", machine().describe_context());
  if (m_file_info_invalidated || curdir.empty()) {
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= CMOK;
    update_hirq();
    return;
  }
  const uint32_t count = cd_file_info_count();
  const uint32_t first = count ? m_file_scope_start : 0;
  const bool at_end = m_file_scope_start + count >= curdir.size();
  cr1 = cd_stat;
  cr2 = count; // ordinary records only; self and parent are always held
  cr3 = (at_end ? 0x0100 : 0) | ((first >> 16) & 0xff);
  cr4 = first;
  // A scope query reports state; it does not complete a filesystem operation.
  hirqreg |= CMOK;
  update_hirq();
}

void saturn_cd_hle_device::cmd_get_target_file_info() {
  if (cd_transfer_wait())
    return;
  const uint32_t temp = (uint32_t(cr3 & 0xff) << 16) | cr4;
  const uint32_t count = cd_file_info_count();
  if (m_file_info_invalidated || curdir.empty() ||
      (temp == 0xffffff ? !count : !cd_file_info_held(temp))) {
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= CMOK;
    update_hirq();
    return;
  }
  m_host_transfer_active = true;
  m_file_info_words = temp == 0xffffff ? count * 6 : 6;

  LOGCMD("%s: Get File Info\n", machine().describe_context());
  cd_stat |= CD_STAT_TRANS;
  cd_stat &= 0xff00;
  // This host metadata transfer does not change the drive producer or
  // its repeat notification count (ST-162 pp.38,53,100 function 8.4).

  if (temp == 0xffffff) // special
  {
    xfertype = XFERTYPE_FILEINFO_254;
    xfercount = 0;

    cr1 = cd_stat;
    cr2 = m_file_info_words;
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

    direntryT const &entry = curdir[temp];
    if (entry.firstfad == 0)
      throw emu_fatalerror("File ID not found in XFERTYPE_FILEINFO_1");
    // A held empty file still has a valid twelve-byte information record;
    // its zero byte length is not a missing-file sentinel.
    //      LOGWARN("%08x %08x\n",curdir[temp].firstfad,curdir[temp].length);
    // first 4 bytes = FAD
    put_u32be(&finfbuf[0], entry.firstfad);
    // second 4 bytes = length of file
    put_u32be(&finfbuf[4], entry.length);
    finfbuf[8] = entry.file_unit_size;
    finfbuf[9] = entry.interleave_gap_size;
    finfbuf[10] = entry.file_number;
    finfbuf[11] = entry.flags;

    xfertype = XFERTYPE_FILEINFO_1;
    xfercount = 0;
  }
  // DRDY exposes a ready response and readable file-information stream.
  hirqreg |= (CMOK | DRDY);
  update_hirq();
  LOG("   = %04x %04x %04x %04x %04x\n", hirqreg, cr1, cr2, cr3, cr4);
}

void saturn_cd_hle_device::cmd_read_file() {
  // Read File
  LOGCMD("%s: Read File\n", machine().describe_context());
  const uint32_t file_offset = (uint32_t(cr1 & 0xff) << 16) | cr2;
  const uint8_t file_filter = cr3 >> 8;
  const uint32_t file_id = (uint32_t(cr3 & 0xff) << 16) | cr4;

  // Filesystem selectors are 0..23, not the FF disconnection sentinel.
  // Refuse an absent/out-of-range directory entry before changing playback,
  // routing or filter conditions. REJECT completes no host/file transfer.
  if (file_filter >= MAX_FILTERS || m_file_info_invalidated ||
      !cd_file_info_held(file_id)) {
    cr_standard_return(CD_STAT_REJECT);
    hirqreg |= CMOK;
    update_hirq();
    return;
  }

  // ST-162 section 6.2.3(2)(c): clear the selected work partition before
  // file access. Private host reservations are not public partition entries.
  cd_clear_partition(file_filter);

  // File offsets are logical (2048-byte) sectors, independent of the host's
  // Get Sector Length selection. Widen the byte-size rounding before adding
  // so neither large files nor a range exceeding 65535 sectors is truncated.
  const uint32_t file_size =
      (uint64_t(curdir[file_id].length) + 2047) / 2048 - file_offset;
  // The beyond-EOF command error policy still needs hardware evidence;
  // this retains the reference's unsigned arithmetic for that invalid case.

  cd_change_status(CD_STAT_PLAY | 0x80); // set "cd-rom" bit
  cd_curfad = (curdir[file_id].firstfad + file_offset) & 0xffffff;
  fadstoplay = file_size;
  cd_connect_cddevice(file_filter);
  // ST-162 section 6.2.3/Table 6.1: file access replaces the work
  // selector's conditions with FAD-range and stored file-number matching.
  filterT &filter = filters[file_filter];
  filter = {};
  filter.mode = 0x41;
  filter.fid = curdir[file_id].file_number;
  filter.fad = cd_curfad;
  filter.range = file_size;
  filter.condtrue = file_filter;
  filter.condfalse = 0xff;

  LOGWARN("Read file %08x (%08x %08x) %02x %d\n", curdir[file_id].firstfad,
          cd_curfad, fadstoplay, file_filter, sectlenin);

  cr_standard_return(cd_stat);

  playtype = 1;

  hirqreg |= (CMOK | EHST);
  update_hirq();
}

void saturn_cd_hle_device::cmd_abort_file() {
  LOGCMD("%s: Abort File\n", machine().describe_context());
  // Stop the filesystem producer, not the independent host data transfer.
  // ST-162 p.101 also preserves buffer partitions and selector settings.
  // This is a commanded pause, not a temporary buffer-space pause: later
  // Delete/DataEnd/reset frees must not restart the aborted file producer.
  buffull_temp_pause = false;
  if (((cd_stat & 0x0f00) != CD_STAT_NODISC) &&
      ((cd_stat & 0x0f00) != CD_STAT_OPEN))
    cd_change_status(CD_STAT_PAUSE); // force to pause

  cr_standard_return(cd_stat);
  // bios expects "2bc" mask to work against this
  hirqreg |= (CMOK | EFLS);
  update_hirq();
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
  trace_boot_state("command", true);
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
  case 0x47:
    cmd_get_filter_connection();
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

  // ST-162 p.31: an idle periodic response/SCDQ cycle is 16.7 ms,
  // independent of the selected transfer speed or the stopped track type.
  // Keep the existing SEEK/SCAN stepping policy separate: this shared timer
  // still also advances the pickup, not just the periodic response.
  const uint16_t state = cd_stat & 0x0f00;
  if (state != CD_STAT_PLAY && state != CD_STAT_SEEK && state != CD_STAT_SCAN)
    m_sector_timer->adjust(attotime::from_hz(60));
  else if (state == CD_STAT_SEEK)
    m_sector_timer->adjust(attotime::from_hz(75));
  else if (m_cdrom_image->get_track_type(
               m_cdrom_image->get_track(cd_curfad - 150)) ==
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
  trace_boot_state("periodic");
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
      blocks[i].raw_data = false; // raw-sector constructors opt in after allocation
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

void saturn_cd_hle_device::cd_clear_partition(uint8_t bufnum) {
  assert(bufnum < MAX_FILTERS);
  partitionT &part = partitions[bufnum];
  for (unsigned i = 0; i < MAX_BLOCKS; ++i) {
    cd_free_block(part.blocks[i]);
    part.blocks[i] = nullptr;
    part.bnum[i] = 0xff;
  }
  part.size = -1;
  part.numblks = 0;
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
void saturn_cd_hle_device::read_new_dir(uint32_t fileno, uint8_t input) {
  int foundpd, i;
  uint32_t cfad; //, dirfad;
  uint8_t sect[2048];

  if (fileno == 0xffffff) {
    if (input < MAX_FILTERS) {
      // Before the PVD supplies the root extent, discovery must not inherit
      // a stale range/subheader match that can discard volume descriptors.
      cd_setup_directory_filter(input, direntryT{});
      filters[input].mode = 0;
    }
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
      curroot.flags = sect[181] & 0x02;
      curroot.file_number = 0;
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
      if (input < MAX_FILTERS)
        cd_setup_directory_filter(input, curroot);
      make_dir_current(curroot.firstfad, curroot.length);
    }
  } else {
    /* fileno is the 24-bit value from CR3/CR4 while curdir only ever holds
       as many entries as make_dir_current() parsed, so an out-of-range one
       would read hundreds of megabytes past the allocation.  Leave the
       current directory alone. The public command preflights this ID, but
       keep the bound for internal callers as well. */
    if (size_t(fileno) >= curdir.size()) {
      LOGWARN("CD: Change Directory %06x beyond directory (%u entries)\n",
              fileno, unsigned(curdir.size()));
      return;
    }

    if (curdir[fileno].length > MAX_DIR_SIZE) {
      LOGWARN("ERROR: new directory too big (%d)!\n", curdir[fileno].length);
    }
    if (input < MAX_FILTERS)
      cd_setup_directory_filter(input, curdir[fileno]);
    make_dir_current(curdir[fileno].firstfad, curdir[fileno].length);
  }
}

// makes the directory pointed to by FAD current
// https://wiki.osdev.org/ISO_9660 for a detailed reference
void saturn_cd_hle_device::make_dir_current(uint32_t fad, uint32_t length) {
  // A child directory has its own extent length, unrelated to curroot.
  // Keep the existing HLE directory-size limit, but never read past it or
  // parse records outside the selected directory's declared byte extent.
  const uint32_t bytes = std::min(length, MAX_DIR_SIZE);
  uint8_t sector[2048];
  m_file_scope_start = 2;
  m_file_info_invalidated = true;
  curdir.clear();
  for (uint32_t offset = 0; offset < bytes; offset += sizeof(sector)) {
    std::fill(std::begin(sector), std::end(sector), 0);
    cd_readblock(fad + offset / sizeof(sector), sector);
    const uint32_t available = std::min<uint32_t>(sizeof(sector), bytes - offset);
    uint32_t position = 0;
    while (position < available && sector[position]) {
      const uint8_t *const record = &sector[position];
      const uint32_t size = record[0];
      // ISO directory records cannot span logical blocks. A zero-length
      // record denotes padding; malformed records must not walk the host
      // allocation or stall the parser. Their hardware error policy is
      // outside this synchronous HLE parser.
      if (size < 34 || size > available - position ||
          !record[32] || record[32] > size - 33)
        break;

      direntryT entry{};
      entry.record_size = record[0];
      entry.xa_record_size = record[1];
      entry.firstfad = get_u32le(&record[2]) + 150;
      entry.length = get_u32le(&record[10]);
      entry.year = record[18];
      entry.month = record[19];
      entry.day = record[20];
      entry.hour = record[21];
      entry.minute = record[22];
      entry.second = record[23];
      entry.gmt_offset = record[24];
      entry.flags = record[25] & 0x02;
      // ST-040 Tables 3.10/3.11: system information follows the name and
      // its even-byte padding. Only a complete XA extension supplies the
      // file number and attribute bits; ISO flags are not XA attributes.
      const uint32_t system_use = 33 + (record[32] | 1);
      if (system_use + 14 <= size && record[system_use + 6] == 'X' &&
          record[system_use + 7] == 'A') {
        entry.file_number = record[system_use + 8];
        entry.flags |= record[system_use + 4] & 0xf8;
      }
      entry.file_unit_size = record[26];
      entry.interleave_gap_size = record[27];
      entry.volume_sequencer_number = get_u16le(&record[28]);
      const uint32_t idlen = std::min<uint32_t>(record[32], sizeof(entry.name) - 1);
      std::copy_n(&record[33], idlen, entry.name);
      entry.name[idlen] = 0;
      curdir.push_back(entry);
      position += size;
    }
  }
  numfiles = curdir.size();
  // Retain parser bookkeeping independently of the exposed held window.
  for (unsigned i = 0; i < curdir.size(); ++i) {
    if (!(curdir[i].flags & 0x02)) {
      firstfile = i;
      break;
    }
  }
  m_file_info_invalidated = false;
}

void saturn_cd_hle_device::device_stop() { curdir.clear(); }

void saturn_cd_hle_device::cd_readTOC(void) {
  int i, ntrks, tocptr, fad;

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

// ST-162 section 5.3: a true output selects a partition, while a false
// output selects another filter. Stored subheaders are zero outside Mode 2.
uint8_t saturn_cd_hle_device::cd_filter_destination(uint8_t fnum, const blockT &sector) const {
  // A repeated filter cannot change its verdict for this sector. Bound the
  // walk for malformed cyclic configurations rather than hanging the host.
  for (unsigned visited = 0; visited < MAX_FILTERS && fnum < MAX_FILTERS; ++visited) {
    const filterT &filter = filters[fnum];
    bool match = (!(filter.mode & 1) || sector.fnum == filter.fid) &&
                 (!(filter.mode & 2) || sector.chan == filter.chan) &&
                 (!(filter.mode & 4) || (sector.subm & filter.smmask) == filter.smval) &&
                 (!(filter.mode & 8) || (sector.cinf & filter.cimask) == filter.cival);
    if (filter.mode & 0x10)
      match = !match;
    // Frame-address selection is outside subheader inversion.
    if ((filter.mode & 0x40) &&
        (uint32_t(sector.FAD) < filter.fad || uint32_t(sector.FAD) >= filter.fad + filter.range))
      match = false;
    if (match)
      return filter.condtrue < MAX_FILTERS ? filter.condtrue : 0xff;
    fnum = filter.condfalse;
  }
  return 0xff;
}

saturn_cd_hle_device::partitionT *
saturn_cd_hle_device::cd_filterdata(filterT *flt, int trktype, uint8_t *p_ok) {
  const uint8_t destination = cd_filter_destination(uint8_t(flt - filters), curblock);
  if (destination == 0xff) {
    *p_ok = 0;
    return nullptr;
  }
  partitionT *const filterprt = &partitions[destination];

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

  // Media data sectors keep headers, subheaders and trailing bytes so a
  // later Get Sector Length can select another view without rereading media.
  // Retain the legacy audio/synthetic-sector representation on this path.
  if (!curblock.raw_data) {
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
  }

  // update the status of the partition
  if (filterprt->size == -1)
    filterprt->size = 0;

  filterprt->size += filterprt->blocks[filterprt->numblks]->size;
  filterprt->numblks++;

  // Get Last Buffer Destination describes the last sector actually stored
  // by the CD device, not a discarded sector or a failed allocation.
  lastbuf = destination;
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

    curblock.raw_data = trktype != cdrom_file::CD_TRACK_AUDIO;
    curblock.size = curblock.raw_data ? cdrom_file::MAX_SECTOR_DATA : sectlenin;
    curblock.FAD = fad;

    // if track is Mode 2, get the subheader values
    if ((trktype != cdrom_file::CD_TRACK_AUDIO) && (curblock.data[15] == 2)) {
      curblock.chan = curblock.data[17];
      curblock.fnum = curblock.data[16];
      curblock.subm = curblock.data[18];
      curblock.cinf = curblock.data[19];

      // Form 2 payload length is selected when the host reads the raw sector.
    } else {
      // ST-162 section 5.4: non-Mode-2 subheaders are treated as zero.
      // Do not inherit metadata from the previous Mode 2 sector.
      curblock.chan = curblock.fnum = curblock.subm = curblock.cinf = 0;
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
    cd_update_cdda();
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

    cur_track = m_cdrom_image->get_track(cd_fad_seek - 150);
    LOGSEEK("Ready (track %d)\n", cur_track + 1);
    cd_curfad = cd_fad_seek;
    cd_change_status(cd_seek_stat);
    if (cd_seek_stat == CD_STAT_PLAY &&
        m_cdrom_image->get_track_type(
            m_cdrom_image->get_track(cd_curfad - 150)) ==
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
                cd_curfad - 150)) != cdrom_file::CD_TRACK_AUDIO) {
          cd_read_filtered_sector(cd_curfad, &p_ok);
          m_cdda->stop_audio(); // stop any pending CD-DA
        } else {
          // This interval's audio was armed on PLAY entry or at the previous
          // sector boundary. Do not restart the converter/sample cache here.
          p_ok = 1;
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
                trace_boot_state("file-complete", true);
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
              cd_fad_seek = m_cdrom_image->get_track_start(cur_track) + 150;
              fadstoplay =
                  m_cdrom_image->get_track_start(cur_track + 1) + 150 - cd_fad_seek;
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

    cd_update_cdda();
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

  // ST-162 section 6.2.2: a disc change invalidates filesystem information.
  // Retain its backing cache for an outstanding host transfer, but reject
  // new file accesses until a directory is freshly loaded.
  m_file_info_invalidated = true;

  // Opening stops the drive, including a read paused for buffer space.
  // Do not cancel the independent host transfer or discard its buffers.
  fadstoplay = 0;
  playtype = 0;
  buffull_temp_pause = false;
  m_seek_in_progress = false;
  m_seek_ticks_left = 0;
  m_cdda->stop_audio();

  // ST-162 function 1.8: both causes precede OPEN, also for manual opening.
  hirqreg |= DCHG | EFLS;
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
