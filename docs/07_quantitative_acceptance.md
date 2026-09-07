# PanoPilot — Iteration-1 Quantitative Acceptance

Status: **PASS — Reference-System Execution Complete**  
Baseline: QA-0.2  
Scope: Iteration 1  
Parent: `03_system_requirements.md`

---

# 1. Purpose

This document defines the repeatable field-verification procedure for the
remaining quantitative requirements.

All functional implementation requirements are closed. The reference-system
run provides the final performance and A/V evidence.

# 2. Reference System

The designated reference machine is the Fedora workstation/laptop used for
PanoPilot development with AMD Radeon 890M / Strix graphics.

`panopilot acceptance-run` records the operating-system and GPU detection
evidence. `SYS-PERF-001` and `SYS-PERF-002` are qualified only when that
reference-system check succeeds.

# 3. Resolved Acceptance Constants

| Identifier | Acceptance value |
|---|---:|
| `SUPPORTED-OSV-PROFILE-001` | `dji-osmo360-dual-1920-hevc-100fps-v1` |
| `CAMERA-EQUIVALENCE-001` | maximum 0.05 source-panorama pixel |
| `CAMERA-RESPONSE-001` | p95 ≤ 100 ms |
| `SCRUB-RESPONSE-001` | p95 ≤ 250 ms |
| `PREVIEW-AV-SYNC-001` | ≤ 100 ms |

# 4. Execution

From the PanoPilot virtual environment:

```bash
panopilot acceptance-run \
  results/panopilot_project.json \
  --report results/acceptance-043.json
```

The command:

1. confirms the runtime is the Fedora / AMD Radeon 890M reference environment;
2. validates every Project source against the qualified OSV profile;
3. evaluates preview/final Virtual Camera map equivalence for 720p and 1080p,
   portrait and landscape;
4. prepares or reuses the normal 1280×640 @20 fps panoramic preview cache;
5. measures cached-preview audio/video start and end timing;
6. measures ready-preview Virtual Camera response latency;
7. performs deterministic random scrub seeks and measures seek-to-frame
   latency;
8. writes a machine-readable JSON report.

The command exits with status 0 only when all five quantitative requirements
pass on the qualified reference system.

# 5. Measurement Definitions

## 5.1 Camera response

Start: immediately before the conventional preview render requested by a
Virtual Camera state change.

End: the conventional 800-pixel-long-edge BGR frame has completed rendering.

The panoramic cache is already decoded and ready before timing begins.

## 5.2 Scrub response

Start: immediately before a random Source-Time request is issued to the
panoramic cache reader.

End: after the requested cached frame has been decoded and reframed to the
800-pixel-long-edge conventional output.

## 5.3 Preview A/V synchronization

The acceptance suite compares the first video and audio stream start times and
their computed end times. The maximum absolute start/end delta is the measured
error.

During interactive Project Preview, Qt Multimedia audio position is used as the
playback clock when available; the video frame follows that media position.

## 5.4 Camera equivalence

The float64 Preview reference equirectangular source map is compared with the
optimized float32 `RectilinearProjector` used by final rendering.

Horizontal map error is seam-aware. The reported quantity is source-panorama
pixel displacement.

# 6. Closure Rule

Iteration 1 can be declared quantitatively closed only when:

```text
SYS-MEDIA-001  PASS
SYS-CAM-009    PASS
SYS-AUDIO-003  PASS
SYS-PERF-001   PASS on qualified reference system
SYS-PERF-002   PASS on qualified reference system
```

The generated `acceptance-043.json` is the final field-verification evidence.


---

# 7. Reference-System Result

The designated reference-system run completed successfully.

| Gate | Measured | Limit | Result |
|---|---:|---:|---|
| Supported OSV profile | 3/3 sources qualified | all sources | PASS |
| Preview/final Camera equivalence | 0.043536 source px | ≤0.05 source px | PASS |
| Preview A/V sync | 35.000 ms worst case | ≤100 ms | PASS |
| Camera response | 12.769 ms worst Clip p95 | ≤100 ms p95 | PASS |
| Random scrub response | 101.393 ms worst Clip p95 | ≤250 ms p95 | PASS |

Reference-system qualification: **PASS**.

The original raw field report remains an execution artifact. The distributable
PanoPilot baseline contains only sanitized evidence in
`iteration1_acceptance_certificate.json`.

Iteration-1 quantitative acceptance is closed.
