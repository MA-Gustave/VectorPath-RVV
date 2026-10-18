#ifndef SIMDJSON_RVV_ENGINE_PLAN_H
#define SIMDJSON_RVV_ENGINE_PLAN_H
#include "rvv/engines/workload_profile.h"

#ifndef SIMDJSON_RVV_ENGINE_LIBRARY
#define SIMDJSON_RVV_ENGINE_LIBRARY 1
#endif
#ifndef SIMDJSON_RVV_FORCE_PLAN
// 0=profile-guided; 1=historical; 2=dense; 3=numeric;
// 4=text; 5=escaped; 6=unicode_escape; 7=utf8; 8=balanced;
// 9=packed-writer; 10=packed-escape; 11=packed-quote+shift;
// 12=fastpath-only (explicit experimental profiles).
#define SIMDJSON_RVV_FORCE_PLAN 0
#endif
// Adaptive Workload Dispatch v2. Compile-time A/B controls:
// 0 = A0: original E14 profile, up to 4096 prefix bytes.
// 1 = A1: no classifier for < 4 KiB; original profile otherwise.
// 2 = A2: A1 size gate + quick bounded prefix scan for larger JSON.
// Requires SIMDJSON_RVV_FORCE_PLAN=0. A3 block-level refinement is NOT
// implemented here; these three profiles are intentionally fixed.
// VectorPath release candidate: Level 2 is the validated X60 default.
// -D flags still permit reproducible A0/A1 comparisons.
#ifndef SIMDJSON_RVV_ADAPTIVE_V2_LEVEL
#define SIMDJSON_RVV_ADAPTIVE_V2_LEVEL 2
#endif
#ifndef SIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES
#define SIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES 16384
#endif
#ifndef SIMDJSON_RVV_ADAPTIVE_V2_QUICK_BYTES
#define SIMDJSON_RVV_ADAPTIVE_V2_QUICK_BYTES 512
#endif
#if SIMDJSON_RVV_ADAPTIVE_V2_LEVEL < 0 || SIMDJSON_RVV_ADAPTIVE_V2_LEVEL > 2
#error "SIMDJSON_RVV_ADAPTIVE_V2_LEVEL must be 0, 1, or 2"
#endif
#if SIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES < 512
#error "SIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES must be >= 512"
#endif
#if SIMDJSON_RVV_ADAPTIVE_V2_QUICK_BYTES < 128 || SIMDJSON_RVV_ADAPTIVE_V2_QUICK_BYTES > 4096
#error "SIMDJSON_RVV_ADAPTIVE_V2_QUICK_BYTES must be in [128, 4096]"
#endif

#ifndef SIMDJSON_RVV_SPARSE_INDEX_THRESHOLD
#define SIMDJSON_RVV_SPARSE_INDEX_THRESHOLD 8
#endif
#ifndef SIMDJSON_RVV_PACKED_INDEX_THRESHOLD
#define SIMDJSON_RVV_PACKED_INDEX_THRESHOLD 64
#endif
#ifndef SIMDJSON_RVV_SPARSE_ESCAPE_THRESHOLD
#define SIMDJSON_RVV_SPARSE_ESCAPE_THRESHOLD 2
#endif
#ifndef SIMDJSON_RVV_ENABLE_PACKED_CONTROL
// Benchmark-supported stable profile keeps packed paths disabled.
// Opt-in historical A/B builds may override each macro with -D.
#define SIMDJSON_RVV_ENABLE_PACKED_CONTROL 0
#endif
#ifndef SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER
#define SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER SIMDJSON_RVV_ENABLE_PACKED_CONTROL
#endif
#ifndef SIMDJSON_RVV_ENABLE_PACKED_ESCAPE
#define SIMDJSON_RVV_ENABLE_PACKED_ESCAPE SIMDJSON_RVV_ENABLE_PACKED_CONTROL
#endif
#ifndef SIMDJSON_RVV_ENABLE_PACKED_QUOTE
#define SIMDJSON_RVV_ENABLE_PACKED_QUOTE SIMDJSON_RVV_ENABLE_PACKED_CONTROL
#endif
#ifndef SIMDJSON_RVV_ENABLE_PACKED_SHIFT
#define SIMDJSON_RVV_ENABLE_PACKED_SHIFT SIMDJSON_RVV_ENABLE_PACKED_CONTROL
#endif

namespace simdjson { namespace rvv { namespace engines {

// A POD plan is chosen once for each parse call; no heap, locks, clocks or
// speculative execution. Writer and string-scanner modules consume its fields.
struct plan {
  workload family{workload::balanced};
  uint16_t sparse_writer_limit{8};
  uint16_t packed_writer_limit{64};
  uint16_t sparse_escape_limit{2};
  bool packed_writer{false};
  bool packed_escape{false};
  bool packed_quote{false};
  bool packed_shift{false};
  bool in_string_fastpath{false};
};

inline plan historical() noexcept {
  plan p{};
  p.sparse_writer_limit = uint16_t(SIMDJSON_RVV_SPARSE_INDEX_THRESHOLD);
  p.packed_writer_limit = uint16_t(SIMDJSON_RVV_PACKED_INDEX_THRESHOLD);
  p.sparse_escape_limit = uint16_t(SIMDJSON_RVV_SPARSE_ESCAPE_THRESHOLD);
  p.packed_writer = SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER != 0;
  p.packed_escape = SIMDJSON_RVV_ENABLE_PACKED_ESCAPE != 0;
  p.packed_quote = SIMDJSON_RVV_ENABLE_PACKED_QUOTE != 0;
  p.packed_shift = SIMDJSON_RVV_ENABLE_PACKED_SHIFT != 0;
  p.in_string_fastpath = false;
  return p;
}

inline plan configure(workload kind) noexcept {
  plan p = historical();
  p.family = kind;
  // Packed quote/shift hurt on measured X60 workloads; keep their hot paths
  // compiled but normally bypassed. Individual modes remain benchmarkable.
  p.packed_quote = false;
  p.packed_shift = false;
  p.packed_writer = false;
  p.packed_escape = false;
  p.in_string_fastpath = true;
  switch(kind) {
    case workload::tiny:
      // No extra prefix scan on tiny payloads; preserve behavior.
      p = historical();
      p.family = workload::tiny;
      return p;
    case workload::dense:
      p.sparse_writer_limit = 4;
      p.sparse_escape_limit = 2;
      break;
    case workload::numeric:
      p.sparse_writer_limit = 8;
      p.sparse_escape_limit = 2;
      break;
    case workload::text:
      p.sparse_writer_limit = 12;
      p.sparse_escape_limit = 4;
      break;
    case workload::escaped:
      p.sparse_writer_limit = 8;
      p.sparse_escape_limit = 8;
      break;
    case workload::unicode_escape:
      p.sparse_writer_limit = 8;
      p.sparse_escape_limit = 8;
      break;
    case workload::utf8:
      p.sparse_writer_limit = 12;
      p.sparse_escape_limit = 8;
      break;
    case workload::balanced:
    default:
      p.sparse_writer_limit = 8;
      p.sparse_escape_limit = 8;
      break;
  }
  return p;
}

inline plan choose(const uint8_t* data, size_t length, bool is_streaming) noexcept {
#if !SIMDJSON_RVV_ENGINE_LIBRARY
  (void)data; (void)length; (void)is_streaming;
  return historical();
#else
  if (is_streaming) { return historical(); }
#if SIMDJSON_RVV_FORCE_PLAN == 1
  (void)data; (void)length; return historical();
#elif SIMDJSON_RVV_FORCE_PLAN == 2
  (void)data; (void)length; return configure(workload::dense);
#elif SIMDJSON_RVV_FORCE_PLAN == 3
  (void)data; (void)length; return configure(workload::numeric);
#elif SIMDJSON_RVV_FORCE_PLAN == 4
  (void)data; (void)length; return configure(workload::text);
#elif SIMDJSON_RVV_FORCE_PLAN == 5
  (void)data; (void)length; return configure(workload::escaped);
#elif SIMDJSON_RVV_FORCE_PLAN == 6
  (void)data; (void)length; return configure(workload::unicode_escape);
#elif SIMDJSON_RVV_FORCE_PLAN == 7
  (void)data; (void)length; return configure(workload::utf8);
#elif SIMDJSON_RVV_FORCE_PLAN == 8
  (void)data; (void)length; return configure(workload::balanced);
#elif SIMDJSON_RVV_FORCE_PLAN == 9
  (void)data; (void)length;
  { plan p = configure(workload::balanced);
    p.packed_writer = SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER != 0;
    return p; }
#elif SIMDJSON_RVV_FORCE_PLAN == 10
  (void)data; (void)length;
  { plan p = configure(workload::escaped);
    p.packed_escape = SIMDJSON_RVV_ENABLE_PACKED_ESCAPE != 0;
    return p; }
#elif SIMDJSON_RVV_FORCE_PLAN == 11
  (void)data; (void)length;
  { plan p = configure(workload::balanced);
    p.packed_quote = SIMDJSON_RVV_ENABLE_PACKED_QUOTE != 0;
    p.packed_shift = SIMDJSON_RVV_ENABLE_PACKED_SHIFT != 0;
    return p; }
#elif SIMDJSON_RVV_FORCE_PLAN == 12
  (void)data; (void)length;
  { plan p = historical(); p.in_string_fastpath = true; return p; }
#else
  // The additional size gate happens only after explicit fixed-plan and
  // streaming checks, keeping the existing research configurations intact.
#if SIMDJSON_RVV_ADAPTIVE_V2_LEVEL >= 1
  if (length < size_t(SIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES)) {
    // Generic plan: E14 balanced configuration with no prefix classifier.
    // Do not use historical(), which would silently change the string path.
    return configure(workload::balanced);
  }
#endif
  if (length < 512) {
    plan p = historical();
    p.family = workload::tiny;
    return p;
  }
#if SIMDJSON_RVV_ADAPTIVE_V2_LEVEL == 2
  // Coarse, NOT perfect classification: scan a fixed 512-byte prefix at most.
  // A2 intentionally pays no extra pass for small documents.
  return configure(classify(
      inspect_prefix(data, length, size_t(SIMDJSON_RVV_ADAPTIVE_V2_QUICK_BYTES)),
      length));
#else
  return configure(classify(inspect_prefix(data, length), length));
#endif
#endif
#endif
}

}}} // simdjson::rvv::engines
#endif
