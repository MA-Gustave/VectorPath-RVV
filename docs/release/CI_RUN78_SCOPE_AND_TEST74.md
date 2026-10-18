# GitHub Actions — evidence and limits (2026-10-18)

| Run | Repository | Commit | Outcome |
|---|---|---|---|
| #74 | MA-Gustave/Simdjson-rvv-vla | `81c6b1c150a73925894c5f5863d2892cc0a1ec4c` | FAIL (root cause not confirmed) |
| #75–#78 | same repository, reported green | #78 explicitly same commit | PASS |
| [#78](https://github.com/MA-Gustave/Simdjson-rvv-vla/actions/runs/39155386567) | same repository | `81c6b1c150a73925894c5f5863d2892cc0a1ec4c` | PASS, 22m 31s job |

## #78 successful workflow stages

- Compiled variants and executed the default-implementation fuzzers with sanitizers and assertions.
- Executed differential implementation fuzzers with sanitizers and assertions.
- Replayed some minimized-corpus files through Valgrind 3.22.0 using `build-replay/fuzz/fuzz_*` binaries.
- Stored fuzzing corpus and Valgrind output as GitHub Actions artifacts.

Artifact SHA-256 values **as displayed by GitHub** (these are not source commit hashes):

- `valgrindresults`: `cee39ccf2f7900216f4f96d78e2a8767f68534ee10cd4229e76c3c4a21b587cd`
- `corpus`: `cf78ebea517aa26f76412e222032e4ecb15b3a53452ace7800ef8b61f0e0f8c1`

## Direct log inspection

The user-provided excerpt shows `ERROR SUMMARY: 0 errors from 0 contexts` and full heap deallocation in **five complete Valgrind processes**. Warnings `sort: write failed: 'standard output': Broken pipe` occur with the script's `sort|head -n200` shell pipeline and are not by themselves a Valgrind memory-error diagnostic.

The full `valgrindresults` artifact was **not obtained**; therefore this is not a claim that all replay processes were independently audited. A green CI stage can also fail to propagate every Valgrind exit code when piped through `tee` without `pipefail` or `--error-exitcode`; do not overstate this evidence.

**Critical distinction:** workflow #78 belongs to `Simdjson-rvv-vla` and ran on GitHub-hosted Ubuntu/x86 using the *default implementation*, whereas native Test 106 ran the frozen **VectorPath-RVV RVV-VLA** fork on Cloud-V and EPCC. Cross-repository source identity and native RVV Valgrind coverage have **not been established**.

Recommended publication wording: *“The related simdjson fork's fuzzing and x86 Valgrind GitHub Actions workflow completed successfully at commit 81c6b1c; native VectorPath performance and conformance were independently validated in Test 106. Native RVV Valgrind testing was not reported.”*
