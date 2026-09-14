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
