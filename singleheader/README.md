# Single-header distribution — VectorPath-RVV

`simdjson.h` and `simdjson.cpp` were regenerated for the 2026-10-18 A2 stable release candidate using `python singleheader/amalgamate.py --quiet`.

**Important:** the previous snapshot's amalgamator omitted the separate `rvv` (VLA) implementation; the updated generator includes it. The regenerated files now use the same A2 / 16 KiB packed-off defaults as `src/rvv/engines/engine_plan.h`.

Compile `singleheader/simdjson.cpp` alongside your program with your RISC-V compiler targeting RVV. The optional flags `SIMDJSON_VECTORPATH_STAGE2_SIMPLE_RUN` / `SIMDJSON_VECTORPATH_STAGE2_NL4` default to zero and remain experimental. See `README-VECTORPATH-RELEASE-CANDIDATE.md`.

Portable smoke test: `python3 scripts/rvv/release_candidate_check.py --compiler g++`. This checks fallback behaviour only; a separate RVV-native validation is mandatory before a shipping claim.
