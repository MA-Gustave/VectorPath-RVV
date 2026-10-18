# VectorPath-RVV — Stable A2 Release Candidate (2026-10-18)

**Status: RELEASE CANDIDATE, not final shipping certification.** Built from the user's `znapshot_VectorPath-RVV_10180838.zip`; *not* merged with MethodLab's `engine/` automatically. This is an independent simdjson **5.0.3 fork**; it is not upstream simdjson 5.0.4. Preserve all existing license and origin notices.

## What is actually optimized in this delivery?

The source defaults now reproduce the proven **RVV A2 / 16 KiB / packed-off** compilation profile used in the recent MethodLab benchmarks. Previously, VectorPath compiled with A0 and packed enabled by default. These defaults are in `src/rvv/engines/engine_plan.h`, with a matching packed-control default in `src/rvv/string_scanner.h`:

| Compile-time setting | Old default | New default | Status |
|---|---:|---:|---|
| `SIMDJSON_RVV_ADAPTIVE_V2_LEVEL` | 0 | **2** | Measured A2 profile |
| `SIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES` | 4096 | **16384** | Measured A2 G16384 profile |
| `SIMDJSON_RVV_ADAPTIVE_V2_QUICK_BYTES` | 512 | **512** | Unchanged |
| `SIMDJSON_RVV_ENABLE_PACKED_CONTROL` | 1 | **0** | Packed-off baseline |
| packed index/escape/quote/shift | inherited 1 | **inherited 0** | Historical experiments can override |
| `SIMDJSON_IMPLEMENTATION_RVV_VLS` when RVV-VLA is available | auto-detect VLS | **0** | Prefer scalable RVV-VLA (overridable) |
| `SIMDJSON_VECTORPATH_STAGE2_SIMPLE_RUN` | unavailable | **0** | Opt-in experimental |
| `SIMDJSON_VECTORPATH_STAGE2_NL4` | unavailable | **0** | Opt-in experimental |

**Only build defaults, the native RVV-VLA-over-VLS auto-selection preference, and opt-in Stage 2 research code have changed**; original Stage 1 vector algorithms, dispatch logic, public API and existing TypeScript/Python front ends remain untouched. `-D` overrides continue to work. The baseline Stage 2 code is byte-for-byte equivalent when the research flags remain at 0 (the added optional block is removed by the preprocessor).

### Tested performance is evidence for the configuration, NOT a new benchmark of this ZIP

Recent MethodLab Test104 *on its pinned 18 public JSON files*, comparing A2 at 16 KiB to official simdjson 5.0.4 **fallback**, reported approximate DOM throughput ratios of **1.894x EPCC** and **1.595x Cloud-V** (configuration and backend differ from official). Tests103/104 confirmed considerable speedups for `SIMPLE_RUN`/`NL4` on pathological 50%-backslash fixtures, but tiny public-corpus shifts diverged slightly across compilers/machines. Hence research switches default **OFF** in the release candidate. Test105's compiler-effect experiment should be reviewed before considering any opt-in Stage 2 code for release.

These are *historical comparisons*, not speedups guaranteed by this source patch or single-header build; validation on both RISC-V machines remains mandatory.

## Installation — DROP ROOT (VectorPath, NOT MethodLab)

1. Back up or commit the current **VectorPath-RVV** repository state first.
2. Extract `VectorPath-RVV_A2_STABLE_STAGE2_OPTIONAL_DROP_ROOT_20261018.zip` **directly in the root of VectorPath-RVV** (where `src/`, `include/`, `tests/`, `singleheader/`, `CMakeLists.txt` live). Overwrite only listed files.
3. **Do not extract this ZIP into `VLA-MethodLab`**. In particular, don't copy the updated engine to MethodLab's `engine/` until the independent validation campaign has finished: Tests 101–105 pin the older source hashes and may reject or mix baselines if overwritten.
4. Run a local portable smoke test: `python3 scripts/rvv/release_candidate_check.py --compiler g++` (or `clang++`). This verifies 3 decoder configurations in both the normal multi-file library and the refreshed `singleheader` distribution, along with portable dispatch policy checks. **This test always uses the fallback CPU backend**, even if run on RISC-V; it does not verify RVV throughput.
5. On **Cloud-V and EPCC**, rebuild as actual native/cross RISC-V (`-march=rv64gcv -mabi=lp64d`) and perform the validation gates in `docs/VECTORPATH_RC_VALIDATION.md` before shipping anything.

## Rebuild & variants

The benchmarked public code uses a modern RISC-V C++ compiler with `-O3 -std=c++17 -march=rv64gcv -mabi=lp64d -pthread` and `SIMDJSON_IMPLEMENTATION_RVV=1`, `SIMDJSON_IMPLEMENTATION_RVV_VLS=0`. To reproduce the earlier A2 baseline precisely, set `SIMDJSON_IMPLEMENTATION_FALLBACK=1` as well as those explicit RVV flags; this includes fallback in the build, not a replacement for RVV. A compiler that lacks native RVV support must **not** silently stand in for RISC-V validation.

Build each candidate separately, applying definitions to **both the library source and any generated amalgamated source as appropriate**:

```text
Stable / intended shipping candidate:
  no extra SIMDJSON_RVV_* / SIMDJSON_VECTORPATH_* overrides

Stage 2: consecutive simple JSON escapes (research only):
  -DSIMDJSON_VECTORPATH_STAGE2_SIMPLE_RUN=1

Stage 2: above + four consecutive \\n sequences (research only):
  -DSIMDJSON_VECTORPATH_STAGE2_SIMPLE_RUN=1 -DSIMDJSON_VECTORPATH_STAGE2_NL4=1

Historical A0 packed-on control (research only):
  -DSIMDJSON_RVV_ADAPTIVE_V2_LEVEL=0 -DSIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES=4096
  -DSIMDJSON_RVV_ENABLE_PACKED_CONTROL=1
```

NL4 without SIMPLE_RUN is a deliberate compilation error. Do not promote either experimental variant automatically. The regenerated `singleheader/simdjson.h` and `.cpp` now include the RVV-VLA backend and the same release profile; the original snapshot's amalgamator was missing RVV-VLA registration.

## Release decision

* Ship the **A2 16KiB packed-off default** only after both machines pass correctness, on-demand and Unicode validation, and measured public performance is consistent with historical A2 data.
* Prefer unchanged Stage 2 at this stage. Only include `SIMPLE_RUN` or `NL4` by default if independent native A/B benchmarks on both machines show no meaningful public regression, including short JSON, and confirm a material benefit on real dense-escape cases.
* Freeze the same source SHA-256 across EPCC/Cloud-V and the singleheader build; archive compiler version, flags, input hashes, two original result ZIPs, and any excluded regressions.

**This is a consolidation milestone, not a claim of a completed product release.**
