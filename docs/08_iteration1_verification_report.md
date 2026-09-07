# PanoPilot — Iteration-1 Verification Report

Status: **PASS — ITERATION 1 CLOSED**  
Baseline: IVR-0.1  
Product release: PanoPilot 0.44.0  
Acceptance evidence: PanoPilot 0.43 reference-system acceptance run

---

# 1. Result

All **208 normative Iteration-1 requirements are PASS**.

```text
PASS       208
PARTIAL      0
OPEN         0
```

# 2. Reference System

- Qualified: yes
- Operating system: Fedora Linux 44 (Workstation Edition)
- Platform: Linux-7.1.4-204.fc44.x86_64-x86_64-with-glibc2.43
- Python: 3.14.7
- Machine: x86_64
- Graphics qualification: AMD Radeon 890M / Strix

# 3. Source Qualification

Supported profile:

```text
dji-osmo360-dual-1920-hevc-100fps-v1
```

Qualified Source Recordings: **3**

Qualified durations:

```text
17.685 s, 6.016 s, 0.661 s
```

The distributed certificate intentionally excludes Source paths, media
fingerprints, and preview-cache paths.

# 4. Quantitative Results

| Requirement | Measurement | Limit | Result |
|---|---:|---:|---|
| `SYS-CAM-009` Camera equivalence | 0.043536 source px | ≤ 0.05 source px | PASS |
| `SYS-AUDIO-003` Preview A/V sync | 35.000 ms worst case | ≤ 100 ms | PASS |
| `SYS-PERF-001` Camera response | 12.769 ms worst Clip p95 | ≤ 100 ms p95 | PASS |
| `SYS-PERF-002` Scrub response | 101.393 ms worst Clip p95 | ≤ 250 ms p95 | PASS |
| `SYS-MEDIA-001` Supported OSV profile | 3 qualified recordings | all sources conform | PASS |

# 5. Closure Statement

The PanoPilot Iteration-1 requirements baseline is **formally closed**.

No Iteration-1 requirement remains OPEN or PARTIAL. Future functionality shall
be introduced as a subsequent requirements baseline rather than silently
changing the closed Iteration-1 acceptance criteria.

Machine-readable sanitized evidence is stored in:

```text
docs/iteration1_acceptance_certificate.json
```

Future acceptance evidence can be certified with:

```bash
panopilot acceptance-certify \
  results/acceptance-043.json \
  --output results/iteration1-acceptance-certificate.json
```
