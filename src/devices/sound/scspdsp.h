// license:BSD-3-Clause
// copyright-holders:ElSemi, R. Belmont
#ifndef MAME_SOUND_SCSPDSP_H
#define MAME_SOUND_SCSPDSP_H

#pragma once

//the DSP Context
struct SCSPDSP
{
//Config
	address_space *space;
	u32 RBP; //Ring buf pointer
	u32 RBL; //Delay ram (Ring buffer) size in words

//context

	struct DecodedStep {
		u8 TRA, TWT, TWA;
		u8 XSEL, YSEL, IRA, IWT, IWA;
		u8 TABLE, MWT, MRD, EWT, EWA, ADRL, FRCL, SHIFT, YRL, NEGB, ZERO, BSEL;
		u8 NOFL, COEF;
		u8 MASA, ADREB, NXADR;
	};

	DecodedStep MPRO_decoded[128];
	s16 COEF[64];     //16 bit signed
	u16 MADRS[32];   //offsets (in words), 16 bit
	u16 MPRO[128*4]; //128 steps 64 bit
	s32 TEMP[128];    //TEMP regs,24 bit signed
	s32 MEMS[32]; //MEMS regs,24 bit signed
	u32 DEC;

//input
	s32 MIXS[16]; //MIXS, 24 bit signed, accumulated by the slots during the current sample
	s32 MIXSPrev[16]; // the stack the program reads: the previous sample's MIXS (double buffered)
	s16 EXTS[2];  //External inputs (CDDA)    16 bit signed

//output
	s16 EFREG[16];    //EFREG, 16 bit signed

	bool Stopped;
	int LastStep;

// registers that keep their value from one sample to the next
	s32 AccReg;    // 26 bit
	s32 FrcReg;    // 13 bit
	s32 YReg;      // 24 bit
	u32 AdrsReg;   // 12 bit
	s32 InputsReg; // 24 bit, the INPUTS bus keeps its value when no source is selected

// memory access pipeline, carried over from one step (and sample) to the next
	bool ReadPending, ReadNOFL, WritePending;
	s32 ReadValue;      // 24 bit, the last finished read
	u16 WriteValue;
	u32 ReadWriteAddr;  // byte address of the pending read or write

	void Init();
	void SetSample(s32 sample, s32 SEL, s32 MXL);
	void Step();
	void Start();
	void DecodeStep(int step);   // decode one program step into MPRO_decoded
	void DecodeAll();            // decode the whole program (after loading a state)
};

#endif // MAME_SOUND_SCSPDSP_H
