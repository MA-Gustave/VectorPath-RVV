# VectorPath-RVV RC — local verification log (2026-10-18)

**Inputs:** `znapshot_VectorPath-RVV_10180838.zip` (verified original core source fingerprint). **Output:** A2 / 16 KiB / packed-off RC with optional Stage 2 experimental macros.

## Completed here

- [PASS] Original fork `src/simdjson.cpp` SHA-256 unchanged: `fdaea284a48b30ab3e912e1cd3580e920fe186a229faabba97d9b24eed095e16`.
- [PASS] Standalone portable profile tests: A2=2 / 16 KiB / all packed OFF; legacy A0 packed-on explicit override still compiles.
- [PASS] GCC 14.2 x86_64 fallback: normal multi-file `src/` build `stable`, `SIMPLE_RUN`, `NL4`. DOM outputs agree for 13 inputs including escaping/Unicode/long strings/malformed JSON and source corpus.
- [PASS] GCC 14.2 x86_64 fallback: regenerated `singleheader/simdjson.cpp` plus `.h`; same three variants and same 13 inputs agree with `src/`.
- [PASS] Clang 17.0 x86_64 fallback: normal multi-file `src/` build same three variants and 13 cases.
- [PASS] Native x86_64 CMake Debug static library target `simdjson` builds without errors.
- [PASS] Standalone RVV-VLA amalgamation now completes, with reproducible `SOURCE_DATE_EPOCH=1792281600` source timestamp; previously the snapshot's generator omitted `rvv` and rejected a missing conditional-include comment.

## NOT completed here

- [ ] Native RVV-VLA compile and execution on Cloud-V (GCC) or EPCC (LLVM16).
- [ ] Full 18-public-JSON + JSONTestSuite native correctness validation.
- [ ] RISC-V On-Demand/streaming + 8/9-backslash boundary tests.
- [ ] Native public-DOM performance regression comparison against the **same earlier A2 build under the same compiler/machine**.
- [ ] Experimental Stage 2 promotion (intentionally not default; no new release gain claimed).

**Do not describe these host-only tests as RISC-V certification.** The release gate and provenance plan are in `docs/VECTORPATH_RC_VALIDATION.md`.
