#ifndef SIMDJSON_RVV_ENGINE_WORKLOAD_PROFILE_H
#define SIMDJSON_RVV_ENGINE_WORKLOAD_PROFILE_H

// Standalone C++17 source-inspection hints. NOT a JSON validator or parser.
// Sampling is bounded to the first 4096 bytes; no allocation, no global state.
// A malformed or adversarial input can affect performance selection only.
#include <cstddef>
#include <cstdint>

namespace simdjson { namespace rvv { namespace engines {

enum class workload : uint8_t {
  tiny, balanced, dense, numeric, text, escaped, unicode_escape, utf8
};

struct sample {
  size_t inspected{0};
  size_t structural{0};       // Outside strings, includes brackets, colon, comma
  size_t digits{0};           // Outside strings
  size_t quote{0};            // Unescaped quote delimiters
  size_t string_bytes{0};     // Includes delimiters, approximate
  size_t backslashes{0};
  size_t unicode_escapes{0};  // Literal ASCII backslash-u, not UTF-8
  size_t nonascii{0};        // Actual bytes >= 0x80
  bool ended_in_string{false};
};

// Adjustable budget for the v2 quick qualifier. Default preserves v1
// behavior. A larger document is never scanned beyond max_bytes.
inline sample inspect_prefix(const uint8_t* data, size_t length,
                             size_t max_bytes = 4096) noexcept {
  sample result{};
  if (!data || !length) { return result; }
  const size_t inspect = length < max_bytes ? length : max_bytes;
  result.inspected = inspect;
  bool inside = false;
  bool escape = false;
  for (size_t i = 0; i < inspect; ++i) {
    const uint8_t c = data[i];
    result.nonascii += size_t(c >= 0x80);
    if (inside) {
      ++result.string_bytes;
      if (escape) {
        if (c == 'u') { ++result.unicode_escapes; }
        escape = false;
      } else if (c == '\\') {
        ++result.backslashes;
        escape = true;
      } else if (c == '"') {
        ++result.quote;
        inside = false;
      }
    } else {
      if (c == '"') {
        inside = true;
        ++result.quote;
        ++result.string_bytes;
      } else if (c == '{' || c == '}' || c == '[' || c == ']' ||
                 c == ':' || c == ',') {
        ++result.structural;
      } else if (c >= '0' && c <= '9') {
        ++result.digits;
      }
    }
  }
  result.ended_in_string = inside;
  return result;
}

inline workload classify(const sample& s, size_t total_length) noexcept {
  if (total_length < 512 || s.inspected < 128) { return workload::tiny; }
  // Prefer distinctive escaping/true UTF-8 features before generic text.
  if (s.nonascii * 100 >= s.inspected * 8) { return workload::utf8; }
  if (s.unicode_escapes >= 4 && s.unicode_escapes * 80 >= s.inspected) {
    return workload::unicode_escape;
  }
  if (s.backslashes >= 5 && s.backslashes * 45 >= s.inspected) {
    return workload::escaped;
  }
  if (s.structural * 100 >= s.inspected * 14) { return workload::dense; }
  if (s.digits * 100 >= s.inspected * 35) { return workload::numeric; }
  if (s.string_bytes * 100 >= s.inspected * 55) { return workload::text; }
  return workload::balanced;
}

inline const char* name(workload value) noexcept {
  switch (value) {
    case workload::tiny: return "tiny";
    case workload::balanced: return "balanced";
    case workload::dense: return "dense";
    case workload::numeric: return "numeric";
    case workload::text: return "text";
    case workload::escaped: return "escaped";
    case workload::unicode_escape: return "unicode_escape";
    case workload::utf8: return "utf8";
  }
  return "unknown";
}

}}} // simdjson::rvv::engines
#endif
