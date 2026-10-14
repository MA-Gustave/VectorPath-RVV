# RVV-VLA / simdjson 5.0.3 source integration

- Upstream tag: `v5.0.3`
- Upstream commit: `bf89ddd00ef5fcb6a7f20611ea8853d258b67249`
- RVV backend: added as a new experimental target, native correctness **not yet validated**.
- Fresh installation: no pre-v5 generic headers or core files copied.
- Streaming modes: VLA mode handlers imported from the v5 upstream filter algorithms.
- GCC function-target RVV dispatch: requires native GCC 14.2 and Clang 20.1.2 verification.
- No retrocompatibility or pre-v5 benchmark data in the active source tree.

## Native verification required before promotion

```sh
python3 scripts/rvv/run_tests.py --compiler gcc --profile global --suite rvv
python3 scripts/rvv/run_tests.py --compiler clang --profile global --suite rvv
python3 scripts/rvv/run_tests.py --compiler gcc --profile dispatch --suite rvv
```

Check both `rvv` and `rvv_vls` at runtime and rerun performance baselines on v5.0.3.
