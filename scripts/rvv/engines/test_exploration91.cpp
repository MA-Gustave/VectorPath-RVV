#include "rvv/engines/exploration91.h"
#include <cassert>
#include <iostream>
#include <string>
using namespace simdjson::rvv;
int main(int argc,char** argv) {
  namespace e=exploration91;
  assert(argc==2);
  assert(e::configure_text(argv[1]));
  auto old=e::active;
  assert(!e::configure_text("1,2"));assert(e::active.policy==old.policy);
  assert(!e::configure_text("-1"));
  std::string bad=std::string(argv[1])+",1";
  assert(!e::configure_text(bad.c_str()));
  e::active.policy=3;e::active.region=64;e::active.hysteresis=2;
  e::active.banks[0]=engines::configure(engines::workload::balanced);
  e::active.banks[1]=engines::configure(engines::workload::dense);
  e::active.banks[2]=engines::configure(engines::workload::text);
  e::active.banks[3]=engines::configure(engines::workload::escaped);
  auto plan=e::active.banks[0];e::regional_policy p{};p.enabled=true;
  e::tracing=true;e::trace={};
  assert(!p.observe(32,20,0,0,0,plan));
  assert(!p.observe(32,20,0,0,0,plan));
  assert(p.observe(64,40,0,0,0,plan));
  assert(plan.sparse_writer_limit==4 && p.bank==1);
  assert(!p.observe(64,0,0,0,64,plan));
  assert(p.observe(64,0,0,0,64,plan));
  assert(plan.sparse_writer_limit==12 && p.bank==2);
  assert(e::trace.changes==2 && e::trace.regions==4);
  assert(e::trace.bank_bytes[0]+e::trace.bank_bytes[1]+e::trace.bank_bytes[2]==256);
  e::active.policy=4;e::active.prefix=128;e::active.gate=0;
  std::string data(1024,'x');data.replace(896,128,std::string(128,'\\'));
  assert(e::initial_bank(reinterpret_cast<const uint8_t*>(data.data()),data.size())==3);
  // Streaming always selects legacy policy regardless of research banks.
  auto a=e::initial_plan(reinterpret_cast<const uint8_t*>(data.data()),data.size(),true);
  auto b=engines::choose(reinterpret_cast<const uint8_t*>(data.data()),data.size(),true);
  assert(e::same_plan(a,b));
  std::cout<<"PASS exploration91 policy, strict config, hysteresis, counters, raw windows\n";
}
