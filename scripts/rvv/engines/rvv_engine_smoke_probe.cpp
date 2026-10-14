// A native smoke of the actual RVV implementation, not a speed benchmark.
// Built together with src/simdjson.cpp, with the same RVV build defines.
#include "simdjson.h"
#include <iostream>
#include <string>

int main() {
  const simdjson::implementation *engine =
      simdjson::get_available_implementations()["rvv"];
  if (engine == nullptr) {
    std::cerr << "RVV implementation was not compiled in\n";
    return 10;
  }
  if (!engine->supported_by_runtime_system()) {
    std::cerr << "RVV implementation unsupported by this CPU\n";
    return 11;
  }
  simdjson::get_active_implementation() = engine;
  simdjson::dom::parser parser;
  const char *valid[] = {
    R"({"number":42,"values":[1,2,3],"flag":true})",
    R"([{"text":"hello","escaped":"\\\""},{"unicode":"\u00e9"}])",
    R"({"nested":{"a":{"b":null}},"empty":[]})"
  };
  for (const char *json : valid) {
    const std::string input(json);
    const simdjson::error_code error = parser.parse(input).error();
    if (error != simdjson::SUCCESS) {
      std::cerr << "RVV failed valid JSON: " << error << '\n';
      return 20;
    }
  }
  const std::string invalid = R"({"truncated":)";
  if (parser.parse(invalid).error() == simdjson::SUCCESS) {
    std::cerr << "RVV incorrectly accepted invalid JSON\n";
    return 21;
  }
  if (simdjson::get_active_implementation()->name() != "rvv") {
    std::cerr << "Unexpected active implementation\n";
    return 22;
  }
  std::cout << "RVV_SMOKE_OK backend=rvv valid=3 invalid=1\n";
  return 0;
}
