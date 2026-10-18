# Final publication / release sign-off (maintainer action)

1. Verify this source package has the intended licences and ownership/provenance notices. They were **preserved unchanged** from the repository snapshot; this package makes no new licensing determination.
2. Commit the complete extracted source tree to **VectorPath-RVV**, not MethodLab or the separate Simdjson-rvv-vla repository. Inspect `git status` / `git diff` and ensure no unreviewed local changes are mixed in.
3. Choose a tag (suggestion only: `vectorpath-a2-2026.10.18`) **after** confirming the actual Git commit. Record that Git commit in the public report/README; this package does not invent one.
4. Verify `SHA256SUMS_RELEASE.txt` and the five Test106-pinned C++ hashes. Do not change source C++ after the Test106 audit without running relevant checks.
5. Publish source and the **separate evidence bundle**. Cite public-document geometric mean +60.07% Cloud-V and +89.46% EPCC **versus simdjson 5.0.4 fallback**, not versus all upstream SIMD implementations.
6. Document tiny-JSON limitations; reserve SIMPLE_RUN / NL4 for optional research.
7. Document CI #74 as one unexplained historical failure; #75–78 passed and #78 is on the same commit. Do not misattribute separate-repository x86 CI as native VectorPath RVV Valgrind.
8. If your policy requires native-RVV memory-safety verification, explicitly mark it outstanding or run it before making a stronger claim.
9. Keep MethodLab's historical `engine/` and results pinned; **do not replace it with this source distribution**.

**Result:** source frozen and ready for publication; GitHub push, Git tag and formal maintainer sign-off remain external actions.
