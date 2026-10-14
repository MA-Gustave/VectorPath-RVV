#ifndef SIMDJSON_RVV_ENGINE_STAGE2_BRIDGE_H
#define SIMDJSON_RVV_ENGINE_STAGE2_BRIDGE_H
// Stage 2 still uses simdjson's tested generic tape builder in this release.
// This hook is deliberately ABI-neutral; it can be benchmarked independently.
// It is not a promise of an upstream/VLA Stage2 swap.
#ifndef SIMDJSON_RVV_STAGE2_PREFETCH
#define SIMDJSON_RVV_STAGE2_PREFETCH 0
#endif
namespace simdjson { namespace rvv { namespace engines {
template <typename Parser>
inline void before_stage2(Parser& parser) noexcept {
#if SIMDJSON_RVV_STAGE2_PREFETCH
  if (parser.n_structural_indexes > 64u) {
    // Readable indexes owned by the parser; never dereference past buf+len.
    const uint32_t pos = parser.structural_indexes[32];
    __builtin_prefetch(parser.structural_indexes.get() + 32, 0, 1);
    if (size_t(pos) < parser.len) {
      __builtin_prefetch(parser.buf + pos, 0, 1);
    }
  }
#else
  (void)parser;
#endif
}
}}} // simdjson::rvv::engines
#endif
