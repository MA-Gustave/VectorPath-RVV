# Native simdjson 5.0.3 RVV-VLA performance laboratory

Reference: simdjson v5.0.3, pinned commit `bf89ddd00ef5fcb6a7f20611ea8853d258b67249`.

Run on native RVV 1.0 hardware, not under QEMU for performance claims.

```sh
python3 scripts/rvv/perf/bench_native.py preflight --compiler gcc
python3 scripts/rvv/perf/bench_native.py all --compiler gcc --profile quick --vls-bits 256
```

Candidate variants: `current`, `sparse-index`, `packed-index`.
The upstream comparison uses the same v5.0.3 source version and the best
available RVV-VLS fixed-width configuration. Stage 1, Stage 2 and DOM
measurements must be labeled independently. Compiler configuration, binary
hashes and the selected implementation must be recorded.

The experiments are not a correctness certificate. First run the native
RVV tests under GCC global, Clang global and GCC dispatch profiles.
