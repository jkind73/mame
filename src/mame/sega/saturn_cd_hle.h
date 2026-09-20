// license:BSD-3-Clause
// copyright-holders:R. Belmont, Angelo Salese

#ifndef MAME_SEGA_SATURN_CD_HLE_H
#define MAME_SEGA_SATURN_CD_HLE_H

#pragma once

#include "cdrom.h"
#include "imagedev/cdromimg.h"
#include "sound/cdda.h"

class saturn_cd_hle_device : public device_t, public device_mixer_interface {
  static constexpr unsigned MAX_FILTERS = 24;
  static constexpr unsigned MAX_BLOCKS = 200;
  static constexpr uint32_t MAX_DIR_SIZE = 256 * 1024;

public:
  saturn_cd_hle_device(const machine_config &mconfig, const char *tag,
                       device_t *owner, uint32_t clock = 0);

  void amap(address_map &map);

  void set_tray_open();
  void set_tray_close();

  // HIRQ output to the host: on real hardware this line is connected to
  // A-Bus external interrupt 0 of the SCU (IST bit 16, vector 0x50, level 7)
  auto host_irq_cb() { return m_host_irq_cb.bind(); }

protected:
  virtual void device_add_mconfig(machine_config &config) override ATTR_COLD;
  virtual void device_start() override ATTR_COLD;
  virtual void device_reset() override ATTR_COLD;
  virtual void device_stop() override ATTR_COLD;
  virtual void device_pre_save() override;
  virtual void device_post_load() override;

private:
  required_device<cdrom_image_device> m_cdrom_image;
  required_device<cdda_device> m_cdda;

  devcb_write_line m_host_irq_cb;

  emu_timer *m_sh1_timer;
  emu_timer *m_sector_timer;
  TIMER_CALLBACK_MEMBER(sh1_command_cb);
  TIMER_CALLBACK_MEMBER(cd_sector_cb);

  struct direntryT {
    uint8_t record_size;
    uint8_t xa_record_size;
    uint8_t file_number; // XA system information; zero when absent
    uint32_t firstfad; // first sector of file
    uint32_t length;   // length of file
    uint8_t year;
    uint8_t month;
    uint8_t day;
    uint8_t hour;
    uint8_t minute;
    uint8_t second;
    uint8_t gmt_offset;
    uint8_t flags; // CdcFile attributes: ISO directory bit plus XA bits3-7
    uint8_t file_unit_size;
    uint8_t interleave_gap_size;
    uint16_t volume_sequencer_number;
    uint8_t name[128];
  };

  struct filterT {
    uint8_t mode;
    uint8_t chan;
    uint8_t smmask;
    uint8_t cimask;
    uint8_t fid;
    uint8_t smval;
    uint8_t cival;
    uint8_t condtrue;
    uint8_t condfalse;
    uint32_t fad;
    uint32_t range;
  };

  struct blockT {
    int32_t size; // size of block
    int32_t FAD;  // FAD on disc
    uint8_t data[cdrom_file::MAX_SECTOR_DATA];
    uint8_t chan; // channel
    uint8_t fnum; // file number
    uint8_t subm; // subchannel mode
    uint8_t cinf; // coding information
    bool raw_data = false; // complete sector image rather than a cooked payload

    int32_t host_size(int32_t length) const {
      if (!raw_data)
        return size;
      return length == 2048 && data[15] == 2 && (data[18] & 0x20) ? 2324 : length;
    }

    uint16_t host_offset(int32_t length) const {
      if (!raw_data || length == 2352)
        return 0;
      if (length == 2340)
        return 12;
      if (length == 2336)
        return 16;
      // ST-162 section 5.4: only Mode 1 places user data after the header.
      return data[15] == 1 ? 16 : 24;
    }
  };

  struct partitionT {
    int32_t size;
    blockT *blocks[MAX_BLOCKS];
    uint8_t bnum[MAX_BLOCKS];
    uint8_t numblks;
  };

  /* MPEG (Video CD / Movie Card) cartridge state.

     The card is driven entirely through CD block host commands $90-$AF: the
     SH-2 writes parameters into CR1-CR4 and reads decoder status back out of
     the same registers, so from the host side the card is this state plus the
     response contract.  Real hardware keeps these values in SH-1 on-chip RAM
     $0F000840-$0F00089F and the CDB-106 firmware only relays them to the two
     decoder LSIs on the cartridge; the addresses in the comments are those
     locations.  What is not modelled is the decoding itself - the raw
     decoder-LSI register encoding is not documented, and MAME has neither a
     card ROM dump nor a Video CD data path, so no picture is produced. */
  enum : unsigned { MPEG_LAYER_VIDEO = 0, MPEG_LAYER_AUDIO = 1 };

  struct mpegT {
    bool present;      // $0F00027D bit 1 - MPEG hardware fitted
    bool image_loaded; // $0F0002FD - cartridge image loaded from the $0E000000
                       // window
    bool active; // $0F000892 bit 7 - subsystem brought up by MpegInit ($93)

    // operation status ($0F00089C video / $0F00089D audio), packed into the CR1
    // low byte
    uint8_t
        video_run; // 1 stopped, 2/3 prep, 4 playing, 5 switching, 6 recovery
    uint8_t audio_run;   // same encoding, shifted into bits 4-6
    bool decode_stopped; // $0F000891 bit 0 -> operation status bit 3

    uint8_t picture_info;  // $0F000842 high byte
    uint8_t audio_status;  // $0F000842 low byte
    uint16_t video_status; // $0F000844
    uint16_t interval;     // $0F000846 - operation-interval (VSYNC) counter

    uint32_t irq_status;  // $0F000848 - read and cleared by Get Interrupt ($91)
    uint32_t irq_mask;    // $0F00084C - written by Set Interrupt Mask ($92)
    uint32_t lsi_a_event; // $0F000850 - $FFFFFFFF after reset
    uint16_t lsi_b_control; // $0F000884 - $8209 after reset
    uint32_t subsys_state;  // $0F000890 - $67818022 after init

    // Set Mode ($94); $FF in any parameter byte keeps the current value
    uint8_t operation_mode, decode_timing, output_dest, scan_mode;
    // Play ($95); same keep-current convention
    uint8_t playback_mode, audio_xfer, video_xfer, play_param4;
    // Set Decode ($96)
    uint8_t audio_mute;
    uint16_t pause_time, freeze_time;

    /* Connection ($9A/$9B/$9C) and stream ($9D/$9E).  Two records per command,
       one per layer, plus the staged "next" slot that Change Connection
       commits. */
    struct layerT {
      uint8_t conn_mode, layer_search, partition;
      uint8_t stream_mode, stream_number, channel;
    };
    layerT layer[2], next_layer[2];

    uint16_t pic_width, pic_height; // Get Picture Size ($9F)

    uint8_t tc_hour, tc_min, tc_sec, tc_frame; // Get Timecode ($98)
    uint8_t tc_bank, tc_pic_type, tc_track;    // 1=I 2=P 3=B 4=D
    uint32_t pts;                              // Get PTS ($99)

    // display and window model ($A0-$A5)
    bool display_on;
    uint8_t display_bank, fade_y, fade_c, video_effect, display_attr;
    uint16_t border_color;
    uint16_t win[5][2]; // $A1 sub-parameters 0-4, X and Y

    uint16_t lsi_a_param[24]; // $0F000854-$0F000883 LSI A parameter block,
                              // first word $88FE
  };

public:
  // 16-bit transfer types - fixed underlying type so the save state system can
  // serialise them, see ALLOW_SAVE_TYPE in the .cpp
  enum transT : u8 {
    XFERTYPE_INVALID,
    XFERTYPE_TOC,
    XFERTYPE_FILEINFO_1,
    XFERTYPE_FILEINFO_254,
    XFERTYPE_SUBQ,
    XFERTYPE_SUBRW
  };

  // 32-bit transfer types
  enum trans32T : u8 {
    XFERTYPE32_INVALID,
    XFERTYPE32_GETSECTOR,
    XFERTYPE32_GETDELETESECTOR,
    XFERTYPE32_PUTSECTOR,
    XFERTYPE32_MOVESECTOR
  };

private:
  int get_track_index(uint32_t fad);
  int sega_cdrom_get_adr_control(int track);
  void cr_standard_return(uint16_t cur_status);
  void mpeg_standard_return(uint16_t cur_status);
  void mpeg_bringup();
  void mpeg_reset();
  bool mpeg_gate(bool need_active);
  void cd_free_block(blockT *blktofree);
  void cd_defragblocks(partitionT *part);
  void cd_copy_move_sector_data(bool move);
  void cd_reset_filter_conditions(filterT &filter);
  void cd_disconnect_filter_input(uint8_t input);
  void cd_connect_cddevice(uint8_t input);
  void cd_getsectoroffsetnum(uint32_t bufnum, uint32_t *sectoffs,
                             uint32_t *sectnum);

  void cd_readTOC();
  void cd_readblock(uint32_t fad, uint8_t *dat);
  void cd_playdata();

  void cd_exec_command(void);
  void trace_host_read(unsigned port, uint16_t value);
  void trace_boot_state(const char *event, bool force = false);
  // Host-only diagnostics, intentionally not emulated/save-state contents.
  int64_t m_trace_second = -1;
  uint64_t m_trace_reads[5]{};
  uint16_t m_trace_last_read[5]{};
  // iso9660 utilities
  void make_dir_current(uint32_t fad, uint32_t length);
  void read_new_dir(uint32_t fileno, uint8_t input = 0xff);
  void cd_setup_directory_filter(uint8_t input, const direntryT &entry);

  blockT *cd_alloc_block(uint8_t *blknum);
  uint8_t cd_filter_destination(uint8_t fnum, const blockT &sector) const;
  partitionT *cd_filterdata(filterT *flt, int trktype, uint8_t *p_ok);
  partitionT *cd_read_filtered_sector(int32_t fad, uint8_t *p_ok);

  // local variables
  partitionT partitions[MAX_FILTERS];
  partitionT m_get_partition{}; // captured GET slot map; backing remains in the pool
  partitionT m_put_partition{}; // reserved host sectors, not yet filter output
  uint8_t m_put_filter = 0xff;

  mpegT mpeg; // MPEG (Video CD) cartridge state
  partitionT *transpart;
  int m_saved_transpart = -1;
  int m_saved_cddevice = -1;

  blockT blocks[MAX_BLOCKS];
  blockT curblock;

  uint8_t tocbuf[102 * 4]{};
  uint8_t subqbuf[5 * 2]{};
  uint8_t subrwbuf[12 * 2]{};
  uint8_t finfbuf[256]{};

  int32_t sectlenin, sectlenout;

  uint8_t lastbuf, playtype;

  transT xfertype;
  trans32T xfertype32;
  bool m_host_transfer_active = false; // remains active through EOF until DataEnd
  uint32_t xfercount, calcsize;
  uint32_t xferoffs, xfersect, xfersectpos, xfersectnum, xferdnum;
  uint16_t m_xfer_raw_offset = 0, m_xfer_raw_size = 0;
  uint32_t m_xfer_raw_sector = 0xffffffff;

  filterT filters[MAX_FILTERS];
  filterT *cddevice;
  int cddevicenum;

  uint16_t cr1, cr2, cr3, cr4;
  uint16_t hirqmask, hirqreg;
  uint16_t cd_stat;
  uint16_t cd_next_stat;
  uint16_t cd_seek_stat;
  uint32_t cd_curfad; // = 0;
  uint32_t cd_fad_seek;
  uint32_t fadstoplay; // = 0;
  int buffull, sectorstore, freeblocks;
  bool buffull_temp_pause;

  /* Seek model: sector periods (1/75 s) of pickup travel left before the
     pending seek completes.  Zeroed whenever a new SEEK is chained so a
     retarget re-measures the travel. */
  int32_t m_seek_ticks_left;
  int cur_track;
  uint8_t cmd_pending;
  uint8_t cd_speed;
  uint8_t cdda_maxrepeat;
  uint8_t cdda_repeat_count;
  uint8_t tray_is_closed;
  bool m_status_change_in_progress, m_seek_in_progress;
  int get_timing_command(void);

  direntryT curroot{};           // root entry of current filesystem
  std::vector<direntryT> curdir; // current directory
  // The HLE parser caches the directory, but firmware exposes only this
  // 254-record ordinary-file window plus the self/parent records.
  uint32_t m_file_scope_start = 2;
  uint16_t m_file_info_words = 0; // accepted host transfer length, not live scope
  // Command validity is separate from the retained cache backing an already
  // accepted host stream. An empty cache is invalid even without this latch.
  bool m_file_info_invalidated = false;
  uint32_t cd_file_info_count() const;
  bool cd_file_info_held(uint32_t file_id) const;
  // The bounded parser accepts records of at least 34 bytes. Stage its
  // resizable cache in fixed storage for native save-state registration.
  static constexpr uint32_t MAX_DIR_ENTRIES = MAX_DIR_SIZE / 34;
  direntryT m_saved_dir[MAX_DIR_ENTRIES]{};
  uint32_t m_saved_dir_count = 0;
  void directory_pre_save();
  void directory_post_load();
  int numfiles;                  // # of entries in current directory
  int firstfile;                 // first non-directory file

  void cd_change_status(u16 new_status);

  // CDC commands
  // 0x00
  void cmd_get_status();
  void cmd_get_hw_info();
  void cmd_get_toc();
  void cmd_get_session_info();
  void cmd_init_cdsystem();
  void cmd_end_data_transfer();
  void finish_get_delete();
  void finish_put();
  bool cd_transfer_wait();
  // 0x10
  void cmd_play_disc();
  void cmd_seek_disc();
  void cmd_ffwd_rew_disc();
  // 0x20
  void cmd_get_subcode_q_rw_channel();
  // 0x30
  void cmd_set_cddevice_connection();
  void cmd_get_cddevice_connection();
  void cmd_last_buffer_destination();
  // 0x40
  void cmd_set_filter_range();
  void cmd_get_filter_range();
  void cmd_set_filter_subheader_conditions();
  void cmd_get_filter_subheader_conditions();
  void cmd_set_filter_mode();
  void cmd_get_filter_mode();
  void cmd_set_filter_connection();
  void cmd_get_filter_connection();
  void cmd_reset_selector();
  // 0x50
  void cmd_get_buffer_size();
  void cmd_get_buffer_partition_sector_number();
  void cmd_calculate_actual_data_size();
  void cmd_get_actual_data_size();
  void cmd_get_sector_information();
  // 0x60
  void cmd_set_sector_length();
  void cmd_get_sector_data();
  void cmd_delete_sector_data();
  void cmd_get_and_delete_sector_data();
  void cmd_put_sector_data();
  void cmd_move_sector_data();
  void cmd_copy_sector_data();
  void cmd_get_sector_data_copy_or_move_error();
  // 0x70
  void cmd_change_directory();
  void cmd_read_directory();
  void cmd_get_file_scope();
  void cmd_get_target_file_info();
  void cmd_read_file();
  void cmd_abort_file();
  // 0x90
  void cmd_mpeg_get_status();        // $90
  void cmd_mpeg_get_irq();           // $91
  void cmd_mpeg_set_irq_mask();      // $92
  void cmd_mpeg_init();              // $93
  void cmd_mpeg_set_mode();          // $94
  void cmd_mpeg_play();              // $95
  void cmd_mpeg_set_decode();        // $96
  void cmd_mpeg_out_decoding_sync(); // $97
  void cmd_mpeg_get_timecode();      // $98
  void cmd_mpeg_get_pts();           // $99
  void cmd_mpeg_set_connection();    // $9A
  void cmd_mpeg_get_connection();    // $9B
  void cmd_mpeg_change_connection(); // $9C
  void cmd_mpeg_set_stream();        // $9D
  void cmd_mpeg_get_stream();        // $9E
  void cmd_mpeg_get_picture_size();  // $9F
  void cmd_mpeg_display();           // $A0
  void cmd_mpeg_set_window();        // $A1
  void cmd_mpeg_set_border_color();  // $A2
  void cmd_mpeg_set_fade();          // $A3
  void cmd_mpeg_set_video_effect();  // $A4
  void cmd_mpeg_set_display_attr();  // $A5
  void cmd_mpeg_get_picture_info();  // $A6
  void cmd_mpeg_read_lsi();          // $AE
  void cmd_mpeg_write_lsi();         // $AF
  // 0xe0
  void cmd_check_copy_protection();
  void cmd_get_disc_region();
  void cmd_get_mpeg_card_boot_rom();

  // comms
  uint32_t datatrns_r(offs_t offset, uint32_t mem_mask = ~0);
  void datatrns_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
  inline u32 dataxfer_long_r();
  inline u16 dataxfer_word_r();
  inline void dataxfer_long_w(u32 data);
  uint16_t dr1_r();
  uint16_t dr2_r();
  uint16_t dr3_r();
  uint16_t dr4_r();
  void cr1_w(uint16_t data);
  void cr2_w(uint16_t data);
  void cr3_w(uint16_t data);
  void cr4_w(uint16_t data);

  uint16_t hirq_r();
  void hirq_w(uint16_t data);
  void update_hirq();
  uint16_t hirqmask_r();
  void hirqmask_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
};

// device type definition
DECLARE_DEVICE_TYPE(SATURN_CD_HLE, saturn_cd_hle_device)

#endif // MAME_SEGA_SATURN_CD_HLE_H
