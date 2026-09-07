# PanoPilot — Technical Spikes

Status: Draft  
Baseline: TS-0.17
Scope: Iteration 1 Architecture Validation  
Parent: `04_functional_architecture.md`

---

# 1. Purpose

This document defines the technical spikes required before PanoPilot software
architecture is baselined.

The purpose of the spikes is to reduce architecture risk through executable
evidence rather than assumption.

The spikes shall validate the three most architecture-driving technical
questions:

1. Can representative DJI Osmo 360 `.OSV` recordings be interpreted and made
   available as a usable panoramic representation on Fedora?
2. Can the panoramic representation be reframed interactively through one
   canonical Camera Model with acceptable responsiveness?
3. Can the same source-time Camera Positions and View Path semantics be used
   to produce a conventional final MP4 whose framing corresponds to preview?

The spikes are intentionally narrow.

They are not intended to implement the production application.

---

# 2. Spike Principles

The following rules apply to all technical spikes.

## SP-PR-001 — Risk First

Each spike shall answer one or more architecture-driving risks.

The spike shall not expand into unrelated product implementation.

---

## SP-PR-002 — Disposable Implementation

Spike code may be replaced after the architecture decision.

Code quality shall be sufficient to:

- understand the experiment;
- repeat the experiment;
- measure the result;
- preserve useful discoveries.

Production abstractions are not required unless they are directly under test.

---

## SP-PR-003 — Representative Media

Spikes shall use real representative DJI Osmo 360 media rather than only
synthetic test data.

Where useful, synthetic inputs may supplement real media for deterministic
camera-math tests.

---

## SP-PR-004 — Measurable Exit Criteria

Each spike shall define explicit success/failure evidence.

A spike is not complete merely because "something works."

---

## SP-PR-005 — Preserve Artifacts

Each spike shall preserve:

- source sample identity;
- commands/scripts used;
- environment information;
- observations;
- measurements;
- output artifacts;
- unresolved issues;
- architecture decisions enabled by the spike.

---

## SP-PR-006 — No Product Scope Creep

The spike implementation shall not introduce:

- timeline editing;
- Project persistence;
- Undo/Redo;
- multi-track editing;
- transitions;
- titles;
- AI functions;
- polished production UI

unless directly required to answer the technical question.

---

# 3. Architecture Risks Covered

| Risk | Description | Covered By |
|---|---|---|
| RISK-01 | DJI OSV interpretation | SPIKE-01 |
| RISK-02 | Interactive panoramic preview | SPIKE-01, SPIKE-02 |
| RISK-03 | Preview/render equivalence | SPIKE-02, SPIKE-03 |
| RISK-04 | Camera interpolation and panoramic wrap | SPIKE-03 |
| RISK-05 | Audio and time mapping | SPIKE-01, SPIKE-03 |
| RISK-06 | Output normalization across source characteristics | SPIKE-03 |

---

# 4. Recommended Spike Workspace

```text
spikes/
├── README.md
├── samples/
│   └── README.md
│
├── spike_01_osv_panorama/
│   ├── README.md
│   ├── src/
│   ├── scripts/
│   ├── results/
│   └── notes.md
│
├── spike_02_virtual_camera/
│   ├── README.md
│   ├── src/
│   ├── results/
│   └── notes.md
│
└── spike_03_viewpath_render/
    ├── README.md
    ├── src/
    ├── scripts/
    ├── results/
    └── notes.md
```

The `samples/` directory should normally contain references or local paths to
test media rather than committing large camera files to source control.

---

# 5. Test Environment Record

Before executing the spikes, record the reference environment.

At minimum:

```text
Operating system:
Fedora version:
Kernel:
CPU:
RAM:
GPU:
GPU driver:
FFmpeg version:
ffprobe version:
Python version:
Browser/WebView version if applicable:
Relevant GPU APIs available:
PanoForge revision/reference:
```

The exact environment shall be copied into each spike result.

This allows future performance results to be interpreted correctly.

---

# 6. Representative Source Set

A minimum source set should include at least one real `.OSV` file.

Before software architecture is finalized, a broader validation set should
eventually include recordings with variation in:

- duration;
- motion;
- scene complexity;
- lighting;
- audio availability;
- source frame rate;
- source resolution;
- camera firmware if multiple firmware versions are available.

For the first execution, one representative file is sufficient to begin.

---

# 7. SPIKE-01 — OSV to Navigable Panorama

## 7.1 Objective

Demonstrate that representative DJI Osmo 360 `.OSV` media can be:

1. inspected;
2. interpreted;
3. transformed or exposed as a panoramic video representation;
4. navigated visually on the Fedora reference system.

This spike validates the Panoramic Source Adapter boundary.

---

## 7.2 Architecture Questions

SPIKE-01 shall answer:

1. What streams exist in the representative `.OSV`?
2. Which streams contain source video, audio, calibration, and DJI metadata?
3. Can the source be interpreted without manual User conversion?
4. Can PanoForge logic be reused or adapted for source inspection and
   panoramic reconstruction?
5. Is calibrated stitching usable with the representative source?
6. What fallback reconstruction path is available if calibrated processing
   fails?
7. Can a practical preview representation be produced?
8. Can source audio be discovered and associated with source timing?
9. What source timing basis should be treated as authoritative?
10. What source-specific behavior should remain isolated inside the DJI OSV
    Adapter?

---

## 7.3 Non-Goals

SPIKE-01 does not need:

- Project support;
- multiple Clips;
- Camera Positions;
- View Path interpolation;
- trimming UI;
- final MP4 export;
- polished desktop UI.

---

## 7.4 Input

Minimum:

```text
1 representative DJI Osmo 360 .OSV recording
```

Optional:

```text
corresponding .LRF file, if available
```

---

## 7.5 Investigation Steps

### Step 1 — Inspect Container

Use `ffprobe` or equivalent inspection to record:

- container information;
- all video streams;
- audio streams;
- metadata/data streams;
- codec;
- pixel format;
- width/height;
- frame rate;
- time base;
- duration;
- stream start times.

Save the inspection result into:

```text
spikes/spike_01_osv_panorama/results/ffprobe.json
```

---

### Step 2 — Identify DJI Metadata

Determine whether the sample exposes DJI metadata required by the existing
PanoForge approach.

Record:

- stream/index containing DJI metadata;
- available calibration information;
- timing relationship between metadata and video;
- whether parsing works unchanged or requires adaptation.

---

### Step 3 — Reconstruct Panorama

Attempt the preferred reconstruction path.

Conceptually:

```text
OSV
 ↓
DJI OSV Adapter
 ↓
lens streams + calibration
 ↓
stitch / remap
 ↓
Panoramic Video Representation
```

Evaluate:

- seam quality;
- orientation;
- obvious geometric distortion;
- temporal stability;
- performance.

---

### Step 4 — Evaluate Fallback

If the calibrated path cannot process the file, evaluate a geometric
fallback sufficient to determine feasibility.

The fallback is an experiment, not necessarily the production choice.

---

### Step 5 — Produce Preview Representation

Create or identify a representation that can support interactive preview.

Possible candidates include:

- lower-resolution stitched H.264;
- `.LRF`;
- another derived panoramic stream.

Record:

- dimensions;
- codec;
- frame rate;
- generation time;
- approximate file size;
- seek behavior.

---

### Step 6 — Navigable Viewer

Display the panoramic representation through a minimal viewer capable of:

- looking left/right;
- looking up/down;
- zooming.

No production UI is required.

The viewer exists only to prove that the panorama is usable as an input to
SPIKE-02.

---

## 7.6 Required Measurements

Record at minimum:

| Metric | Result |
|---|---|
| Source duration | TBD |
| Source video stream count | TBD |
| Source audio streams | TBD |
| Source codec/pixel format | TBD |
| Source frame rate | TBD |
| Preview dimensions | TBD |
| Preview frame rate | TBD |
| Preview generation time | TBD |
| Preview size | TBD |
| Approximate seek latency | TBD |
| Reconstruction CPU/GPU path | TBD |

---

## 7.7 Success Criteria

SPIKE-01 passes when:

- a representative `.OSV` is accepted without manual preconversion;
- source video structure is understood;
- source audio availability/timing is understood;
- a panoramic representation is produced or exposed;
- the panoramic output is visually usable;
- the surrounding 360 environment can be navigated;
- the necessary DJI-specific logic can be isolated conceptually behind the
  Panoramic Source Adapter;
- unresolved issues are documented.

---

## 7.8 Failure Criteria

SPIKE-01 fails or remains open if:

- the representative `.OSV` cannot be interpreted reliably;
- panoramic reconstruction is unusably distorted;
- source timing cannot be determined;
- no practical preview representation can be generated or consumed;
- required DJI-specific information is unavailable.

A failed spike is still useful if it clearly identifies the blocking
technical assumption.

---

## 7.9 Deliverables

```text
results/ffprobe.json
results/source_notes.md
results/panorama_preview.<ext>
results/screenshots/
results/performance.md
notes.md
```

The spike README shall end with:

```text
PASS / FAIL / PARTIAL

Architecture implications:
- ...
- ...

Open questions:
- ...
```

---

# 8. SPIKE-02 — Interactive Canonical Virtual Camera

## 8.1 Objective

Demonstrate a responsive conventional camera view driven by the canonical
Camera Model.

This spike validates the interaction path:

```text
Panoramic Video Representation
             +
        Camera State
             +
        Output Profile
             ↓
       Conventional Preview
```

---

## 8.2 Architecture Questions

SPIKE-02 shall answer:

1. What exact canonical coordinate system should PanoPilot use?
2. What is zero orientation?
3. What axis convention and handedness are used?
4. What does positive horizontal/vertical motion mean?
5. What FOV convention is authoritative?
6. What horizon/roll convention is authoritative?
7. Can one Camera State produce predictable 16:9 and 9:16 framing?
8. Can mouse interaction update the camera with acceptable latency?
9. Can the Camera Model be implemented independently from source-format logic?
10. Can the state representation later be consumed by the final renderer?

---

## 8.3 Canonical Camera Contract to Resolve

SPIKE-02 must produce a written proposal for:

```text
CameraState
├── orientation
├── field_of_view
└── horizon_orientation
```

and define:

```text
reference frame
axis directions
handedness
zero view
positive rotations
FOV convention
FOV limits
horizon convention
wrap normalization
```

The spike may internally use any practical representation.

The output contract is more important than the storage format.

---

## 8.4 Minimal Interaction

Required controls:

```text
mouse drag horizontal
    → horizontal view movement

mouse drag vertical
    → vertical view movement

mouse wheel
    → FOV change

Reset View
    → canonical default Camera State
```

Exploration shall remain temporary.

No Camera Position is committed automatically.

---

## 8.5 Output Profiles

Test at least:

```text
16:9
9:16
```

For the spike, use explicit temporary dimensions such as:

```text
16:9 → 1920 × 1080
9:16 → 1080 × 1920
```

unless the requirement parameter `OUTPUT-PROFILE-001` has already been
baselined.

These values are experimental until the Project output policy is formally
confirmed.

---

## 8.6 Performance Measurements

Measure at minimum:

- input-event to visible-frame response;
- rendered preview frame rate;
- CPU utilization;
- GPU utilization if available;
- memory use;
- seek-to-visible-frame delay.

Run measurements on the recorded reference environment.

---

## 8.7 Success Criteria

SPIKE-02 passes when:

- horizontal drag predictably changes horizontal view;
- vertical drag predictably changes vertical view;
- wheel input changes FOV;
- Reset View is deterministic;
- 16:9 and 9:16 framing are correct;
- the Camera Model contract is documented;
- interaction is usable and measurable;
- the implementation demonstrates that Camera Model semantics can remain
  independent of DJI-specific source parsing.

---

## 8.8 Deliverables

```text
results/camera_model.md
results/performance.md
results/16x9_reference.png
results/9x16_reference.png
results/interaction_capture.<ext>
notes.md
```

The `camera_model.md` result is a required input to SPIKE-03.

---

# 9. SPIKE-03 — Source-Time View Path to Final MP4

## 9.1 Objective

Demonstrate end-to-end equivalence between source-time Camera Positions,
interactive Camera State semantics, and final conventional rendering.

This spike is the primary proof that the PanoPilot editing model can produce
the intended delivered video.

---

## 9.2 Architecture Questions

SPIKE-03 shall answer:

1. Can Camera Positions be stored using Source Time?
2. Does changing the Clip In point preserve Camera Position attachment to the
   same source event?
3. Can the View Path evaluator compute deterministic Camera State at arbitrary
   Source Time?
4. Can panoramic wrap interpolation avoid an unintended long rotation?
5. Can the final renderer consume the same Camera semantics as preview?
6. How closely does final framing match preview framing?
7. Can source audio remain synchronized through trim and export?
8. How should source frame rate be normalized to one Project output frame
   rate?
9. Can the result be delivered as conventional H.264/MP4?

---

## 9.3 Minimal Test Edit

Use one representative recording initially.

Example:

```text
Source duration: 60 s

Clip trim:
source_in  = 10 s
source_out = 30 s

Camera Position A:
source_time = 12 s

Camera Position B:
source_time = 20 s

Camera Position C:
source_time = 28 s
```

Then change:

```text
source_in = 15 s
```

Expected:

- Position A becomes inactive because it is outside trim;
- Position B still points at source event at 20 s;
- Position C still points at source event at 28 s;
- no Camera Position Source Time changes.

---

## 9.4 View Path Evaluation

The spike shall implement one deterministic interpolation model.

Required tests include:

### Ordinary interpolation

```text
A -------- B
```

Intermediate Camera State shall be deterministic.

### Panoramic wrap

Example:

```text
350° → 10°
```

The system shall select the intended short angular path rather than rotating
approximately 340°.

The exact production interpolation representation may remain open, but the
behavior must be proven.

---

## 9.5 Preview/Render Equivalence Test

Create reference timestamps:

```text
T1
T2
T3
...
```

For each timestamp:

1. evaluate `CameraState(T)`;
2. capture the interactive preview frame;
3. render the corresponding final-quality frame;
4. compare composition.

The required architecture property is:

```text
Preview(T, C, P)
≈
FinalRender(T, C, P)
```

where:

```text
T = Source Time
C = Camera State
P = Output Profile
```

The exact tolerance remains:

```text
CAMERA-EQUIVALENCE-001 = TBD
```

until the experiment provides evidence for an appropriate value.

---

## 9.6 Audio Test

The final output shall include source audio corresponding to the selected
trim interval.

Verify:

- beginning trim;
- end trim;
- output duration;
- perceptual sync;
- measured sync if practical.

Record the observed error for comparison with:

```text
EXPORT-AV-SYNC-001
```

---

## 9.7 Output Normalization Test

The architecture requires one Project frame rate.

At minimum, SPIKE-03 shall document how the renderer behaves when:

```text
source frame rate != Project frame rate
```

If multiple representative recordings with different frame rates are
available, test them.

The spike shall produce a recommendation for:

```text
OUTPUT-PROFILE-001
```

including:

- default 16:9 dimensions;
- default 9:16 dimensions;
- default Project frame-rate policy.

---

## 9.8 Success Criteria

SPIKE-03 passes when:

- Camera Positions remain source-time anchored;
- trim changes do not retime them;
- View Path evaluation is deterministic;
- panoramic-wrap behavior is correct;
- final H.264/MP4 is produced;
- the output is conventional non-360 video;
- final framing corresponds to preview framing;
- source audio is included and acceptably synchronized;
- Project output normalization policy can be recommended.

---

## 9.9 Deliverables

```text
results/viewpath_definition.md
results/time_mapping_tests.md
results/wrap_tests.md
results/preview_render_comparison/
results/output_profile_recommendation.md
results/export_test.mp4
results/audio_sync.md
notes.md
```

---

# 10. Cross-Spike Verification Assets

The following assets should be retained after the spikes and later reused as
regression tests.

## 10.1 Golden Source Samples

Representative `.OSV` recordings with documented identity and expected
properties.

---

## 10.2 Camera Math Tests

Tests for:

- zero/default orientation;
- horizontal rotation;
- vertical rotation;
- FOV;
- horizon;
- normalization;
- wrap behavior.

---

## 10.3 Time Mapping Tests

Tests for:

```text
Source Time
Clip Time
Project Time
```

including trim changes.

---

## 10.4 Source-Time Anchor Tests

Given a Camera Position at Source Time `T`:

```text
change Clip In
```

shall not alter `T`.

---

## 10.5 Preview/Render Golden Frames

Store expected preview/final reference pairs for fixed:

```text
Source Time
Camera State
Output Profile
```

These become high-value regression assets.

---

# 11. Spike Decision Record Template

Each spike shall conclude with:

```markdown
# Result

Status: PASS | PARTIAL | FAIL

## What Was Demonstrated

...

## Measurements

...

## What Was Not Demonstrated

...

## Architecture Implications

...

## Decisions Enabled

...

## Open Risks

...

## Recommendation

Proceed | Repeat Spike | Change Architecture Assumption
```

---

# 12. Exit Gate Before Software Architecture

`06_software_architecture.md` should not be baselined until the following are
true.

## Gate A — Source Feasibility

SPIKE-01 demonstrates a usable path from representative `.OSV` media to
Panoramic Video Representation.

## Gate B — Camera Contract

SPIKE-02 defines the canonical Camera Model sufficiently for both preview and
rendering.

## Gate C — Rendering Equivalence

SPIKE-03 demonstrates that one View Path model can drive preview and final
rendering consistently.

## Gate D — Output Policy

A recommendation exists for:

```text
OUTPUT-PROFILE-001
```

## Gate E — Performance Evidence

Measurements exist for:

```text
CAMERA-RESPONSE-001
SCRUB-RESPONSE-001
```

even if final acceptance thresholds remain TBR.

## Gate F — Remaining Risk Is Explicit

Any unresolved architecture-driving issue is documented before technology
boundaries are frozen.

---

# 13. Immediate Next Action

Begin:

```text
SPIKE-01 — OSV to Navigable Panorama
```

The first implementation task is intentionally narrow:

```text
Take one real DJI Osmo 360 .OSV
        ↓
inspect it
        ↓
extract/interpret the required source information
        ↓
produce a usable panoramic representation
        ↓
display it in a minimal navigable viewer
```

Do not build the Project, timeline, trim editor, View Path editor, or final
desktop shell during SPIKE-01.

The purpose of the spike is to establish technical truth for the next
architecture decision.


---

# 14. Spike Closure Status — PanoPilot 0.19

## SPIKE-01 — OSV to Navigable Panorama

**Status:** PASS for Iteration 1.

Evidence established:

- real DJI Osmo 360 OSV inspection;
- synchronized dual HEVC Main10 lens decode;
- DJI factory calibration extraction;
- 3840-calibration to 1920-source scaling;
- factory-calibrated panoramic reconstruction;
- per-frame and high-rate DJI orientation extraction;
- IMU/video timing alignment;
- spherical horizon stabilization;
- H.264 panoramic editing preview with source audio;
- disposable preview cache.

## SPIKE-02 — Canonical Virtual Camera

**Status:** PASS for Iteration 1.

Evidence established:

- canonical yaw/pitch/horizontal-FOV semantics;
- 16:9 and 9:16 rectilinear output;
- full horizontal panoramic navigation;
- Fedora GNOME/Wayland desktop interaction using PySide6;
- exploration separate from editing;
- explicit persisted Camera Positions.

## SPIKE-03 — Source-Time View Path to Conventional Output

**Status:** PARTIALLY CLOSED / final export gate remains.

Validated:

- Source-Time Camera Position persistence;
- zero/one/multiple Camera Position semantics;
- shortest-route yaw interpolation;
- configurable easing presets and easing Amount;
- Clip preview application of persisted View Path;
- project-aware conventional frame rendering;
- sequential Project Time mapping;
- multi-Clip Project Preview with active-Clip View Path evaluation.

Remaining architecture exit evidence:

- final-quality sequential MP4 from original OSV sources;
- complete Project audio assembly;
- measured preview/final framing equivalence over representative Camera Paths;
- output-profile normalization for final delivery.

The next implementation milestone shall therefore target the final sequential
render/export path rather than additional exploratory panoramic processing.


---

# 15. SPIKE-03 Final Export Implementation — PanoPilot 0.20

SPIKE-03 now has an executable original-source Project export path.

Implemented evidence:

- one Project-wide 30 fps frame clock;
- deterministic Project Time → Clip → Source Time allocation;
- original synchronized OSV dual-lens decode;
- DJI factory-calibrated panoramic reconstruction;
- final-path DJI horizon stabilization;
- persisted View Path and Camera Motion evaluation per final output frame;
- conventional 16:9 and 9:16 Output Profile rendering;
- one continuous H.264 video encode;
- original source-audio trim assembly in Project order;
- silence continuity for no-audio Clips in an otherwise audible Project;
- MP4 mux and post-render verification;
- transactional output promotion.

**Status:** IMPLEMENTED — USER MEDIA ACCEPTANCE PENDING.

SPIKE-03 shall be marked PASS after representative multi-Clip OSV Projects
confirm:

1. expected visual framing throughout final playback;
2. acceptable stitch/stabilization quality at delivery resolution;
3. correct Clip boundary order and trims;
4. A/V synchronization within `EXPORT-AV-SYNC-001`;
5. practical render completion on the Fedora reference machine.


---

# 16. SPIKE-03 Closure — PASS

The user validated the PanoPilot 0.20 final exported Project on representative
media as correct.

SPIKE-03 is therefore **PASS for Iteration 1**.

Validated end-to-end behaviors include:

- ordered multi-Clip final export;
- original OSV source rendering;
- Clip trim application;
- persisted View Path application;
- configurable Camera Motion application;
- conventional H.264 MP4 delivery.

PanoPilot 0.21 moves from feasibility validation into optimization. The first
optimization removes the intermediate full-panorama horizon resample by
composing horizon and Virtual Camera spherical mappings.

Future performance work shall preserve the now-frozen Iteration-1 semantic
baseline.


---

# 17. Post-Spike Performance Baseline — PanoPilot 0.22

All Iteration-1 feasibility spikes are closed. PanoPilot 0.22 introduces a
measurement gate for post-spike optimization.

A representative export report shall be captured before another major
render-path optimization is selected.

Primary decision candidates are expected to include:

- original lens decode throughput;
- factory calibrated stitch cost;
- composed rectilinear projection cost;
- H.264 encoder backpressure.

The actual measured dominant stage shall determine the next optimization.


---

# 18. Post-Spike Benchmark Result — PanoPilot 0.23

Representative accepted media produced the first complete performance baseline:

```text
23.7 s Project
148.04 s export
4.80 output frames/s
6.25× real-time factor
```

Measured hotspot order:

1. factory stitch — 38.2%;
2. composed projection — 29.3%;
3. source PTS setup — 26.8%;
4. lens decoder wait — 2.6%;
5. encoder write wait — 1.4%.

This measurement explicitly rules out hardware HEVC decode or H.264 encode as
the first optimization target. 0.23 therefore addresses source-PTS setup and
factory blending before introducing GPU media paths or a more invasive direct
lens projection.


---

# 19. 0.23 Benchmark Result and 0.24 Decision

The representative 0.23 export measured:

```text
total export            69.64 s
throughput               10.21 fps
real-time factor          2.94×

composed projection      73.2%
factory stitch           13.3%
decoder wait              6.1%
encoder write             3.1%
source PTS setup          ~0%
```

The CFR source-time optimization therefore closed the previous 26.8% setup
hotspot.

0.24 targets composed projection directly. Hardware video decode/encode and
direct lens-to-output fusion remain deferred because the measured projection
kernel is materially larger than either codec stage.


---

# 20. 0.24 Benchmark Result and 0.25 Decision

The representative 0.24 export measured:

```text
41.39 s total
17.18 fps
1.75× real-time factor

composed projection       48.3%
factory stitch            25.4%
decoder wait              12.1%
encoder write              7.0%
```

Projection sub-profiling showed:

```text
map generation            18.88 s
panorama remap             0.86 s
```

Therefore the next optimization remains inside map generation. 0.25 removes a
general floating-point modulo from the per-pixel hot path while preserving the
accepted map exactly.


---

# 21. 0.25 Benchmark Result and 0.26 Decision

The representative 0.25 export measured:

```text
39.01 s total
18.23 fps
1.65× real-time factor

decoder read/wait        33.6%
factory stitch           25.1%
composed projection      24.9%
encoder write             9.0%
```

Decoder wait is now the largest measured stage, so 0.26 introduces
runtime-tested VAAPI decode before pursuing more invasive geometry fusion.

---

# 22. 0.26 A/B Result and 0.27 Decision

The representative 0.26 A/B run measured 37.46 s with VAAPI versus 41.35 s
with software decoding. VAAPI reduced decoder-read blocking from 13.50 s to
5.29 s.

Before introducing direct lens-to-output geometry, 0.27 tests a lower-risk
scheduling optimization: overlap next-frame projection-map generation with
current-frame decode/stitch.


---

# 23. Direct Final Renderer Spike — PanoPilot 0.28

The representative 0.27 no-prefetch run measured projection-map wait at 12.81 s and factory stitch at 11.46 s. This is sufficient evidence to spike removal of the full intermediate panorama while preserving the existing renderer as the reference.


---

# 24. Stabilization Adjustment Spike — PanoPilot 0.29

Representative direct output validated image geometry but exposed physical-camera shake. 0.29 separates absolute horizon leveling from adjustable high-frequency full-orientation motion damping. Initial smoothing target is centered 400 ms; User amount controls correction strength.


---

# 25. 0.29 Stabilization Failure and 0.30 Decision

Representative 0.29 output remained visibly shaky at 70%. 0.30 moves stabilization to the native DJI quaternion timeline and uses velocity-adaptive filtering before exposure-time SLERP. The existing DJI per-frame/high-rate anchor remains the timing authority. Optical-flow residual correction remains a future stage if non-rotational motion persists.


---
# 26. Visual Residual Stabilization Spike — PanoPilot 0.31
Representative 0.30 100% gyro-stabilized output retained visible high-frequency 2D displacement. 0.31 tests a hybrid optical-flow similarity stage with an explicit crop budget.

---

# 25. Extreme Stabilization Spike — PanoPilot 0.32

The 0.31 crop-backed single-pass stabilizer improved representative footage but
did not reach the requested gimbal/tripod-like steadiness.

The next spike therefore tests iterative residual estimation rather than a
larger single smoothing coefficient. The hypothesis is that estimation error,
scale jitter, and unmodelled residual motion become measurable after the first
correction and can be removed by additional offline passes.

Acceptance is primarily visual. Crop loss up to 60% is permitted for this mode.


---

# 26. 0.32 Wobble Finding and 0.33 Decision

The 0.32 representative run removed substantially more shake but introduced
visible wobble. Diagnostics showed non-trivial visual scale estimates and
later-pass crop limiting with near-zero correction ratios on some frames.

0.33 tests the hypothesis that the remaining objectionable motion is primarily
translation while similarity-model scale/rotation and frame-local crop clipping
are creating the wobble. Locked mode therefore removes those degrees of freedom.

---

# 26. Walking Wobble Root-Cause Review — PanoPilot 0.34

The 0.31–0.33 experiments showed that increasing a global residual transform
does not converge on walking footage. The failure mode is consistent with
spatially variant motion: parallax and rolling-shutter/stitch residuals cause
different image regions to request different corrections.

0.34 tests an anchored coarse-mesh architecture. The acceptance criteria are:

- materially less walking shake;
- no rubber/zoom wobble;
- materially less crop than the 40–50% experiments;
- no per-frame stabilization-strength clipping.


---

# 27. 360-Domain Stabilization Root Cause — PanoPilot 0.34

Code review concluded that 0.31–0.33 incorrectly spent crop budget on the
largest residual motion after converting a complete 360 capture to a narrow
16:9 frame. Walking translation/parallax then forced incompatible scene depths
through one 2D transform and produced wobble.

0.34 tests the opposite decomposition: use the sphere for dominant global
visual correction and reserve 2D spatial deformation for small local residuals.


---

# 27. Residual Rotation Review — PanoPilot 0.35

The representative 0.34 output showed materially higher residual rotation in
the walking Clip than in the first Clip. The previous spherical analyzer had no
roll output channel, so this residual could not be corrected by the second 360
render.

The 0.35 spike adds rigid visual roll correction and removes the automatic
post-spherical mesh. It also measures spatial rotation disagreement. Persistent
intra-frame disagreement after the rigid correction is the gate for a later
row-time rolling-shutter correction spike.

---

# 28. Source Rolling-Shutter Rectification Spike — PanoPilot 0.36

The previous stabilization sequence materially improved frame-level motion but
continued to show walking-related rotational wobble. Public rolling-shutter
literature identifies this as a characteristic failure when high-frequency
camera rotation is stabilized between frames but source sensor rows were
captured at different times.

0.36 tests a source-domain row-time gyro warp in the direct renderer.

The calibration gate is empirical:

- zero-readout output is always scored;
- positive and negative readout durations are tested;
- frame-reference timing offset is fitted jointly;
- a non-zero solution must materially improve residual rigidity/spatial
  rotational agreement.

Acceptance is visual reduction of walking jello/rotation wobble without
reintroducing large crop or flexible-mesh deformation.


---

# 29. Final Delivery Options — PanoPilot 0.37

The previous fixed 1080p/30 fps policy is generalized only across the requested
720p–1080p range. This keeps output geometry bounded while allowing a materially
faster/smaller 720p delivery. Quality remains CRF-based H.264 with named presets
rather than exposing codec parameters as the primary UI.
