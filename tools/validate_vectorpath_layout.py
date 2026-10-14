#!/usr/bin/env python3
"""Source distribution checks only; no native benchmark or RVV test."""
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
for p in ['LICENSE','LICENSE-MIT','src/rvv/stage1.h','src/rvv/engines/engine_plan.h','src/rvv/engines/workload_profile.h','include/simdjson.h','scripts/rvv/engines/experiments.json','PROVENANCE-ADDITIONS.md']:
    assert (root/p).is_file(),p
x=json.loads((root/'scripts/rvv/engines/experiments.json').read_text(encoding='utf8'))
assert len(x.get('points',[]))>=15
print('PASS: VectorPath RVV repository layout and experiment schema (NOT a runtime correctness test)')
