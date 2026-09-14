// license:BSD-3-Clause
// copyright-holders:ElSemi, R. Belmont
#ifndef MAME_SOUND_SCSPDSP_H
#define MAME_SOUND_SCSPDSP_H

#pragma once

// the DSP Context
struct SCSPDSP {
  // Config
  address_space *space;
  u32 RBP; // Ring buf pointer
  u32 RBL; // Delay ram (Ring buffer) size in words

  // context

  s16 COEF[64];      // 16 bit signed
  u16 MADRS[32];     // offsets (in words), 16 bit
  u16 MPRO[128 * 4]; // 128 steps 64 bit
  s32 TEMP[128];     // TEMP regs,24 bit signed
  s32 MEMS[32];      // MEMS regs,24 bit signed
  u32 DEC;

  // input
  s32 MIXS[16]; // MIXS, 24 bit signed
  s16 EXTS[2];  // External inputs (CDDA)    16 bit signed

  // runtime registers, not memory mapped - INPUTS is a latch, so it keeps its
  // value across steps and across samples until a step loads a new one
  s32 INPUTS; // 24 bit signed

  /* The remaining runtime registers are chip state, not per-sample
     temporaries: the MiSTer core holds Y_REG/FRC_REG/ADRS_REG and the
     adder/shifter register as module-level registers that only a hard reset
     clears, and Ymir keeps them as save-stated members.  Zeroing them at the
     start of every sample would truncate any effect whose program carries a
     partial result (an interpolated address fraction, a latched Y operand)
     across a sample boundary. */
  s32 ACC;      // 26 bit signed
  s32 FRC_REG;  // 13 bit
  s32 Y_REG;    // 24 bit signed
  s32 ADRS_REG; // 12 bit

  /* Sound-memory access pipeline.  A request raised by step N is carried out
     during step N+1, and the value a read latches is what IWT of step N+2
     stores: the DRAM port moves one access per step, so a pending read also
     defers a pending write.  mednafen (ReadPending = 1 + NOFL), SaturnRecomp
     (read_pending / write_pending) and the cassini model all carry the same
     two flags, and the MiSTer core implements them as the DSP_READ/DSP_WRITE
     pipeline stages with NOFL delayed through NOFL1/NOFL2.  Doing the access
     in the requesting step instead makes delay lines read one sample early. */
  u32 RWAddr;     // byte address of the pending access
  s32 ReadValue;  // last value latched by a completed read
  u8 ReadPending; // 0 = none, 1 = convert from float, 2 = raw (NOFL)
  bool WritePending;
  u16 WriteValue;

  // output
  s16 EFREG[16]; // EFREG, 16 bit signed

  bool Stopped;
  int LastStep;

  void Init();
  void SetSample(s32 sample, s32 SEL, s32 MXL);
  void Step();
  void Start();
};

#endif // MAME_SOUND_SCSPDSP_H
