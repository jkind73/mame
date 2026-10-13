# Remaining source audit — 2026-10-13

The original rewrite checklist retains its original item membership and prose.
Partial fixes below do not close a combined item.

## CD-ROM legacy metadata

`cdrom_file::parse_metadata` previously indexed an empty or truncated legacy
metadata vector, read 595 words without validating its size, and accepted an
invalid track count after byte swapping. It now rejects incomplete metadata and
counts outside 1–99 before populating the TOC. Copying into aligned word storage
also removes the unaligned/aliasing access through a byte-vector pointer.
Existing valid legacy metadata in either accepted byte order is preserved.
This does not claim that the historical host-endian format has been redesigned.

`scripts/cdrom_legacy_metadata_test.py` extracts the actual production decoder
and track structure. ASan/UBSan pass all 2,380 truncated lengths, invalid counts,
and valid 1/99-track metadata in both byte orders. The parent decoder crashes on
empty metadata under the same fixture. The full Saturn/ST-V subtarget builds.
The combined nvram/ticket/cdrom checklist item remains open.
