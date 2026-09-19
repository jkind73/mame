#!/usr/bin/env python3
"""Generate a synthetic CD image (CUE/BIN) for CD-DA work: a MODE1/2352 data
track (a minimal ISO9660 volume) followed by audio tracks with a known tone.

The image is generated, not copied: every byte comes from this script, so it can
be regenerated and shipped as a fixture without any third-party content.
"""
import argparse
import math
import struct
from pathlib import Path

SECTOR = 2352
DATA = 2048
SYNC = bytes([0x00, 0xFF] * 5 + [0x00])


def msf(lba):
    """Sector time as (m, s, f) in 75-frame seconds.  The disc's absolute time
    counts from the lead-in, so LBA 0 is MSF 00:02:00."""
    total = lba + 150
    return total // (60 * 75), (total // 75) % 60, total % 75


def mode1_sector(lba, data):
    """A MODE1/2352 raw sector: sync, header, 2048 user bytes, zero EDC/ECC.

    EDC/ECC are left zero: the emulator's sector reader extracts the user data
    fields, and the CD block's own error correction is not modelled.
    """
    m, s, f = msf(lba)
    header = bytes([m, s, f, 0x01])
    return SYNC + header + data + b'\x00' * (SECTOR - 16 - DATA)


def iso_dir_record(name, lba, size, flags):
    rec = bytearray(33 + len(name) + (1 - len(name) % 2))
    rec[0] = len(rec)
    rec[2:6] = struct.pack('<I', lba)
    rec[6:10] = struct.pack('<I', size)
    rec[25] = flags
    rec[28:30] = struct.pack('<H', 1)
    rec[30] = len(name)
    rec[32:32 + len(name)] = name.encode('ascii')
    if len(rec) > 33 + len(name):
        rec[33 + len(name)] = 0
    return bytes(rec)


def build_iso():
    """A one-file ISO9660 volume: PVD at LBA 16, directory at 17, file at 18."""
    sectors = {}

    def write_lba(lba, payload):
        for i in range(0, len(payload), DATA):
            chunk = payload[i:i + DATA]
            sectors[lba + i // DATA] = chunk.ljust(DATA, b'\x00')

    # root directory: '.', '..' and one file
    dir_data = (iso_dir_record('\x00', 17, DATA, 0x02) +
                iso_dir_record('\x01', 17, DATA, 0x02) +
                iso_dir_record('TEST.DAT;1', 18, DATA, 0x00))
    write_lba(17, dir_data)

    file_data = bytes((i * 7 + 3) & 0xFF for i in range(DATA))
    write_lba(18, file_data)

    pvd = bytearray(DATA)
    pvd[0] = 1
    pvd[1:6] = b'CD001'
    pvd[8:40] = b' '*8 + b'SATURN' + b' '*24
    pvd[40:72] = b' '*8 + b'SYNTHDISC' + b' '*22
    pvd[80:88] = struct.pack('<II', 19, 19)          # volume space size
    pvd[120:124] = struct.pack('<HHI', 1, 1, 0)      # set size / seq
    pvd[128:132] = struct.pack('<I', DATA)           # logical block size
    pvd[132:140] = struct.pack('<II', 0, 0)
    pvd[156:190] = (iso_dir_record('\x00', 17, DATA, 0x02) + b'\x00' * 34)[:34]
    pvd[190:318] = (b'SATURN' + b' ' * 120)[:128]
    pvd[318:446] = (b'SYNTHDISC' + b' ' * 120)[:128]
    pvd[881] = 0
    write_lba(16, bytes(pvd))
    # a terminator volume descriptor so the BIOS's scan ends cleanly
    term = bytearray(DATA)
    term[0] = 0xFF
    term[1:6] = b'CD001'
    term[6] = 1
    write_lba(20, bytes(term))
    return sectors


def build_audio(lba, seconds, hz, amplitude):
    """A stereo tone: left = sine, right = sine at half amplitude and opposite
    phase, 44100 Hz samples, 588 samples per sector (2352 bytes)."""
    out = bytearray()
    n = int(44100 * seconds)
    for i in range(n):
        t = i / 44100.0
        l = int(amplitude * math.sin(2 * math.pi * hz * t))
        r = int(amplitude * 0.5 * math.sin(2 * math.pi * hz * t + math.pi))
        out += struct.pack('>hh', l, r)
    out.ljust(((len(out) + SECTOR - 1) // SECTOR) * SECTOR, b'\x00')
    return bytes(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--audio-seconds', type=float, default=4.0)
    ap.add_argument('--tone-hz', type=float, default=1000.0)
    ap.add_argument('--amplitude', type=int, default=20000)
    args = ap.parse_args()

    audio_len = int(44100 * args.audio_seconds)
    audio_sectors = (audio_len * 4 + SECTOR - 1) // SECTOR
    # track 1: the data sectors; track 2 keeps its two second pregap as INDEX 00
    # at the end of the data area and INDEX 01 150 sectors later, so the audio
    # begins at a two second boundary exactly as a pressed disc does
    data_sectors = 32
    data_lba = 0
    pregap = 150
    audio1_lba = data_sectors + pregap
    audio2_lba = audio1_lba + audio_sectors
    total = audio2_lba + audio_sectors

    iso = build_iso()
    sectors = []
    # the data track runs to the end of the volume, then the first audio track's
    # pregap: 150 seconds-worth of silence, which INDEX 00 covers
    for lba in range(data_lba, data_lba + data_sectors):
        sectors.append(mode1_sector(lba, iso.get(lba, b'\x00' * DATA)))
    sectors.append(b'\x00' * (pregap * SECTOR))
    bin_path = args.output.with_suffix('.bin')
    with bin_path.open('wb') as out:
        for sector in sectors:
            out.write(sector)
        out.write(build_audio(audio1_lba, args.audio_seconds, args.tone_hz,
                              args.amplitude))
        out.write(build_audio(audio2_lba, args.audio_seconds, args.tone_hz * 2,
                              args.amplitude))

    cue = ['FILE "%s" BINARY' % bin_path.name]
    cue.append('  TRACK 01 MODE1/2352')
    cue.append('    INDEX 01 %s' % msf_string(0))
    cue.append('  TRACK 02 AUDIO')
    cue.append('    INDEX 00 %s' % msf_string(data_sectors))
    cue.append('    INDEX 01 %s' % msf_string(audio1_lba))
    cue.append('  TRACK 03 AUDIO')
    cue.append('    INDEX 01 %s' % msf_string(audio2_lba))
    cue_path = args.output.with_suffix('.cue')
    cue_path.write_text('\n'.join(cue) + '\n')
    print('wrote %s (%d bytes, %d sectors: %d data, %d audio track 2, %d audio '
          'track 3)' % (bin_path, bin_path.stat().st_size, total, data_sectors,
                        audio_sectors, audio_sectors))
    print('audio track 2 starts at LBA %d (%s), track 3 at LBA %d (%s)'
          % (audio1_lba, msf_string(audio1_lba), audio2_lba,
             msf_string(audio2_lba)))
    print('cue: %s' % cue_path)


def msf_string(lba):
    """CUE MSF: the disc's absolute time, i.e. LBA + 150 lead-in sectors."""
    return '%02d:%02d:%02d' % msf(lba)


if __name__ == '__main__':
    main()
