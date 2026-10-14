#ifndef SIMDJSON_RVV_ENGINE_STRUCTURAL_WRITERS_H
#define SIMDJSON_RVV_ENGINE_STRUCTURAL_WRITERS_H
#include "rvv/engines/engine_plan.h"
#ifndef SIMDJSON_CONDITIONAL_INCLUDE
#include "rvv/string_scanner.h"
#endif

namespace simdjson { namespace rvv { namespace engines {

enum class writer_engine : uint8_t { events, mask_words, compress };

inline writer_engine select_writer(const plan& selected, size_t count) noexcept {
  if (count <= selected.sparse_writer_limit) { return writer_engine::events; }
  if (selected.packed_writer && SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER &&
      count <= selected.packed_writer_limit) { return writer_engine::mask_words; }
  return writer_engine::compress;
}

// Three independently identifiable algorithms. No heap or out-of-order output;
// caller has already reserved sufficient n_structural_indexes capacity.
simdjson_really_inline void append_structural_indexes(
    vbool4_t structural, size_t vl, uint32_t base, uint32_t*& tail,
    const plan& selected) noexcept {
  const size_t count = __riscv_vcpop_m_b4(structural, vl);
  if (simdjson_likely(count == 0)) { return; }
  const writer_engine engine = select_writer(selected, count);
  if (engine == writer_engine::events) {
    vbool4_t pending = structural;
    for (size_t i = 0; i < count; ++i) {
      const long index = __riscv_vfirst_m_b4(pending, vl);
      *tail++ = base + uint32_t(index);
      const vbool4_t first = __riscv_vmsof_m_b4(pending, vl);
      pending = __riscv_vmxor_mm_b4(pending, first, vl);
    }
    return;
  }
  if (engine == writer_engine::mask_words) {
    ::simdjson::rvv::stage1::packed_mask_words bits{};
    if (simdjson_likely(::simdjson::rvv::stage1::pack_mask(structural, vl, bits))) {
      const size_t words = ::simdjson::rvv::stage1::packed_word_count(vl);
      for (size_t i = 0; i < words; ++i) {
        uint64_t word = bits.words[i];
        const uint32_t word_base = base + uint32_t(i * size_t(64));
        while (word) {
          // This portable builtin does not require Zbb instructions.
          const unsigned tz = unsigned(__builtin_ctzll(word));
          *tail++ = word_base + tz;
          word &= word - 1;
        }
      }
      return;
    }
  }
  // Unrestricted VLEN fallback, and the dense structural engine.
  const vuint32m8_t lanes = __riscv_vid_v_u32m8(vl);
  const vuint32m8_t packed = __riscv_vcompress_vm_u32m8(lanes, structural, vl);
  const vuint32m8_t absolute = __riscv_vadd_vx_u32m8(packed, base, count);
  __riscv_vse32_v_u32m8(tail, absolute, count);
  tail += count;
}

}}} // simdjson::rvv::engines
#endif
