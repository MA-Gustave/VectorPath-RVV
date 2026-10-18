# Test 106 — VectorPath-RVV Release Candidate: Native Validation and Performance Report

**Technical report (English) | 18 October 2026 | Cloud-V and EPCC | Frozen A2 release-candidate evaluation**

**Evidence:** `106-cloudv.zip`, `106-eppc.zip`; cross-checked against the Test 106 run manifests, measured CSVs, summaries, conformance records, and Test 107 release audit. The analysis below describes completed Test 106 runs; no additional RISC-V runs were performed to prepare this report.

## Executive summary

The stable VectorPath-RVV release candidate reproduces the performance of the previously validated MethodLab A2 configuration. The release candidate is configured for the **RVV-VLA backend**, **A2 adaptive dispatch (16 KiB threshold)**, **packed features disabled**, and the **original Stage 2 string decoder**. Two optional Stage 2 variants, `SIMPLE_RUN` and `NL4`, were also measured but are **not enabled for the release**.

| Primary result, 18 public JSON documents | Cloud-V | EPCC |
|---|---:|---:|
| **VectorPath stable / official simdjson v5.0.4 fallback** | **1.6007x (+60.071%)** | **1.8946x (+89.459%)** |
| Original A2 / official fallback | 1.6007x (+60.070%) | 1.8954x (+89.537%) |
| Optional SIMPLE_RUN / official fallback | 1.5950x (+59.504%) | 1.9012x (+90.124%) |
| Optional NL4 / official fallback | 1.5907x (+59.066%) | 1.9026x (+90.262%) |

Across both systems, **92,435 + 75,400 = 167,835** measurements were recorded. Each Test 106 run completed its planned measurement budget. The stable VectorPath and original A2 ELF binaries have **matching SHA-256 digests within each machine**, supporting functional build equivalence for the tested configurations.

**Decision:** keep `VP_STABLE` as the release candidate. Its public-corpus regression gate passes on both systems. Leave `SIMPLE_RUN` optional, and keep `NL4` disabled: despite strong synthetic escape gains, NL4 fails the predefined Cloud-V public-corpus performance gate. A subsequent GitHub Actions run (#78) succeeded in the related Simdjson-rvv-vla repository on an x86 runner; its coverage is supplementary, not proof of native RVV memory safety.

## 1. Research question and experimental design

Test 106 asked whether the release-bound VectorPath repository, after consolidating the historically successful A2 settings, behaves and performs like the **unchanged A2 reference**. It also checked whether experimental Stage 2 escape-loop improvements are safe to promote before publication. The experiment used **five separately compiled variants** on each target:

| ID | Meaning | Release role |
|---|---|---|
| `OFFICIAL_504` | Unmodified official simdjson 5.0.4 compiled for the **fallback** implementation | External speed baseline |
| `A2_ORIGINAL` | Previously pinned MethodLab RVV-VLA A2, 16 KiB, packed disabled | Internal reference |
| `VP_STABLE` | Consolidated VectorPath-RVV with the same A2 behavior as defaults; original Stage 2 | **Candidate to ship** |
| `VP_SIMPLE` | VectorPath with `SIMPLE_RUN` Stage 2 escape processing enabled | Optional A/B |
| `VP_NL4` | SIMPLE_RUN plus an additional repeated `\n` handling optimization | Optional A/B |

For an official-baseline speedup, throughput ratio = `candidate throughput / OFFICIAL_504 throughput`. For the incremental change attributable to VectorPath consolidation or Stage 2 options, throughput ratio = `candidate throughput / A2_ORIGINAL throughput`. These are **different comparisons** and should never be interchanged.

### Platforms and build environment

| Property | Cloud-V | EPCC |
|---|---|---|
| Recorded host | `bpf3-16G-2` | `rvc02` |
| Architecture / backend | riscv64 / RVV-VLA | riscv64 / RVV-VLA |
| Compiler reported by run | GCC `g++` (native) | LLVM/Clang 16 (`--target=riscv64-unknown-linux-gnu`) |
| Common optimization settings | `-O3 -DNDEBUG -g0 -pthread -std=c++17` | same |
| Target ISA / ABI | `-march=rv64gcv -mabi=lp64d` | same |
| Affinity listed in manifest | 8 CPUs | 2 CPUs |
| Duration | 1.97 h | 1.97 h |
| Measurement rows | 92,435 | 75,400 |
| Paired five-variant groups | 18,487 | 15,080 |
| Completed rounds | 136 | 111 |

**Cross-platform caveat:** use same-machine speed ratios for inference. Cloud-V and EPCC use different compilers, system conditions and CPU affinity. Their absolute throughput measurements should not be pooled into one universal RISC-V number. Test 106 was **not** the cross-compiler factorial experiment proposed for Test 105.

### Measurement and aggregation

- The CSV contains separate `dom_gbps`, `stage1_gbps`, and `stage2_gbps` measurements, with five variants in each paired group. Grouping by input and measurement phase improves comparability.
- Main reported results use the **confirmation phase** and the original **18 public JSON documents**. Paired ratios are aggregated in logarithmic space, then each document contributes equal weight to the geometric mean. The 18 files are not weighted by bytes or by number of rows.
- Exploration and confirmation are reported separately. Synthetic inputs are not combined with original public JSON or tiny standardized-valid JSON.
- Stage 1 and Stage 2 throughputs are internal measurements, **not additive** and not a decomposition that should be multiplied or summed to reconstruct DOM throughput.
- A ratio of `1.6007x` means **60.07% higher throughput**, not 60.07% less elapsed time. To express a time reduction under equivalent work, compute `1 − (1 / 1.6007)` (approximately 37.53%).

## 2. Public corpus: primary performance results

The benchmark uses 18 original public JSON files from pinned `simdjson-data` commit `4197c425e857f0ec38e89822fdd0bd9ea21f4daf`. The files span **10,075 to 3,327,831 bytes**. File SHA-256 digests match between the two target manifests.

### 2.1 DOM throughput versus official simdjson v5.0.4 fallback

| Variant | Cloud-V | Cloud-V advantage | EPCC | EPCC advantage |
|---|---:|---:|---:|---:|
| `A2_ORIGINAL` | 1.6007x | +60.070% | 1.8954x | +89.537% |
| `VP_STABLE` | 1.6007x | +60.071% | 1.8946x | +89.459% |
| `VP_SIMPLE` | 1.5950x | +59.504% | 1.9012x | +90.124% |
| `VP_NL4` | 1.5907x | +59.066% | 1.9026x | +90.262% |

All 18 public files favor the stable VectorPath RVV backend over the official fallback in these two runs (the per-document ratios below are all above 1.0x). This is a statement about **this pinned corpus and this fallback backend**, not every JSON workload or every available simdjson backend.

### 2.2 Stage-level results (stable candidate versus official fallback)

| Confirm-phase throughput ratio | Cloud-V | EPCC |
|---|---:|---:|
| DOM | 1.6007x | 1.8946x |
| Stage 1 | 2.0376x | 2.5035x |
| Stage 2 | 1.2727x | 1.4687x |

The largest relative advantage occurs in **Stage 1**. Stage 2 still benefits from the RVV release configuration on this corpus, but less strongly. Whole-document throughput should be evaluated using the DOM row, not estimated by combining stage ratios.

### 2.3 Exploration / confirmation stability

| Stable candidate / official fallback | Cloud-V | EPCC |
|---|---:|---:|
| Explore | 1.6075x | 1.8940x |
| Confirm | 1.6007x | 1.8946x |

The primary improvement is present in both phases, without choosing the higher phase as the headline result.

### 2.4 Per-document confirmation results

Per-document ratios use the same paired, logarithmic aggregation as the campaign summaries. The two **vs A2** columns quantify any incremental change from the VectorPath release candidate; the **vs official** columns quantify the larger RVV backend advantage.

| Public JSON document | Bytes | Cloud-V stable / official | EPCC stable / official | Cloud-V stable / A2 | EPCC stable / A2 |
|---|---:|---:|---:|---:|---:|
| `apache_builds.json` | 127,275 | 1.719x | 2.210x | 0.9976x | 1.0005x |
| `canada.json` | 2,251,051 | 1.331x | 1.292x | 1.0001x | 0.9998x |
| `citm_catalog.json` | 1,727,204 | 1.528x | 1.758x | 1.0025x | 1.0011x |
| `github_events.json` | 65,132 | 2.076x | 2.658x | 1.0005x | 1.0009x |
| `google_maps_api_compact_response.json` | 11,812 | 1.252x | 1.615x | 1.0006x | 1.0003x |
| `google_maps_api_response.json` | 26,102 | 1.410x | 1.690x | 0.9992x | 0.9993x |
| `gsoc-2018.json` | 3,327,831 | 3.087x | 4.152x | 0.9978x | 0.9988x |
| `instruments.json` | 220,346 | 1.440x | 1.761x | 1.0013x | 1.0011x |
| `marine_ik.json` | 2,983,466 | 1.259x | 1.391x | 1.0023x | 1.0005x |
| `mesh.json` | 723,597 | 1.352x | 1.359x | 1.0018x | 0.9994x |
| `mesh.pretty.json` | 1,577,353 | 1.493x | 1.489x | 0.9994x | 0.9970x |
| `numbers.json` | 150,124 | 1.405x | 1.318x | 1.0000x | 0.9978x |
| `twitter.json` | 631,515 | 1.908x | 2.370x | 1.0011x | 1.0008x |
| `twitter_api_compact_response.json` | 10,075 | 1.767x | 2.283x | 1.0003x | 0.9991x |
| `twitter_api_response.json` | 15,253 | 1.829x | 2.263x | 0.9984x | 0.9996x |
| `twitter_timeline.json` | 42,233 | 1.572x | 1.974x | 1.0005x | 1.0006x |
| `twitterescaped.json` | 562,408 | 1.409x | 1.805x | 0.9983x | 0.9984x |
| `update-center.json` | 533,178 | 1.712x | 2.294x | 0.9985x | 0.9978x |

A machine-readable companion table, `TEST106_Public_18JSON_PerDocument_Results_EN.csv`, includes all 18 SHA-256 file digests plus per-file ratios for the two experimental Stage 2 variants.

## 3. Incremental regression assessment against the old A2

The relevant shipping test is **not** whether the experimental variant still beats the official fallback; it is whether it outperforms or at least preserves the prior A2 on representative public workloads. The Test 106 release rule was predetermined as follows:

> The equal-document geometric-mean throughput ratio must be **at least 0.995x**, and **no individual document may fall below 0.980x** versus `A2_ORIGINAL`, on each target.

| Candidate | Cloud-V vs A2 | Cloud-V minimum document | Cloud-V gate | EPCC vs A2 | EPCC minimum document | EPCC gate |
|---|---:|---:|---|---:|---:|---|
| `VP_STABLE` | +0.001% | 0.9976x (`apache_builds.json`) | PASS | -0.041% | 0.9970x (`mesh.pretty.json`) | PASS |
| `VP_SIMPLE` | -0.354% | 0.9851x (`twitter_api_compact_response.json`) | PASS | +0.309% | 0.9976x (`mesh.pretty.json`) | PASS |
| `VP_NL4` | -0.628% | 0.9797x (`twitterescaped.json`) | **FAIL** | +0.382% | 0.9976x (`twitterescaped.json`) | PASS |

**Interpretation:**

1. **Stable passes both targets.** Its deviations from the original A2 are extremely small and consistent with run-to-run timing variation; the strongest evidence is the **identical ELF SHA-256 within each machine**.
2. **SIMPLE_RUN passes the formal numerical gate**, but its average effect has opposite signs: it slightly improves EPCC and slightly slows Cloud-V. This is not a cross-platform improvement worth enabling globally for this release.
3. **NL4 fails Cloud-V on both criteria**: the overall public mean is below 0.995x and `twitterescaped.json` falls to about 0.9797x (−2.03%) versus A2. It must remain opt-in only.

Binary equality is **within**, not **between**, machines: GCC and Clang produce distinct ELFs, as expected. It shows that the compiled stable candidate did not change the executable relative to its old-A2 control at the same toolchain/settings, not that the source trees or toolchains are universally equivalent.

## 4. Conformance and standardized small-input behavior

Both machines ran JSONTestSuite at pinned commit `1ef36fa01286573e846ac449e8683f8833c5b26a`. Each conformance record lists **340 evaluated cases**: **95 `y_` (valid)**, **188 `n_` (invalid)**, **35 `i_` (implementation-defined)**, and **22 transformation cases**. The `i_` class is checked for agreement but not assigned a universal validity requirement.

| Conformance outcome | Cloud-V | EPCC |
|---|---:|---:|
| Cases evaluated | 340 | 340 |
| Cross-variant disagreements | 0 | 0 |
| Mismatches with declared expected verdicts | 0 | 0 |

**Outcome:** no conformance discrepancies were detected in this test suite. This does not substitute for independent fuzzing, sanitizers, or Valgrind.

The 95 valid `y_` inputs are also benchmarked **separately**. These files are only 2–110 bytes (median 8 bytes), so fixed dispatch and timing overhead can dominate. They must not be merged with the original 18-document corpus.

| 95 valid JSONTestSuite fixtures — DOM vs official fallback | Cloud-V | EPCC |
|---|---:|---:|
| `A2_ORIGINAL` | 0.6662x (-33.381%) | 0.8497x (-15.034%) |
| `VP_STABLE` | 0.6665x (-33.347%) | 0.8497x (-15.034%) |
| `VP_SIMPLE` | 0.6717x (-32.827%) | 0.8473x (-15.273%) |
| `VP_NL4` | 0.6647x (-33.530%) | 0.8476x (-15.238%) |

**Known limitation:** on these very small inputs the fallback outperforms RVV A2, substantially so on Cloud-V. The positive public-corpus result cannot be claimed to hold for tiny messages.

## 5. Stage 2 escape experiments: separate stress tests

The synthetic workload classes (`mixed`, `newline`, `unicode`) deliberately control escape content; exploration and confirmation use separate generated inputs. Their purpose is to expose Stage 2 sensitivity, **not** to estimate the distribution of production JSON.

| Confirm synthetic family — DOM improvement vs original A2 | Cloud-V SIMPLE_RUN | Cloud-V NL4 | EPCC SIMPLE_RUN | EPCC NL4 |
|---|---:|---:|---:|---:|
| `mixed` | +34.335% | +33.177% | +39.187% | +38.196% |
| `newline` | +32.453% | +37.041% | +38.128% | +46.345% |
| `unicode` | -0.221% | -2.938% | +0.069% | -0.178% |

These results show that the candidate decoder optimizations can be highly effective when strings contain many consecutive simple escapes. They also show a drawback: the NL4 variant is less effective for Unicode-heavy samples on Cloud-V. The sign of the small public-corpus change remains more important for a general-purpose release.

### Extreme mixed-escape stress (requested 50% density)

This subcase contains **two generated documents per machine**. It is an intentionally pathological test and should be treated as a diagnostic, not as a broad workload claim.

| Mixed 50% requested density — DOM ratio | Cloud-V | EPCC |
|---|---:|---:|
| `A2_ORIGINAL` / `OFFICIAL_504` | 0.431x | 0.462x |
| `VP_SIMPLE` / `A2_ORIGINAL` | 2.850x | 3.199x |
| `VP_NL4` / `A2_ORIGINAL` | 2.993x | 3.192x |
| `VP_SIMPLE` / `OFFICIAL_504` | 1.228x | 1.478x |
| `VP_NL4` / `OFFICIAL_504` | 1.290x | 1.474x |

No selective synthetic gain is used in the headline overall-public speedup.

## 6. Integrity, reproducibility, and provenance

### 6.1 Evidence inventory

| Property | Cloud-V | EPCC |
|---|---|---|
| Outer archive | `106-cloudv.zip` | `106-eppc.zip` |
| Archive ZIP integrity | PASS | PASS |
| Embedded `test106_results.zip` CRC check | PASS | PASS |
| `results106.csv` row count agrees with `status106.json` | PASS | PASS |
| Five-variant grouping (one of each variant per group) | PASS | PASS |
| Input public-file digests match across targets | PASS | PASS |
| Stable ELF SHA-256 equals old A2 ELF SHA-256 | PASS | PASS |

**Source and build identifiers:**

- VectorPath release candidate patch SHA-256: `513dbf6ea2241d469ade18a354e18a77303d66ce9d6794fb8595ee59e01f0388`
- Shared harness SHA-256: `41357ac625b3872195fce3c1584664fe84033eec888eec3953a68cbeffc68265`
- Original A2 source `simdjson.cpp` SHA-256: `fdaea284a48b30ab3e912e1cd3580e920fe186a229faabba97d9b24eed095e16`
- Original engine-plan SHA-256: `7ebd7d2f4606c9ed9db77bcced50371e669698e5278f1afc4e5369fc5b4e7f4e`
- Official 5.0.4 source commit recorded: `3b0b2b53aaffb46208817821dce2cd47a5e6bb2a`

| Executable hash | Cloud-V | EPCC |
|---|---|---|
| `A2_ORIGINAL` | `87e658bd1be322dd41a92e42a60d0d41308819dac9af188ac535f138c93b555f` | `9c965fb58f31053f0b9a1cfc54e051d8787ab59d4eda307bb6878a78023ecddb` |
| `VP_STABLE` | `87e658bd1be322dd41a92e42a60d0d41308819dac9af188ac535f138c93b555f` | `9c965fb58f31053f0b9a1cfc54e051d8787ab59d4eda307bb6878a78023ecddb` |
| `VP_SIMPLE` | `2eee5a5623daeeb93fa79685a41f350831d9a1b7c1f6ee801316b145c48c96f4` | `48017c86b24d85615f781806829f60b8b08d35646278e930164fd134779c98e8` |
| `VP_NL4` | `37431c756e03038ff7aeb49f1f7a8b7c15722df55b98f393fd91646d5b8e5329` | `5f55fcb9123340ee188a061d2098d6bc47d4c6995edd53e0bd5d091a9bde75ac` |
| `OFFICIAL_504` | `f51062249b0b9a563e87c0d21973d154b621b2ae25b14b873f52f8526fe432e8` | `e6d0a86dd3bf36b25addfe888c0ca42fa124eb730dc8ae1371e641390bf537db` |

The VectorPath candidate source manifest includes modifications to five C++ implementation/detection files and was reconstructed in an isolated directory without overwriting the historical MethodLab engine. The build report records `VP_STABLE` and `A2_ORIGINAL` as byte-identical executables on each host.

### 6.2 Reproducing the ratios

The following pseudocode states the aggregation principle implemented by the campaign summaries:

```text
for each target and phase:
  for each public document d:
    for each matched measurement group g of d:
      r[g,d] = throughput(candidate, g, d) / throughput(reference, g, d)
    document_ratio[d] = exp(mean(log(r[g,d]) over g))
  target_geomean = exp(mean(log(document_ratio[d]) over 18 documents))
  reported_gain_percent = 100 * (target_geomean - 1)
```

The report values were cross-checked against the CSV-derived paired-ratio calculations, run `summary106.json`, and the `public_gate106.json` results. Public/performance, tiny JSONTestSuite/performance, synthetic stress, and conformance are distinct strata; they are not merged.

## 7. Historical context and fair baseline framing

Test 106 measures a **specific release candidate** against a **specific official baseline**. In the prior Cloud-V campaigns, a +62.90% gain was recorded in Test 101 on the same 18 documents under an earlier benchmark harness. Test 106 records +60.07%; the difference between campaigns **does not establish a VectorPath source regression**. Test 106 internally compiles old A2 and stable VectorPath to identical ELF hashes. Other historical results, such as Test 89 around +64.1%, used different public/exploratory workloads and an official VLS256 rather than this fallback baseline; those gains are not strictly comparable.

The final report should quote **Test 106 confirmation figures** for the delivered release candidate and keep any historical peak figures explicitly tied to their original corpus, baseline, and protocol. No runtime statistical significance analysis was provided that would justify interpreting sub-1% cross-campaign differences as a source-level slowdown.

## 8. CI, security, and final release sign-off (updated 18 October 2026)

GitHub Actions [**Fuzz and run valgrind #78**](https://github.com/MA-Gustave/Simdjson-rvv-vla/actions/runs/39155386567) completed successfully in **22m 31s** on commit `81c6b1c150a73925894c5f5863d2892cc0a1ec4c`, the same commit associated with the earlier failed #74. Runs #75–78 were shown green. The precise root cause of #74 was **not independently established**. A transient external upload failure is a hypothesis, not a confirmed diagnosis.

The successful #78 steps visibly include sanitizer-backed fuzzing, differential implementation fuzzing, and Valgrind replay with `build-replay/fuzz/fuzz_*`. The supplied log excerpt reports **zero memory errors and fully freed heaps in five complete Valgrind processes**. The complete `valgrindresults` archive was **not inspected**. The workflow may not propagate every Valgrind exit code through a `tee` pipeline without `pipefail` and a nonzero `--error-exitcode`, so the green step alone is not a proof of zero errors in all Valgrind replays.

**Scope limit:** #78 runs in the **separate `Simdjson-rvv-vla` repository on Ubuntu/x86**, using the default implementation; source/commit identity with the frozen VectorPath-RVV distribution was **not established**, nor is this native-RISC-V Valgrind coverage. The native Test 106 performance and conformance evidence comes from separate pinned builds on Cloud-V and EPCC. We therefore report performance and conformance qualification **PASS**, and describe #78 as **related-project supporting CI evidence** rather than claiming native RVV memory-safety certification.

**Recommended release configuration:**

```text
RVV implementation      : RVV-VLA
Adaptive dispatch       : A2 (level 2)
Adaptive min size       : 16,384 bytes (16 KiB)
Packed paths            : disabled
Stage 2 decoder         : original/stable
SIMPLE_RUN / NL4         : both off by default
```

**Distribution status:** frozen A2 source tree prepared for maintainer publication and tagging. GitHub commit/tag creation and formal maintainer sign-off remain external steps. The package does not certify native RVV Valgrind safety.

## 9. Limitations

1. **Comparative scope:** the reference is official simdjson **v5.0.4 fallback**, not every official SIMD backend nor a comparison with x86 AVX2/AVX-512.
2. **Corpus scope:** 18 original JSON documents are the primary performance population; 95 extremely small valid standardized fixtures behave differently. The measured geometric mean is not a workload-agnostic performance guarantee.
3. **Compiler/platform scope:** GCC Cloud-V and Clang EPCC are not a fully controlled same-compiler/same-CPU experiment; gains should be presented individually.
4. **Repeated measurement scope:** numerous timed rows improve precision within these fixed environments, but do not represent that many statistically independent JSON files or hardware platforms. Exact confidence intervals were not calculated.
5. **Correctness scope:** no disagreement in this finite JSONTestSuite is not proof of the absence of all parsing defects. Dedicated fuzz/Valgrind checks are still required for release claims.
6. **Experimental paths:** SIMPLE_RUN and NL4 stress-case gains depend on synthetic escape distributions; NL4 regresses on the Cloud-V public corpus and remains excluded from the standard shipping configuration.

## Appendix A. Files that support this report

Both Test 106 archive sets include: `results106.csv`, `summary106.json`, `status106.json`, `builds106.json`, `machine106.json`, `inputs106.json`, `public_gate106.json`, `corpus_manifest106.json`, `conformance_manifest106.json`, `conformance106.csv`, `conformance106.json`, `REPORT_106.md`, and `test106_results.zip`. The separate `TEST107_FORMAL_RELEASE_AUDIT_EN.md` documents a subsequent offline evidence gate; it did **not** rerun native code.

## Appendix B. Suggested publication claim

> On 18 pinned public JSON documents, the stable VectorPath-RVV A2 configuration achieved geometric-mean DOM throughput **1.6007×** that of official simdjson v5.0.4 fallback on Cloud-V and **1.8946×** on EPCC (**+60.07%** and **+89.46%**, respectively). In a same-run A/B qualification, the stable release-candidate binaries were byte-identical to the established A2 reference on each machine and satisfied the predefined public-corpus non-regression criteria. Validity checks covering 340 standardized cases per target found no cross-variant or expected-verdict mismatches. Very small JSON workloads remained slower than the official fallback, and a related fork's later x86 fuzz/Valgrind CI run (#78) passed at commit 81c6b1c; native RVV Valgrind verification was not demonstrated.

---
**Report prepared from archived Test 106 evidence and the later user-provided GitHub Actions #78 records; no additional native benchmark execution is claimed.**
