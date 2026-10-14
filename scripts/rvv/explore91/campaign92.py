"""Test 92: staged, time-bounded exploration based on the Test 91 native engine.
No changes to the compiled parser or reference binaries. Works with the same
validity gates and paired A2/official/experimental measurements.
"""
from collections import defaultdict
import math
import statistics
import time

from campaign import Campaign as Campaign91, FILES
from design import KINDS, SEED, gm, proposals

FOCUS = ('long_strings', 'utf8', 'escaped', 'unicode_escape')


def paired_stats(rows):
    """Training-only data, complete triplets, uniquely counted corpora per variant.

    Screen and adaptive observations may inform selection. Fresh-seed holdout
    must never be read here, even after it has been recorded.
    """
    grouped = defaultdict(dict)
    for r in rows:
        if r.get('role') == 'holdout':
            continue
        grouped[r['group']][r['variant']] = r
    samples = defaultdict(lambda: defaultdict(list))
    for group in grouped.values():
        if not {'A2', 'official'} <= set(group) or len(group) != 3:
            continue
        baseline = group['A2']
        for variant, row in group.items():
            if variant in ('A2', 'official'):
                continue
            try:
                ratios = tuple(float(row[key]) / float(baseline[key]) for key in
                    ('dom_all_gbps', 'stage1_gbps', 'stage2_gbps'))
            except (KeyError, ValueError, TypeError, ZeroDivisionError):
                continue
            if not all(math.isfinite(v) and v > 0 for v in ratios):
                continue
            samples[variant][row['corpus']].append((ratios, row.get('family', '')))
    out = {}
    for name, corpora in samples.items():
        vals = [(tuple(gm(t[0][idx] for t in trials) for idx in range(3)), trials[0][1])
                for trials in corpora.values()]
        dom, stage1, stage2 = (gm(x[0][idx] for x in vals) for idx in range(3))
        # Stage 1 overhead deserves attention, but DOM is the primary result.
        score = math.log(dom) + .15 * math.log(stage1)
        out[name] = dict(cases=len(corpora), dom=dom, stage1=stage1,
                         stage2=stage2, score=score,
                         families=set(k for _, f in vals for k in f.split('+')),
                         corpora=set(corpora))
    return out


def shortlist(points, rows, rejected, cap=48):
    """Fair within-anchor screening plus policy diversity and control coverage."""
    stats = paired_stats(rows)
    byanchor = defaultdict(list)
    for row in rows:
        if row.get('phase') != 'screen' or row.get('variant') in ('A2','official'):
            continue
        byanchor[row['corpus']].append(row['variant'])
    chosen = []
    def add(name):
        if name not in chosen and name not in rejected and name in stats and len(chosen) < cap:
            chosen.append(name)
    # Both experimental overhead controls must survive even if they are slow.
    for p in points[:2]:
        add(p['id'])
    # Guarantee policy diversity *before* filling the slots with fast anchors.
    # Include the overhead controls even when they rank poorly.
    for policy in (0,1,2,3,4):
        bucket = [p['id'] for p in points if p['settings']['policy']==policy and p['id'] in stats]
        for name in sorted(bucket, key=lambda x:stats[x]['score'], reverse=True)[:4]:
            add(name)
    # Cross-anchor global ranking can be biased by JSON family. Select within
    # each shared reference corpus, before filling any remaining slots.
    per_anchor = max(4, cap // max(1,len(byanchor)))
    for _, names in sorted(byanchor.items()):
        for name in sorted(set(names), key=lambda x:stats.get(x,{}).get('score',float('-inf')), reverse=True)[:per_anchor]:
            add(name)
    for p in sorted(points, key=lambda p:stats.get(p['id'],{}).get('score',float('-inf')), reverse=True):
        add(p['id'])
    return chosen


def finalists(points, rows, rejected, cap=6):
    """Stage-aware exploratory finalists, requiring two distinct training JSON."""
    stats = paired_stats(rows)
    ids = {p['id']:p for p in points}
    eligible = [(key, s) for key,s in stats.items() if key in ids and key not in rejected and s['cases'] >= 2]
    chosen=[]
    def add(name):
        if name not in chosen and len(chosen) < cap:
            chosen.append(name)
    for group in (('ascii','dense','many_keys'),('utf8','escaped','unicode_escape','long_strings'),
                  ('nested','integers','floats'),('boolnull','whitespace')):
        pool = [(k,s) for k,s in eligible if s['families'].intersection(group)]
        if pool:add(max(pool,key=lambda p:p[1]['score'])[0])
    for name,_ in sorted(eligible,key=lambda p:p[1]['score'],reverse=True):
        add(name)
    return chosen


class Campaign(Campaign91):
    REPORT_FILENAME = 'EXPLORATION_92.md'
    REPORT_TITLE = '# Test 92 — staged adaptive 8h, Stage 1 diagnosis'
    SNAPSHOT_FILES = tuple('EXPLORATION_92.md' if n == 'EXPLORATION_91.md' else n for n in FILES)

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.status.update(campaign='Test92',strategy='staged_8h',
                           phase_progress={},screened_compositions=0,
                           refined_compositions=0,overhead_control_groups=0)
        self.meta.update(experiment='staged_composition_exploration_92',
            strategy='Single matched screening per configuration on rotating shared anchors, '
                     'balanced 48-point refinement on different corpora, Stage1-focused '
                     'adaptive search, dedicated policy=0 overhead controls, fresh-seed holdout.',
            sampling='No unpaired comparisons; Stage1 is a diagnostic (15% ranking weight); '
                     'finalists require >=2 distinct training corpora; last 15% of post-build time held out.',
            selection_limitations='Screen is one corpus per candidate. Stratified screening is noisy; '
                     'shortlist preserves policy diversity and the controls. Stage1 timings are not DOM addends.',
            inherited_native_engine='Test91 with identical source/compiler/validity gates')

    def explore(self):
        # Absolute deadline includes three builds, so only allocate the remaining
        # post-build budget. Incomplete stages safely transition when time runs out.
        start=time.monotonic()
        available=max(0,self.deadline_mono-start)
        exploration_end=start+available*.85
        screen_end=start+available*.34
        refinement_end=start+available*.57
        anchor_cases=(('ascii',4096),('dense',65536),('utf8',65536),
                      ('escaped',65536),('long_strings',1048576),('floats',65536))
        anchors=[next(s for s in self.specs if s['kinds']==[kind] and s['target']==size)
                 for kind,size in anchor_cases]
        order=self.points[2:].copy();self.rng.shuffle(order);order=self.points[:2]+order
        seen=set();used={}
        # Phase 1: one anchor per configuration, evenly staggered among common
        # anchors to avoid spending 5+ hours on 242x8 exhaustive screening.
        for i, point in enumerate(order):
            if time.monotonic()>=screen_end or time.monotonic()>=exploration_end:break
            spec=anchors[i%len(anchors)]
            self.group(point,spec,'screen',i)
            seen.add(point['id']);used.setdefault(point['id'],set()).add(spec['id'])
            self.status['screened_compositions']=len(seen)
        self.status['phase_progress']['screen']=len(seen)
        # Phase 2: a policy-diverse shortlist gets fresh (still TRAINING)
        # measurements on two *different* common anchors.
        picks=shortlist(self.points,self.rows,self.rejected,48)
        for trial in range(2):
            for i, key in enumerate(picks):
                if time.monotonic()>=refinement_end or time.monotonic()>=exploration_end:break
                point=self.byid[key]
                options=[s for s in anchors if s['id'] not in used.get(key,set())]
                if not options:continue
                spec=options[(trial+i)%len(options)]
                self.group(point,spec,'refine',trial)
                used.setdefault(key,set()).add(spec['id'])
                self.status['refined_compositions']=sum(1 for k in picks if len(used.get(k,set()))>=2)
            if time.monotonic()>=refinement_end:break
        self.status['phase_progress']['refine']=self.status['refined_compositions']
        # Phase 3: 15% of adaptive groups measure policy=0 on diverse,
        # *matched* corpus/A2 controls. The rest sample specialists and Stage1
        # stress families with explicit corpus size rotation, including 64 MiB.
        sizes=sorted(set(s['target'] for s in self.specs))
        bysize=defaultdict(list)
        for spec in self.specs:bysize[spec['target']].append(spec)
        weight={256:1,4096:3,65536:5,1048576:4,8388608:2,67108864:1}
        weighted=[size for size in sizes for _ in range(weight.get(size,1))]
        focus=[s for s in self.specs if set(s['kinds']).intersection(FOCUS)
               and s['target'] in (65536,1048576,8388608)]
        step=0
        while time.monotonic()<exploration_end:
            self.check()
            active=[p for p in self.points if p['id'] in picks and p['id'] not in self.rejected]
            if not active:raise RuntimeError('No refined compositions remain valid')
            size=weighted[step%len(weighted)]
            spec=self.rng.choice(bysize[size])
            phase='adaptive';point=self.rng.choice(active)
            if step%12==0:
                # Dedicated policy=0 versus dedicated A2: experimental binary
                # overhead, not a claim about the policy's own speedup.
                point=self.points[0]
                spec=anchors[(step//12)%len(anchors)]
                phase='overhead_control'
                self.status['overhead_control_groups']+=1
            elif step%7==0:
                spec=self.rng.choice(focus)
                phase='stage1_focus'
            elif self.rng.random()<.35:
                stats=paired_stats(self.rows)
                eligible=[p for p in active if p['id'] in stats and stats[p['id']]['cases']>=2]
                if eligible:
                    point=max(eligible, key=lambda p:stats[p['id']]['score']+self.rng.random()*.07)
                    phase='specialists'
            elif step%17==0 and self.schedule:
                prev=self.rng.choice([r for r in self.schedule if r['phase']!='holdout'][-100:])
                if prev['candidate'] in self.byid and prev['candidate'] not in self.rejected:
                    point=self.byid[prev['candidate']]
                    spec=next(s for s in self.specs if s['id']==prev['corpus'])
                    phase='repeat'
            self.group(point,spec,phase,step)
            # Proposals are allowed only after multi-case refinement, and are
            # never silently substituted for the 242 tested original plans.
            if step==40 and self.generated_rounds==0:
                from design import matched_summary
                info=[r for r in matched_summary(self.rows) if r['variant'] not in self.rejected]
                for proposal in proposals(self.points,info,8):
                    if proposal['id'] not in self.byid:
                        self.points.append(proposal);self.byid[proposal['id']]=proposal
                        picks.append(proposal['id'])
                self.generated_rounds=1
            step+=1
        self.status['phase_progress']['adaptive_groups']=step
        # Holdout is frozen before its first sample; never feeds paired_stats().
        winners=finalists(self.points,self.rows,self.rejected,cap=6)
        self.frozen=winners
        self.status['phase_progress']['holdout_finalists']=len(winners)
        self.checkpoint('holdout',force=True)
        if not winners:
            raise RuntimeError('No finalist with two distinct training JSON corpora; holdout not possible')
        # Every finalist gets the SAME fresh-seed JSON for each round.
        hold_sizes=[s for s in sizes if s in (4096,65536,1048576,8388608,67108864)]
        for trial in range(10000):
            if time.monotonic()>=self.deadline_mono:break
            base=self.rng.choice(bysize[hold_sizes[trial%len(hold_sizes)]])
            spec=dict(base,id=f'H{trial:05d}',seed=SEED+10**10+trial*99991,role='holdout')
            for key in winners:
                self.group(self.byid[key],spec,'holdout',trial)
