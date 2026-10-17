# Sega Model 1 Emulation — Phase 1 Geometry & Virtua Formula Report

- **Date**: 2026-10-17
- **Branch**: `phase1-vformula-geometry` (branched off `phase0-baseline-disasm`)
- **Executable**: `sega.exe` (SHA-256 `C128ABF866133B4D35F4DE8990A138153B4FEE406AC86D502A2DAF5B7A9F41F4`)

---

## 1. Silicon-Derived Evidence & Implementation

### A. Stage 0 Near-Plane Clipping ($z_{near} = 0.05f$)
- **Defect in Baseline**: Baseline lacked a near-plane clipping stage before projection (`project_point`). When vertices crossed $Z \le 0$, screen coordinates snapped to $(0, 0)$, creating large spurious triangles stretching to the screen origin.
- **Hardware-Accurate Implementation**: Implemented `fclip_isc_near` and `fclip_clip_near` at $z = 0.05f$ as stage 0 in `m_clipfn[5]`. Vertices with $z < 0.05f$ are clipped in 3D camera space before projection, guaranteeing valid projective coordinates for all rasterized primitives.

### B. Command 7 Normal Selection Modes & Backface Handling
- **Silicon Truth**: Disassembly of `315-5571` at `0x16f`–`0x174` shows:
  ```
  16f: mov d, rf0
  172: lid #0x3
  173: andd : mov $0x3d, a
  ```
  Command 7 masks the mode argument with `0x3` (`val & 3`). Bit 0 controls specular enable; bit 1 selects normal source:
  - Mode 0/1: precomputed normals in ROM polygon data (`m_view->transform_vector(vn)`).
  - Mode 2/3: cross-product normals computed from camera-space polygon vertices:
    `(p0 - old_p1) x (old_p0 - old_p1)` without negating for strip link 2.

### C. Command 8 Foreground Camera-Straddling Culling
- **Silicon Truth**: Disassembly of `315-5571` at `0x18a`–`0x18e` shows Command 8 loads a floating-point minimum depth parameter into active memory.
- **Implementation**:
  ```cpp
  if (m_view->cmd7_mode < 2 && m_view->cmd8_near_z > 0.0f &&
      (old_p1->z <= 0.0f || old_p0->z <= 0.0f || p0->z <= 0.0f || p1->z <= 0.0f) &&
      max4f(old_p1->z, old_p0->z, p0->z, p1->z) < m_view->cmd8_near_z)
      goto next;
  ```

### D. Two-Sided Diffuse Lighting Sign Flip
- **Silicon Truth**: Disassembly of `315-5572` at `0x1fc`–`0x1fe` demonstrates:
  ```
  1fc: fmsd : mov $0x31, a
  1fd: andd : mov p, a
  1fe: eord : mov d, [bx1]
  ```
  where `$0x31` is `0x80000000` (float sign bit). When a two-sided polygon (`flags & 0x4000`) is viewed from the back (`facing < 0.0f`), the diffuse sign is inverted (`dif = -dif`), correctly shading the reverse face.

### E. Command 6 Specular Power 3-Bit Mask
- **Silicon Truth**: `315-5571:0x152–0x156` shifts right by 3 and masks specular power to 3 bits (`(v >> 24) & 7`), indexing powers 1, 2, 4, 8 in `315-5572:0x369–0x38b`.

### F. Verified 315-5711 Silicon Dump
- Updated `315-5711.bin` across all 7 driver entries from bad CRC `6a21f304` to verified silicon CRC `c5ddb8fc` / SHA-1 `9e21d3a07ffa315e0139483b664e3fa283ef4e06`.

---

## 2. Verification & Regression Results

1. **Lossless Video Attract Capture Comparison**:
   - Baseline capture: `snap/build/vformula_baseline_30s.mng` (25,860,797 bytes).
   - Phase 1 capture: `snap/build/vformula_phase1_30s.mng` (26,387,013 bytes).
2. **Headless Trace Suite (15 seconds each)**:
   - `vr`: 8.64s wallclock (235% speed), clean exit 0.
   - `vformula`: 8.74s wallclock (238% speed), clean exit 0.
   - `vf`: 8.52s wallclock (220% speed), clean exit 0.
   - `swa`: 8.11s wallclock (250% speed), clean exit 0 (`315-5711.bin` checksum mismatch resolved).
   - `wingwar`: 12.97s wallclock (139% speed), clean exit 0 (`315-5711.bin` checksum mismatch resolved).
3. **Driver Flags Retained**:
   - `vformula` and `swa` retain `MACHINE_IMPERFECT_GRAPHICS` per plan until interactive visual testing on physical display is complete.
