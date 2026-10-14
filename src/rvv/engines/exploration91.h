#ifndef SIMDJSON_RVV_EXPLORATION91_H
#define SIMDJSON_RVV_EXPLORATION91_H
#include "rvv/engines/engine_plan.h"
#ifndef SIMDJSON_RVV_EXPLORATION91
#define SIMDJSON_RVV_EXPLORATION91 0
#endif
#if SIMDJSON_RVV_EXPLORATION91
#include <cstdlib>
namespace simdjson { namespace rvv { namespace exploration91 {
// Research-only process configuration; set BEFORE parsing, never during a parse.
// No environment reads, allocations or clocks on the parsing path.
struct settings {
  unsigned policy{0}, prefix{512}, gate{4096}, region{16384};
  unsigned hysteresis{1}, vl_cap{0}, unroll{1};
  engines::plan banks[4]{}; // balanced, dense, text, escaped/UTF8
};
inline settings active{};
struct counters {
  uint64_t parses{0}, regions{0}, changes{0}, bank_bytes[4]{};
};
inline bool tracing{false};
inline counters trace{};
inline bool same_plan(const engines::plan& a, const engines::plan& b) noexcept {
  return a.sparse_writer_limit==b.sparse_writer_limit &&
    a.packed_writer_limit==b.packed_writer_limit && a.sparse_escape_limit==b.sparse_escape_limit &&
    a.packed_writer==b.packed_writer && a.packed_escape==b.packed_escape &&
    a.packed_quote==b.packed_quote && a.packed_shift==b.packed_shift &&
    a.in_string_fastpath==b.in_string_fastpath;
}
// Strict 23-integer wire format. Four effective plans, NOT named presets.
inline bool configure_text(const char* text) noexcept {
  if (!text || !*text) return false;
  unsigned v[23]{}; const char* cursor=text;
  for(unsigned i=0;i<23;i++) {
    if(*cursor<'0' || *cursor>'9') return false;
    char* end=nullptr; const unsigned long value=std::strtoul(cursor,&end,10);
    if(end==cursor || value>1048576) return false;
    v[i]=unsigned(value);
    if(i<22) { if(*end!=',') return false; cursor=end+1; }
    else if(*end!='\0') return false;
  }
  if(v[0]>4 || v[1]<128 || v[1]>4096 || v[2]>1048576 ||
     v[3]<64 || v[3]>262144 || v[4]<1 || v[4]>4 ||
     (v[5]!=0 && v[5]!=16 && v[5]!=32 && v[5]!=64) ||
     (v[6]!=1 && v[6]!=2 && v[6]!=4)) return false;
  settings s{};
  s.policy=v[0];s.prefix=v[1];s.gate=v[2];s.region=v[3];
  s.hysteresis=v[4];s.vl_cap=v[5];s.unroll=v[6];
  for(unsigned i=0;i<4;i++) {
    const unsigned n=7+4*i;
    if(v[n]>64 || v[n+1]>512 || v[n+2]>64 || v[n+3]>31) return false;
    auto& p=s.banks[i];
    p.sparse_writer_limit=uint16_t(v[n]);p.packed_writer_limit=uint16_t(v[n+1]);
    p.sparse_escape_limit=uint16_t(v[n+2]);
    p.packed_writer=(v[n+3]&1)!=0;p.packed_escape=(v[n+3]&2)!=0;
    p.packed_quote=(v[n+3]&4)!=0;p.packed_shift=(v[n+3]&8)!=0;
    p.in_string_fastpath=(v[n+3]&16)!=0;
  }
  active=s;return true;
}
inline unsigned bank_for(engines::workload w) noexcept {
  switch(w) {
    case engines::workload::dense:return 1;
    case engines::workload::text:return 2;
    case engines::workload::escaped:case engines::workload::unicode_escape:
    case engines::workload::utf8:return 3;
    default:return 0;
  }
}
inline unsigned initial_bank(const uint8_t* data,size_t len) noexcept {
  if(active.policy==4 && len>=active.gate) {
    // Raw-byte hints at three positions. No assumption that a middle window
    // starts outside a string; these hints only select a fully valid parser.
    engines::sample sample{};
    const size_t count=len<active.prefix?len:active.prefix;
    const size_t offsets[3]={0,(len-count)/2,len-count};
    for(size_t offset:offsets) for(size_t i=0;i<count;i++) {
      const uint8_t c=data[offset+i];++sample.inspected;
      sample.nonascii+=c>=128;sample.backslashes+=c=='\\';
      sample.structural+=c=='{' || c=='}' || c=='[' || c==']' || c==':' || c==',';
      sample.digits+=c>='0' && c<='9';
    }
    // Raw windows cannot reliably count inside-string bytes. Low-density ASCII
    // is a text hint, never a validation shortcut.
    if(sample.nonascii*100>=sample.inspected*8 || sample.backslashes*45>=sample.inspected)return 3;
    if(sample.structural*100>=sample.inspected*14)return 1;
    if(sample.digits*100>=sample.inspected*35)return 0;
    return 2;
  }
  if(active.policy==2 && len>=active.gate)
    return bank_for(engines::classify(engines::inspect_prefix(data,len,active.prefix),len));
  return 0;
}
inline engines::plan initial_plan(const uint8_t* data,size_t len,bool streaming) noexcept {
  if(streaming || active.policy==0) return engines::choose(data,len,streaming);
  return active.banks[initial_bank(data,len)];
}
struct regional_policy {
  size_t bytes{0}, structures{0}, escaped{0}, high{0}, inside{0};
  unsigned bank{0}, pending{0}, streak{0};
  bool enabled{false};
  // Statistics describe the PRECEDING region, maintaining all parser state.
  bool observe(size_t n,size_t structural,size_t esc,size_t nonascii,size_t in_string,
               engines::plan& selected) noexcept {
    if(tracing) trace.bank_bytes[bank]+=n;
    if(!enabled)return false;
    bytes+=n;structures+=structural;escaped+=esc;high+=nonascii;inside+=in_string;
    if(bytes<active.region)return false;
    unsigned next=(high*100>=bytes*8 || escaped*100>=bytes*2)?3:
                  structures*100>=bytes*14?1:inside*100>=bytes*55?2:0;
    bytes=structures=escaped=high=inside=0;
    if(tracing)++trace.regions;
    if(next==pending)++streak;else {pending=next;streak=1;}
    if(next==bank || streak<active.hysteresis)return false;
    bank=next;
    const bool changed=!same_plan(selected,active.banks[next]);
    selected=active.banks[next];
    if(tracing && changed)++trace.changes;
    return changed;
  }
};
}}}
#endif
#endif
