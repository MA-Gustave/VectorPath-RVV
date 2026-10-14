// Portable C++17 CLI: inspect a JSON corpus sample without parsing/validating it.
// Builds on x86/ARM/RISC-V; does not require simdjson or RVV intrinsics.
#include "rvv/engines/engine_plan.h"
#include <algorithm>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

using namespace simdjson::rvv::engines;
int main(int argc, char** argv) {
  if (argc < 2) {
    std::cerr << "Usage: engine_probe file1.json [file2.json ...]\n";
    return 2;
  }
  std::cout << "file\tbytes\tprofile\tstructurals\tdigits\tbackslashes\tunicode_escapes\tutf8_bytes"
               "\twriter_sparse\tescape_sparse\tpacked_writer\tpacked_escape\tpacked_quote"
               "\tpacked_shift\tstring_fastpath\n";
  int errors = 0;
  for (int i=1; i<argc; ++i) {
    std::ifstream stream(argv[i], std::ios::binary | std::ios::ate);
    if (!stream || stream.tellg() < 0) {
      std::cerr << "Cannot read: " << argv[i] << '\n';
      ++errors;
      continue;
    }
    const size_t bytes = size_t(stream.tellg());
    stream.seekg(0);
    std::vector<uint8_t> head(std::min(size_t(4096), bytes));
    if (!head.empty()) stream.read(reinterpret_cast<char*>(head.data()), std::streamsize(head.size()));
    if (!stream && !head.empty()) { ++errors; continue; }
    const sample metrics = inspect_prefix(head.data(), head.size());
    const plan chosen = choose(head.data(), bytes, false);
    std::cout << argv[i] << '\t' << bytes << '\t' << name(chosen.family) << '\t'
              << metrics.structural << '\t' << metrics.digits << '\t'
              << metrics.backslashes << '\t' << metrics.unicode_escapes << '\t'
              << metrics.nonascii << '\t' << chosen.sparse_writer_limit << '\t'
              << chosen.sparse_escape_limit << '\t' << chosen.packed_writer << '\t'
              << chosen.packed_escape << '\t' << chosen.packed_quote << '\t'
              << chosen.packed_shift << '\t' << chosen.in_string_fastpath << '\n';
  }
  return errors ? 1 : 0;
}
