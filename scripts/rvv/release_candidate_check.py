#!/usr/bin/env python3
"""Reproducible host smoke tests for VectorPath release-candidate sources.

The host tests are NOT a replacement for the required EPCC/Cloud-V RVV tests.
Compiles both normal src/include and regenerated singleheader in three modes.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, shutil, subprocess, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
MODES = {'stable': [], 'simple': ['-DSIMDJSON_VECTORPATH_STAGE2_SIMPLE_RUN=1'],
         'nl4': ['-DSIMDJSON_VECTORPATH_STAGE2_SIMPLE_RUN=1', '-DSIMDJSON_VECTORPATH_STAGE2_NL4=1']}

def run(cmd, log, timeout=240):
    with open(log, 'w', encoding='utf-8') as stream:
        proc=subprocess.run([str(x) for x in cmd], stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
    if proc.returncode:
        raise RuntimeError('Command failed (' + str(proc.returncode) + '): ' + str(cmd[:3]) + '\n' + pathlib.Path(log).read_text(errors='replace')[-1800:])

def inputs(folder):
    samples = [
        ({'x':'hello','i':123,'bool':True}, True),
        ({'x': '\n' * 1700, 'z': {'deep':['a']*30}}, True),
        ({'x': 'A' * 600 + '\n' * 3000 + '\\' * 400}, True),
        ({'x': 'é 😁 𝄞 \u0000 你好' * 100, 'numbers':[1,-2,0.1,2**31]}, True),
        ({'x':'\t\n\r\b\f"\\/'*1500}, True),
        ({'x': 'abc' * 6000}, True),
        ([{'a': '"'*200, 'b': '\\'*200} for _ in range(30)],True),
    ]
    paths=[]
    for i,(v,expect) in enumerate(samples):
        path=folder/f'generated_{i}.json'
        path.write_text(json.dumps(v,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        paths.append((path,expect))
    for i, data in enumerate([b'{"bad":}', b'{"bad":"\\q"}', b'{"bad": [1,2,}', b'{"bad": "\\uD800"}',b'{"bad": "\xff"}']):
        p=folder/f'invalid_{i}.json';p.write_bytes(data);paths.append((p,False))
    for fn in ('twitter.json','canada.json','twitterescaped.json'):
        p=ROOT/'jsonexamples'/fn
        if p.is_file():paths.append((p,True))
    return paths

def check_profile(cxx, out):
    src=ROOT/'tests/rvv/release_profile_tests.cpp'
    includes=['-I'+str(ROOT/'src')]
    for mode,extra in [('stable',['-DVECTORPATH_REQUIRE_STABLE=1']),
                        ('A0',['-DSIMDJSON_RVV_ADAPTIVE_V2_LEVEL=0', '-DSIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES=4096',
                               '-DSIMDJSON_RVV_ENABLE_PACKED_CONTROL=1'])]:
        exe=out/('profile_'+mode)
        run([cxx,'-O2','-std=c++17',*includes,*extra,src,'-o',exe],out/f'{mode}-compile.log')
        run([exe],out/f'{mode}-run.log',timeout=20)

def build(cxx, out, mode, merged):
    exe=out/('dom_'+mode+('_single' if merged else '_source'))
    inc=ROOT/'singleheader' if merged else ROOT/'include'
    src=ROOT/'singleheader/simdjson.cpp' if merged else ROOT/'src/simdjson.cpp'
    flags=['-std=c++17','-O0','-DNDEBUG','-pthread','-DSIMDJSON_IMPLEMENTATION_FALLBACK=1',
           '-DSIMDJSON_IMPLEMENTATION_RVV=0','-DSIMDJSON_IMPLEMENTATION_RVV_VLS=0',*MODES[mode]]
    # Distinguish include modes: the test harness sees the same public API.
    obj=out/('lib_'+mode+('_single' if merged else '_source')+'.o')
    run([cxx,*flags,'-I'+str(inc)]+([] if merged else ['-I'+str(ROOT/'src')])+['-c',src,'-o',obj],out/(obj.stem+'.log'),timeout=450)
    run([cxx,*flags,'-I'+str(inc),ROOT/'tests/rvv/release_dom_check.cpp',obj,'-o',exe],out/('link_'+exe.name+'.log'))
    return exe

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--compiler',default='g++')
    ap.add_argument('--skip-singleheader',action='store_true')
    ap.add_argument('--workdir',default=None)
    args=ap.parse_args()
    cxx=shutil.which(args.compiler)
    if not cxx:ap.error('Missing compiler: '+args.compiler)
    ctx = tempfile.TemporaryDirectory(prefix='vectorpath-release-check-') if not args.workdir else None
    folder=pathlib.Path(args.workdir or ctx.name).resolve();folder.mkdir(exist_ok=True,parents=True)
    try:
        check_profile(cxx,folder)
        docs=inputs(folder)
        previous={}
        for merged in ([False] if args.skip_singleheader else [False,True]):
            for mode in MODES:
                exe=build(cxx,folder,mode,merged)
                output=[]
                for path,expect in docs:
                    r=subprocess.run([str(exe),str(path)],capture_output=True,text=True,timeout=35)
                    result=r.stdout.strip()
                    if r.returncode or (expect and not result.startswith('ACCEPT ')) or (not expect and result!='REJECT'):
                        raise RuntimeError(f'Wrong result: {mode} merged={merged} {path} {r.returncode} {result} {r.stderr[:200]}')
                    output.append(result)
                key='singleheader' if merged else 'source'
                previous.setdefault(key,{})[mode]=output
                if output != previous[key]['stable']:
                    raise RuntimeError('DOM mismatch against stable in '+key+' mode='+mode)
                if merged and output != previous['source'][mode]:
                    raise RuntimeError('Singleheader/source DOM mismatch in mode '+mode)
                print('PASS',key,mode,len(docs),'documents')
        save={'compiler':cxx, 'tested_cases':len(docs), 'variants':list(MODES), 'singleheader_checked':not args.skip_singleheader,
              'rvv_native_tested':False, 'note':'Host fallback smoke only; native RVV validation still required.'}
        (folder/'release_smoke_results.json').write_text(json.dumps(save,indent=2)+'\n')
        print('PASS release candidate host smoke',len(docs), 'cases per variant; RVV native not tested')
    finally:
        if ctx:ctx.cleanup()
if __name__=='__main__':main()
