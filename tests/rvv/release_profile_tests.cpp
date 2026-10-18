// Portable smoke test for VectorPath-RVV delivery profile; runs on x86, too.
#include "rvv/engines/engine_plan.h"
#include <cassert>
#include <cstdint>
#include <vector>
using namespace simdjson::rvv::engines;
int main() {
#if defined(VECTORPATH_REQUIRE_STABLE)
  static_assert(SIMDJSON_RVV_ADAPTIVE_V2_LEVEL == 2, "Expected A2 default");
  static_assert(SIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES == 16384, "Expected 16 KiB gate");
  static_assert(SIMDJSON_RVV_ENABLE_PACKED_CONTROL == 0, "Packed control should be disabled");
  static_assert(SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER == 0, "Packed index should be disabled");
  static_assert(SIMDJSON_RVV_ENABLE_PACKED_ESCAPE == 0, "Packed escape should be disabled");
  static_assert(SIMDJSON_RVV_ENABLE_PACKED_QUOTE == 0, "Packed quote should be disabled");
  static_assert(SIMDJSON_RVV_ENABLE_PACKED_SHIFT == 0, "Packed shift should be disabled");
#endif
  std::vector<uint8_t> dense(16384, ',');
  const plan small = choose(dense.data(), 16383, false);
#if SIMDJSON_RVV_ADAPTIVE_V2_LEVEL >= 1 && SIMDJSON_RVV_FORCE_PLAN == 0
  assert(small.family == workload::balanced);
#endif
  const plan boundary = choose(dense.data(), 16384, false);
#if SIMDJSON_RVV_ADAPTIVE_V2_LEVEL == 2 && SIMDJSON_RVV_FORCE_PLAN == 0
  assert(boundary.family == workload::dense);
#endif
  const plan streaming = choose(dense.data(), 16384, true);
  const plan historical_plan = historical();
  assert(streaming.packed_writer == historical_plan.packed_writer);
  assert(streaming.packed_escape == historical_plan.packed_escape);
  assert(streaming.packed_quote == historical_plan.packed_quote);
  assert(streaming.packed_shift == historical_plan.packed_shift);
#if defined(VECTORPATH_REQUIRE_STABLE)
  assert(!historical_plan.packed_writer && !historical_plan.packed_escape);
#endif
  return 0;
}
