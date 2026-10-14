#!/usr/bin/env python3
# license:BSD-3-Clause
"""Align read-only bitmap captures by source bytes, independently of emulated time.

Records contain a big-endian frame number followed by a fixed-size bitmap.
This compares all captured bitmap bytes; equal frame numbers are not assumed
to represent the same stage of a movie or attract sequence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def frames(path, bitmap_bytes):
    result = {}
    with path.open('rb') as source:
        while header := source.read(4):
            data = source.read(bitmap_bytes)
            if len(header) != 4 or len(data) != bitmap_bytes:
                raise ValueError(f'{path}: truncated record')
            frame = struct.unpack('>I', header)[0]
            if frame in result:
                raise ValueError(f'{path}: duplicate frame {frame}')
            result[frame] = hashlib.sha256(data).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reference', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--bitmap-bytes', type=lambda v: int(v, 0), default=0x38000)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.bitmap_bytes <= 0:
        parser.error('--bitmap-bytes must be positive')
    reference = frames(args.reference, args.bitmap_bytes)
    candidate = frames(args.candidate, args.bitmap_bytes)
    index = {}
    for frame, digest in reference.items():
        index.setdefault(digest, []).append(frame)
    matches = {frame: index[digest] for frame, digest in candidate.items() if digest in index}
    result = {
        'reference': str(args.reference.resolve()),
        'candidate': str(args.candidate.resolve()),
        'bitmap_bytes': args.bitmap_bytes,
        'reference_frames': len(reference),
        'candidate_frames': len(candidate),
        'matched_candidate_frames': len(matches),
        'matches': matches,
    }
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f'{len(matches)}/{len(candidate)} candidate bitmaps match a reference bitmap')


if __name__ == '__main__':
    main()
