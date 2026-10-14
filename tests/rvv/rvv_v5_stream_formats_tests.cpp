#include "rvv_test_common.h"

namespace {
bool test_stream(const std::string &input, simdjson::stream_format format,
                 size_t expected_count, size_t batch_size) {
  simdjson::dom::parser parser;
  simdjson::dom::document_stream stream;
  const auto source = simdjson::padded_string(input);
  const auto error = parser.parse_many(source, batch_size, format).get(stream);
  if (error != simdjson::SUCCESS) {
    std::cerr << "[FAIL] stream setup " << error << "\n";
    return false;
  }
  size_t count = 0;
  for (auto result : stream) {
    simdjson::dom::element doc;
    if (result.get(doc) != simdjson::SUCCESS) {
      std::cerr << "[FAIL] stream document index " << count << "\n";
      return false;
    }
    ++count;
  }
  if (count != expected_count) {
    std::cerr << "[FAIL] stream count expected=" << expected_count
              << " got=" << count << "\n";
    return false;
  }
  return true;
}
}

int main() {
  if (!rvv_test::require_implementation("rvv")) { return 1; }
  rvv_test::active_implementation_guard guard;
  simdjson::get_active_implementation() = rvv_test::rvv();
  bool ok = true;
  const std::string rs("\x1e", 1);
  // RFC 7464: include objects, arrays, scalar numbers, strings, and booleans.
  const std::string seq = rs + "{\"a\":1}\n" + rs + "[2,3]\n"
                        + rs + "42\n" + rs + "\"text\"\n" + rs + "true\n";
  const std::string comma = "{\"a\":1},[2,3],42,\"text\",true";
  const std::string ndjson = "{\"a\":1}\n[2,3]\n42\n\"text\"\ntrue\n";
  for (size_t batch_size : {size_t(64), size_t(128), size_t(1024)}) {
    ok &= test_stream(seq, simdjson::stream_format::json_sequence, 5, batch_size);
    ok &= test_stream(comma, simdjson::stream_format::comma_delimited, 5, batch_size);
    ok &= test_stream(ndjson, simdjson::stream_format::whitespace_delimited, 5, batch_size);
  }
  return rvv_test::finish(ok, "rvv_v5_stream_formats_tests");
}
