// Policy-only microbenchmark; not a DOM benchmark. No RVV required.
// Measures the approximate added cost of choose() in isolation.
#include "rvv/engines/engine_plan.h"
#include <chrono>
#include <cstdint>
#include <iostream>
#include <vector>
using namespace simdjson::rvv::engines;
int main() {
  std::vector<uint8_t> buffer(65536,'7');
  for(size_t i=0;i<buffer.size();i+=11) buffer[i]=',';
  volatile uint32_t sink=0;
  constexpr int repeats=200000;
  for(size_t len : {size_t(128),size_t(2048),size_t(8192),size_t(65536)}) {
    const auto start=std::chrono::steady_clock::now();
    for(int i=0;i<repeats;++i) {
      // Mutation outside sampled bytes prevents a trivially constant input.
      buffer[6000]=static_cast<uint8_t>('0'+(i%10));
      auto chosen=choose(buffer.data(),len,false);
      sink=sink+static_cast<uint32_t>(chosen.sparse_writer_limit);
    }
    auto end=std::chrono::steady_clock::now();
    const double ns=std::chrono::duration<double,std::nano>(end-start).count()/repeats;
    std::cout << "bytes="<<len<<" level="<<SIMDJSON_RVV_ADAPTIVE_V2_LEVEL
              <<" choose_ns="<<ns<<"\n";
  }
  (void)sink;
}
