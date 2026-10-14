// license:BSD-3-Clause
// copyright-holders:MAMEdev Team
// Reference decoder from b11e8b66737, before the transparent-word fast path.
renderer::sprite_dot renderer::decode_sprite(decoded const &d, uint16_t data) const
{
	unsigned const type = d.sp_type;
	bool msb = false, nsd = false, tpen = false;
	unsigned pr = 0, cc = 0, dc = 0;
	auto const bit = [data](unsigned n) -> unsigned { return (data >> n) & 1; };
	auto const all_ones = [data](unsigned hi, unsigned lo) { unsigned const m = ((1U << (hi - lo + 1)) - 1) << lo; return (data & m) == m; };

	switch (type) {
	case 0x0: msb = 0; nsd = all_ones(10, 1) && !bit(0); tpen = 0; pr = (bit(15) << 1) | bit(14); cc = bits(data, 13, 11); dc = data & 0x7ff; break;
	case 0x1: msb = 0; nsd = all_ones(10, 1) && !bit(0); tpen = 0; pr = bits(data, 15, 13); cc = bits(data, 12, 11); dc = data & 0x7ff; break;
	case 0x2: msb = bit(15); nsd = all_ones(10, 1) && !bit(0); tpen = bit(15); pr = bit(14); cc = bits(data, 13, 11); dc = data & 0x7ff; break;
	case 0x3: msb = bit(15); nsd = all_ones(10, 1) && !bit(0); tpen = bit(15); pr = bits(data, 14, 13); cc = bits(data, 12, 11); dc = data & 0x7ff; break;
	case 0x4: msb = bit(15); nsd = all_ones(9, 1) && !bit(0); tpen = bit(15); pr = bits(data, 14, 13); cc = bits(data, 12, 10); dc = data & 0x3ff; break;
	case 0x5: msb = bit(15); nsd = all_ones(10, 1) && !bit(0); tpen = bit(15); pr = bits(data, 14, 12); cc = bit(11); dc = data & 0x7ff; break;
	case 0x6: msb = bit(15); nsd = all_ones(9, 1) && !bit(0); tpen = bit(15); pr = bits(data, 14, 12); cc = bits(data, 11, 10); dc = data & 0x3ff; break;
	case 0x7: msb = bit(15); nsd = all_ones(8, 1) && !bit(0); tpen = bit(15); pr = bits(data, 14, 12); cc = bits(data, 11, 9); dc = data & 0x1ff; break;
	case 0x8: msb = 0; nsd = all_ones(6, 1) && !bit(0); tpen = 1; pr = bit(7); cc = 0; dc = data & 0x7f; break;
	case 0x9: msb = 0; nsd = all_ones(5, 1) && !bit(0); tpen = 1; pr = bit(7); cc = bit(6); dc = data & 0x3f; break;
	case 0xa: msb = 0; nsd = all_ones(5, 1) && !bit(0); tpen = 1; pr = bits(data, 7, 6); cc = 0; dc = data & 0x3f; break;
	case 0xb: msb = 0; nsd = all_ones(5, 1) && !bit(0); tpen = 1; pr = 0; cc = bits(data, 7, 6); dc = data & 0x3f; break;
	case 0xc: msb = 0; nsd = all_ones(7, 1) && !bit(0); tpen = 1; pr = bit(7); cc = 0; dc = data & 0xff; break;
	case 0xd: msb = 0; nsd = all_ones(7, 1) && !bit(0); tpen = 1; pr = bit(7); cc = bit(6); dc = data & 0xff; break;
	case 0xe: msb = 0; nsd = all_ones(7, 1) && !bit(0); tpen = 1; pr = bits(data, 7, 6); cc = 0; dc = data & 0xff; break;
	default:  msb = 0; nsd = all_ones(7, 1) && !bit(0); tpen = 1; pr = 0; cc = bits(data, 7, 6); dc = data & 0xff; break;
	}

	bool const type8 = type & 8;
	bool const tp = !(((data & 0x7f00) && !type8) || (data & 0xff));
	bool const rgb_tp = type8 ? tp : (tp && tpen && d.sp_winen);
	bool const msd = msb && !tp && !d.sp_winen;
	bool const tsd = msb && tp && d.tpsdsl && !d.sp_winen;
	bool const pal_tp = tp || nsd || tsd;

	sprite_dot s;
	if (d.sp_clmd && bit(15)) {
		s.palette = false;
		s.tp = rgb_tp;
		s.wn = false;
		s.sd = false;
		s.pr = 0;
		s.cc = 0;
		s.dc = ((data & 0x1f) << 19) | (((data >> 5) & 0x1f) << 11) | (((data >> 10) & 0x1f) << 3);
	} else {
		s.palette = true;
		s.tp = pal_tp;
		s.wn = msb;
		s.sd = nsd || msd || tsd;
		s.pr = pr;
		s.cc = cc;
		s.dc = dc;
	}
	return s;
}
