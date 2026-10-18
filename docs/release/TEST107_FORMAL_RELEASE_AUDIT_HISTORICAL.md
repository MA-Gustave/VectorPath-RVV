# Test 107 — Formal release qualification (evidence audit)

**Scope:** An independent audit of completed Test106 evidence. **No native code was executed by Test107.**

| Target | Stable vs simdjson 5.0.4 fallback | Stable vs original A2 | Worst document vs A2 | Test106 rows | JSONTestSuite |
|---|---:|---:|---:|---:|---:|
| Cloud-V | +60.07% | +0.001% | -0.24% | 92,435 | 340 / 340 |
| EPCC | +89.46% | -0.041% | -0.30% | 75,400 | 340 / 340 |

**Engine qualification:** PASS
**Release authorization:** HOLD_CI_AND_RELEASE_SIGNOFF
**CI proof:** NOT_VERIFIED

The A2 original and VectorPath stable binaries are byte-identical on each machine.
The 18 public JSON input digests and harness hashes are identical across targets.
Test106 paired rows audited: 167,835.

## CI / safety qualification

GitHub Actions #74 failed and the exact failing step is not independently established. Fuzz/Valgrind not proven green.

A historical CI failure neither invalidates these completed native benchmarks nor certifies fuzzing/Valgrind.
A green workflow in another repository/commit is **not** proof that the frozen VectorPath sources passed fuzzing and Valgrind.

## Release rules

1. Keep A2 / 16 KiB / packed OFF, original Stage 2. SIMPLE_RUN and NL4 remain optional.
2. Do not modify the frozen VectorPath source tree unless a correctness defect is found.
3. Verify fuzz/Valgrind or independent equivalent against the actual release candidate before final ship sign-off.
4. Tag the exact git commit and archive SHA256. A code change after this audit requires relevant requalification.
5. Do not reinterpret Test89 (+64.1% vs a different baseline/corpus) as a regression against Test106.

## Artifact provenance

- Pinned Test106 RC patch SHA256: `513dbf6ea2241d469ade18a354e18a77303d66ce9d6794fb8595ee59e01f0388`
- VectorPath distribution SHA256: `39377f4a106ae4eaadc9d8377ec8c7b8ffacdcf80eaa3eec2c13b015aea22c09`

- Cloud-V: evidence `cb0808f0fdc95d2cda99039af78abe8b91349c1d74832254c21df52ac2258168`; stable binary `87e658bd1be322dd41a92e42a60d0d41308819dac9af188ac535f138c93b555f`
- EPCC: evidence `d670d27d0811c97dae1427921ed19e397046d01c15de830fa447a95d9bd0b25a`; stable binary `9c965fb58f31053f0b9a1cfc54e051d8787ab59d4eda307bb6878a78023ecddb`
