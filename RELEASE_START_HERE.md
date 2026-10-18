# VectorPath-RVV — A2 Stable / Release Sources (2026-10-18)

**Distribution status:** frozen, publication-ready source package reconstructed from a supplied repository snapshot and the tested release-candidate overlay. **Not a Git tag** and **not an assertion that the current live GitHub branch has been updated**.

## Stable configuration

- RISC-V **RVV-VLA**, with preference over the optional RVV-VLS backend.
- Adaptive dispatch A2 (`SIMDJSON_RVV_ADAPTIVE_V2_LEVEL=2`), minimum threshold **16,384 bytes**.
- Packed structural/index/escape/quote/shift paths **disabled by default**.
- Original Stage 2 decoder is the shipping/default path.
- `SIMDJSON_VECTORPATH_STAGE2_SIMPLE_RUN=1` and `SIMDJSON_VECTORPATH_STAGE2_NL4=1` are **experimental opt-in only**. Do not enable them for the published stable build.

## Performance evidence — Test 106 native confirmation

**Primary population:** 18 pinned public JSON documents, confirmation phase; paired throughput ratios aggregated geometrically **by document**. Reference: **official simdjson 5.0.4 fallback**, not its accelerated x86 backends or VLS256.

| Target | Stable vs official fallback | Incremental vs original A2 | Standardized correctness |
|---|---:|---:|---:|
| Cloud-V (riscv64 GCC) | **1.6007× (+60.07%)** | **+0.001%** | **340/340** |
| EPCC rvc02 (riscv64 LLVM 16) | **1.8946× (+89.46%)** | **−0.041%** | **340/340** |

Original A2 and the stable candidate produced **identical ELF SHA-256 digests on each machine** in the test harness. The stable public-corpus non-regression gate passed on both machines. The `NL4` option failed that gate on Cloud-V, and stays off.

**Limits:** 95 valid JSONTestSuite fixtures (2–110 bytes) were slower than fallback; the stable ratios were 0.6665× on Cloud-V and 0.8497× on EPCC. Escaping-heavy stress patterns vary considerably; a headline gain from 18 public files must not be generalized to every JSON size or distribution. Relative historical figures from Test 89 (+64.1% against another backend and corpus) and Test 101 (+62.9% with a different benchmark procedure) are not directly comparable to Test 106.

## CI coverage — scoped evidence, not source identity

GitHub Actions **Fuzz and run valgrind #78**, run `39155386567`, succeeded on commit `81c6b1c150a73925894c5f5863d2892cc0a1ec4c` in the **separate** repository `MA-Gustave/Simdjson-rvv-vla`. The earlier #74 failed at that same commit, while #75–78 subsequently succeeded. The cause of #74 was not proved; a transient external upload/network failure remains only a hypothesis.

The #78 workflow visibly performed fuzzing with sanitizers and a Valgrind **x86/default-implementation replay**, with archives `corpus` and `valgrindresults`. The provided partial Valgrind log showed five full clean `ERROR SUMMARY: 0` / no-leak runs; the complete `valgrindresults` artifact was not inspected. The workflow does **not** prove that these exact VectorPath files were tested under Valgrind on RISC-V. Do not claim native RVV memory-safety certification.

## What exactly is frozen?

The five native C++ files examined by Test 106 are SHA-identical in this package (see `FROZEN_SOURCE_MANIFEST.json`). The original fork `src/simdjson.cpp` fingerprint is unchanged. The rest of the repository comes from `znapshot_VectorPath-RVV_10180838.zip` plus the source/metadata overlay `VectorPath-RVV_A2_STABLE_STAGE2_OPTIONAL_DROP_ROOT_20261018.zip`.

The underlying VectorPath repository is a **simdjson 5.0.3-derived fork**. The comparative official reference used in Test 106 is **upstream v5.0.4 fallback**. This difference must remain explicit in any publication.

## Distribution and integrity

This is a **complete source tree**, not a DROP ROOT overlay and not a Git repository clone. Source, licences and notices are preserved; extra publication documentation has been added in `docs/release/`. SHA-256 file inventory: `SHA256SUMS_RELEASE.txt` (every distribution file except itself). The Git commit/tag **must be created by the maintainer** after importing this tree; no commit is invented in this archive.

Reproduce the portable host smoke tests with `python3 scripts/rvv/release_candidate_check.py --compiler g++`. That is a fallback-only host check, **not** a replacement for completed native Test 106 evidence.

For paper-ready methodology, results and qualifications, see `docs/release/TEST106_PUBLICATION_REPORT_EN.md`. The raw EPCC and Cloud-V archives are distributed separately as the evidence bundle.
