# Test 98 — Pinned public JSON benchmark corpus

This repository contains the **corpus acquisition/verification tool**, not the corpus bytes.
The experiment runner and Slurm/Cloud-V orchestration live in **VLA-MethodLab**.

## Upstream and scientific scope

- Dataset: [simdjson/simdjson-data](https://github.com/simdjson/simdjson-data), pinned Git commit `4197c425e857f0ec38e89822fdd0bd9ea21f4daf`.
- Subset: 18 named, unmodified `.json` examples from `jsonexamples/`; excludes `random.json`, `repeat.json` and NDJSON.
- This is a **published/common JSON parser fixture collection**. It contains API-derived, catalog, geographic, numeric, structured and illustrative examples. It is **not** a representative random sample of production traffic.
- Individual source file SHA256, byte size, upstream Git commit and original path are written into `manifest.json` inside the ZIP.
- Sources are not modified/reformatted. The tool verifies every file is valid as **one complete JSON document**.
- Corpus ZIP and extracted data are ignored by Git. Before redistributing files, check each upstream file's licensing/provenance. The upstream dataset README does not provide a blanket redistribution license.

## Local corpus preparation (Windows/Linux/macOS; network required)

```bash
python tools/corpus98.py prepare --cache .cache/test98-corpus
```

On the *first* invocation it downloads the 18 selected originals through immutable Git-commit-specific HTTPS URLs, validates full JSON syntax, builds a ZIP and checks every SHA256. On later invocations it reuses the verified ZIP without fetching anything. **Network failure is a hard failure; it never generates replacement JSON.**

To inspect the manifest and SHA256:

```bash
python tools/corpus98.py verify .cache/test98-corpus/simdjson-data-4197c425-test98.zip
```

## EPCC and Cloud-V distribution

In VLA-MethodLab, run **Test 98 — Corpus public simdjson-data : RVV vs officiel (EPCC / Cloud-V)** under the appropriate existing SSH profile. Studio automatically prepares the archive on the PC and SFTP-transfers the **same exact ZIP** to the currently selected destination. It compares SHA256 before upload, after upload, and after extracting per-document data in a remote content-addressed cache:

```text
~/rvvlab-v5/corpora/test98/<zip-sha-prefix>/
    simdjson-data-4197c425-test98.zip
    corpus98.py
    data/simdjson-data-4197c425-test98/
        manifest.json
        files/*.json
```

Transfer once to EPCC using the EPCC profile; once to Cloud-V using the Cloud-V profile. Later tests on either machine reuse the corresponding verified cache. **Studio does not silently connect to a second server or copy credentials between profiles.**

## Comparison methodology

The experiment builds published simdjson v5.0.3 and v5.0.4 (official `fallback`), and fork A2 (thresholds 4096/8192, `rvv`). Four parser builds process the **identical corpus files** via the common DOM API on the **same compute node** in randomized paired order.

The headline ratio is the geometric mean of **per-file** paired throughput ratios, with equal weight for each original document; raw per-file ratios are mandatory. Measurement repetition reuses the same files and **is not an unseen-data holdout**. Report the machine/CPU, compiler, source commits and backend differences; the RISC-V upstream fallback-versus-RVV comparison does not isolate algorithm changes.

## Integrity and run safety

- New jobs are started only by selecting Test98 and clicking Run in the chosen profile.
- Reopening a previous Test98 on the same profile shows its status or downloads its packet; no automatic re-submission.
- Any missing file, SHA256 mismatch, Git/source mismatch, build failure, compilation incompatibility, or wrong architecture blocks the benchmark.
- No `git add` for corpus ZIPs, no synthetic performance-input fallback, and no automatic promotion of source changes.
