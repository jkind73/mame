#!/usr/bin/env python3
# license:BSD-3-Clause
# copyright-holders:MAMEdev Team
"""Assert the CD block's position arithmetic without building MAME.

The CD drive speaks FADs (sector counts from the start of the programme area,
LBA + 150) while the image API speaks logical LBAs and numbers its tracks from
zero, with an extra lead-out entry after the last one.  saturn_cd_hle.cpp mixed
the two, which put every Red Book play 150 sectors (2 s) away from where the
pickup reported it and finished a track-mode range one whole track late.

This test extracts the real functions from the driver source and compiles them
against a fake image device that reproduces the semantics the image API is
documented to have, including the part that makes a past-the-end lookup
indistinguishable from track 1 (src/lib/util/cdrom.cpp, logical_to_chd_lba only
assigns its track out-parameter inside the track loop).  It then asserts:

  geometry   track starts as FADs, the lead-out, and that an out-of-range track
             index clamps instead of reading past the track table
  lookups    cd_track_at()/cd_is_audio() distinguish "past the lead-out" from
             "track 1", get_track_index() reports the 150 sector pregap of an
             audio track, and no lookup can leave the table
  ranges     Play Disc in track mode requests exactly the length of the track
             asked for (300 sectors for the fixture's 4 s track, not 600), a
             FAD end position is a position rather than a length, and a range
             that runs off the disc is clamped to the lead-out
  seek       Seek Disc in track mode converts the host's one-based track number
             to the index the image API uses and lands on that track's start FAD
  cdda       the Red Book converter is handed a logical LBA and the sector
             count of the remaining range, and is not started on a data track

Requires Python 3 and a C++ compiler.  Does not build MAME and needs no BIOS.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'src/mame/sega/saturn_cd_hle.cpp'


def extract(text, signature):
    start = text.index(signature)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def build_source():
    text = SOURCE.read_text()
    functions = '\n'.join(extract(text, s) for s in (
        'int saturn_cd_hle_device::get_track_index(',
        'uint32_t saturn_cd_hle_device::cd_track_start_fad(',
        'uint32_t saturn_cd_hle_device::cd_track_count(',
        'int saturn_cd_hle_device::cd_track_at(',
        'uint32_t saturn_cd_hle_device::cd_sectors_to_leadout(',
        'bool saturn_cd_hle_device::cd_is_audio(',
        'void saturn_cd_hle_device::cd_start_cdda(',
        'void saturn_cd_hle_device::cd_stop_cdda(',
        'void saturn_cd_hle_device::cd_change_status(',
        'void saturn_cd_hle_device::cmd_play_disc(',
        'void saturn_cd_hle_device::cmd_seek_disc('))
    return functions


HARNESS = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <memory>
#include <string>
#include <vector>
using u8 = uint8_t; using u16 = uint16_t; using u32 = uint32_t;

namespace cdrom_file {
constexpr int MAX_SECTOR_DATA = 2352;
enum { CD_TRACK_DATA = 0, CD_TRACK_AUDIO = 1 };
}
using cdrom_file::CD_TRACK_AUDIO;
using cdrom_file::CD_TRACK_DATA;
constexpr int CMOK = 0x0001, PEND = 0x0010;
constexpr int EFLS = 0x0002, ESEL = 0x0004, ECPY = 0x0008, EHST = 0x0080;
constexpr int CD_STAT_BUSY = 0x0400, CD_STAT_PAUSE = 0x0100;
constexpr int CD_STAT_STANDBY = 0x0200, CD_STAT_PLAY = 0x0300;
constexpr int CD_STAT_SEEK = 0x0500, CD_STAT_SCAN = 0x0600;
constexpr int CD_STAT_OPEN = 0x0700, CD_STAT_NODISC = 0x0800;
constexpr int CD_STAT_PERI = 0x2000;
struct filterT {};
void popmessage(const char *, ...) {}
#define LOG(...) ((void)0)
#define LOGWARN(...) ((void)0)
#define LOGCMD(...) ((void)0)
#define LOGSTATUS(...) ((void)0)
#define LOGSEEK(...) ((void)0)

/* Stand-in for cdrom_image_device/cdrom_file.  get_track() mirrors
   logical_to_chd_lba's behaviour: the track out-parameter is only written
   inside the loop, so a position at or past the lead-out comes back as the
   caller's initialiser, 0. */
struct fake_image {
  struct trackT { u32 start; int type; };
  std::vector<trackT> tracks;   // last entry is the lead-out
  bool present = true;
  int lookups = 0, type_lookups = 0;

  bool exists() const { return present; }
  int get_last_track() const { return int(tracks.size()) - 1; }
  u32 get_track_start(u32 track) const {
    if (track == 0xaa) track = u32(tracks.size()) - 1;
    if (track >= tracks.size()) { std::printf("TRACK TABLE OVERRUN %u\n", track); std::abort(); }
    return tracks[track].start;
  }
  u32 get_track(u32 frame) const {
    ++const_cast<fake_image *>(this)->lookups;
    u32 track = 0;
    for (size_t i = 0; i + 1 < tracks.size(); ++i)
      if (frame < tracks[i + 1].start) { track = u32(i); break; }
    return track;
  }
  int get_track_type(int track) const {
    ++const_cast<fake_image *>(this)->type_lookups;
    if (track < 0 || size_t(track) >= tracks.size()) { std::printf("TYPE OVERRUN %d\n", track); std::abort(); }
    return tracks[track].type;
  }
  int get_adr_control(int track) const {
    return get_track_type(track) == CD_TRACK_AUDIO ? 0x01 : 0x41;
  }
};

struct fake_cdda {
  int starts = 0, stops = 0, cancels = 0;
  bool active = false, paused = false;
  u32 lba = 0, sectors = 0;
  void start_audio(u32 l, u32 n) { ++starts; lba = l; sectors = n; active = true; paused = false; }
  void stop_audio() { ++stops; active = false; }
  void cancel_scan() { ++cancels; }
  void scan_forward() {}
  void scan_reverse() {}
  bool audio_active() const { return active; }
  bool audio_paused() const { return paused; }
};

struct saturn_cd_hle_device {
  fake_image *m_cdrom_image = nullptr;
  fake_cdda *m_cdda = nullptr;

  u32 cd_curfad = 150, cd_fad_seek = 150, fadstoplay = 0;
  int cur_track = 0xff;
  u16 cr1 = 0, cr2 = 0, cr3 = 0, cr4 = 0;
  u16 cd_stat = CD_STAT_PAUSE, cd_next_stat = CD_STAT_PAUSE;
  u16 cd_seek_stat = CD_STAT_PAUSE, hirqreg = 0;
  u8 playtype = 0, cdda_maxrepeat = 0, cdda_repeat_count = 0, cd_speed = 2;
  bool m_status_change_in_progress = false;
  int32_t m_seek_ticks_left = 0;
  std::vector<std::string> statuses;

  // the functions under test, defined below from the driver source
  int get_track_index(uint32_t lba);
  uint32_t cd_track_start_fad(uint32_t track_index);
  uint32_t cd_track_count();
  int cd_track_at(uint32_t fad);
  uint32_t cd_sectors_to_leadout();
  bool cd_is_audio(uint32_t fad);
  void cd_start_cdda();
  void cd_stop_cdda();
  void cd_change_status(u16 new_status);
  void cmd_play_disc();
  void cmd_seek_disc();

  void update_hirq() {}
  void cr_standard_return(u16) {}
};

// FUNCTIONS

int main() {
  fake_image image;
  image.tracks = {{0, CD_TRACK_DATA}, {182, CD_TRACK_AUDIO},
                  {482, CD_TRACK_AUDIO}, {782, CD_TRACK_DATA}};
  fake_cdda cdda;
  auto d = std::make_unique<saturn_cd_hle_device>();
  d->m_cdrom_image = &image;
  d->m_cdda = &cdda;

  unsigned cases = 0;
  auto chk = [&](bool cond, const char *what, long got, long want) {
    if (!cond) {
      std::printf("FAIL %s got=%ld want=%ld\n", what, got, want);
      std::exit(1);
    }
    ++cases;
  };

  // ---- geometry: track starts as FADs, lead-out, out-of-range clamping
  chk(d->cd_track_count() == 3, "track_count", d->cd_track_count(), 3);
  chk(d->cd_track_start_fad(0) == 150, "start_fad_0", d->cd_track_start_fad(0), 150);
  chk(d->cd_track_start_fad(1) == 332, "start_fad_1", d->cd_track_start_fad(1), 332);
  chk(d->cd_track_start_fad(2) == 632, "start_fad_2", d->cd_track_start_fad(2), 632);
  chk(d->cd_track_start_fad(3) == 932, "leadout_fad", d->cd_track_start_fad(3), 932);
  chk(d->cd_track_start_fad(4) == 932, "clamp_fad", d->cd_track_start_fad(4), 932);
  chk(d->cd_track_start_fad(0xaa) == 932, "clamp_aa", d->cd_track_start_fad(0xaa), 932);

  // ---- lookups
  chk(d->cd_track_at(150) == 0, "track_at_first", d->cd_track_at(150), 0);
  chk(d->cd_track_at(331) == 0, "track_at_before_audio", d->cd_track_at(331), 0);
  chk(d->cd_track_at(332) == 1, "track_at_audio", d->cd_track_at(332), 1);
  chk(d->cd_track_at(931) == 2, "track_at_last", d->cd_track_at(931), 2);
  chk(d->cd_track_at(932) == -1, "track_at_leadout", d->cd_track_at(932), -1);
  chk(d->cd_track_at(5000) == -1, "track_at_past_end", d->cd_track_at(5000), -1);
  chk(d->cd_track_at(0) == -1, "track_at_before_disc", d->cd_track_at(0), -1);
  chk(d->cd_track_at(149) == -1, "track_at_lead_in", d->cd_track_at(149), -1);
  chk(!d->cd_is_audio(150), "data_not_audio", d->cd_is_audio(150), 0);
  chk(d->cd_is_audio(332), "audio_is_audio", d->cd_is_audio(332), 1);
  chk(!d->cd_is_audio(932), "leadout_not_audio", d->cd_is_audio(932), 0);
  chk(!d->cd_is_audio(5000), "past_end_not_audio", d->cd_is_audio(5000), 0);

  // ---- subcode index: 0 through an audio track's 150 sector pregap, 1 after;
  //      a data track is always index 1; past the lead-out must not read the
  //      track table with a nonsense index
  chk(d->get_track_index(482) == 0, "pregap_audio", d->get_track_index(482), 0);
  chk(d->get_track_index(500) == 0, "pregap_audio_mid", d->get_track_index(500), 0);
  chk(d->get_track_index(631) == 0, "pregap_audio_end", d->get_track_index(631), 0);
  chk(d->get_track_index(632) == 1, "index_after_pregap", d->get_track_index(632), 1);
  chk(d->get_track_index(100) == 1, "pregap_data_track", d->get_track_index(100), 1);
  chk(d->get_track_index(2000) == 1, "index_past_end", d->get_track_index(2000), 1);
  chk(image.type_lookups > 0, "type_lookups_happened", image.type_lookups, 1);

  // ---- distance to the lead-out
  d->cd_curfad = 332;
  chk(d->cd_sectors_to_leadout() == 600, "to_leadout_from_track2",
      d->cd_sectors_to_leadout(), 600);
  d->cd_curfad = 932;
  chk(d->cd_sectors_to_leadout() == 0, "to_leadout_at_end",
      d->cd_sectors_to_leadout(), 0);
  d->cd_curfad = 5000;
  chk(d->cd_sectors_to_leadout() == 0, "to_leadout_past_end",
      d->cd_sectors_to_leadout(), 0);

  // ---- Play Disc, track mode: play tracks 2 and 3.  An end position is the
  //      *last* index of the named track (ST-162-062094 printed p.53), so the
  //      range runs to the start of the track after track 3 - the lead-out of
  //      a three track disc - and has to be 600 sectors.
  auto reset = [&]() {
    d->cd_curfad = 150;
    d->cd_fad_seek = 150;
    d->fadstoplay = 0;
    d->cur_track = 0xff;
    d->playtype = 0;
    d->cd_stat = CD_STAT_PAUSE;
    d->cd_seek_stat = CD_STAT_PAUSE;
    d->hirqreg = 0;
    cdda = fake_cdda();
  };
  reset();
  d->cr1 = 0x1000; d->cr2 = (2 << 8); d->cr3 = 0; d->cr4 = (3 << 8);
  d->cmd_play_disc();
  chk(d->cd_fad_seek == 332, "play_track_seek", d->cd_fad_seek, 332);
  chk(d->cur_track == 1, "play_track_index", d->cur_track, 1);
  chk(d->fadstoplay == 600, "play_track_range", d->fadstoplay, 600);

  // ---- a single track: start and end name the same track, so the range is
  //      that track's own length and not an empty "will not play" range
  reset();
  d->cr1 = 0x1000; d->cr2 = (2 << 8); d->cr3 = 0; d->cr4 = (2 << 8);
  d->cmd_play_disc();
  chk(d->cd_fad_seek == 332, "play_one_track_seek", d->cd_fad_seek, 332);
  chk(d->fadstoplay == 300, "play_one_track_range", d->fadstoplay, 300);

  // ---- and the last track plays up to the lead-out
  reset();
  d->cr1 = 0x1000; d->cr2 = (3 << 8); d->cr3 = 0; d->cr4 = (3 << 8);
  d->cmd_play_disc();
  chk(d->fadstoplay == 300, "play_last_track_range", d->fadstoplay, 300);

  // ---- end track 0 is the default position: the end of the disc
  reset();
  d->cr1 = 0x1000; d->cr2 = (2 << 8); d->cr3 = 0; d->cr4 = 0;
  d->cmd_play_disc();
  chk(d->fadstoplay == 600, "play_track_default_end", d->fadstoplay, 600);

  // ---- start track 0 is also a default: the first track of the disc
  reset();
  d->cr1 = 0x1000; d->cr2 = 0; d->cr3 = 0; d->cr4 = (2 << 8);
  d->cmd_play_disc();
  chk(d->cd_fad_seek == 150, "play_default_start_seek", d->cd_fad_seek, 150);
  chk(d->fadstoplay == 482, "play_default_start_range", d->fadstoplay, 482);

  // ---- Play Disc, FAD mode: an end position is a *sector count* from the
  //      start position ("the end position is designated by sector number
  //      (FAD sector number) from the starting FAD", printed p.53; the manual
  //      states the range as End FAD = Start FAD + count - 1)
  reset();
  d->cr1 = 0x1080; d->cr2 = 332;              // start FAD 0x80014C
  d->cr3 = 0x0080; d->cr4 = 600;              // 600 sectors
  d->cmd_play_disc();
  chk(d->cd_fad_seek == 332, "play_fad_seek", d->cd_fad_seek, 332);
  chk(d->fadstoplay == 600, "play_fad_range", d->fadstoplay, 600);

  // ---- a count smaller than the start position is a short range, not the
  //      negative difference a position reading would produce
  reset();
  d->cr1 = 0x1080; d->cr2 = 332;
  d->cr3 = 0x0080; d->cr4 = 50;
  d->cmd_play_disc();
  chk(d->fadstoplay == 50, "play_fad_short_range", d->fadstoplay, 50);

  // ---- the 0xFFFFFF "no end" encoding means play to the lead-out
  reset();
  d->cr1 = 0x1080; d->cr2 = 332;
  d->cr3 = 0x00ff; d->cr4 = 0xffff;          // 0xFFFFFF end = no end
  d->cmd_play_disc();
  chk(d->fadstoplay == 600, "play_open_range", d->fadstoplay, 600);

  // ---- a range that runs off the disc is clamped to the lead-out
  reset();
  d->cr1 = 0x1080; d->cr2 = 850;             // start FAD 850, near the lead-out
  d->cr3 = 0x00ff; d->cr4 = 0xffff;
  d->cmd_play_disc();
  chk(d->cd_fad_seek == 850, "play_late_seek", d->cd_fad_seek, 850);
  chk(d->fadstoplay == 82, "play_late_range", d->fadstoplay, 82);

  // ---- resume from a pause plays out the rest of the current track.  The
  //      seek state is what the previous command left behind, so the range is
  //      measured from the position the pickup holds.
  reset();
  d->cd_curfad = 400;
  d->cur_track = 1;
  d->fadstoplay = 0;
  d->cr1 = 0x10ff; d->cr2 = 0xffff; d->cr3 = 0xffff; d->cr4 = 0xffff;
  d->cmd_play_disc();
  chk(d->fadstoplay == 232, "resume_range", d->fadstoplay, 232);

  // ---- a resume whose remaining range would leave the disc is clamped
  reset();
  d->cd_curfad = 900;
  d->cur_track = 2;
  d->cr1 = 0x10ff; d->cr2 = 0xffff; d->cr3 = 0xffff; d->cr4 = 0xffff;
  d->cmd_play_disc();
  chk(d->fadstoplay == 32, "resume_range_clamped", d->fadstoplay, 32);

  // ---- Seek Disc, track mode: host track number 3 is index 2, and the target
  //      is that track's start FAD
  reset();
  d->cr1 = 0x1100; d->cr2 = (3 << 8); d->cr3 = 0; d->cr4 = 0;
  d->cmd_seek_disc();
  chk(d->cur_track == 2, "seek_track_index", d->cur_track, 2);
  chk(d->cd_fad_seek == 632, "seek_track_fad", d->cd_fad_seek, 632);

  // ---- Seek Disc to a FAD, and the pause form
  reset();
  d->cr1 = 0x1180; d->cr2 = 0x014c; d->cr3 = 0; d->cr4 = 0;
  d->cmd_seek_disc();
  chk(d->cd_fad_seek == 332, "seek_fad", d->cd_fad_seek, 332);
  reset();
  d->cd_curfad = 400;
  d->cr1 = 0x11ff; d->cr2 = 0xffff; d->cr3 = 0; d->cr4 = 0;
  d->cmd_seek_disc();
  chk(d->cd_fad_seek == 400, "pause_holds_position", d->cd_fad_seek, 400);

  // ---- the Red Book converter is handed a logical LBA, not a FAD
  reset();
  d->cd_curfad = 332;
  d->fadstoplay = 300;
  d->cd_start_cdda();
  chk(cdda.starts == 1, "cdda_started", cdda.starts, 1);
  chk(cdda.lba == 182, "cdda_lba", long(cdda.lba), 182);
  chk(cdda.sectors == 300, "cdda_sectors", long(cdda.sectors), 300);
  chk(cdda.active, "cdda_active", cdda.active, 1);
  d->cd_stop_cdda();
  chk(cdda.stops == 1 && !cdda.active, "cdda_stopped", cdda.stops, 1);
  // a data track must never start it
  reset();
  d->cd_curfad = 200;
  d->fadstoplay = 50;
  d->cd_start_cdda();
  chk(cdda.starts == 0, "cdda_data_track_silent", cdda.starts, 0);
  chk(cdda.stops == 1, "cdda_data_track_stops", cdda.stops, 1);
  // an open range plays to the lead-out
  reset();
  d->cd_curfad = 632;
  d->fadstoplay = 0;
  d->cd_start_cdda();
  chk(cdda.sectors == 300, "cdda_open_range", long(cdda.sectors), 300);

  std::printf("CD CDDA MATH: %u position/range/CD-DA routing cases passed\n",
              cases);
  return 0;
}
'''


def main():
    source = build_source()
    harness = HARNESS.replace('// FUNCTIONS', source)
    with tempfile.TemporaryDirectory(prefix='cdda-math-') as tmp:
        path = Path(tmp) / 'cdda_math.cpp'
        path.write_text(harness)
        compiler = os.environ.get('CXX', 'g++')
        result = subprocess.run([compiler, '-std=c++17', '-Wall', '-O0', '-g',
                                 str(path), '-o', str(Path(tmp) / 'cdda_math')],
                                capture_output=True, text=True)
        if result.returncode:
            print(result.stderr[-4000:])
            raise AssertionError('harness did not compile')
        run = subprocess.run([str(Path(tmp) / 'cdda_math')],
                             capture_output=True, text=True)
        print(run.stdout, end='')
        if run.returncode:
            print(run.stderr[-2000:])
            raise AssertionError('CD-DA position cases failed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
