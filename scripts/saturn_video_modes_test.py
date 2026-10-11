#!/usr/bin/env python3
# license:BSD-3-Clause
"""Exercise actual sprite adapter and CRTC methods for Sega STN-22/23/24."""
from pathlib import Path
import subprocess
import tempfile
from saturn_vdp_wip_test import method

root = Path(__file__).resolve().parent.parent
sega = root / 'src/mame/sega'
source = (sega / 'saturn.cpp').read_text()
start = source.index('class saturn_state::vdp2_sprite_fb')
end = source.index('\n};', start) + 3
adapter = source[start:end].replace('saturn_state::vdp2_sprite_fb', 'vdp2_sprite_fb')
vdp1 = (sega / 'saturn_vdp1.cpp').read_text()
crtc = (sega / 'saturn_vdp2.cpp').read_text()
names = ['get_hblank_duration', 'get_vblank_duration', 'get_pixel_clock', 'get_vblank_start_position', 'get_ystep_count', 'horizontal_phase', 'counter_increment_dot', 'get_hcounter', 'get_vcounter', 'get_hblank', 'get_vblank', 'hblank_in_dot', 'hblank_out_dot', 'dot_scale', 'exlat_w']
def crtc_method(name):
    return method(crtc.replace('saturn_vdp2_device::', 'saturn_vdp1_device::'), name).replace('saturn_vdp1_device::', 'saturn_vdp2_device::')
fixture = r'''
#include <cassert>
#include <algorithm>
#include <cstdint>
#include <array>
#include <memory>
#include "saturn_vdp2_render.h"
using saturn_vdp2_render::sprite_source;
using u8 = uint8_t;
constexpr bool BIT(unsigned x, unsigned n) { return (x >> n) & 1; }
struct saturn_vdp1_device {
    mutable unsigned px=0, py=0; mutable bool field=false;
    std::array<uint16_t,512*256> buffer{};
    std::unique_ptr<uint16_t[]> m_field_copy[2];
    unsigned m_field_cur=0; bool m_disp_die=false,m_disp_dil=false,m_prev_die=false,m_prev_dil=false;
    bool packed=false;
    bool bpp8() const {return packed;}
    const uint16_t* display_buffer() const {return buffer.data();}
    uint16_t display_pixel(unsigned x,unsigned y) const;
    uint16_t display_pixel_field(unsigned x,unsigned y) const;
    uint16_t display_rotated_pixel(int32_t,int32_t) const {return 0;}
};
struct saturn_vdp2_device {
    unsigned m_hreso=0,m_lsmd=0,m_is_pal=0,m_vreso=0;
    unsigned m_hdisplay=320; bool m_exlat_level=true,m_exlten=false,m_exltfg=false;
    uint16_t m_hcounter_latch=0,m_vcounter_latch=0;
    uint16_t true_vcount[313][4]{};
    struct screen {int x=0,y=0,total=525;int height() const {return total;} int hpos() const {return x;}int vpos() const {return y;}unsigned frame_number() const {return 0;}} storage, *m_screen=&storage;
    unsigned clock() const {return 53693175;}
    int get_hblank_duration(); int get_vblank_duration(); int get_pixel_clock();
    int get_vblank_start_position(); int get_ystep_count();
    int horizontal_phase() const;int counter_increment_dot() const;
    int get_hcounter();int get_vcounter();int get_hblank();int get_vblank();
    int hblank_in_dot() const;int hblank_out_dot() const;int dot_scale() const;
    void exlat_w(int);
};
// METHODS
int main() {
    saturn_vdp1_device v;
    v.m_field_copy[0]=std::make_unique<uint16_t[]>(512*256);
    v.m_field_copy[1]=std::make_unique<uint16_t[]>(512*256);
    for(unsigned i=0;i<512*256;++i) {v.buffer[i]=0x1234;v.m_field_copy[1][i]=0x5678;}
    for(bool packed:{false,true}) for(unsigned parity:{0U,1U}) {
        v.packed=packed; v.m_disp_die=v.m_prev_die=true;
        v.m_disp_dil=parity;v.m_prev_dil=!parity;
        unsigned cur=packed?0xff12:0x1234, prev=packed?0xff56:0x5678;
        assert(v.display_pixel_field(0,34+parity)==cur);
        assert(v.display_pixel_field(0,34+!parity)==prev);
    }
    for(unsigned h=0;h<8;++h) for(bool packed:{false,true}) {
        bool half=packed && (h&6)==0;
        bool twice=(!packed && (h&6)==2) || (h&6)==6;
        vdp2_sprite_fb adapter(v,false,half,twice);
        adapter.sprite_word(100,17);
        assert(v.px==(half?200U:twice?50U:100U));
        assert(v.py==17 && !v.field);
    }
    for(unsigned lsmd:{0U,1U,3U}) for(bool die:{false,true}) for(unsigned parity:{0U,1U}) {
        bool fields=lsmd==3 || (lsmd==1 && die);
        vdp2_sprite_fb adapter(v,fields,false,false,lsmd==1,parity);
        adapter.sprite_word(100,17);
        assert(v.field==fields);
        assert(v.py==(lsmd==1 && die ? 34+parity : 17));
    }
    saturn_vdp2_device d;
    for(unsigned h=0;h<4;++h) {
        d.m_hreso=h;unsigned scale=(h&2)?2:1;
        unsigned before=(h&1)?375:347;
        d.storage.x=(before-1)*scale;
        assert(d.get_hcounter()==int((before-1)*2));
        d.storage.x=before*scale;
        assert(d.get_hcounter()==0x360);
        d.storage.x=((h&1)?455:427)*scale-1;
        assert(d.get_hcounter()==((h&2)?0x3ff:0x3fe));
    }
    d.storage.x=0;
    for(bool pal:{false,true}) for(unsigned mode=0;mode<(pal?3U:2U);++mode) {
        d.m_hreso=0;d.m_is_pal=pal;d.m_vreso=mode;d.storage.total=pal?313:263;
        unsigned before=pal?(mode==0?259:mode==1?267:275):(mode==0?237:245);
        unsigned target=pal?(mode==0?0x1ca:mode==1?0x1d2:0x1da):(mode==0?0x1e6:0x1ee);
        d.storage.y=before-1;assert(d.get_vcounter()==int(before-1));
        ++d.storage.y;assert(d.get_vcounter()==int(target));
        d.storage.y=d.storage.total-1;assert(d.get_vcounter()==511);
    }
    d.m_is_pal=d.m_vreso=0;d.storage.x=d.storage.y=0;
    for(unsigned h=0;h<8;++h) {
        d.m_hreso=h;
        unsigned total=(h&4)?((h&1)?424:426):((h&1)?455:427);
        assert(d.get_hblank_duration()==int(total*((h&2)?2:1)));
        if(h&4) {
            d.storage.total=(h&1)?562:525;
            assert(d.get_vblank_duration()==((h&1)?562:525));
            assert(d.get_vblank_start_position()==480);
            assert(d.get_ystep_count()==1);
            // Master clock is twice the system clock. Dedicated raster budgets.
            unsigned divisor=(h&2)?2:4;
            assert(d.get_hblank_duration()*divisor/2==((h&1)?848:852));
            unsigned scale=(h&2)?2:1;
            unsigned pre=(h&1)?188:173;
            d.storage.x=(pre*2-1)*scale;
            assert(d.horizontal_phase()==int((pre-1)*2));
            d.storage.x=pre*2*scale;
            assert(d.horizontal_phase()==((h&1)?0x3d0:0x3b0));
            d.storage.x=d.get_hblank_duration()-1;
            assert(d.horizontal_phase()==0x3fe);
            assert(d.get_hcounter()==((h&2)?0x1ff:0x1fe));
            d.storage.x=0;assert(d.get_hblank());
            d.storage.x=8*scale;assert(!d.get_hblank());
            d.storage.x=((h&1)?0x168:0x148)*scale;assert(d.get_hblank());
            d.storage.y=479;d.storage.x=d.counter_increment_dot()-1;
            assert(d.get_vcounter()==479 && !d.get_vblank());
            ++d.storage.x;assert(d.get_vcounter()==480 && d.get_vblank());
            d.storage.y=d.storage.total-1;assert(d.get_vcounter()==0 && !d.get_vblank());
            d.storage.y=0;d.storage.x=100;d.m_exlten=true;
            d.exlat_w(0);assert(d.m_exltfg && d.m_hcounter_latch==d.get_hcounter());
            auto latched=d.m_hcounter_latch;d.storage.x=120;d.exlat_w(0);assert(d.m_hcounter_latch==latched);
            d.exlat_w(1);d.m_exlten=false;d.exlat_w(0);assert(d.m_hcounter_latch==latched);
            d.exlat_w(1);d.storage.x=d.storage.y=0;
        }
    }
}
'''
pixel = method(vdp1,'display_pixel').replace('{\n', '{\n px=x;py=y;field=false;\n',1)
field = method(vdp1,'display_pixel_field')
# Record adapter arguments after the actual readout, including its nested display_pixel call.
field = field.replace('return display_pixel(x, row);', 'auto result=display_pixel(x,row);px=x;py=line;field=true;return result;')
field = field.replace('{\n', '{\n px=x;py=line;field=true;\n',1)
fixture = fixture.replace('// METHODS', adapter + '\n' + pixel + '\n' + field + '\n' + '\n'.join(crtc_method(n) for n in names))
with tempfile.TemporaryDirectory(prefix='saturn-video-modes-') as directory:
    path=Path(directory)
    (path/'test.cpp').write_text(fixture)
    subprocess.run(['clang++','-std=c++20','-O1','-g','-fsanitize=address,undefined','-I'+str(sega),str(path/'test.cpp'),'-o',str(path/'test')],check=True)
    subprocess.run([str(path/'test')],check=True)
print('Video mode adapter and CRTC fixtures passed (ASan/UBSan)')
