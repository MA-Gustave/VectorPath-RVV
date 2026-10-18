// DOM equivalence CLI. 'valid' and 'invalid' are tested by the Python driver.
#include "simdjson.h"
#include <iostream>
#include <string>
#include <cstdint>
int main(int argc, char **argv) {
  if (argc != 2) { return 64; }
  simdjson::padded_string input;
  if (simdjson::padded_string::load(argv[1]).get(input)) { return 66; }
  simdjson::dom::parser parser;
  simdjson::dom::element el;
  const auto status = parser.parse(input).get(el);
  if (status) {
    // Parser variations should reject identically, without implying that an
    // exact simdjson error-code spelling is a cross-release API guarantee.
    std::cout << "REJECT\n";
    return 0;
  }
  const std::string canonical = simdjson::to_string(el);
  std::uint64_t hash = 14695981039346656037ULL;
  for (unsigned char c : canonical) {
    hash ^= c;
    hash *= 1099511628211ULL;
  }
  std::cout << "ACCEPT " << canonical.size() << " " << std::hex << hash << "\n";
  return 0;
}
