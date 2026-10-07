// license:BSD-3-Clause
// copyright-holders:ElSemi, R. Belmont
#include "emu.h"
#include "scspdsp.h"

#include <cstring>


namespace {

u16 PACK(s32 val)
{
	int const sign = BIT(val, 23);
	u32 temp = (val ^ (val << 1)) & 0xFFFFFF;
	int exponent = 0;
	for (int k = 0; k < 12; k++)
	{
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

static s32 UNPACK(u16 val)
{
	int const sign = BIT(val, 15);
	int exponent = (val >> 11) & 0xF;
	int const mantissa = val & 0x7FF;
	s32 uval = mantissa << 11;
	if (exponent > 11)
	{
		exponent = 11;
		uval |= sign << 22;
	}
	else
	{
		uval |= (sign ^ 1) << 22;
	}
	uval |= sign << 23;
	uval <<= 8;
	uval >>= 8;
	uval >>= exponent;

	return uval;
}

} // anonymous namespace


void SCSPDSP::Init()
{
	std::memset(this, 0, sizeof(*this));
	RBL = (8*1024); // Initial RBL is 0
	Stopped = true;
}

void SCSPDSP::Step()
{
	if (Stopped)
	{
		std::fill(std::begin(MIXS), std::end(MIXS), 0);
		return;
	}

#if 0
	int dump=0;
	FILE *f=nullptr;
	if(dump)
		f=fopen("dsp.txt","wt");
#endif

	s32 ACC = AccReg;       //26 bit
	s32 FRC_REG = FrcReg;   //13 bit
	s32 Y_REG = YReg;       //24 bit
	u32 ADRS_REG = AdrsReg; //12 bit

	for (int step = 0; step < /*128*/LastStep; ++step)
	{
		DecodedStep const &inst = MPRO_decoded[step];

		u32 const TRA   = inst.TRA;
		u32 const TWT   = inst.TWT;
		u32 const TWA   = inst.TWA;

		u32 const XSEL  = inst.XSEL;
		u32 const YSEL  = inst.YSEL;
		u32 const IRA   = inst.IRA;
		u32 const IWT   = inst.IWT;
		u32 const IWA   = inst.IWA;

		u32 const TABLE = inst.TABLE;
		u32 const MWT   = inst.MWT;
		u32 const MRD   = inst.MRD;
		u32 const EWT   = inst.EWT;
		u32 const EWA   = inst.EWA;
		u32 const ADRL  = inst.ADRL;
		u32 const FRCL  = inst.FRCL;
		u32 const SHIFT = inst.SHIFT;
		u32 const YRL   = inst.YRL;
		u32 const NEGB  = inst.NEGB;
		u32 const ZERO  = inst.ZERO;
		u32 const BSEL  = inst.BSEL;

		u32 const NOFL  = inst.NOFL;
		u32 const COEF  = inst.COEF;

		u32 const MASA  = inst.MASA;
		u32 const ADREB = inst.ADREB;
		u32 const NXADR = inst.NXADR;

		//operations are done at 24 bit precision
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
			DUMP(MEMVAL);
			DUMP(FRC_REG);
			DUMP(Y_REG);
			DUMP(ADDR);
			DUMP(ADRS_REG);
			fprintf(f, "\n");
#undef DUMP
		}
#endif

		//INPUTS RW
		// colmns97 hits this
		//assert(IRA < 0x32);
		// an IRA beyond EXTS leaves INPUTS as the previous step had it (MiSTer SCSP.sv, Ymir DSP::Step)
		s32 INPUTS = InputsReg; // 24-bit
		if (IRA <= 0x1f)
			INPUTS = MEMS[IRA];
		else if (IRA <= 0x2F)
			INPUTS = MIXSPrev[IRA - 0x20] << 4;  //MIXS is 20 bit
		else if (IRA <= 0x31)
			INPUTS = EXTS[IRA - 0x30] << 8;  //EXTS is 16 bit

		INPUTS = util::sext(INPUTS, 24);
		InputsReg = INPUTS;


		//Operand sel
		s32 B; // 26-bit
		if (!ZERO)
		{
			if (BSEL)
				B = ACC;
			else
				B = util::sext(TEMP[(TRA + DEC) & 0x7f], 24);
			if (NEGB)
				B = 0 - B;
		}
		else
			B = 0;

		s32 X; // 24-bit
		if (XSEL)
			X = INPUTS;
		else
			X = util::sext(TEMP[(TRA + DEC) & 0x7f], 24);

		s32 Y = 0;  //13 bit
		if (YSEL == 0)
			Y = FRC_REG;
		else if (YSEL == 1)
			Y = this->COEF[COEF] >> 3;   //COEF is 16 bits
		else if (YSEL == 2)
			Y = (Y_REG >> 11) & 0x1fff;
		else if (YSEL == 3)
			Y = (Y_REG >> 4) & 0x0fff;

		if (YRL)
			Y_REG = INPUTS;

		//Shifter
		s32 SHIFTED = 0;    //24 bit
		if (SHIFT == 0)
			SHIFTED = std::clamp<s32>(ACC, -0x00800000, 0x007fffff);
		else if (SHIFT == 1)
			SHIFTED = std::clamp<s32>(ACC * 2, -0x00800000, 0x007fffff);
		else if (SHIFT == 2)
			SHIFTED = util::sext(ACC * 2, 24);
		else if (SHIFT == 3)
			SHIFTED = util::sext(ACC, 24);

		//ACCUM
		Y = util::sext(Y, 13);

		s64 const v = (s64(X) * s64(Y)) >> 12;
		ACC = util::sext(int(v + B), 26);

		if (TWT)
			TEMP[(TWA + DEC) & 0x7f] = SHIFTED;

		if (FRCL)
		{
			if (SHIFT == 3)
				FRC_REG = SHIFTED & 0x0fff;
			else
				FRC_REG = (SHIFTED >> 11) & 0x1fff;
		}

		if (IWT)
			MEMS[IWA] = ReadValue;   // the read issued two steps ago, see the pipeline below

		// A read or write issued by a step is carried out by the next one, with the address that step
		// calculated (MiSTer SCSP.sv DSP_READ/DSP_WRITE, Ymir DSP::Step), so the value of a read is
		// there for an IWT two steps after the MRD. A write waits while a read is carried out.
		if (ReadPending)
		{
			u16 const data = space->read_word(ReadWriteAddr);
			ReadValue = ReadNOFL ? s32(s16(data)) << 8 : UNPACK(data);
			ReadPending = false;
			ReadNOFL = false;
		}
		else if (WritePending)
		{
			space->write_word(ReadWriteAddr, WriteValue);
			WritePending = false;
		}

		{
			u32 ADDR = MADRS[MASA];
			if (!TABLE)
				ADDR += DEC;
			if (ADREB)
				ADDR += u32(util::sext(ADRS_REG, 12));
			if (NXADR)
				ADDR++;
			if (!TABLE)
				ADDR &= RBL - 1;
			else
				ADDR &= 0xffff;
			ADDR += RBP << 12;
			ReadWriteAddr = ADDR << 1;
		}

		if (MRD)
		{
			ReadPending = true;
			ReadNOFL = NOFL;
		}
		if (MWT)
		{
			WritePending = true;
			WriteValue = NOFL ? u16(SHIFTED >> 8) : PACK(SHIFTED);
		}

		if (ADRL)
		{
			if (SHIFT == 3)
				ADRS_REG = (SHIFTED >> 12) & 0xfff;
			else
				ADRS_REG = INPUTS >> 16;
		}

		if (EWT)
			EFREG[EWA] = SHIFTED >> 8;   // a register: the last value written stays
	}

	AccReg = ACC;
	FrcReg = FRC_REG;
	YReg = Y_REG;
	AdrsReg = ADRS_REG;

	// finish a write issued by the last step
	if (WritePending)
	{
		space->write_word(ReadWriteAddr, WriteValue);
		WritePending = false;
	}

	--DEC;
	// the slots fill one MIXS bank while the program reads the other (MiSTer SCSP.sv MIXS_GEN, Ymir mixStack)
	std::copy(std::begin(MIXS), std::end(MIXS), std::begin(MIXSPrev));
	std::fill(std::begin(MIXS), std::end(MIXS), 0);
	//if (f)
		//fclose(f);
}

void SCSPDSP::SetSample(s32 sample, int SEL, int MXL)
{
	//MIXS[SEL] += sample << (MXL + 1)/*7*/;
	MIXS[SEL] += sample;
	//if (MXL)
		//int a = 1;
}

// The program words are decoded once, when the host writes them, not at every sample: the fields
// of step `step` of MPRO
void SCSPDSP::DecodeStep(int step)
{
	u16 const *const IPtr = MPRO + (step * 4);
	DecodedStep &d = MPRO_decoded[step];
	d.TRA   = (IPtr[0] >>  8) & 0x7f;
	d.TWT   = (IPtr[0] >>  7) & 0x01;
	d.TWA   = (IPtr[0] >>  0) & 0x7f;

	d.XSEL  = (IPtr[1] >> 15) & 0x01;
	d.YSEL  = (IPtr[1] >> 13) & 0x03;
	d.IRA   = (IPtr[1] >>  6) & 0x3f;
	d.IWT   = (IPtr[1] >>  5) & 0x01;
	d.IWA   = (IPtr[1] >>  0) & 0x1f;

	d.TABLE = (IPtr[2] >> 15) & 0x01;
	d.MWT   = (IPtr[2] >> 14) & 0x01;
	d.MRD   = (IPtr[2] >> 13) & 0x01;
	d.EWT   = (IPtr[2] >> 12) & 0x01;
	d.EWA   = (IPtr[2] >>  8) & 0x0f;
	d.ADRL  = (IPtr[2] >>  7) & 0x01;
	d.FRCL  = (IPtr[2] >>  6) & 0x01;
	d.SHIFT = (IPtr[2] >>  4) & 0x03;
	d.YRL   = (IPtr[2] >>  3) & 0x01;
	d.NEGB  = (IPtr[2] >>  2) & 0x01;
	d.ZERO  = (IPtr[2] >>  1) & 0x01;
	d.BSEL  = (IPtr[2] >>  0) & 0x01;

	d.NOFL  = (IPtr[3] >>  8) & 0x01;
	d.COEF  = (IPtr[3] >>  9) & 0x3f;

	d.MASA  = (IPtr[3] >>  2) & 0x1f;
	d.ADREB = (IPtr[3] >>  1) & 0x01;
	d.NXADR = (IPtr[3] >>  0) & 0x01;
}

// Decode the whole program, e.g. after a saved state was loaded (MPRO is saved, its decoded copy is not)
void SCSPDSP::DecodeAll()
{
	for (int step = 0; step < 128; ++step)
		DecodeStep(step);
}

void SCSPDSP::Start()
{
	Stopped = false;
	int i;
	for (i = 127; i >= 0; --i)
	{
		u16 const *const IPtr = MPRO + (i * 4);
		if (IPtr[0] || IPtr[1] || IPtr[2] || IPtr[3])
			break;
	}
	// an all-zero instruction still updates the accumulator, and the hardware runs all 128 steps, so one
	// step past the last used one carries out the side effects of the program (Ymir UpdateProgramLength)
	LastStep = std::min(i + 2, 128);

}
