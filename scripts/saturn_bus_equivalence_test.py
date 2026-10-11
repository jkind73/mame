#!/usr/bin/env python3
# license:BSD-3-Clause
"""Compare actual bus arbitration methods, including contiguous history expiry."""
import sys,subprocess,tempfile
from pathlib import Path
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root/'scripts'))
from saturn_vdp_wip_test import method
old=(root/'tests/saturn/bus_arbitration_reference.cpp').read_text()
new=(root/'src/mame/sega/saturn_bus.cpp').read_text()
def extract(s,cls):return method(s.replace('saturn_state::','saturn_vdp1_device::'),'sh2_bus_arbitrate').replace('saturn_vdp1_device::',cls+'::')
fixture=r'''
#include <algorithm>
#include <array>
#include <utility>
#include <deque>
#include <random>
#include <cassert>
#include <cstdint>
#include <iostream>
using offs_t=uint32_t;
struct attotime {int64_t n=0;static const attotime zero,never;static attotime from_msec(int n){return {n*100000};}bool is_zero()const{return n==0;}attotime& operator+=(attotime b){n+=b.n;return *this;}attotime operator+(attotime b)const{return {n+b.n};}attotime operator-(attotime b)const{return {n-b.n};}auto operator<=>(attotime const&)const=default;};
const attotime attotime::zero{0},attotime::never{INT64_MAX/2};
struct sh7604_device {attotime cycles_to_attotime(uint64_t c)const{return {int64_t(c)*3};}uint64_t attotime_to_cycles(attotime t)const{return t.n/3;}};

#include "saturn_bus.h"
template<typename History>struct base {static constexpr unsigned BUS_REQUESTERS=4;using bus_interval=saturn_bus::interval;sh7604_device a,b,*m_maincpu=&a,*m_slave=&b;History m_sh2_bus_log[4];attotime m_sh2_bus_debt[4]{},m_sh2_bus_debt_from[4]{attotime::never,attotime::never,attotime::never,attotime::never};attotime m_bsc_last_end[2]{};unsigned m_bsc_last_area[2]{};bool m_bsc_last_read[2]{};};
struct reference:base<std::deque<saturn_bus::interval>> {uint64_t sh2_bus_arbitrate(unsigned,const attotime&,uint64_t,offs_t,bool);};
struct current:base<saturn_bus::interval_history> {uint64_t sh2_bus_arbitrate(unsigned,const attotime&,uint64_t,offs_t,bool);};
// METHODS
int main(){std::mt19937 rng(9137);reference r;current c;int64_t times[4]{};for(int i=0;i<20000;i++){unsigned who=rng()%4;times[who]+=rng()%400+200;attotime now{times[who]};unsigned cost=rng()%80,addr=rng()&0x07ffffff;bool write=rng()&1;assert(r.sh2_bus_arbitrate(who,now,cost,addr,write)==c.sh2_bus_arbitrate(who,now,cost,addr,write));for(int j=0;j<4;j++){assert(std::equal(r.m_sh2_bus_log[j].begin(),r.m_sh2_bus_log[j].end(),c.m_sh2_bus_log[j].begin(),c.m_sh2_bus_log[j].end(),[](auto const&a,auto const&b){return a.start==b.start&&a.end==b.end;}));assert(r.m_sh2_bus_debt[j]==c.m_sh2_bus_debt[j]);assert(r.m_sh2_bus_debt_from[j]==c.m_sh2_bus_debt_from[j]);}for(int j=0;j<2;j++){assert(r.m_bsc_last_end[j]==c.m_bsc_last_end[j]);assert(r.m_bsc_last_area[j]==c.m_bsc_last_area[j]);assert(r.m_bsc_last_read[j]==c.m_bsc_last_read[j]);}}std::cout<<"20000 actual-method arbitration comparisons PASS\n";}
'''
with tempfile.TemporaryDirectory(prefix='saturn-bus-equivalence-') as td:
 p=Path(td)/'test.cpp';p.write_text(fixture.replace('// METHODS',extract(old,'reference')+'\n'+extract(new,'current')))
 subprocess.run(['clang++','-std=c++20','-O1','-I'+str(root/'src/mame/sega'),'-fsanitize=address,undefined',str(p),'-o',str(p.with_suffix(''))],check=True)
 subprocess.run([str(p.with_suffix(''))],check=True)
