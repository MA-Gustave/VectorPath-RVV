"""Test 91 effective compositions, seeded JSON generator and paired search policy.
Standard library only; safe to import on Windows without starting any campaign.
"""
import hashlib, itertools, json, math, random, statistics
from collections import defaultdict

SEED=2026101291
KINDS=('ascii','long_strings','many_keys','dense','integers','floats','escaped','unicode_escape','utf8','nested','boolnull','whitespace')
SIZES=(256,4096,65536,1048576,8388608,67108864)
LAYOUTS=('interleaved','regions4096','regions16384','regions65536','regions262144','drift')
# bank = sparse index threshold, packed index threshold, sparse escape threshold,
# bitfield: packed writer=1, escape=2, quote=4, shift=8, interior string=16.
BALANCED=(8,64,8,16)

def normalize(c):
    c=dict(c);c['banks']=[list(p) for p in c['banks']]
    for p in c['banks']:
        if not p[3]&1:p[1]=64 # inactive threshold must not create fake diversity
    if c['policy']==0:
        c.update(prefix=512,gate=4096,region=16384,hysteresis=1,vl_cap=0,unroll=1,banks=[list(BALANCED)]*4)
    elif c['policy']==1:
        c.update(prefix=512,gate=0,region=16384,hysteresis=1,banks=[c['banks'][0]]*4)
    elif c['policy'] in (2,4):c.update(region=16384,hysteresis=1)
    elif c['policy']==3:c['prefix']=512
    return {k:c[k] for k in ('policy','prefix','gate','region','hysteresis','vl_cap','unroll','banks')}

def wire(c):
    c=normalize(c)
    return ','.join(map(str,[c[k] for k in ('policy','prefix','gate','region','hysteresis','vl_cap','unroll')]+[v for p in c['banks'] for v in p]))

def candidate(c,origin='precommitted'):
    c=normalize(c);s=wire(c)
    return dict(id='P'+hashlib.sha256(s.encode()).hexdigest()[:12],settings=c,wire=s,origin=origin)

def catalog():
    rng=random.Random(SEED);result=[];seen=set()
    def add(c):
        obj=candidate(c)
        if obj['wire'] not in seen:seen.add(obj['wire']);result.append(obj)
    default=dict(policy=1,prefix=512,gate=0,region=16384,hysteresis=1,vl_cap=0,unroll=1,banks=[BALANCED]*4)
    add({**default,'policy':0}) # quantify overhead of the experimental binary
    add(default) # classifier-free balanced for ALL sizes
    pool=list(itertools.product((0,4,8,16),(0,2,8,16),(0,16,17,18,20,24,31),(0,32,64),(1,2,4)))
    rng.shuffle(pool)
    for sw,se,flags,cap,unroll in pool:
        add({**default,'banks':[(sw,32 if flags&1 else 64,se,flags)]*4,'vl_cap':cap,'unroll':unroll})
        if len(result)==98:break
    for policy in (2,3,4):
        start=len(result)
        while len(result)<start+48:
            banks=[(rng.choice((0,4,8,16)),rng.choice((16,32,64)),rng.choice((0,2,8,16)),rng.choice((16,17,18,20,24,31))) for _ in range(4)]
            add({**default,'policy':policy,'banks':banks,'prefix':rng.choice((128,512,2048)),
                 'gate':rng.choice((0,4096)),'region':rng.choice((4096,16384,65536,262144)),
                 'hysteresis':rng.choice((1,2)),'vl_cap':rng.choice((0,32,64)),'unroll':rng.choice((1,2,4))})
    return result

def corpus_specs(max_mib=64):
    """2,304 designs at 64 MiB: 144 pure + 2,160 mixed, lazy materialization."""
    result=[]
    def add(kinds,size,layout,weights,serial):
        if size>max_mib*1048576:return
        result.append(dict(id=f'C{len(result):04d}',kinds=list(kinds),target=size,layout=layout,
            weights=list(weights),seed=SEED+serial*104729,role='explore',family='+'.join(kinds)))
    serial=0
    for kind,size,rep in itertools.product(KINDS,SIZES,range(2)):
        add((kind,),size,'interleaved',(1,),serial);serial+=1
    # Each seed produces different mixtures of 2 to 5 real JSON families.
    rng=random.Random(SEED)
    for mixture in range(60):
        kinds=rng.sample(KINDS,2+mixture%4)
        weights=([1]*len(kinds) if mixture%3==0 else [9]+[1]*(len(kinds)-1) if mixture%3==1 else [1]*(len(kinds)-1)+[9])
        for size,layout in itertools.product(SIZES,LAYOUTS):
            add(kinds,size,layout,weights,serial);serial+=1
    return result

def atom(kind,i):
    if kind=='ascii':v={'id':i,'name':'alpha_beta_'+str(i),'ok':True}
    elif kind=='long_strings':v={'id':i,'text':('long_text_'+str(i)+'_')*80}
    elif kind=='many_keys':v={f'k{j}_{i%97}':i+j for j in range(24)}
    elif kind=='dense':v=[i,[0,1],{},[],True,False,None,{'x':[],'y':0}]
    elif kind=='integers':v=[i,-i,i%1000,0,2147483647,9007199254740991]
    elif kind=='floats':v=[i+.125,1.23456789e-12,-9.87654e20,.0000234,3.141592653589793]
    elif kind=='escaped':v={'id':i,'s':('path\\x\\y\nquoted"\t')*12}
    elif kind=='unicode_escape':v={'id':i,'s':'😺漢字é'*24}
    elif kind=='utf8':v={'id':i,'s':'中文 العربية हिन्दी 🐈 café '*16}
    elif kind=='nested':
        v={'id':i}
        for _ in range(8+i%16):v={'n':[v,True]}
    elif kind=='boolnull':v={'id':i,'v':[True,False,None]*20}
    elif kind=='whitespace':v={'id':i,'v':[i,True,None,{'x':i}]*4}
    else:raise ValueError(kind)
    return json.dumps(v,ensure_ascii=(kind=='unicode_escape'),allow_nan=False,
                      indent=2 if kind=='whitespace' else None,
                      separators=None if kind=='whitespace' else (',',':')).encode('utf8')

def generate(spec,path,check=lambda:None):
    """Stream valid atoms; no giant ASCII padding. Bounded memory, deterministic."""
    rng=random.Random(spec['seed']);kinds=spec['kinds'];weights=spec['weights']
    layout=spec['layout'];region=int(layout[7:]) if layout.startswith('regions') else 0
    # A bounded vocabulary avoids millions of json.dumps calls on huge inputs.
    vocab={k:[atom(k,spec['seed']+j) for j in range(16)] for k in kinds}
    # Every case includes its seed; repeated atom vocabulary is documented.
    header=('['+str(spec['seed'])).encode();digest=hashlib.sha256();n=0;counts=defaultdict(int)
    def emit(f,b):
        nonlocal n
        f.write(b);digest.update(b);n+=len(b)
    with open(path,'wb',buffering=1048576) as f:
        emit(f,header);i=0;next_check=1048576
        while n<spec['target']-1:
            if region:
                pos=(n//region)%sum(weights);total=0;kind=kinds[-1]
                for k,w in zip(kinds,weights):
                    total+=w
                    if pos<total:kind=k;break
            elif layout=='drift':
                pivot=min(len(kinds)-1,int(n*len(kinds)/spec['target']))
                kind=kinds[pivot] if rng.random()<.8 else rng.choices(kinds,weights)[0]
            else:kind=rng.choices(kinds,weights)[0]
            b=b','+vocab[kind][i%16];emit(f,b);counts[kind]+=len(b);i+=1
            if n>=next_check:check();next_check=n+1048576
        emit(f,b']')
    return dict(**spec,bytes=n,sha256=digest.hexdigest(),family_bytes=dict(counts),
                effective_families=sorted(counts),atoms=i)

def gm(values):return math.exp(statistics.mean(math.log(v) for v in values))

def matched_summary(rows):
    groups=defaultdict(dict)
    for r in rows:groups[r['group']][r['variant']]=r
    case=defaultdict(list)
    for g in groups.values():
        if 'A2' not in g or 'official' not in g:continue
        for name,r in g.items():
            if name in ('A2','official'):continue
            if r.get('role')=='holdout':continue
            case[(name,r['family'],r['corpus'])].append(float(r['dom_all_gbps'])/float(g['A2']['dom_all_gbps']))
    families=defaultdict(list)
    for (tag,family,cid),values in case.items():families[tag,family].append(gm(values))
    return [dict(variant=tag,family=family,cases=len(v),dom_vs_A2=gm(v)) for (tag,family),v in sorted(families.items())]

def proposals(points,summary,limit=24):
    """Compose family specialists; suggestions stay experimental, never production."""
    byid={p['id']:p for p in points};available=[r for r in summary if r['cases']>=2 and r['variant'] in byid and byid[r['variant']]['settings']['policy']==1]
    if len(available)<2:return []
    def best(kinds):
        subset=[r for r in available if any(k in r['family'].split('+') for k in kinds)] or available
        return sorted(subset,key=lambda r:r['dom_vs_A2'],reverse=True)[0]['variant']
    parents=[best(KINDS),best(('dense','many_keys')),best(('ascii','long_strings')),best(('escaped','unicode_escape','utf8'))]
    banks=[byid[p]['settings']['banks'][0] for p in parents]
    result=[]
    for region,hys,cap in itertools.product((4096,16384,65536,262144),(1,2),(0,32,64)):
        c=dict(policy=3,prefix=512,gate=4096,region=region,hysteresis=hys,vl_cap=cap,unroll=1,banks=banks)
        p=candidate(c,'family_specialists');p['parents']=parents;result.append(p)
    return result[:limit]
