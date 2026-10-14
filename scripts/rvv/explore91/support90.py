#!/usr/bin/env python3
"""Two-hour precommitted holdout validation of Adaptive Dispatch v2 with JSON correctness gates.

No CMake, CPM, benchmark framework, external experimental strategy, sudo or cleanup
outside this run. Every experiment is determined before launch; only hard-coded
conservative early abandonment is allowed. Two hours include native GCC builds, native validation and all checks.
"""
from __future__ import annotations
import argparse
import contextlib
import csv
import datetime as dt
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import statistics
import subprocess
import time
import zipfile

GIB=1024**3
MAX_HOURS=2.0
BENCH_MAX_ITERATIONS=1000
WORK_CAP=2*GIB
FREE_FLOOR=200*1024**2
BUILD_START_FLOOR=FREE_FLOOR
SNAPSHOT_LIMIT=32*1024**2
RUN_FILES=('status.json','checkpoint.json','map.csv','ranking.csv','hypotheses.md','failures.csv','metadata.json','corpus_manifest.json','trend_candidates.csv','prequal_pairwise.csv','TRENDS.md','coverage_by_design.csv','hypotheses_to_confirm.csv','VALIDATION_2H.md')
RESULT_FIELDS=('timestamp','phase','variant','defines','corpus','bytes','parse_iterations','trial',
               'dom_all_gbps','stage1_gbps','stage2_gbps','all_cpb','stage1_cpb','stage2_cpb',
               'elapsed_seconds','method','scenario','distribution','size_target','sampling_bias')
RANK_FIELDS=('variant','metric','paired_n','median_ratio','geomean_ratio','mad_ratio')
EARLY_ABORT_DOM_RATIO=.65
EARLY_ABORT_MIN_CORPORA=3
UPSTREAM_SHA='bf89ddd00ef5fcb6a7f20611ea8853d258b67249'
UPSTREAM_URL='https://github.com/simdjson/simdjson.git'

# Standalone measurement harness. Built from the exact pinned source tree with
# src/simdjson.cpp and the same flags; it does NOT pull in CMake dependencies.
# DOM throughput only. No synthetic Stage1/Stage2 numbers are produced.
BENCH_CPP=r'''// Standalone native split-stage benchmark for simdjson RVV-VLA.
// Measures actual internal stage1() / stage2() calls plus independent public DOM parse().
// Stage1 + Stage2 timings are NOT claimed to equal DOM timing.
#include "simdjson.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <cstdlib>
#include <cstdint>

static bool parse_ok(simdjson::dom::parser& p, const std::string& s) {
  return p.parse(s).error() == simdjson::SUCCESS;
}
static bool parse_ok(simdjson::dom::parser& p, const simdjson::padded_string& s) {
  return p.parse(s).error() == simdjson::SUCCESS;
}
static int select_backend(const std::string &backend) {
  const auto* chosen=simdjson::get_available_implementations()[backend];
  if (!chosen || !chosen->supported_by_runtime_system()) {
    std::cerr << "Unsupported backend: " << backend << "\n";
    return 3;
  }
  simdjson::get_active_implementation()=chosen;
  if (simdjson::get_active_implementation()->name()!=backend) return 4;
  return 0;
}
static int validate_file(simdjson::dom::parser& parser, const char *path, bool expected) {
  std::ifstream in(path);
  if (!in) { std::cerr << "Missing JSONL: " << path << "\n"; return 5; }
  std::string line;
  int count=0;
  while (std::getline(in,line)) {
    // CR-LF line ending support for Windows-built input.
    if (!line.empty() && line.back()=='\r') line.pop_back();
    const bool actual=parse_ok(parser,line);
    if (actual!=expected) {
      std::cerr<< "JSON classification mismatch file=" << path
               << " line=" << count+1 << " expected=" << expected
               << " actual=" << actual << "\n";
      return 20;
    }
    ++count;
  }
  if (count<10) {std::cerr<< "Insufficient correctness coverage in " << path << "\n";return 21;}
  std::cout<<"VALIDATION "<<(expected?"valid":"invalid")<<"="<<count<<"\n";
  return 0;
}
int main(int argc,char** argv) {
  if (argc < 3) {std::cerr<<"usage: bench <rvv|rvv_vls> <validate|split> args...\n";return 2;}
  std::string backend=argv[1], mode=argv[2];
  if (int rc=select_backend(backend)) return rc;
  simdjson::dom::parser parser;
  if (mode=="validate") {
    if (argc!=5) return 2;
    int rc=validate_file(parser,argv[3],true);if (rc) return rc;
    rc=validate_file(parser,argv[4],false);if (rc) return rc;
    std::cout << "RVV_VALIDATION_OK backend=" << backend << "\n";
    return 0;
  }
  if (mode!="split" || argc!=5) return 2;
  simdjson::padded_string doc;
  if (simdjson::padded_string::load(argv[3]).get(doc)!=simdjson::SUCCESS || doc.size()==0)
    return 5;
  char* end=nullptr;
  long count=std::strtol(argv[4],&end,10);
  if (!end || *end || count<1 || count>1000) {
    std::cerr << "Iteration count outside 1..1000: " << argv[4] << "\n";
    return 6;
  }
  // Warm init is required: parser.implementation is created lazily by parse().
  if (!parse_ok(parser,doc)) {std::cerr<<"Corpus fails full DOM parse\n";return 22;}
  const uint8_t* data=reinterpret_cast<const uint8_t*>(doc.data());
  auto stage_cycle = [&]() -> int {
    auto rc=parser.implementation->stage1(data,doc.size(),simdjson::stage1_mode::regular);
    if (rc!=simdjson::SUCCESS) {std::cerr<<"Stage1 error "<<rc<<"\n";return 23;}
    rc=parser.implementation->stage2(parser.doc);
    if (rc!=simdjson::SUCCESS) {std::cerr<<"Stage2 error "<<rc<<"\n";return 24;}
    return 0;
  };
  if (int rc=stage_cycle()) return rc;
  using clock=std::chrono::steady_clock;
  double dom_rates[3],stage1_rates[3],stage2_rates[3];
  double dom_times[3],stage1_times[3],stage2_times[3];
  for (int rep=0;rep<3;rep++) {
    // Measure stages from actual implementation calls, not an inferred split.
    double ns1=0,ns2=0;
    for(long i=0;i<count;i++) {
      const auto t0=clock::now();
      auto rc=parser.implementation->stage1(data,doc.size(),simdjson::stage1_mode::regular);
      const auto t1=clock::now();
      if(rc!=simdjson::SUCCESS) return 30;
      rc=parser.implementation->stage2(parser.doc);
      const auto t2=clock::now();
      if(rc!=simdjson::SUCCESS) return 31;
      ns1+=std::chrono::duration<double>(t1-t0).count();
      ns2+=std::chrono::duration<double>(t2-t1).count();
    }
    const auto start=clock::now();
    for(long i=0;i<count;i++) {
      if(!parse_ok(parser,doc)) {std::cerr<<"Corrupt DOM parse during benchmark\n";return 32;}
    }
    const auto finish=clock::now();
    dom_times[rep]=std::chrono::duration<double>(finish-start).count();
    stage1_times[rep]=ns1;
    stage2_times[rep]=ns2;
    if (dom_times[rep]<=0||ns1<=0||ns2<=0)return 33;
    const double bytes=double(count)*double(doc.size());
    dom_rates[rep]=bytes / dom_times[rep] / 1e9;
    stage1_rates[rep]=bytes / ns1 / 1e9;
    stage2_rates[rep]=bytes / ns2 / 1e9;
  }
  std::sort(dom_rates,dom_rates+3);
  std::sort(stage1_rates,stage1_rates+3);
  std::sort(stage2_rates,stage2_rates+3);
  std::sort(dom_times,dom_times+3);
  std::sort(stage1_times,stage1_times+3);
  std::sort(stage2_times,stage2_times+3);
  std::cout.precision(12);
  std::cout<<"SPLIT_RESULT "<<dom_rates[1]<<' '<<stage1_rates[1]<<' '
           <<stage2_rates[1]<<' '<<dom_times[1]<<' '<<stage1_times[1]
           <<' '<<stage2_times[1]<<' '<<count<<' '<<doc.size()<<"\n";
  return 0;
}
'''



def iterations_for_bytes(n):
    """Native-compatible bounded iteration schedule; no value may exceed the C++ cap."""
    if not isinstance(n,int) or n<1:
        raise ValueError('Invalid corpus length')
    requested=(1000 if n<=512 else 768 if n<=2048 else 512 if n<=8192 else
               144 if n<=65536 else 48 if n<=262144 else 18 if n<=1048576 else 8)
    return min(requested,BENCH_MAX_ITERATIONS)

def now():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')

def atomic_text(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.tmp')
    with tmp.open('w',encoding='utf8') as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)

def atomic_json(path,data):atomic_text(path,json.dumps(data,indent=2,ensure_ascii=False,sort_keys=True)+'\n')

def write_csv(path,rows,fields):
    p=Path(path);tmp=p.with_name(p.name+'.tmp')
    with tmp.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
        f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)

def read_tail(path,limit=9500):
    p=Path(path)
    if not p.is_file():return ''
    with p.open('rb') as f:
        f.seek(0,os.SEEK_END);f.seek(max(0,f.tell()-limit))
        return f.read().decode('utf8','replace')[-limit:]

def extract_errors(log):
    lines=log.splitlines();results=[]
    for i,line in enumerate(lines):
        if re.search(r'(^|\s)(fatal error:|error:|FAILED:|undefined reference)',line,re.I):
            results.append('\n'.join(lines[max(i-1,0):i+2])[:850])
            if len(results)==12:break
    return results

def catalog(_unused=None):
    """Precommitted 6-way exploratory pilot set, chosen from existing v5 patterns.

    All variants are separate native GCC binaries. No unvalidated runtime
    switching, no data-dependent compilation and no automatic winner.
    """
    e14={'SIMDJSON_RVV_ENGINE_LIBRARY':'1','SIMDJSON_RVV_FORCE_PLAN':'0',
         'SIMDJSON_RVV_ENABLE_PACKED_CONTROL':'0',
         'SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER':'0'}
    adaptive={'SIMDJSON_RVV_ENGINE_LIBRARY':'1','SIMDJSON_RVV_FORCE_PLAN':'0'}
    sparse={'SIMDJSON_RVV_ENGINE_LIBRARY':'0',
      'SIMDJSON_RVV_SPARSE_INDEX_THRESHOLD':'8',
      'SIMDJSON_RVV_SPARSE_ESCAPE_THRESHOLD':'8',
      'SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER':'0',
      'SIMDJSON_RVV_ENABLE_PACKED_ESCAPE':'0',
      'SIMDJSON_RVV_ENABLE_PACKED_QUOTE':'0',
      'SIMDJSON_RVV_ENABLE_PACKED_SHIFT':'0'}
    return [
      ('upstream_vls256',{},'rvv_vls','vls'),
      ('A0_E14_original',{**e14,'SIMDJSON_RVV_ADAPTIVE_V2_LEVEL':'0'},'rvv','vla'),
      ('A1_size_gate',{**e14,'SIMDJSON_RVV_ADAPTIVE_V2_LEVEL':'1'},'rvv','vla'),
      ('A2_quick_dispatch',{**e14,'SIMDJSON_RVV_ADAPTIVE_V2_LEVEL':'2'},'rvv','vla'),
      ('sparse8_escape8_reference',sparse,'rvv','vla'),
    ]


def should_abandon(entries):
    distinct={name for name,ratio in entries}
    return (len(distinct)>=EARLY_ABORT_MIN_CORPORA
            and all(math.isfinite(r) and 0<r<EARLY_ABORT_DOM_RATIO for _,r in entries))

class Stopped(Exception):pass
class Deadline(Stopped):pass
class Safety(Exception):pass
class TimedOut(Exception):pass

def run_logged(command,log_path,*,cwd,deadline,stopfile,timeout,free_floor=FREE_FLOOR):
    """Never accumulate unbounded stdout in pipes. Stop the whole compiler group."""
    started=time.monotonic()
    cutoff=min(deadline,started+timeout)
    with Path(log_path).open('wb') as log:
        p=subprocess.Popen([str(x) for x in command],cwd=cwd,stdin=subprocess.DEVNULL,
           stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            while p.poll() is None:
                if Path(stopfile).exists():raise Stopped('STOP requested')
                if time.monotonic()>=cutoff:
                    if deadline<=started+timeout:raise Deadline('2-hour budget reached')
                    raise TimedOut(f'command exceeded {timeout:.0f}s')
                if shutil.disk_usage(cwd).free < free_floor:raise Safety('disk below 200 MiB safety floor during native command')
                time.sleep(.3)
        except (Stopped,TimedOut,Safety):
            with contextlib.suppress(ProcessLookupError):os.killpg(p.pid,signal.SIGTERM)
            try:p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):os.killpg(p.pid,signal.SIGKILL)
                p.wait()
            raise
    return p.returncode,round(time.monotonic()-started,3)


def parse_split_output(text):
    match=re.search(r'^SPLIT_RESULT\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d+)\s*$', text, re.M)
    if not match:raise ValueError('No SPLIT_RESULT from native benchmark')
    vals=[float(x) for x in match.groups()[:6]]
    if not all(math.isfinite(x) and x>0 for x in vals):raise ValueError('invalid rates or durations')
    return vals+[int(x) for x in match.groups()[6:]]


def rankings(rows):
    controls={(r['phase'],r['corpus'],str(r['parse_iterations']),str(r['trial'])):r
              for r in rows if r['variant']=='upstream_vls256'}
    matched={}
    for r in rows:
        key=(r['phase'],r['corpus'],str(r['parse_iterations']),str(r['trial']))
        ref=controls.get(key)
        if not ref:continue
        for col,metric in [('dom_all_gbps','dom_all'),('stage1_gbps','stage1'),('stage2_gbps','stage2')]:
            try:b=float(ref[col]);v=float(r[col])
            except (KeyError,TypeError,ValueError):continue
            if b>0 and v>0 and math.isfinite(b) and math.isfinite(v):
                matched.setdefault((r['variant'],metric),[]).append(v/b)
    result=[]
    for (label,metric),ratios in matched.items():
        med=statistics.median(ratios)
        gm=math.exp(statistics.mean(math.log(x) for x in ratios))
        result.append(dict(variant=label,metric=metric,paired_n=len(ratios),
            median_ratio=round(med,6),geomean_ratio=round(gm,6),
            mad_ratio=round(statistics.median(abs(x-med) for x in ratios),6)))
    return sorted(result,key=lambda d:(d['metric'],-d['geomean_ratio'],d['variant']))

# Expanded precommitted workload matrix. Synthetic JSON inputs deliberately
# cover combinations, ordering, spatial locality and misleading 512B samples.
# This is workload diversity on ONE hardware/OS/compiler, not multiple environments.
EXPLORATION_SEED=20261013
BASE_SIZES=(256,1024,4095,4096,8192,32768,131072,1048576)
BASE_KINDS=('ascii','numbers','dense','escaped','unicode_escape','utf8',
    'nested','whitespace','long_strings','many_keys','mixed',
    'boolnull','scientific','punctuation','slashstorm','sparse')
COMBINATION_PAIRS=(
    ('ascii','escaped'),('ascii','utf8'),('ascii','dense'),('ascii','numbers'),
    ('numbers','dense'),('numbers','utf8'),('numbers','escaped'),
    ('dense','escaped'),('dense','unicode_escape'),('dense','utf8'),
    ('escaped','utf8'),('escaped','unicode_escape'),('escaped','slashstorm'),
    ('unicode_escape','utf8'),('long_strings','dense'),('many_keys','numbers'),
    ('punctuation','escaped'),('slashstorm','utf8'),('scientific','dense'),
    ('sparse','dense'),('boolnull','utf8'),('whitespace','punctuation'))
TRIPLES=(('ascii','escaped','utf8'),('dense','numbers','utf8'),
    ('dense','escaped','unicode_escape'),('many_keys','long_strings','utf8'),
    ('boolnull','numbers','dense'),('scientific','punctuation','escaped'),
    ('slashstorm','utf8','unicode_escape'),('sparse','dense','long_strings'),
    ('nested','escaped','utf8'),('numbers','escaped','punctuation'),
    ('whitespace','dense','utf8'),('ascii','scientific','unicode_escape'))
PAIR_SIZES=(2048,8192,65536,262144)
TRIPLE_SIZES=(8192,65536,262144,1048576)
SEGMENT_PLACEMENTS=('front','middle','back','alternating')
TRIPLE_PLACEMENTS=('front','middle','back')
SKEW_SIZES=(8192,65536,262144,1048576)
SKEW_KINDS=('escaped','utf8','dense','numbers','unicode_escape','slashstorm')
SKEW_DISTRIBUTIONS=('front','middle','back')
EDGE_SIZES=(128,511,512,513,1023,1024,2047,2048,4094,4095,4096,4097,4098,8191,8192,8193,16384)
HEAVY_SIZES=(2*1024*1024,4*1024*1024)


def _json_atom(kind,index):
    # Deterministic, valid, diverse JSON tokens, with numbers kept finite.
    if kind=='ascii':return {'name':'lorem_ipsum_alpha_beta_gamma'*2,'id':index%1000,'ok':True}
    if kind=='numbers':return [index,-index,0.0000001234,1.234e22,index+0.75]
    if kind=='dense':return [[0,1],[2,3],{'a':0,'b':[]},True,False,None]
    if kind=='escaped':return {'p':'back\\slash\\route\nquoted"value\t'*3,'index':index}
    if kind=='unicode_escape':return {'p':'😺😀漢字é'*9,'index':index}
    if kind=='utf8':return {'str':'中文 العربية हिन्दी 🐈 café '*4,'id':index}
    if kind=='nested':
        v={'leaf':[1,2,None,'z']}
        for _ in range(12):v={'child':v}
        return v
    if kind=='whitespace':return {'a':[0,1,2],'space':'   '*3,'b':True}
    if kind=='long_strings':return {'text':'abcdefghij'*100,'n':index}
    if kind=='many_keys':return {f'key_{i:02d}':i+index for i in range(30)}
    if kind=='mixed':return {'json':[1,'abc',None,{'a':[True,{'z':4}]}], 'utf8':'résumé 🧪','escape':'a\nb','n':index}
    if kind=='boolnull':return [None,False,True,None,{'ok':True,'nil':None},[False,True]]
    if kind=='scientific':return {'f':[1.3e-18,9.27e+27,-5.63e-12,1.0e-9], 'n':index}
    if kind=='punctuation':return {'text':'[]{},:[]{}"\\'*5,'n':index}
    if kind=='slashstorm':return {'text':('\\\\\\n\\\\u0041\\t"')*7, 'n':index}
    if kind=='sparse':return {'s':'s'*600, 'i':index,'b':False}
    raise ValueError(kind)


def _atom_bytes(kind,index):
    return json.dumps(_json_atom(kind,index),ensure_ascii=(kind=='unicode_escape'),
        separators=(',',':'),allow_nan=False).encode('utf8')


def make_combo_bytes(kinds,target,placement='alternating',seed=EXPLORATION_SEED):
    """Produce valid JSON arrays; switch between kinds by byte position.

    All selections are deterministic and independent of benchmark outcomes.
    This is a corpus generator, NOT a runtime prequalification analyzer.
    """
    import random
    if not kinds:raise ValueError('empty kinds')
    salt=sum(sum(map(ord,k))*(i+17) for i,k in enumerate(kinds))
    rng=random.Random(seed+target+salt+sum(map(ord,placement)))
    pieces=[];total=2;index=(seed % 9973)
    # Mix by requested byte position; segments intentionally cover 512B
    # prefix false positives and multi-phase documents.
    while total<target and index<500000:
        progress=total/max(1,target)
        if placement=='front':
            # Triple cases MUST really include all three structural families.
            choice=(kinds[0] if progress<.26 else
                    kinds[1] if len(kinds)>2 and progress<.70 else kinds[-1])
        elif placement=='middle':
            choice=(kinds[0] if .36<=progress<.64 else
                    kinds[1] if len(kinds)>2 and progress<.36 else kinds[-1])
        elif placement=='back':
            choice=(kinds[0] if progress>.73 else
                    kinds[1] if len(kinds)>2 and progress>.38 else kinds[-1])
        elif placement=='alternating':
            choice=kinds[(index//(1+((target//8192)%5)))%len(kinds)]
        elif placement=='staircase':
            choice=kinds[min(len(kinds)-1,int(progress*len(kinds)))]
        elif placement=='bursts':
            choice=kinds[0] if (index//7)%10<2 else kinds[-1]
        elif placement=='randomized':
            choice=kinds[rng.randrange(len(kinds))]
        elif placement=='uniform':
            choice=kinds[0]
        else:raise ValueError('unknown placement '+placement)
        atom=_atom_bytes(choice,index)
        if index and choice=='whitespace' and index%4==0:atom=b' 	'+atom+b' '
        pieces.append(atom)
        total+=len(atom)+(1 if index else 0)
        index+=1
    if index>=500000:raise RuntimeError('corpus generator limit')
    return b'['+b','.join(pieces)+b']'


def exact_gate_bytes(kind,size):
    # Exact byte boundaries around 512B, 2KiB, 4KiB, 8KiB.
    head=b'{"data":"';tail=b'"}'
    base=len(head)+len(tail)
    assert size>=base
    remaining=size-base
    if kind=='utf8':inner=('é'*(remaining//2)+'z'*(remaining%2)).encode('utf8')
    elif kind=='escaped':inner=(('\\\\'*(remaining//2))+'z'*(remaining%2)).encode('utf8')
    else:inner=b'x'*remaining
    result=head+inner+tail
    assert len(result)==size
    json.loads(result)
    return result


def _safe_pad(n, seed):
    """ASCII-only JSON string filler, deterministic per scenario, no quoting hazards."""
    import random
    rng=random.Random(seed)
    alphabet='abcdefghijklmnopqrstuvwxyz0123456789'
    return ''.join(alphabet[rng.randrange(len(alphabet))] for _ in range(n)).encode('ascii')


def make_holdout_exact(kind, size, seed):
    """New independently-seeded JSON of EXACT requested UTF-8 byte length."""
    body=_json_atom(kind, seed)
    data=json.dumps({'test90_seed':seed,'kind':kind,'body':body,'pad':'__PAD90__'},
                    ensure_ascii=(kind=='unicode_escape'),separators=(',',':')).encode('utf8')
    marker=b'__PAD90__'
    assert data.count(marker)==1
    remaining=size-len(data)+len(marker)
    if remaining<0:raise ValueError(f'Exact case too small: {kind}/{size}, min={len(data)-len(marker)}')
    result=data.replace(marker,_safe_pad(remaining,seed+size*17))
    assert len(result)==size
    json.loads(result)
    return result


def make_holdout_deceptive(kind, size, offset, seed):
    """Starts complex JSON atom exactly at byte offset; 512B prefix can be misleading."""
    header=b'{"lead":"'; split=b'","hard":'; suffix=b',"tail":"'; end=b'"}'
    # Offset is the first byte of the hard value (not the object's initial delimiter).
    leading=offset-len(header)-len(split)
    if leading<0:raise ValueError('Offset too small')
    hard=_atom_bytes(kind,seed)
    trailing=size-(len(header)+leading+len(split)+len(hard)+len(suffix)+len(end))
    if trailing<0:raise ValueError('Target too short for deceptive payload')
    result=(header+_safe_pad(leading,seed)+split+hard+suffix+
            _safe_pad(trailing,seed+83)+end)
    assert len(result)==size and result.index(hard)==offset
    json.loads(result)
    return result


def holdout_specs():
    """Frozen scenarios: held-out seeds never appeared in Test89."""
    cases=[]
    gate512=(480,496,504,508,511,512,513,516,520,528,544,576,640)
    gate4k=(3840,3968,4032,4064,4080,4088,4092,4095,4096,4097,4100,4104,4112,4128,4160,4224,4352)
    for kind in ('ascii','escaped','utf8','numbers'):
        for size in gate512:
            for replication in (0,1):
                cases.append(dict(design='gate512',kinds=(kind,),target=size,placement='threshold',
                                  seed=EXPLORATION_SEED+100003*replication+size+sum(map(ord,kind))))
    for kind in ('ascii','escaped','unicode_escape','dense'):
        for size in gate4k:
            for replication in (0,1):
                cases.append(dict(design='gate4096',kinds=(kind,),target=size,placement='threshold',
                                  seed=EXPLORATION_SEED+200003*replication+size+sum(map(ord,kind))))
    for kind in ('escaped','utf8','unicode_escape','dense','numbers'):
        for offset in (480,511,512,513,2048,4095,4096,4097):
            for size in (8192,65536):
                for replication in (0,1):
                    cases.append(dict(design='deceptive_prefix',kinds=(kind,),target=size,
                        placement=f'offset{offset}',offset=offset,
                        seed=EXPLORATION_SEED+300007*replication+size+offset+sum(map(ord,kind))))
    challenger=(('dense','numbers','utf8'),('dense','unicode_escape'),
                ('many_keys','long_strings','utf8'),('escaped','slashstorm'),
                ('numbers','utf8'),('dense','escaped','unicode_escape'),
                ('sparse','dense','long_strings'),('whitespace','dense','utf8'))
    for kinds in challenger:
        for place in ('front','middle','back'):
            for target in (8192,65536):
                for replication in (0,1):
                    cases.append(dict(design='sparse_challenge',kinds=kinds,target=target,
                        placement=place,seed=EXPLORATION_SEED+400009*replication+target+
                        sum(sum(map(ord,k))*(i+1) for i,k in enumerate(kinds))+
                        sum(map(ord,place))))
    return cases

def sampling_signals(data,window=512):
    n=len(data);samples={}
    for name,start in [('head',0),('middle',max(0,(n-window)//2)),('tail',max(0,n-window))]:
        chunk=data[start:start+window]
        cnt=max(1,len(chunk))
        samples[name]={'n':len(chunk),'slash_density':round(chunk.count(b'\\')/cnt,5),
          'quote_density':round(chunk.count(b'"')/cnt,5),
          'struct_density':round(sum(chunk.count(bytes([c])) for c in (91,93,123,125,44,58))/cnt,5),
          'highbyte_density':round(sum(c>=128 for c in chunk)/cnt,5),
          'digit_density':round(sum(48<=c<=57 for c in chunk)/cnt,5)}
    samples['head_4096']={'n':min(4096,n),'slash_density':round(data[:4096].count(b'\\')/max(1,min(4096,n)),5),
        'highbyte_density':round(sum(c>=128 for c in data[:4096])/max(1,min(4096,n)),5)}
    return samples


def derived_trends(rows, corpus_info):
    from collections import defaultdict
    reference={(r['phase'],r['corpus'],str(r['trial'])):r for r in rows
               if r['variant']=='upstream_vls256'}
    slots=defaultdict(list)
    for r in rows:
        if r['variant']=='upstream_vls256':continue
        ref=reference.get((r['phase'],r['corpus'],str(r['trial'])))
        if ref is None:continue
        try: ratio=float(r['dom_all_gbps'])/float(ref['dom_all_gbps'])
        except (ValueError,ZeroDivisionError):continue
        if not math.isfinite(ratio) or ratio<=0:continue
        info=corpus_info.get(r['corpus'].split('@',1)[0],{})
        shape=info.get('kind','unknown');size=info.get('size_target',0)
        band=('tiny (<4KiB)' if size<4096 else 'gate (4-8KiB)' if size<=8192 else
              'medium (8-256KiB)' if size<=262144 else 'large (>=1MiB)')
        slots[(shape,band,r['variant'])].append(ratio)
    fields=('kind','size_band','variant','n','geomean_dom_vs_vls256','median_dom_vs_vls256','exploratory_only')
    output=[]
    for (shape,band,tag),vals in sorted(slots.items()):
        gm=math.exp(statistics.mean(math.log(x) for x in vals))
        output.append(dict(zip(fields,[shape,band,tag,len(vals),round(gm,6),round(statistics.median(vals),6),True])))
    return output,fields


def prequal_pairwise(rows,corpus_info):
    # Mode-to-mode comparisons are more relevant than a baseline speedup when
    # researching the incremental value of classification. Match EXACT trial,
    # corpus and iteration count. Require full positive finite measurements.
    from collections import defaultdict
    groups=defaultdict(dict)
    for r in rows:
        key=(r['phase'],r['corpus'],str(r['parse_iterations']),str(r['trial']))
        groups[key][r['variant']]=r
    pairs=tuple((name,'A0_E14_original') for name in
         ('A1_size_gate','A2_quick_dispatch','E01_adaptive',
          'sparse8_escape8_reference','E03_numeric','E05_escaped',
          'E06_unicode_escape','E07_utf8')) + (('A2_quick_dispatch','A1_size_gate'),('A2_quick_dispatch','sparse8_escape8_reference'),('A2_quick_dispatch','upstream_vls256'),('sparse8_escape8_reference','upstream_vls256'),('A1_size_gate','upstream_vls256'))
    fields=('phase','corpus','trial','iterations','kind','distribution','size_target',
            'bytes','sample_spread_proxy','numerator','denominator',
            'dom_ratio','stage1_ratio','stage2_ratio','exploratory_only')
    output=[]
    for key,variants in sorted(groups.items()):
        phase,corpus,iterations,trial=key
        info=corpus_info.get(corpus.split('@',1)[0],{})
        for a,b in pairs:
            if a not in variants or b not in variants:continue
            vals=[]
            for metric in ('dom_all_gbps','stage1_gbps','stage2_gbps'):
                try:ratio=float(variants[a][metric])/float(variants[b][metric])
                except (ValueError,ZeroDivisionError,KeyError):break
                if not math.isfinite(ratio) or ratio<=0:break
                vals.append(round(ratio,7))
            if len(vals)!=3:continue
            output.append(dict(zip(fields,[phase,corpus,trial,iterations,
                info.get('kind','?'),info.get('distribution','?'),
                info.get('size_target',0),info.get('bytes',0),
                info.get('sample_spread_proxy',0),a,b,*vals,True])))
    return output,fields


class Campaign:
    def __init__(self,source,workdir,hours,jobs,core):
        self.source=Path(source).resolve();self.root=Path(workdir).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.started=time.time();self.deadline_mono=time.monotonic()+hours*3600
        self.stopfile=self.root/'STOP';self.jobs=jobs;self.core=core
        self.rows=[];self.failures=[];self.binaries={};self.abandoned={}
        self.meta={'schema':2,'experiment':'adaptive_v2_holdout_validation_2h','compiler':'gcc',
          'iteration_cap':BENCH_MAX_ITERATIONS,'benchmark_method':'Direct g++ -O3: independent DOM parse() timing + direct stage1()/stage2() timing; 3-repetition medians; 1e9 bytes/s',
          'metric_limits':'Internal parser stage1 and stage2 measured explicitly (warm preallocated parser); stage durations do not necessarily add to DOM public API timing; CPU wall time, no cycles',
          'points':catalog(),'upstream_sha':UPSTREAM_SHA,'builds':[], 'compiler_diagnostics':[],
          'runtime_probes':[], 'code_sha256':hashlib.sha256(BENCH_CPP.encode()).hexdigest()}
        self.status={'schema':2,'state':'preflight','started_utc':now(),'last_update':now(),
          'observations':0,'source':str(self.source),'jobs':jobs,'core':core,
          'deadline_utc':dt.datetime.fromtimestamp(self.started+hours*3600,dt.timezone.utc).isoformat(),
          'budget_seconds':int(hours*3600),'fixed_round_completed':0,'point_catalog':[p[0] for p in catalog()],
          'stop_reason':None,'abandoned_points':{},'current_candidate':None}
        self.last_snap=0
    def check(self,building=False):
        if self.stopfile.exists():raise Stopped('STOP requested')
        if time.monotonic()>=self.deadline_mono:raise Deadline('2-hour budget reached')
        free=shutil.disk_usage(self.root).free
        self.status['disk_free_gib']=round(free/GIB,3)
        self.status['disk_free_mib']=round(free/(1024**2),1)
        self.status['disk_safety_floor_mib']=200
        self.status['disk_monitor_interval_seconds']=900
        instant=time.monotonic()
        if instant-getattr(self,'last_disk_monitor_monotonic',float('-inf'))>=900:
            self.last_disk_monitor_monotonic=instant
            self.status['disk_last_15m_check_utc']=now()
            self.meta.setdefault('disk_monitor_15m',[]).append({'utc':now(),'free_mib':round(free/(1024**2),1)})
        if free < (BUILD_START_FLOOR if building else FREE_FLOOR):
            raise Safety(f'free disk below safety floor ({free/GIB:.2f} GiB)')
        # Bounded workspace, including any temporary source files.
        total=0
        for base,dirs,files in os.walk(self.root,followlinks=False):
            dirs[:]=[d for d in dirs if not (Path(base)/d).is_symlink()]
            for file in files:
                with contextlib.suppress(OSError):total+=(Path(base)/file).stat().st_size
        if total>WORK_CAP:raise Safety('run exceeded 2 GiB work cap')
    def checkpoint(self,phase=None,force=False):
        if phase:self.status['state']=phase
        self.status['observations']=len(self.rows)
        self.status['last_update']=now()
        with contextlib.suppress(OSError):self.status['disk_free_gib']=round(shutil.disk_usage(self.root).free/GIB,3)
        atomic_json(self.root/'status.json',self.status)
        atomic_json(self.root/'checkpoint.json',{'started_epoch':self.started,
            'completed':len(self.rows),'updated_utc':now()})
        if force or time.monotonic()-self.last_snap>=240:
            write_csv(self.root/'map.csv',self.rows,RESULT_FIELDS)
            write_csv(self.root/'failures.csv',self.failures,('time','step','candidate','error'))
            ranking=rankings(self.rows)
            write_csv(self.root/'ranking.csv',ranking,RANK_FIELDS)
            self.meta['abandoned_points']=self.abandoned
            self.meta['build_coverage']={'passed':sorted(self.binaries),
                 'attempted':len(self.meta['builds']),'planned':len(catalog())}
            atomic_json(self.root/'metadata.json',self.meta)
            text=['Holdout validation 2h — fixed hypotheses from Test 89',
              '','- Snapshot updated: '+now(),'- State: '+self.status['state'],
              '- Measurements: '+str(len(self.rows)),
              '- GCC direct compile; separate DOM, Stage1 and Stage2 wall times, each median of 3; GB=1e9 bytes.',
              '- Stage1 and Stage2 are measured from implementation methods, not derived from DOM; warm allocated parser.',
              '- Five fixed points, holdout corpus and three precommitted independent-process repeats per primary case.',
              '- Randomized corpus order and alternated/reversed candidates; exploratory results only.',
              '','## Paired metric ratios against official v5.0.3 VLS256','',
              '| Candidate | Metric | Geo-mean vs official VLS256 | N | MAD |','|---|---|---:|---:|---:|']
            text += [f"| {r['variant']} | {r['metric']} | {r['geomean_ratio']:.3f}x | {r['paired_n']} | {r['mad_ratio']:.3f} |" for r in ranking]
            atomic_text(self.root/'hypotheses.md','\n'.join(text)+'\n')
            info=getattr(self,'corpi_info',{})
            trends,fields=derived_trends(self.rows,info)
            write_csv(self.root/'trend_candidates.csv',trends,fields)
            comparisons,comparison_fields=prequal_pairwise(self.rows,info)
            write_csv(self.root/'prequal_pairwise.csv',comparisons,comparison_fields)
            review=['# Targeted holdout validation 2h: descriptive data, no automatic winner', '',
               f'As of {now()}, {len(self.rows)} records; {len(info)} planned JSON cases.',
               '', 'These per-shape values are geometric means of matched DOM ratios against',
               'official simdjson VLS256. Repeated trials are correlated. The same corpus',
               'design drives all variants, but there is no multi-hardware replication.',
               'Subgroups with small paired n are especially noisy. These are candidates',
               'for future confirmation, not a winner, not statistically significant.',
               '', '| Family | Size band | Mode | Matched n | DOM vs VLS256 |',
               '|---|---|---|---:|---:|']
            review += [f"| {r['kind']} | {r['size_band']} | {r['variant']} | {r['n']} | {r['geomean_dom_vs_vls256']:.3f}x |" for r in trends]
            # Avoid claiming a winner. Rank only the most extreme, noisy
            # pairwise DOM observations as *follow-up candidates*.
            suggestions=[r for r in comparisons if r['numerator']=='A2_quick_dispatch'
                 and r['denominator']=='A0_E14_original']
            suggestions.sort(key=lambda r:abs(math.log(r['dom_ratio'])),reverse=True)
            review += ['','## Hypotheses to re-test (single-trial outliers; NOT validated)',
                '','The following are extreme A2/A0 DOM comparisons only, selected',
                'post hoc among many related tests. Expect selection bias and noise.',
                'Re-run each with new data, repeated fresh processes, and independent',
                'reference order. Do not publish them as achieved speedups.','',
                '| Corpus | Kind | Placement | A2/A0 DOM | Prefix-vs-rest proxy |',
                '|---|---|---|---:|---:|']
            review += [f"| `{r['corpus'].split('@')[0]}` | {r['kind']} | {r['distribution']} | {r['dom_ratio']:.3f}x | {r['sample_spread_proxy']:.4f} |"
                       for r in suggestions[:15]]
            atomic_text(self.root/'TRENDS.md','\n'.join(review)+'\n')
            self.extended_analysis(comparisons)
            self.snapshot()
            self.last_snap=time.monotonic()
    def extended_analysis(self, comparisons):
        """Offline-only descriptive trend mining, never changes scheduling/flags."""
        from collections import defaultdict
        info=getattr(self,'corpi_info',{})
        measured=defaultdict(set)
        for r in self.rows:
            measured[r['corpus'].split('@',1)[0]].add(r['variant'])
        fields=('scenario_id','design','kind','distribution','size_target','bytes',
                'measured_variants','paired_all_variants','sampling_spread_proxy')
        coverage=[]
        for cid,obj in sorted(info.items()):
            variants=measured.get(cid,set())
            coverage.append(dict(scenario_id=cid,design=obj.get('design','?'),
               kind=obj['kind'],distribution=obj['distribution'],
               size_target=obj['size_target'],bytes=obj['bytes'],
               measured_variants=len(variants),paired_all_variants=len(variants)==len(catalog()),
               sampling_spread_proxy=obj['sample_spread_proxy']))
        write_csv(self.root/'coverage_by_design.csv',coverage,fields)
        cases=defaultdict(list)
        for r in comparisons:
            a,b=r['numerator'],r['denominator']
            if (a,b) not in ((x,'A0_E14_original') for x in ('A1_size_gate','A2_quick_dispatch')):
                continue
            if r['phase'] not in ('confirm_primary','confirm_secondary'):continue
            cid=r['corpus'].split('@',1)[0]
            obj=info.get(cid,{})
            key=(obj.get('design','unknown'),obj.get('kind','unknown'),
                obj.get('distribution','?'),a,b)
            cases[key].append(float(r['dom_ratio']))
        result=[]
        for (design,kind,placement,a,b),vals in cases.items():
            if not vals:continue
            gm=math.exp(statistics.mean(math.log(v) for v in vals))
            result.append(dict(design=design,kind=kind,placement=placement,
                candidate=a,reference=b,paired_n=len(vals),
                dom_geomean_ratio=round(gm,6),dom_median_ratio=round(statistics.median(vals),6),
                mad=round(statistics.median(abs(v-statistics.median(vals)) for v in vals),6),
                exploratory_only=True))
        f=('design','kind','placement','candidate','reference','paired_n',
           'dom_geomean_ratio','dom_median_ratio','mad','exploratory_only')
        write_csv(self.root/'hypotheses_to_confirm.csv',sorted(result,key=lambda r:(r['design'],r['kind'],r['candidate'])),f)
        well=[r for r in result if r['paired_n']>=3]
        well.sort(key=lambda r:abs(math.log(r['dom_geomean_ratio'])),reverse=True)
        lines=['# Independent holdout validation 2-hour campaign — descriptive findings', '',
          'NO claims of statistical significance, robustness, winner or cross-device speedup.',
          'Subgroup patterns and the following extremes are POST HOC hypotheses.',
          'They must be tested with held-out JSON and new independent runs.', '',
          f'Available records: {len(self.rows)}',
          f'Precommitted corpus scenarios: {len(info)}',
          f'Scenarios observed with all {len(catalog())} compiled variants: '+
           str(sum(1 for x in coverage if x['paired_all_variants'])),
          '', '## Extreme subgroup A1/A2 vs A0 signals (paired n >= 3)', '',
          '| Design | Kind | Placement | Candidate | Paired n | DOM geomean |',
          '|---|---|---|---|---:|---:|']
        lines += [f"| {r['design']} | {r['kind']} | {r['placement']} | {r['candidate']} | {r['paired_n']} | {r['dom_geomean_ratio']:.3f}x |" for r in well[:35]]
        lines += ['', '## Coverage warnings', '',
          'A partial final trial or failed build may leave missing reference/candidate pairs.',
          'Unpaired measurements are intentionally excluded from summary ratios.',
          'Compiler flags and hypotheses are frozen; no mutation during the run.',
          'Absolute timings of tiny documents are vulnerable to call/timer overhead.',
          'Byte-density probes describe corpus geometry, NOT the actual runtime plan selected.',
          'The campaign intentionally mixes JSON shapes on one host; different CPU/OS/compilers have NOT been tested.']
        self.write_holdout_report(comparisons, lines)

    def write_holdout_report(self, comparisons, previous_lines):
        """Holdout-only descriptive statistics; each JSON counts once (not per trial)."""
        from collections import defaultdict
        by_corpus=defaultdict(list)
        for r in comparisons:
            if r['phase']!='confirm_primary':continue
            cid=r['corpus'].split('@',1)[0]
            by_corpus[(cid,r['numerator'],r['denominator'])].append(r)
        stats=defaultdict(list)
        complete=0
        for (cid,a,b),matches in by_corpus.items():
            if len(set(int(x['trial']) for x in matches))<2:continue
            obj=self.corpi_info[cid]
            complete+=1
            for metric in ('dom_ratio','stage1_ratio','stage2_ratio'):
                values=[float(x[metric]) for x in matches]
                if not all(v>0 and math.isfinite(v) for v in values):continue
                # Predeclared group-level hypotheses; independent seed/corpus is the unit.
                gate=(f'{obj["size_target"]}' if obj['design'].startswith('gate') else obj['design'])
                groups=[('all_primary','all')]
                groups.append((obj['design'],gate))
                if obj['design']=='deceptive_prefix':
                    groups.append(('hard_offset',str(obj['hard_offset'])))
                    groups.append(('prefix_after512','yes' if obj['hard_offset']>=512 else 'no'))
                for level,subgroup in groups:
                    stats[(a,b,metric,level,subgroup)].append(math.exp(statistics.mean(math.log(v) for v in values)))
        lines=['# Test 90 — held-out targeted native validation (2h)', '',
          'Predeclared hypotheses from Test 89. New JSON seeds, no reruns of the original JSON.',
          'Five separately compiled native RISC-V v5.0.3 backends, including official VLS256.',
          'All reported ratios are matched within the same JSON and trial; each JSON counts once.',
          'Primary protocols require at least TWO independent subprocess trials per JSON to count.',
          'All primary scenarios are scheduled for THREE trials before secondary coverage.',
          'Stage1 and Stage2 measured directly, not inferred from public DOM.',
          'Single host and compiler; intervals below are naive case-resampling estimates,',
          'NOT a performance guarantee, hardware generalization, or corrected multiple-testing inference.',
          '',f'Observations: {len(self.rows)}; primary paired case-metric clusters: {complete}.',
          f'Independent holdout JSON generated: {len(getattr(self,"corpi_info",{}))}.',
          '', '## Precommitted questions',
          '- H1: quantify A1/A0 overhead near 512B, not a backend switch.',
          '- H2: is the 4095 -> 4096B discontinuity of A1/A0 and A2/A0 reproducible?',
          '- H3: when does sparse8 outperform A2 on mixed JSON?',
          '- H4: does moving difficulty after byte 512 change A2 against A0/sparse8?',
          '- H5: are A2/A0 differences mainly in Stage1, not Stage2?',
          '', '## Primary per-corpus geometric mean, with 90% case-bootstrap interval', '',
          '| Numerator / denominator | Metric | Design | Subgroup | JSON n | Geo-mean | 90% case CI |',
          '|---|---|---|---|---:|---:|---|']
        import random
        for key,vals in sorted(stats.items()):
            a,b,metric,level,subgroup=key
            if (a,b) not in (('A1_size_gate','A0_E14_original'),
                ('A2_quick_dispatch','A0_E14_original'),
                ('A2_quick_dispatch','sparse8_escape8_reference'),
                ('A2_quick_dispatch','upstream_vls256')):continue
            if level=='gate512' and metric!='dom_ratio':continue
            if level=='gate4096' and metric!='dom_ratio':continue
            if len(vals)<2:continue
            logs=[math.log(v) for v in vals]
            gm=math.exp(statistics.mean(logs))
            # Case bootstrap captures between-JSON variability, not shared-host systematic error.
            seed=int(hashlib.sha256(str(key).encode()).hexdigest()[:10],16)
            rng=random.Random(seed)
            draws=[]
            for _ in range(400):
                draws.append(math.exp(sum(logs[rng.randrange(len(logs))] for j in logs)/len(logs)))
            draws.sort()
            lo,hi=draws[int(.05*len(draws))],draws[int(.95*len(draws))-1]
            lines.append(f'| {a} / {b} | {metric} | {level} | {subgroup} | {len(vals)} | {gm:.3f}x | {lo:.3f}–{hi:.3f}x |')
        lines+=['','## Interpretation restrictions','',
          'Do NOT treat a narrow CI on one machine as independent-machine replication.',
          '512B is a classifier INSPECTION WINDOW for large JSON, NOT the dispatch gate (4096B).',
      'Iterations change between 512B and 513B; benchmark iteration count is a possible confound.',
      'The 512- and 4096-byte families are selected due to Test89, so confirmatory',
          'language applies only to this held-out corpus and prespecified contrasts.',
          'All per-trial rows and exact content SHA256 values are archived; inconclusive n is not hidden.',
          'The stop_reason and partial primary-round coverage must be checked before claiming a result.']
        atomic_text(self.root/'VALIDATION_2H.md','\n'.join(lines)+'\n')

    def snapshot(self):
        temp=self.root/'snapshot.zip.tmp';target=self.root/'snapshot.zip'
        manifest={'schema':1,'files':[]}
        with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for name in RUN_FILES:
                p=self.root/name
                if p.is_file():
                    blob=p.read_bytes();manifest['files'].append({'name':name,'bytes':len(blob),
                       'sha256':hashlib.sha256(blob).hexdigest()})
                    z.writestr(name,blob)
            z.writestr('MANIFEST.json',json.dumps(manifest,sort_keys=True))
        if temp.stat().st_size>SNAPSHOT_LIMIT:
            temp.unlink();raise Safety('snapshot > 12 MiB')
        os.replace(temp,target)
        atomic_text(self.root/'snapshot.sha256',hashlib.sha256(target.read_bytes()).hexdigest()+'\n')
    def failure(self,step,tag,detail):
        self.failures.append({'time':now(),'step':step,'candidate':tag,'error':str(detail)[-4800:]})
        self.checkpoint(force=True)
    def preflight(self):
        mandatory=['src/simdjson.cpp','src/rvv/stage1.h','src/rvv/engines/engine_plan.h',
                   'src/rvv/engines/structural_writers.h','src/rvv/engines/stage2_bridge.h',
                   'scripts/rvv/engines/experiments.json','scripts/rvv/perf/bench_native.py',
                   'include/simdjson/simdjson_version.h']
        absent=[n for n in mandatory if not (self.source/n).is_file()]
        if absent:raise RuntimeError('Missing Engine Library files: '+', '.join(absent))
        version=(self.source/'include/simdjson/simdjson_version.h').read_text(encoding='utf8')
        if not re.search(r'^#define SIMDJSON_VERSION\s+"5\.0\.3"',version,re.M):
            raise RuntimeError('Source is not simdjson v5.0.3')
        header=(self.source/'src/rvv/engines/engine_plan.h').read_text(encoding='utf8')
        for marker in ('SIMDJSON_RVV_ADAPTIVE_V2_LEVEL',
                       'SIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES',
                       'SIMDJSON_RVV_ADAPTIVE_V2_QUICK_BYTES'):
            if marker not in header:raise RuntimeError('Missing Adaptive Dispatch v2 marker: '+marker)
        if subprocess.check_output(['uname','-m'],text=True).strip()!='riscv64':
            raise RuntimeError('Native RISC-V required')
        if not shutil.which('g++') or not shutil.which('taskset'):
            raise RuntimeError('g++ or taskset missing')
        self.meta['compiler_version']=subprocess.check_output(['g++','--version'],text=True).splitlines()[0]
        # Preserve the original 30m campaign's authoritative native VLEN check.
        from argparse import Namespace
        module=importlib.util.spec_from_file_location('rvv_native_bench',
                    self.source/'scripts/rvv/perf/bench_native.py')
        bn=importlib.util.module_from_spec(module)
        module.loader.exec_module(bn)
        bn.REPO_ROOT=self.source
        with contextlib.redirect_stdout(io.StringIO()):
            hw=bn.preflight(Namespace(compiler='gcc',allow_emulation=False,core=self.core),self.root)
        if hw.get('hardware_vlen_bits')!=256:
            raise RuntimeError('Native RVV VLEN must be 256; found '+str(hw.get('hardware_vlen_bits')))
        self.status['vlen_bits']=256
        self.meta['hardware']=hw
        self.bn=bn
        self.meta['source_git_sha']=(self.source/'rvvlab-source-manifest.json').read_text(encoding='utf8')[:3000] if (self.source/'rvvlab-source-manifest.json').is_file() else 'no provenance manifest'
        probe_cpp=self.root/'split_stage_bench.cpp';atomic_text(probe_cpp,BENCH_CPP)
        self.check(building=True)
        self.checkpoint('build',force=True)
    def source_upstream(self):
        self.check(building=True)
        dest=self.root/'upstream-official-v5.0.3'
        if dest.is_dir() and (dest/'.git').is_dir():
            actual=subprocess.check_output(['git','-C',str(dest),'rev-parse','HEAD'],text=True).strip()
            if actual==UPSTREAM_SHA:return dest
        log=self.root/'upstream_clone.log'
        if not dest.exists():
            rc,_=run_logged(['git','clone','--depth','1','--branch','v5.0.3',
                 '--single-branch',UPSTREAM_URL,str(dest)],log,cwd=self.root,
                 deadline=self.deadline_mono,timeout=180,stopfile=self.stopfile,free_floor=FREE_FLOOR)
            if rc:raise RuntimeError('Official reference clone failed: '+read_tail(log,2500))
        actual=subprocess.check_output(['git','-C',str(dest),'rev-parse','HEAD'],text=True).strip()
        if actual!=UPSTREAM_SHA:
            raise RuntimeError(f'Official v5.0.3 SHA mismatch: {actual}; expected {UPSTREAM_SHA}')
        return dest
    def flags(self,kind,defines):
        base=['-O3','-DNDEBUG','-g0','-pthread','-std=c++17','-mabi=lp64d',
              '-DSIMDJSON_IMPLEMENTATION_FALLBACK=1']
        if kind=='vla':
            base += ['-march=rv64gcv','-DSIMDJSON_IMPLEMENTATION_RVV=1',
                     '-DSIMDJSON_IMPLEMENTATION_RVV_VLS=0']
        else:
            base += ['-march=rv64gcv_zvl256b','-mrvv-vector-bits=zvl',
                     '-DSIMDJSON_IMPLEMENTATION_RVV_VLS=1']
        return base+[f'-D{k}={v}' for k,v in sorted(defines.items())]
    def build(self,spec,upstream):
        tag,defines,engine,kind=spec
        self.check(building=True)
        self.status['current_candidate']=tag
        self.checkpoint('build')
        binfolder=self.root/'bin';binfolder.mkdir(exist_ok=True)
        binary=binfolder/('parse-'+tag)
        if binary.is_file():self.binaries[tag]=(str(binary),engine,defines);return True
        src=self.source if kind=='vla' else upstream
        if not src:raise RuntimeError('Missing upstream for pinned VLS reference')
        scratch=self.root/'scratch_build';scratch.mkdir(exist_ok=True)
        obj=scratch/'simdjson.o';exe=scratch/'parse'
        flags=['g++',*self.flags(kind,defines),'-I'+str(src/'include'),'-I'+str(src/'src')]
        start=time.monotonic()
        try:
            for step,cmd,max_time in (
                ('compile',[*flags,'-c',str(src/'src/simdjson.cpp'),'-o',str(obj)],340),
                ('link',[*flags,str(self.root/'split_stage_bench.cpp'),str(obj),'-o',str(exe)],100)):
                self.check(building=True)
                log=self.root/f'{step}_{tag}.log'
                try:rc,_=run_logged(cmd,log,cwd=self.root,deadline=self.deadline_mono,
                    timeout=max_time,stopfile=self.stopfile,free_floor=FREE_FLOOR)
                except TimedOut as exc:
                    self.record_build_error(step,tag,log,124,str(exc));return False
                if rc:self.record_build_error(step,tag,log,rc,step+' error');return False
            log=self.root/f'correctness_{tag}.log'
            self.check()
            rc,_=run_logged(['taskset','-c',str(self.core),str(exe),engine,'validate',
                              str(self.root/'valid.jsonl'),str(self.root/'invalid.jsonl')],
                log,cwd=self.root,deadline=self.deadline_mono,timeout=90,stopfile=self.stopfile)
            if rc or f'RVV_VALIDATION_OK backend={engine}' not in read_tail(log,2500):
                self.record_build_error('correctness',tag,log,rc,'JSONL validation failed');return False
            # Mandatory native split smoke. A prior 8h run passed JSON correctness
            # but failed *every measurement* because Python requested 2048/1024
            # iterations when the C++ benchmark only accepted <= 1000.
            for smoke_label,smoke_path,smoke_iters in self.smoke_specs:
                log=self.root/f'smoke_{tag}_{smoke_label}.log'
                if not 1<=smoke_iters<=BENCH_MAX_ITERATIONS:
                    raise RuntimeError('Invalid smoke iteration schedule')
                rc,_=run_logged(['taskset','-c',str(self.core),str(exe),engine,'split',
                     str(smoke_path),str(smoke_iters)],log,cwd=self.root,
                     deadline=self.deadline_mono,timeout=45,stopfile=self.stopfile)
                if rc:
                    self.record_build_error('native_smoke',tag,log,rc,
                        f'native {smoke_label} split failed; do not start exploration')
                    return False
                try:
                    *rates,actual,size=parse_split_output(read_tail(log,3000))
                    if actual!=smoke_iters or size!=smoke_path.stat().st_size:
                        raise ValueError('Native smoke echo mismatch')
                except ValueError as exc:
                    self.record_build_error('native_smoke',tag,log,99,str(exc))
                    return False
                self.meta['runtime_probes'].append({'tag':tag,'smoke':smoke_label,
                    'bytes':size,'iterations':actual,'result':'PASS'})
            shutil.copy2(exe,binary);binary.chmod(0o755)
            self.binaries[tag]=(str(binary),engine,defines)
            self.meta['runtime_probes'].append({'tag':tag,'result':'PASS',
                'selftest':self.meta['validation_cases'],'backend':engine})
            self.meta['builds'].append({'tag':tag,'result':'PASS','seconds':round(time.monotonic()-start,2)})
            self.checkpoint(force=True)
            return True
        finally:shutil.rmtree(scratch,ignore_errors=True)
    def record_build_error(self,step,tag,log,rc,why):
        tail=read_tail(log)
        diagnostics={'tag':tag,'step':step,'rc':rc,'why':why,'errors':extract_errors(tail),
                     'log_file':log.name,'tail':tail[-4000:]}
        self.meta['compiler_diagnostics'].append(diagnostics)
        self.meta['builds'].append({'tag':tag,'result':'FAIL','step':step,'returncode':rc})
        self.failure(step,tag,'\n'.join(diagnostics['errors']) or tail[-2000:])
    def make_validation_cases(self):
        import random
        rng=random.Random(20261010)
        val=[None,True,False,[],{},0,-1,1e-300,1e300,'',
             'hello','héllo 😺 世界', '\u0000\n\t\b', '\\',
             {'key':'😊','arr':[1,2,3], 'escaped':'a\"b\\c'},
             [True,False,None], {'emoji':'😀','text':'áçœ漢字'},
             {str(i):i for i in range(30)},
             {'nested':{'level':{'other':{'k':1}}}}]
        alphabet=['héllo','😺','世界','escape\n','ASCII','\u2028','\\','"','']
        for i in range(150):
            val.append({'round':i, 'strings':[rng.choice(alphabet) for _ in range(i%11)],
              'integers':[rng.randint(-2**53,2**53) for _ in range(i%7)],
              'object':{'ok':bool(i%2),'empty':[], 'nil':None},
              'float':round(rng.uniform(-1e8,1e8),4)})
        bad=['{', '[1,]', '{"a":}', '{"a":1,}', '[1,,2]',
             '{"x":01}', '{"x":+1}', '{"x":1e}', '{"x":1}junk',
             '[NaN]', '{"x":1 "y":2}', '"unterminated',
             '[true false]', '{"a":undefined}', '{"a":1, "b"}',
             '[}', '{"x":.5}', '{"x":1.}', '[-]', 'tru',
             '{"x":--1}', '{"x":2e+}', '{"x":+0}', '[1,2,3,]']
        valid_path=self.root/'valid.jsonl';invalid_path=self.root/'invalid.jsonl'
        atomic_text(valid_path, ''.join(json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n' for x in val))
        atomic_text(invalid_path, ''.join(x+'\n' for x in bad))
        self.meta['validation_cases']={'valid':len(val),'invalid':len(bad),
            'method':'seeded Python json.dumps reference plus 24 deliberately malformed JSON documents'}
        self.smoke_specs=[]
        for label,kind,n,count in (
            ('small_256_maxiters','ascii',256,BENCH_MAX_ITERATIONS),
            ('boundary_4095','escaped',4095,32),
            ('boundary_4096','utf8',4096,32),
            ('boundary_4097','numbers',4097,32)):
            doc=exact_gate_bytes(kind,n)
            json.loads(doc)
            if len(doc)!=n:raise RuntimeError('Smoke size invariant failed')
            p=self.root/('smoke_'+label+'.json');p.write_bytes(doc)
            self.smoke_specs.append((label,p,count))
        self.meta['native_smoke_spec']=[{'label':x,'bytes':p.stat().st_size,'iterations':n}
                                          for x,p,n in self.smoke_specs]
        self.checkpoint(force=True)

    def make_corpus(self):
        """Holdout Test 90 frozen workload; no performance-dependent selection."""
        self.check()
        cases=holdout_specs()
        self.meta['exploration_design']={
          'seed':EXPLORATION_SEED,'precommitted':len(cases),
          'design_counts':{d:sum(x['design']==d for x in cases)
                           for d in ('gate512','gate4096','deceptive_prefix','sparse_challenge')},
          'hypotheses':[
           'H1: quantify A1/A0 overhead for small inputs around 512B; 512B is NOT the dispatch threshold',
           'H2: A1/A0 and A2/A0 change around exact 4095/4096/4097-byte dispatch threshold',
           'H3: A2/sparse8 competition in dense, numbers, UTF8 and escaping mixes',
           'H4: moving non-ASCII/escape/structural payload after first 512B weakens quick classification only on inputs >=4096B',
           'H5: A2/A0 changes mainly in true Stage1 rather than Stage2'],
          'primary_repeats':3, 'measurement_design':'new test90 JSON, paired same-trial five-mode measurements, randomized/reversed order',
          'no_online_tuning':True,'one_native_host_not_portable':True}
        directory=self.root/'holdout90_corpus';directory.mkdir(exist_ok=True)
        result=[];manifest=[];seen={}
        for i,obj in enumerate(cases):
            self.check()
            kind='+'.join(obj['kinds']);target=obj['target'];place=obj['placement']
            label=f'{i:04d}_{obj["design"]}_{kind}_{place}_{target}_{obj["seed"]}'
            path=directory/(label+'.json')
            if obj['design'].startswith('gate'):
                data=make_holdout_exact(obj['kinds'][0],target,obj['seed'])
            elif obj['design']=='deceptive_prefix':
                data=make_holdout_deceptive(obj['kinds'][0],target,obj['offset'],obj['seed'])
            else:
                data=make_combo_bytes(obj['kinds'],target,place,seed=obj['seed'])
            json.loads(data)
            digest=hashlib.sha256(data).hexdigest()
            if digest in seen:raise RuntimeError('Holdout duplicate SHA256: '+str(seen[digest])+', '+str(path))
            seen[digest]=path.name
            path.write_bytes(data)
            features=sampling_signals(data)
            spread=sum(max(features[v][attr] for v in ('head','middle','tail'))-
                       min(features[v][attr] for v in ('head','middle','tail'))
                       for attr in ('slash_density','highbyte_density','struct_density'))
            item={'id':path.parent.name+'/'+path.name,'design':obj['design'],
                  'kind':kind,'kinds':list(obj['kinds']),'distribution':place,
                  'size_target':target,'bytes':len(data),'exact_target':obj['design']!='sparse_challenge',
                  'hard_offset':obj.get('offset'),'seed':obj['seed'],
                  'sha256':digest,'sample_spread_proxy':round(spread,5),'sample_windows':features}
            manifest.append(item);result.append(path)
        self.corpi_info={v['id']:v for v in manifest}
        self.meta['corpus_count']=len(manifest)
        self.meta['corpus_files']=[{k:r[k] for k in ('id','bytes','sha256','design','kind','distribution')}
             for r in manifest]
        atomic_json(self.root/'corpus_manifest.json',{'schema':1,'protocol':'test90-independent-holdout-2h',
                     'seed':EXPLORATION_SEED,'scenarios':manifest})
        self.checkpoint(force=True)
        return result

    def measure(self,phase,tag,path,iters,trial):
        self.check()
        if not isinstance(iters,int) or not 1 <= iters <= BENCH_MAX_ITERATIONS:
            raise RuntimeError(f'Refuse unsafe iteration request: {iters}')
        binary,engine,defines=self.binaries[tag]
        cid=path.parent.name+'/'+path.name+'@'+str(path.stat().st_size)
        log=self.root/'latest_bench.log'
        rc,_=run_logged(['taskset','-c',str(self.core),binary,engine,'split',str(path),str(iters)],
            log,cwd=self.root,deadline=self.deadline_mono,timeout=90,stopfile=self.stopfile)
        if rc:raise RuntimeError(f'split benchmark rc={rc}: '+read_tail(log,1600))
        dom,stage1,stage2,tdom,tstage1,tstage2,actual,size=parse_split_output(read_tail(log,3000))
        if actual!=iters or size!=path.stat().st_size:raise RuntimeError('Corpus/iteration mismatch')
        self.rows.append({'timestamp':now(),'phase':phase,'variant':tag,
           'defines':json.dumps(defines,sort_keys=True,separators=(',',':')),
           'corpus':cid,'bytes':size,'parse_iterations':iters,'trial':trial,
           'dom_all_gbps':dom,'stage1_gbps':stage1,'stage2_gbps':stage2,
           'all_cpb':'','stage1_cpb':'','stage2_cpb':'',
           'elapsed_seconds':tdom,'method':'native_DOM_and_direct_stage1_stage2_median3_gcc_O3',
           'scenario':self.corpi_info[path.parent.name+'/'+path.name]['kind'],
           'distribution':self.corpi_info[path.parent.name+'/'+path.name]['distribution'],
           'size_target':self.corpi_info[path.parent.name+'/'+path.name]['size_target'],
           'sampling_bias':self.corpi_info[path.parent.name+'/'+path.name]['sample_spread_proxy']})
        path_csv=self.root/'map.csv'
        with path_csv.open('a',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=RESULT_FIELDS)
            if f.tell()==0:w.writeheader()
            w.writerow(self.rows[-1]);f.flush();os.fsync(f.fileno())
        self.checkpoint(phase)
    def abandon(self,tag,why):
        self.abandoned[tag]=why;self.status['abandoned_points']=self.abandoned
        self.failure('abandoned',tag,why)
    def explore(self):
        """Precommitted 3x repeated priority wave BEFORE any secondary exploration."""
        import random
        from collections import defaultdict
        tags=[tag for tag,*_ in catalog() if tag in self.binaries]
        expected=[tag for tag,*_ in catalog()]
        if set(tags)!=set(expected):raise RuntimeError('All five benchmark modes required: '+str(tags))
        group=defaultdict(list)
        for path in self.corpi:group[self.corpi_info[path.parent.name+'/'+path.name]['design']].append(path)
        # Primary population: fixed balanced seeded holdout subsample, not chosen by results.
        caps={'gate512':24,'gate4096':24,'deceptive_prefix':20,'sparse_challenge':20}
        selection={}
        for design,n in caps.items():
            slots=defaultdict(list)
            for p in group[design]:
                obj=self.corpi_info[p.parent.name+'/'+p.name]
                key=(obj['size_target'] if design.startswith('gate') else
                     obj.get('hard_offset') if design=='deceptive_prefix' else obj['distribution'])
                slots[key].append(p)
            rng=random.Random(EXPLORATION_SEED+sum(map(ord,design)))
            for candidates in slots.values():rng.shuffle(candidates)
            ordered=[];keys=sorted(slots,key=str)
            while any(slots.values()):
                for key in keys:
                    if slots[key]:ordered.append(slots[key].pop(0))
            selection[design]=ordered[:n]
        primary=[]
        while any(selection.values()):
            for design in caps:
                if selection[design]:primary.append(selection[design].pop(0))
        self.meta['primary_case_ids']=[p.name for p in primary]
        self.meta['primary_cases']=len(primary)
        self.status['primary_cases_planned']=len(primary)
        primary_set=set(primary)
        secondary=[p for p in self.corpi if p not in primary_set]
        self.meta['ordering']='Frozen balanced primary (3 fresh-process repeats before secondary); alternating randomized native engines, fixed seed.'
        def case(phase,path,trial,idx):
            self.check()
            size=path.stat().st_size
            iterations=iterations_for_bytes(size)
            if not 1<=iterations<=1000:raise RuntimeError('Invalid native iteration schedule')
            order=list(tags)
            random.Random(EXPLORATION_SEED+trial*7919+idx*131).shuffle(order)
            if trial%2:order.reverse()
            self.status['last_measurement_order']=order
            for tag in order:
                self.status['current_candidate']=tag
                # Never selectively abandon a slower competing mode in a confirmatory study.
                self.measure(phase,tag,path,iterations,trial)
        for trial in range(3):
            self.status['experiment_phase']='confirm_primary'
            self.status['primary_round']=trial+1
            order=primary.copy()
            random.Random(EXPLORATION_SEED+trial*3571).shuffle(order)
            for i,path in enumerate(order):case('confirm_primary',path,trial,i)
            self.status['fixed_round_completed']=trial+1
            self.checkpoint('confirm_primary',force=True)
        for trial in range(3,100):
            self.status['experiment_phase']='confirm_secondary'
            order=secondary.copy()+primary.copy()
            random.Random(EXPLORATION_SEED+trial*1433).shuffle(order)
            for i,path in enumerate(order):case('confirm_secondary',path,trial,i)
            self.status['fixed_round_completed']=trial+1
            self.checkpoint('confirm_secondary',force=True)

    def execute(self):
        import fcntl
        lock=self.root.parent/'.night_runner_global.lock'
        with lock.open('w') as f:
            try:fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError('Another Night Runner is active')
            f.write(str(os.getpid()));f.flush()
            try:
                self.checkpoint('preflight',force=True)
                self.preflight()
                # Pin orchestration to a different allowed CPU than measurements.
                if hasattr(os,'sched_setaffinity'):
                    other=next((c for c in sorted(os.sched_getaffinity(0)) if c!=self.core),None)
                    if other is not None:
                        os.sched_setaffinity(0,{other})
                        self.status['orchestration_cpu']=other
                self.make_validation_cases()
                self.status['current_candidate']='A0_E14_original'
                if not self.build(catalog()[1],None):
                    raise RuntimeError('A0 E14 baseline failed; inspect metadata.json compiler_diagnostics')
                self.check()
                upstream=self.source_upstream()
                if not self.build(catalog()[0],upstream):
                    raise RuntimeError('Official upstream VLS256 reference failed; no valid comparison')
                for item in catalog():
                    if item[0] in self.binaries:continue
                    self.check(building=True)
                    try:self.build(item,upstream)
                    except (Stopped,Safety):raise
                    except Exception as exc:
                        self.meta['builds'].append({'tag':item[0],'result':'FAIL','step':'unexpected',
                                                    'error':str(exc)[-1200:]})
                        self.failure('unexpected_build',item[0],exc)
                if set(self.binaries)!=set(p[0] for p in catalog()):
                    raise RuntimeError('Test90 requires all five passing native split smokes')
                self.meta['coverage']={'passed':list(self.binaries),'expected':len(catalog())}
                self.corpi=self.make_corpus()
                self.explore()
                self.status['state']='completed'
            except Stopped as exc:
                self.status['state']='stopped';self.status['stop_reason']=str(exc)
            except Safety as exc:
                self.status['state']='safety_stop';self.status['stop_reason']=str(exc)
            except Exception as exc:
                self.status['state']='failed';self.status['stop_reason']=str(exc)[-1800:]
                self.failures.append({'time':now(),'step':'fatal','candidate':self.status['current_candidate'],
                                      'error':str(exc)[-4600:]})
            finally:self.checkpoint(force=True)


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True);p.add_argument('--workdir',required=True)
    p.add_argument('--hours',type=float,default=2.0)
    p.add_argument('--jobs',type=int,default=2);p.add_argument('--core',type=int,default=0)
    args=p.parse_args(argv)
    if not (0<args.hours<=MAX_HOURS):p.error('hours must be in (0,1.0]')
    if args.jobs not in (1,2):p.error('jobs must be 1 or 2')
    campaign=Campaign(args.source,args.workdir,args.hours,args.jobs,args.core)
    campaign.execute()
    print(json.dumps({'state':campaign.status['state'],'observations':len(campaign.rows),
      'reason':campaign.status['stop_reason']},ensure_ascii=False))
    return 0 if campaign.status['state'] in ('completed','stopped') else 1

if __name__=='__main__':raise SystemExit(main())
