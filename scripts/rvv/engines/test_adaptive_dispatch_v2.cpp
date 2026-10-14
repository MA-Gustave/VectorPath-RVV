// Portable C++17 policy tests. No RVV machine required, no JSON parsing.
#include "rvv/engines/engine_plan.h"
#include <cassert>
#include <cstdint>
#include <string>
#include <vector>
using namespace simdjson::rvv::engines;

static bool same(const plan& a,const plan& b) {
  return a.family==b.family && a.sparse_writer_limit==b.sparse_writer_limit &&
         a.packed_writer_limit==b.packed_writer_limit &&
         a.sparse_escape_limit==b.sparse_escape_limit &&
         a.packed_writer==b.packed_writer && a.packed_escape==b.packed_escape &&
         a.packed_quote==b.packed_quote && a.packed_shift==b.packed_shift &&
         a.in_string_fastpath==b.in_string_fastpath;
}
int main() {
  // Below the threshold, both v2 profiles choose E14 balanced immediately.
  std::vector<uint8_t> tiny(12,'7');
  auto p=choose(tiny.data(),tiny.size(),false);
  (void)p;
#if SIMDJSON_RVV_ADAPTIVE_V2_LEVEL >= 1 && SIMDJSON_RVV_FORCE_PLAN == 0
  assert(same(p,configure(workload::balanced)));
#elif SIMDJSON_RVV_FORCE_PLAN == 0
  assert(p.family==workload::tiny);
#endif
  // Large dense corpus; quick prefix and full prefix both say dense.
  std::vector<uint8_t> dense(8192,',');
  assert(inspect_prefix(dense.data(),dense.size(),32).inspected==32);
  assert(inspect_prefix(dense.data(),dense.size(),0).inspected==0);
  assert(inspect_prefix(nullptr,512).inspected==0);
  assert(classify(inspect_prefix(dense.data(),dense.size()),dense.size())==workload::dense);
  auto d=choose(dense.data(),dense.size(),false);
  (void)d;
#if SIMDJSON_RVV_FORCE_PLAN == 0
  assert(d.family==workload::dense);
#endif
  // Unicode escapes vs literal high-bit UTF8 remain distinguishable.
  std::string esc="\"";
  for(size_t i=0;i<1024;++i) esc+=(i%2) ? "\\u1234" : "abc";
  esc += "\"";
  auto se=inspect_prefix(reinterpret_cast<const uint8_t*>(esc.data()),esc.size(),512);
  assert(se.unicode_escapes>4 && se.nonascii==0);
  auto utf8=std::vector<uint8_t>(8192,0xc3);
  assert(classify(inspect_prefix(utf8.data(),utf8.size(),512),utf8.size())==workload::utf8);
  // With streaming, never activate a document-based mode.
  assert(same(choose(dense.data(),dense.size(),true),historical()));
  // Forced plan must override the v2 gate.
#if SIMDJSON_RVV_FORCE_PLAN == 2
  assert(choose(tiny.data(),tiny.size(),false).family==workload::dense);
#endif
  return 0;
}
