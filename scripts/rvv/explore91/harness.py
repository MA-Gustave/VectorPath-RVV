"""Build the research harness from the unchanged Test90 split timer."""
def source(original):
    original=original.replace('#include "simdjson.h"','#include "simdjson.h"\n#if SIMDJSON_RVV_EXPLORATION91\n#include "rvv/engines/exploration91.h"\n#endif')
    insert=r'''
// Full DOM comparison with fallback, outside all performance timings.
static bool agrees(const std::string& backend,const simdjson::padded_string& doc) {
  if(select_backend(backend))return false;
  simdjson::dom::parser p;simdjson::dom::element a;
  auto ea=p.parse(doc).get(a);
  std::string sa;if(ea==simdjson::SUCCESS)sa=simdjson::to_string(a);
  if(select_backend("fallback"))return false;
  simdjson::dom::parser q;simdjson::dom::element b;
  auto eb=q.parse(doc).get(b);
  std::string sb;if(eb==simdjson::SUCCESS)sb=simdjson::to_string(b);
  if(select_backend(backend))return false;
  return (ea==simdjson::SUCCESS)==(eb==simdjson::SUCCESS) && sa==sb;
}
'''
    original=original.replace('int main(int argc,char** argv) {',insert+'\nint main(int argc,char** argv) {')
    original=original.replace('std::string backend=argv[1], mode=argv[2];',r'''
#if SIMDJSON_RVV_EXPLORATION91
  if(!simdjson::rvv::exploration91::configure_text(std::getenv("RVV_EXPERIMENT_CONFIG"))) {
    std::cerr<<"Missing/invalid research configuration\n";return 42;
  }
  std::cout<<"CONFIG "<<std::getenv("RVV_EXPERIMENT_CONFIG")<<"\n";
#endif
  std::string backend=argv[1], mode=argv[2];''')
    original=original.replace('simdjson::dom::parser parser;\n  if (mode=="validate")',r'''
  simdjson::dom::parser parser;
  if(mode=="check" || mode=="trace") {
    if(argc!=4)return 2;
    simdjson::padded_string doc;
    if(simdjson::padded_string::load(argv[3]).get(doc)!=simdjson::SUCCESS)return 5;
    if(!agrees(backend,doc)) {std::cerr<<"DOM differs from fallback\n";return 41;}
    if(!parse_ok(parser,doc))return 22;
#if SIMDJSON_RVV_EXPLORATION91
    if(mode=="trace") {
      namespace ex=simdjson::rvv::exploration91;
      ex::trace={};ex::tracing=true;
      bool ok=parse_ok(parser,doc);ex::tracing=false;if(!ok)return 22;
      std::cout<<"TRACE "<<ex::trace.parses<<' '<<ex::trace.regions<<' '<<ex::trace.changes;
      for(auto n:ex::trace.bank_bytes)std::cout<<' '<<n;
      std::cout<<"\n";
    }
#endif
    std::cout<<"DOM_AGREES\n";return 0;
  }
  if (mode=="validate")''')
    # Enrich validation_file without altering parse_ok timing functions.
    original=original.replace('static int validate_file(', 'static bool agrees(const std::string&,const simdjson::padded_string&);\nstatic int validate_file(')
    original=original.replace('const bool actual=parse_ok(parser,line);',r'''
    const std::string backend(simdjson::get_active_implementation()->name());
    if(!agrees(backend,simdjson::padded_string(line))) {
      std::cerr<<"Differential validation mismatch at "<<count+1<<"\n";return 41;
    }
    const bool actual=parse_ok(parser,line);''')
    # Catch invalid UTF8 and escaped/unescaped control bytes as raw JSONL bytes too.
    return original
