# VectorPath-RVV — Short final validation and release plan

**Decision objective:** deliver the validated RVV A2 engine, not another open-ended optimization cycle. Measure **same-hardware, same-compiler A/B** against the pre-consolidation A2 baseline and official fallback; never compare absolute speeds between machines as if compiler/hardware were fixed.

## Gate 0 — provenance and immutable builds

- Record `sha256sum src/simdjson.cpp src/rvv/engines/engine_plan.h src/generic/stage2/stringparsing.h singleheader/simdjson.cpp` and compiler `--version`.
- Confirm RVV VLA is selected (`SIMDJSON_IMPLEMENTATION_RVV=1`, VLS=0); compile `-O3 -march=rv64gcv -mabi=lp64d`.
- Keep source and linked binaries separate for `stable`, `simple`, `nl4`. Do not write experimental flags into stable build.
- **Important:** MethodLab's existing pinned Test105 harness expects the old original fork header SHA-256. It is a historical A/B test, *not* a new-build benchmark. Run it against its original sources only. Do not overwrite its `engine/` copy during this gate.

## Gate 1 — correctness (required, both targets)

1. **Native RVV binary**: 18 pinned original public JSON examples, compare canonical DOM output to reference.
2. **JSONTestSuite**: all pinned conformance inputs. `y_` accepted, `n_` rejected according to current documented Test104 expectations, `i_` compared across implementations only. Record every input hash and discrepancy. Do not benchmark malformed inputs.
3. On-demand, DOM, Stage1 boundaries, streaming, UTF-8 and unescape surrogate cases; use the existing `tests/rvv` native suite and `scripts/rvv/run_tests.py` (inspect its help/requirements on the machine).
4. Verify normal `src/include` and regenerated `singleheader` produce identical results; all three opt-in variants must pass before any comparative performance result is accepted.
5. If any correctness mismatch, **stop promotion**. Maintain the original stable A2 reference.

## Gate 2 — performance (same hardware + same compiler)

| Variant | Cloud-V / GCC | EPCC / LLVM16 |
|---|---|---|
| Original MethodLab pinned A2 / 16KiB packed-off | control | control |
| New VectorPath default stable A2 / 16KiB packed-off | required | required |
| New VectorPath `SIMPLE_RUN` | optional | optional |
| New VectorPath `NL4` | optional | optional |
| Official simdjson 5.0.4 fallback | context baseline | context baseline |

- Pair measurements by document/round. Use original 18 public JSON equally weighted, with repeat runs and randomized variant order. Preserve each 18-file ratio and each individual document. Include 95 tiny valid JSONTestSuite files but do **not** pool them into large-file results.
- Separate original public, tiny public, and synthetic dense-escape probes; include real-world escaped JSON when available. Report DOM, Stage1 and Stage2 independently.
- Confirm stable defaults and explicit old flags compile to the **same dispatch configuration**. If a native performance gap remains, inspect compiler flags or binary differences before accepting it as algorithmic.
- Proposed conservative promotion rule (pre-declared, adjustable only *before* looking at results): no more than **0.5% negative geometric shift on the 18 public files** on either machine versus original A2, no major single-file regression (suggest investigate any below 0.98x), no correctness drift; specialized variant needs **at least +10%** on independently held out real escaped workloads to offset added complexity. Failure on one machine means do not promote that variant globally.
- Test105 (GCC vs LLVM) is useful to explain the slight public shifts but not required for shipping the old A2 stable profile if native checks succeed. Cross-compiler effects should be reported, not mixed into the same-machine baseline ratio.

## Gate 3 — freeze and deliver

1. Use stable A2 default with both Stage 2 switches OFF unless native gates justify a promotion.
2. Produce a final source tar/ZIP from the verified Git commit and an untouched reproducible `singleheader/`. Do not replace upstream licences or misrepresent the fork as simdjson official.
3. Include checksum manifest, compiler flags, both original per-machine benchmark ZIPs, correctness log, limitations (`fallback` official comparator, sparse escaped corpus), and reproducible build instructions.
4. Freeze the commit and **do not perform more performance tweaks** once source is tagged for the results report. A subsequent improvement must start a separate revision and re-run gates.

Expected end state: **VectorPath stable A2**, research variants documented, MethodLab remains a separate validation environment.
