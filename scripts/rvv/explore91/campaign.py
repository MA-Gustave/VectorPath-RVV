"""Native wide exploration, reused Lab lifecycle; no SSH or autostart on import."""
import contextlib,csv,hashlib,json,math,os,random,shutil,statistics,sys,time,zipfile
from pathlib import Path
from collections import defaultdict
import support90 as support
from design import SEED,KINDS,catalog,corpus_specs,generate,matched_summary,proposals,gm
from harness import source as harness_source

support.BENCH_CPP=harness_source(support.BENCH_CPP)
# Existing commands retain process-group termination, 200 MiB disk guard and deadlines.
BASE_RUN=support.run_logged
CONFIG=catalog()[0]['wire']
def run_logged(command,log_path,**kw):
    cmd=[str(x) for x in command]
    if any('/parse-' in x or x.endswith('/parse') for x in cmd):
        cmd=['env','RVV_EXPERIMENT_CONFIG='+CONFIG,*cmd]
    try:return BASE_RUN(cmd,log_path,**kw)
    except support.Deadline:raise support.Deadline('Test91 wall-time budget reached')
support.run_logged=run_logged
FIELDS=('timestamp','group','phase','role','variant','corpus','family','layout','bytes','iterations','trial','dom_all_gbps','stage1_gbps','stage2_gbps','seconds')
FILES=('status.json','checkpoint.json','map.csv','ranking.csv','hypotheses.md','failures.csv','metadata.json',
       'corpus_manifest.json','composition_catalog.json','schedule.json','diagnostics.csv','EXPLORATION_91.md','policy_candidates.json','build_provenance.json')
CONTROL_SPECS=[('A2',{'SIMDJSON_RVV_ADAPTIVE_V2_LEVEL':'2','SIMDJSON_RVV_ENABLE_PACKED_CONTROL':'0','SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER':'0'},'rvv','vla'),
 ('official',{},'rvv_vls','vls'),
 ('compositions',{'SIMDJSON_RVV_EXPLORATION91':'1','SIMDJSON_RVV_ADAPTIVE_V2_LEVEL':'2','SIMDJSON_RVV_ENABLE_PACKED_CONTROL':'1','SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER':'1'},'rvv','vla')]

class Campaign(support.Campaign):
    REPORT_FILENAME = 'EXPLORATION_91.md'
    REPORT_TITLE = '# Test 91 — broad composition exploration'
    SNAPSHOT_FILES = FILES
    def __init__(self,source,workdir,hours=8,jobs=2,core=0,max_mib=64):
        if (Path(workdir)/'status.json').exists():raise ValueError('Use a new run directory; never overwrite earlier evidence')
        super().__init__(source,workdir,hours,jobs,core)
        self.points=catalog();self.byid={p['id']:p for p in self.points};self.specs=corpus_specs(max_mib)
        self.rng=random.Random(SEED);self.validated=set();self.rejected={};self.diagnostics=[];self.schedule=[]
        self.manifest={};self.build_info=[];self.group_no=0;self.last_space=0;self.max_mib=max_mib
        self.generated_rounds=0;self.precommitted=len(self.points);self.frozen=[]
        self.meta.update(experiment='composition_exploration_91',points=self.points,
            sampling='65% new/uniform, 25% family specialist/interactions, 10% repeats; final 10% measurement time fresh-seed holdout',
            seed=SEED,max_mib=max_mib,planned_corpora=len(self.specs),no_production_promotion=True,
            validation='Every composition gates on valid/invalid differential DOM tests; every measured candidate/corpus agrees with fallback before timing',
            benchmark_method='Three median repeats of public DOM and direct Stage1/Stage2; matched triplets; warmed same document',
            limitations=['Research runtime binary has overhead; compare runtime A2 with dedicated A2.','No claim of cold-cache/fresh-document latency.','Fused regional counters add work; not free.','Stage1/Stage2 times do not sum to public DOM.'])
        self.status.update(point_catalog=[p['id'] for p in self.points],campaign='Test91',planned_corpora=len(self.specs),validated_compositions=0)
        self.last_disk_monitor_monotonic=float('-inf')
    def check(self,building=False):
        if self.stopfile.exists():raise support.Stopped('STOP requested')
        if time.monotonic()>=self.deadline_mono:raise support.Deadline('Test91 wall-time budget reached')
        now=time.monotonic();free=shutil.disk_usage(self.root).free
        self.status.update(disk_free_mib=round(free/1048576,1),disk_free_gib=round(free/1073741824,3),disk_safety_floor_mib=200,disk_monitor_interval_seconds=900)
        if free<support.FREE_FLOOR:raise support.Safety('Free disk below 200 MiB')
        if now-self.last_disk_monitor_monotonic>=900:
            self.last_disk_monitor_monotonic=now;self.status['disk_last_15m_check_utc']=support.now()
            self.meta.setdefault('disk_monitor_15m',[]).append(dict(utc=support.now(),free_mib=round(free/1048576,1)))
        if building or now-self.last_space>=30:
            self.last_space=now
            total=sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file() and not p.is_symlink())
            if total>2*1073741824:raise support.Safety('Run workspace exceeded 2 GiB')
        # Preserve sync-compatible bounded evidence even for very fast boards.
        if len(self.rows)>=45000:raise support.Stopped('45,000 observation evidence budget reached')
    def checkpoint(self,phase=None,force=False):
        if phase:self.status['state']=phase
        self.status.update(observations=len(self.rows),last_update=support.now(),validated_compositions=len(self.validated),rejected_compositions=len(self.rejected),measured_json=len(self.manifest),point_catalog=[p['id'] for p in self.points])
        support.atomic_json(self.root/'status.json',self.status)
        if not force and time.monotonic()-self.last_snap<120:return
        self.last_snap=time.monotonic()
        summary=[r for r in matched_summary(self.rows) if r['variant'] not in self.rejected]
        support.write_csv(self.root/'map.csv',self.rows,FIELDS)
        support.write_csv(self.root/'ranking.csv',summary,('variant','family','cases','dom_vs_A2'))
        support.write_csv(self.root/'failures.csv',self.failures,('time','step','candidate','error'))
        support.write_csv(self.root/'diagnostics.csv',self.diagnostics,('variant','corpus','parses','regions','changes','balanced_bytes','dense_bytes','text_bytes','escape_bytes'))
        support.atomic_json(self.root/'metadata.json',self.meta)
        support.atomic_json(self.root/'corpus_manifest.json',dict(schema=1,planned=self.specs,materialized=list(self.manifest.values())))
        support.atomic_json(self.root/'composition_catalog.json',dict(schema=1,points=self.points,rejected=self.rejected))
        support.atomic_json(self.root/'schedule.json',dict(seed=SEED,groups=self.schedule))
        support.atomic_json(self.root/'build_provenance.json',self.build_info)
        support.atomic_json(self.root/'policy_candidates.json',dict(status='experimental_only',frozen_holdout=self.frozen,
            suggestions=proposals(self.points,summary),instruction='Native confirmation required; no production header is changed.'))
        support.atomic_json(self.root/'checkpoint.json',dict(schema=1,started_epoch=self.started,observations=len(self.rows),groups=self.group_no,
            validated=sorted(self.validated),rng_state=repr(self.rng.getstate()),note='Evidence checkpoint; launch a new campaign to rerun, no automatic resume.'))
        paired=defaultdict(dict)
        for r in self.rows:paired[r['group']][r['variant']]=r
        complete=sum('A2' in g and 'official' in g and len(g)==3 for g in paired.values())
        report=[self.REPORT_TITLE,'',f'State: {self.status["state"]}; reason: {self.status.get("stop_reason")}',
          f'Observations: {len(self.rows)}; complete matched groups: {complete}; generated JSON: {len(self.manifest)}.',
          f'Compositions: {len(self.points)} catalogued; {len(self.validated)} validated; {len(self.rejected)} rejected.',
          '', 'Exploratory family champions below are selection-biased. Each JSON counts once within a family.',
          'Do not compare global means from different sampled populations. No automatic production winner.',
          'Runtime overhead control is policy=0 in composition_catalog; compare its paired DOM to dedicated A2.',
          'Every timed candidate/corpus received an untimed full DOM comparison with fallback.',
          'Generated data repeats a 16-atom vocabulary per family; no cold-cache claim.',
          '', '| Variant | Family | JSON | DOM / A2 |','|---|---|---:|---:|']
        report += [f'| {r["variant"]} | {r["family"]} | {r["cases"]} | {r["dom_vs_A2"]:.3f}x |' for r in sorted(summary,key=lambda x:x['dom_vs_A2'],reverse=True)[:80]]
        # Holdout is separate and only contains the frozen candidates, fresh seeds.
        hold=defaultdict(lambda:defaultdict(list))
        for g in paired.values():
            if 'A2' not in g or 'official' not in g:continue
            for tag,r in g.items():
                if r['role']=='holdout' and tag not in ('A2','official'):
                    hold[tag][r['corpus']].append(float(r['dom_all_gbps'])/float(g['A2']['dom_all_gbps']))
        report += ['', '## Fresh-seed holdout (not used for scheduling)','', '| Variant | JSON | DOM / A2 |','|---|---:|---:|']
        report += [f'| {tag} | {len(cases)} | {gm([gm(v) for v in cases.values()]):.3f}x |' for tag,cases in sorted(hold.items())]
        support.atomic_text(self.root/self.REPORT_FILENAME,'\n'.join(report)+'\n')
        support.atomic_text(self.root/'hypotheses.md',f'Explore mechanisms and family specialists; see {self.REPORT_FILENAME} and diagnostics.csv. No validated speedup is asserted.\n')
        self.snapshot()
    def snapshot(self):
        manifest={'schema':1,'files':[]};tmp=self.root/'snapshot.zip.tmp'
        with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
            total=0
            for name in self.SNAPSHOT_FILES:
                data=(self.root/name).read_bytes();total+=len(data)
                if total>60*1048576:raise support.Safety('Snapshot uncompressed evidence limit')
                z.writestr(name,data);manifest['files'].append(dict(name=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
            z.writestr('MANIFEST.json',json.dumps(manifest))
        if tmp.stat().st_size>32*1048576:raise support.Safety('Snapshot exceeds 32 MiB')
        os.replace(tmp,self.root/'snapshot.zip')
        support.atomic_text(self.root/'snapshot.sha256',hashlib.sha256((self.root/'snapshot.zip').read_bytes()).hexdigest()+'\n')
    def make_validation_cases(self):
        super().make_validation_cases()
        # Cross-region carries, not merely tiny examples. Surrogates, literal
        # UTF8, escape runs and controls around 16/32/64 and region boundaries.
        good=[];bad=[]
        for n in (15,16,31,32,63,64,4095,4096,16383,16384,65535,65536,262143,262144):
            prefix=b'"'+b'a'*n
            good += [prefix+b'\\\\\\\"tail"',prefix+b'\xf0\x9f\x98\xba"',prefix+b'\\uD83D\\uDE3A"']
            bad += [prefix+b'\x01"',prefix+b'\xf0\x80\x80\x80"',prefix+b'\\uD800"',prefix+b'\\']
        # Two full regions of different structures exercise switches and hysteresis.
        for n in (4096,16384,65536,262144):
            good.append(b'['+b'0,'*n+b'"'+b'z'*(2*n)+b'",'+b'"a\\\\b",'*n+b'0]')
        for name,items in (('valid.jsonl',good),('invalid.jsonl',bad)):
            with (self.root/name).open('ab') as f:
                for doc in items:f.write(doc+b'\n')
        self.meta['validation_cases'].update(valid=self.meta['validation_cases']['valid']+len(good),invalid=self.meta['validation_cases']['invalid']+len(bad),regional_carry_cases=len(good)+len(bad),method='Python-generated valid JSON, malformed bytes, differential full DOM vs fallback, region-boundary carries')
    def build(self,spec,upstream):
        # Reuse a binary only if sources, flags, harness and compiler match and
        # its stored binary hash is intact. Cache is confined to this run.
        tag,defines,engine,kind=spec
        src=self.source if kind=='vla' else upstream
        digest=hashlib.sha256()
        for folder in ('include','src'):
            for p in sorted((src/folder).rglob('*')):
                if p.is_file():digest.update(str(p.relative_to(src)).encode());digest.update(p.read_bytes())
        key=hashlib.sha256(json.dumps(dict(source=digest.hexdigest(),flags=self.flags(kind,defines),harness=self.meta['code_sha256'],compiler=self.meta.get('compiler_version')),sort_keys=True).encode()).hexdigest()
        path=self.root/'bin'/('parse-'+tag);stamp=path.with_suffix('.cache.json')
        cached=False
        if path.exists() and stamp.exists():
            saved=json.loads(stamp.read_text());cached=saved.get('key')==key and saved.get('binary_sha256')==hashlib.sha256(path.read_bytes()).hexdigest()
        if path.exists() and not cached:path.unlink()
        ok=super().build(spec,upstream)
        if ok:
            entry=dict(tag=tag,key=key,source_sha256=digest.hexdigest(),flags=self.flags(kind,defines),cached=cached,binary_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            support.atomic_json(stamp,entry);self.build_info.append(entry)
        return ok
    def native(self,tag,mode,args,point=None,timeout=120):
        global CONFIG
        self.check();CONFIG=(point or self.points[0])['wire']
        binary,engine,_=self.binaries[tag]
        log=self.root/'latest_bench.log'
        rc,_=run_logged(['taskset','-c',self.core,binary,engine,mode,*args],log,cwd=self.root,deadline=self.deadline_mono,stopfile=self.stopfile,timeout=timeout)
        text=support.read_tail(log,6000)
        if rc:raise RuntimeError(f'{mode} rc={rc}: {text[-2000:]}')
        if tag=='compositions' and ('CONFIG '+CONFIG) not in text.splitlines():raise RuntimeError('Effective native configuration echo mismatch')
        return text
    def ensure_valid(self,point):
        tag=point['id']
        if tag in self.rejected:return False
        if tag in self.validated:return True
        self.status['current_candidate']=tag;self.checkpoint('correctness')
        try:
            text=self.native('compositions','validate',[self.root/'valid.jsonl',self.root/'invalid.jsonl'],point,180)
            if 'RVV_VALIDATION_OK backend=rvv' not in text:raise RuntimeError('Missing correctness marker')
            self.validated.add(tag);return True
        except (support.Stopped,support.Safety):raise
        except Exception as e:
            self.rejected[tag]=str(e);self.failure('composition_correctness',tag,e);return False
    def group(self,point,spec,phase,trial=0):
        if not self.ensure_valid(point):return
        self.group_no+=1;group=f'G{self.group_no:06d}';path=self.root/'active_corpus.json'
        self.status.update(current_candidate=point['id'],current_corpus=spec['id'],experiment_phase=phase)
        self.checkpoint(phase)
        try:
            item=generate(spec,path,self.check);self.manifest[spec['id']]=item
            trace=self.native('compositions','trace',[path],point)
            if 'DOM_AGREES' not in trace:raise RuntimeError('Differential DOM comparison missing')
            for line in trace.splitlines():
                if line.startswith('TRACE '):
                    nums=list(map(int,line.split()[1:]));
                    if len(nums)!=7 or nums[0]!=1 or sum(nums[3:])!=item['bytes']:raise RuntimeError('Runtime configuration/trace byte accounting mismatch')
                    self.diagnostics.append(dict(zip(('variant','corpus','parses','regions','changes','balanced_bytes','dense_bytes','text_bytes','escape_bytes'),[point['id'],spec['id'],*nums])))
                    break
            else:raise RuntimeError('Missing instrumented trace')
            iters=max(1,min(128,1048576//item['bytes']))
            order=['official','A2',point['id']];self.rng.shuffle(order)
            self.schedule.append(dict(group=group,phase=phase,role=spec['role'],candidate=point['id'],corpus=spec['id'],trial=trial,order=order))
            for tag in order:
                binary='compositions' if tag==point['id'] else tag
                text=self.native(binary,'split',[path,iters],point)
                dom,s1,s2,seconds,_,_,actual,size=support.parse_split_output(text)
                if actual!=iters or size!=item['bytes']:raise RuntimeError('Native echo mismatch')
                row=dict(timestamp=support.now(),group=group,phase=phase,role=spec['role'],variant=tag,corpus=spec['id'],family='+'.join(item['effective_families']),layout=spec['layout'],bytes=size,iterations=iters,trial=trial,dom_all_gbps=dom,stage1_gbps=s1,stage2_gbps=s2,seconds=seconds)
                self.rows.append(row)
                with (self.root/'map.csv').open('a',newline='',encoding='utf8') as f:
                    w=csv.DictWriter(f,fieldnames=FIELDS)
                    if f.tell()==0:w.writeheader()
                    w.writerow(row);f.flush();os.fsync(f.fileno())
                self.checkpoint(phase)
        except (support.Stopped,support.Safety):raise
        except Exception as e:
            # A correctness discrepancy or candidate runtime failure permanently
            # rejects it. A failed reference stops the campaign.
            self.rejected[point['id']]=str(e);self.failure('candidate_or_measurement',point['id'],e)
            if 'binary' in locals() and binary in ('official','A2'):raise
        finally:
            # Only this run's regenerated temporary file; never historical data.
            with contextlib.suppress(FileNotFoundError):path.unlink()
    def explore(self):
        started=time.monotonic();remaining=self.deadline_mono-started
        exploration_end=started+remaining*.90
        bysize=defaultdict(list)
        for s in self.specs:bysize[s['target']].append(s)
        sizes=sorted(bysize)
        # Every plan is exposed to a common diverse screen before selection.
        anchors=[]
        for kind,size in (('ascii',4096),('dense',65536),('escaped',65536),('utf8',65536),('floats',65536),('long_strings',1048576)):
            anchors.append(next(s for s in self.specs if s['kinds']==[kind] and s['target']==size))
        regional=next(s for s in self.specs if len(s['kinds'])>=3 and s['target']==1048576 and s['layout']=='regions16384')
        anchors.append(regional)
        # Add a true large-file anchor when enabled, before adaptive scheduling.
        if self.max_mib>=8:anchors.append(next(s for s in self.specs if len(s['kinds'])>=3 and s['target']==self.max_mib*1048576 and s['layout']=='regions65536'))
        order=self.points[2:].copy();self.rng.shuffle(order);order=self.points[:2]+order
        # Cross points in waves: do not spend all time on one configuration.
        for trial in range(len(anchors)):
            for index,point in enumerate(order):
                spec=anchors[(trial+index)%len(anchors)]
                if time.monotonic()>=exploration_end:break
                self.group(point,spec,'screen',trial)
            if time.monotonic()>=exploration_end:break
        step=0;size_cursor=0
        while time.monotonic()<exploration_end:
            self.check();summary=[r for r in matched_summary(self.rows) if r['variant'] not in self.rejected];eligible=[p for p in self.points if p['id'] not in self.rejected]
            if not eligible:raise RuntimeError('No valid experimental compositions')
            if step%100==0 and self.generated_rounds<3:
                for p in proposals(self.points,summary,8):
                    if p['id'] not in self.byid:self.points.append(p);self.byid[p['id']]=p
                self.generated_rounds+=1
            chance=self.rng.random();size=sizes[size_cursor%len(sizes)];size_cursor+=1
            spec=self.rng.choice(bysize[size]);point=self.rng.choice(eligible);phase='explore'
            if chance>=.65 and chance<.90:
                champions=[r for r in summary if r['cases']>=2 and r['variant'] not in self.rejected and any(k in r['family'].split('+') for k in spec['kinds'])]
                if champions:
                    top=sorted(champions,key=lambda r:r['dom_vs_A2'],reverse=True)[:8]
                    point=self.byid[self.rng.choice(top)['variant']];phase='specialists'
            elif chance>=.90 and self.schedule:
                previous=self.rng.choice(self.schedule)
                if previous['candidate'] not in self.rejected:
                    point=self.byid[previous['candidate']];spec=next(s for s in self.specs if s['id']==previous['corpus']);phase='repeat'
            self.group(point,spec,phase,step);step+=1
        # Freeze a diversified finalist set. These measurements NEVER feed selection.
        summary=[r for r in matched_summary(self.rows) if r['variant'] not in self.rejected];winners=[]
        for kind in KINDS:
            pool=[r for r in summary if r['cases']>=2 and kind in r['family'].split('+') and r['variant'] not in self.rejected]
            if pool:winners.append(max(pool,key=lambda r:r['dom_vs_A2'])['variant'])
        winners=list(dict.fromkeys(winners))[:12]
        self.frozen=winners;self.checkpoint('holdout',force=True)
        if not winners:raise support.Stopped('Exploration ended without sufficiently covered finalists')
        for trial in range(10000):
            spec=dict(self.rng.choice(bysize[sizes[trial%len(sizes)]]))
            spec.update(id=f'H{trial:05d}',seed=SEED+10**10+trial*99991,role='holdout')
            for tag in winners:self.group(self.byid[tag],spec,'holdout',trial)
    def execute(self):
        import fcntl
        with (self.root.parent/'.night_runner_global.lock').open('w') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError('Another campaign is active')
            try:
                self.checkpoint('preflight',force=True);self.preflight()
                if hasattr(os,'sched_setaffinity'):
                    other=next((c for c in sorted(os.sched_getaffinity(0)) if c!=self.core),None)
                    if other is not None:os.sched_setaffinity(0,{other});self.status['orchestration_cpu']=other
                self.make_validation_cases()
                if not self.build(CONTROL_SPECS[0],None):raise RuntimeError('A2 reference build failed')
                upstream=self.source_upstream()
                if not self.build(CONTROL_SPECS[1],upstream):raise RuntimeError('Official reference build failed')
                if not self.build(CONTROL_SPECS[2],None):raise RuntimeError('Composition research build failed')
                self.meta['coverage']=dict(passed=list(self.binaries),expected=3)
                self.explore();self.status['state']='completed'
            except support.Stopped as e:self.status.update(state='stopped',stop_reason=str(e))
            except support.Safety as e:self.status.update(state='safety_stop',stop_reason=str(e))
            except Exception as e:
                self.status.update(state='failed',stop_reason=str(e));self.failures.append(dict(time=support.now(),step='fatal',candidate=self.status.get('current_candidate'),error=str(e)))
            finally:self.checkpoint(force=True)
