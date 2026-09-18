// license:BSD-3-Clause
// copyright-holders:ElSemi, R. Belmont
#include "emu.h"
#include "scspdsp.h"


#include <cstring>

namespace {

u16 PACK(s32 val) {
  int const sign = BIT(val, 23);
  u32 temp = (val ^ (val << 1)) & 0xFFFFFF;
  int exponent = 0;
  for (int k = 0; k < 12; k++) {
    if (temp & 0x800000)
      break;
    temp <<= 1;
    exponent += 1;
  }
  if (exponent < 12)
    val = (val << exponent) & 0x3FFFFF;
  else
    val <<= 11;
  val >>= 11;
  val &= 0x7FF;
  val |= sign << 15;
  val |= exponent << 11;

  return u16(val);
}

static s32 UNPACK(u16 val) {
  int const sign = BIT(val, 15);
  int exponent = (val >> 11) & 0xF;
  int const mantissa = val & 0x7FF;
  s32 uval = mantissa << 11;
  if (exponent > 11) {
    exponent = 11;
    uval |= sign << 22;
  } else {
    uval |= (sign ^ 1) << 22;
  }
  uval |= sign << 23;
  uval <<= 8;
  uval >>= 8;
  uval >>= exponent;

  return uval;
}

} // anonymous namespace

void SCSPDSP::Init() {
  std::memset(this, 0, sizeof(*this));
  RBL = (8 * 1024); // Initial RBL is 0
  Stopped = true;
}

void SCSPDSP::Step() {
  if (Stopped) {
    // MIXS is consumed every sample period, even when the DSP program is
    // stopped, otherwise the slot inputs would pile up until it is started
    std::fill(std::begin(MIXS), std::end(MIXS), 0);
    return;
  }

  /* EFREG is a register file, not a per-sample scratchpad: an entry the
     program never writes keeps its previous value.  The MiSTer core models it
     as a RAM the effect mixer reads at slot 0 and Ymir never clears it, so
     clearing it here would mute any effect return a program leaves untouched
     for a sample. */

#if 0
	int dump=0;
	FILE *f=nullptr;
	if(dump)
		f=fopen("dsp.txt","wt");
#endif

  /* ACC, FRC_REG, Y_REG and ADRS_REG are chip registers that persist across
     samples; see the declaration in scspdsp.h. */

  for (int step = 0; step < /*128*/ LastStep; ++step) {
    u16 *const IPtr = MPRO + (step * 4);

    // if (!IPtr[0] && !IPtr[1] && !IPtr[2] && !IPtr[3])
    // break;

    u32 const TRA = (IPtr[0] >> 8) & 0x7f;
    u32 const TWT = (IPtr[0] >> 7) & 0x01;
    u32 const TWA = (IPtr[0] >> 0) & 0x7f;

    u32 const XSEL = (IPtr[1] >> 15) & 0x01;
    u32 const YSEL = (IPtr[1] >> 13) & 0x03;
    u32 const IRA = (IPtr[1] >> 6) & 0x3f;
    u32 const IWT = (IPtr[1] >> 5) & 0x01;
    u32 const IWA = (IPtr[1] >> 0) & 0x1f;

    u32 const TABLE = (IPtr[2] >> 15) & 0x01;
    u32 const MWT = (IPtr[2] >> 14) & 0x01;
    u32 const MRD = (IPtr[2] >> 13) & 0x01;
    u32 const EWT = (IPtr[2] >> 12) & 0x01;
    u32 const EWA = (IPtr[2] >> 8) & 0x0f;
    u32 const ADRL = (IPtr[2] >> 7) & 0x01;
    u32 const FRCL = (IPtr[2] >> 6) & 0x01;
    u32 const SHIFT = (IPtr[2] >> 4) & 0x03;
    u32 const YRL = (IPtr[2] >> 3) & 0x01;
    u32 const NEGB = (IPtr[2] >> 2) & 0x01;
    u32 const ZERO = (IPtr[2] >> 1) & 0x01;
    u32 const BSEL = (IPtr[2] >> 0) & 0x01;

    /* NOFL sits at bit 8 of the fourth instruction word, with bit 15 unused.
       Four independent implementations agree on that placement: the MiSTer
       core's MPRO_t record (UNUSED at 63/44/15/7, NOFL at 8), Ymir's
       scsp_dsp_instr.hpp bitfield, mednafen's SS_SCSP DSP decoder (which
       even asserts the unused bits of this layout) and SaturnRecomp, which
       validates against real-hardware probes.  The older "bit 15" reading
       (yabause, and an early draft of the cassini notes) put NOFL in a
       reserved bit, so NOFL=1 programs - linear-format delay lines - were
       never honoured and their memory was mis-decoded as floating point. */
    u32 const NOFL = (IPtr[3] >> 8) & 0x01;
    u32 const COEF = (IPtr[3] >> 9) & 0x3f;

    // MASA is bits 6-2, selecting one of the 32 MADRS entries (Saturn); the
    // AICA widens it to 6 bits and shifts it, which is where the old doubt
    // about this field came from
    u32 const MASA = (IPtr[3] >> 2) & 0x1f;
    u32 const ADREB = (IPtr[3] >> 1) & 0x01;
    u32 const NXADR = (IPtr[3] >> 0) & 0x01;

    // operations are done at 24 bit precision
#if 0
		if (MASA)
			int a=1;
		if (NOFL)
			int a=1;

		//int dump=0;

		if (f)
		{
#define DUMP(v) fprintf(f, " " #v ": %04X", v);
			fprintf(f, "%d: ", step);
			DUMP(ACC);
			DUMP(SHIFTED);
			DUMP(X);
			DUMP(Y);
			DUMP(B);
			DUMP(INPUTS);
			DUMP(ReadValue);
			DUMP(FRC_REG);
			DUMP(Y_REG);
			DUMP(ADDR);
			DUMP(ADRS_REG);
			fprintf(f, "\n");
#undef DUMP
		}
#endif

    /* INPUTS RW.  INPUTS is a latch rather than a per-step temporary: a step
       loads it from MEMS, MIXS or EXTS according to IRA and otherwise leaves it
       holding its previous value.  IRA $32-$3F is reserved and is exactly that
       "no load" case - it must not abandon the step, because returning here
       also skips the remaining microprogram, the MDEC_CT decrement and the MIXS
       clear for this sample.  colmns97 runs a program that reaches it. */
    if (IRA <= 0x1f)
      INPUTS = MEMS[IRA];
    else if (IRA <= 0x2F)
      INPUTS = MIXS[IRA - 0x20] << 4; // MIXS is 20 bit
    else if (IRA <= 0x31)
      INPUTS = EXTS[IRA - 0x30] << 8; // EXTS is 16 bit

    INPUTS = util::sext(INPUTS, 24);

    if (IWT) {
      // ReadValue was latched by the read completed in the previous step
      MEMS[IWA] = ReadValue;
      if (IRA == IWA)
        INPUTS = ReadValue;
    }

    // Operand sel
    s32 B; // 26-bit
    if (!ZERO) {
      if (BSEL)
        B = ACC;
      else
        B = util::sext(TEMP[(TRA + DEC) & 0x7f], 24);
      if (NEGB)
        B = 0 - B;
    } else
      B = 0;

    s32 X; // 24-bit
    if (XSEL)
      X = INPUTS;
    else
      X = util::sext(TEMP[(TRA + DEC) & 0x7f], 24);

    s32 Y = 0; // 13 bit
    if (YSEL == 0)
      Y = FRC_REG;
    else if (YSEL == 1)
      Y = this->COEF[COEF] >> 3; // COEF is 16 bits
    else if (YSEL == 2)
      Y = (Y_REG >> 11) & 0x1fff;
    else if (YSEL == 3)
      Y = (Y_REG >> 4) & 0x0fff;

    if (YRL)
      Y_REG = INPUTS;

    // Shifter
    s32 SHIFTED = 0; // 24 bit
    if (SHIFT == 0)
      SHIFTED = std::clamp<s32>(ACC, -0x00800000, 0x007fffff);
    else if (SHIFT == 1)
      SHIFTED = std::clamp<s32>(ACC * 2, -0x00800000, 0x007fffff);
    else if (SHIFT == 2)
      SHIFTED = util::sext(ACC * 2, 24);
    else if (SHIFT == 3)
      SHIFTED = util::sext(ACC, 24);

    // ACCUM
    Y = util::sext(Y, 13);

    /* the 24-bit X by 13-bit Y product is shifted down by 12 and added to the
       26-bit B operand; the sum is held in a 26-bit accumulator, so it has to
       be masked and sign extended or an overflow into bit 26 reads back through
       BSEL with the wrong sign */
    s64 const v = (s64(X) * s64(Y)) >> 12;
    ACC = util::sext(int(v + B) & 0x3ffffff, 26);

    if (TWT)
      TEMP[(TWA + DEC) & 0x7f] = SHIFTED;

    if (FRCL) {
      if (SHIFT == 3)
        FRC_REG = SHIFTED & 0x0fff;
      else
        FRC_REG = (SHIFTED >> 11) & 0x1fff;
    }

    /* Complete the access the previous step requested before raising a new
       one.  One access per step, reads first: a step that both reads and
       writes leaves the write for the step after. */
    if (ReadPending) {
      u16 const tmp = space->read_word(RWAddr);
      ReadValue = (ReadPending == 2) ? (s32(tmp) << 8) : UNPACK(tmp);
      ReadPending = 0;
    } else if (WritePending) {
      space->write_word(RWAddr, WriteValue);
      WritePending = false;
    }

    {
      u32 ADDR = MADRS[MASA];
      if (!TABLE)
        ADDR += DEC;
      if (ADREB)
        ADDR += ADRS_REG & 0x0FFF;
      if (NXADR)
        ADDR++;
      if (!TABLE)
        ADDR &= RBL - 1;
      else
        ADDR &= 0xffff;
      ADDR += RBP << 12;
      ADDR <<= 1;
      RWAddr = ADDR;

      /* The manual's "memory flags are permitted only in odd steps" is a
         programming rule, not a hardware gate: MiSTer, mednafen and
         SaturnRecomp all honour MRD/MWT on any step, so programs that
         ignore the rule must still get their access. */
      if (MRD)
        ReadPending = NOFL ? 2 : 1;
      if (MWT) {
        WritePending = true;
        WriteValue = NOFL ? u16(SHIFTED >> 8) : PACK(SHIFTED);
      }
    }

    if (ADRL) {
      if (SHIFT == 3)
        ADRS_REG = (SHIFTED >> 12) & 0xfff;
      else
        ADRS_REG = INPUTS >> 16;
    }

    // EFREG writes replace the current value rather than accumulating, so that
    // when several steps in one cycle target the same index the last one wins
    if (EWT)
      EFREG[EWA] = SHIFTED >> 8;
  }
  /* a write requested by the program's last step still reaches memory once
     the program ends (SaturnRecomp services it the same way) */
  if (WritePending) {
    space->write_word(RWAddr, WriteValue);
    WritePending = false;
  }

  --DEC;
  std::fill(std::begin(MIXS), std::end(MIXS), 0);
  // if (f)
  // fclose(f);
}

void SCSPDSP::SetSample(s32 sample, int SEL, int MXL) {
  // MIXS[SEL] += sample << (MXL + 1)/*7*/;
  MIXS[SEL] += sample;
  // if (MXL)
  // int a = 1;
}

void SCSPDSP::Start() {
  Stopped = false;
  int i;
  for (i = 127; i >= 0; --i) {
    u16 const *const IPtr = MPRO + (i * 4);
    if (IPtr[0] || IPtr[1] || IPtr[2] || IPtr[3])
      break;
  }
  LastStep = i + 1;
}
