# PanoPilot — Documentation Change Summary

Status: Updated  
Release alignment: PanoPilot 0.48.0
Date: 2026-09-07

## Documents

- `01_system_definition.md` → SD-0.26
- `02_use_cases.md` → UC-0.6
- `03_system_requirements.md` → SYS-0.28
- `04_functional_architecture.md` → FA-0.22
- `05_technical_spikes.md` → TS-0.18
- `06_requirements_traceability.md` → RTM-0.3
- `07_quantitative_acceptance.md` → QA-0.2
- `08_iteration1_verification_report.md` → IVR-0.1
- `iteration1_acceptance_certificate.json` → certificate schema v1
- `09_iteration2_requirements.md` → I2-SYS-0.4
- `10_iteration2_traceability.md` → I2-RTM-0.4

## Changes incorporated

The documentation now reflects executable behavior through PanoPilot 0.43:

- Project Organizer / Clip Editor split;
- multi-Clip sequential Project model;
- stable Clip identity;
- non-destructive Source-Time trim;
- Camera Position persistence through Set Camera;
- configurable Camera Motion presets:
  Smooth, Ease In + Out, Ease In, Ease Out, Linear;
- configurable easing Amount from 0% to 100%;
- Project schema v3 Camera Motion persistence;
- Clip playback and preview-only exploration behavior;
- desktop loading-state lifecycle;
- sequential Project Preview;
- Project Time → Clip → Source Time mapping;
- active-Clip View Path application across Project playback;
- active-Clip source audio switching;
- Play-at-Project-end restart;
- technical-spike closure status.

## Remaining Iteration-1 gap

Final sequential MP4 export from original OSV media remains the principal
unimplemented end-to-end capability.


## PanoPilot 0.20 additions

- final sequential H.264 MP4 Project export;
- original OSV sources are authoritative export image inputs;
- Project Timeline order and Clip trims are applied to final video;
- persisted Clip View Paths and Project Camera Motion are applied per frame;
- Iteration-1 Output Profile policy resolved to 1920×1080/30 fps for 16:9 and
  1080×1920/30 fps for 9:16;
- original source audio is assembled in Clip order, with silence for a no-audio
  Clip only when required to preserve a Project that otherwise contains audio;
- export is written transactionally through a `.preparing.mp4` artifact and is
  verified before replacing the requested output;
- Export Project is available from the Project Organizer and through
  `panopilot project-export`;
- exported A/V stream-duration delta acceptance policy is 50 ms.


## PanoPilot 0.21 additions

- user acceptance closes the Iteration-1 end-to-end Project export gate;
- SPIKE-03 is now PASS;
- final export projection is optimized from two post-stitch resamples per frame
  to one;
- DJI horizon correction is composed mathematically with the Virtual Camera
  inverse projection;
- final export no longer creates a full rotated equirectangular intermediate
  frame;
- a reusable RectilinearProjector caches Output Profile coordinate axes for the
  complete export;
- canonical Camera Position, View Path, horizon, and Output Profile semantics
  are unchanged.


## PanoPilot 0.22 additions

- final-export stage profiling;
- per-frame decoder wait, factory stitch, horizon math, View Path, composed
  projection, and encoder-write timing;
- overall video, audio, mux, and verification timing;
- dominant final-video stage identification;
- real-time-factor and effective export-frame throughput reporting;
- optional complete JSON export/performance report through
  `project-export --report`.


## PanoPilot 0.22.1 additions

- durable external Project backups;
- Project backup history and recovery CLI;
- warning when an expected Project is missing but recoverable;
- distributable/runtime-data separation;
- packaged examples moved to `examples/`;
- packaged `results/` directory removed.


## PanoPilot 0.22.2 additions

- recovery of original source-recording references from panoramic preview-cache
  metadata;
- explicit user-selected Clip order during Project shell reconstruction;
- no attempt to infer unrecoverable trim or Camera Position state.


## PanoPilot 0.22.4 additions

- cumulative nearest-frame CFR Clip-boundary allocation;
- bounded EOF frame cloning for normal decoder time-base rounding;
- regression coverage for the 6.016 s DJI sample export boundary.


## PanoPilot 0.23 additions

- optimization selected from the 0.22 representative performance report;
- CFR metadata source-exposure-time generation with safe VFR fallback;
- native OpenCV factory seam blending;
- no change to Camera, calibration, trim, View Path, or Project semantics.


## PanoPilot 0.24 additions

- optimized float32 analytical composed-projection kernel;
- single per-frame combined Camera+horizon matrix;
- removal of H×W×3 final-projector ray tensor;
- projection map-generation versus panorama-remap profiling.


## PanoPilot 0.25 additions

- measured map-generation hotspot refinement;
- bounded in-place equirectangular seam wrap;
- removal of general floating-point modulo from the final projection hot path;
- exact map-wrap equivalence regression coverage.


## PanoPilot 0.26 additions

- runtime-tested VAAPI lens decoding;
- safe software fallback in automatic mode;
- explicit decoder backend/device CLI controls;
- per-Clip decoder diagnostics and probe timing.


## PanoPilot 0.27 additions

- bounded one-frame-ahead projection-map pipeline;
- map CPU work overlapped with decode/stitch;
- concurrent worker-time and critical-path wait diagnostics;
- projection-prefetch A/B control.


## PanoPilot 0.28 additions

- experimental direct dual-lens-to-delivery-frame renderer;
- no full intermediate panorama in direct mode;
- explicit accepted-baseline versus experimental render-pipeline selection.


## PanoPilot 0.29 additions

- Project schema v4 with Stabilization Amount;
- adjustable 3-axis gyro shake correction plus horizon leveling;
- zero-phase quaternion smoothing;
- Project Organizer slider and preview/final semantic alignment.


## PanoPilot 0.30 additions

- native-rate adaptive quaternion stabilization;
- velocity-sensitive smoothing;
- exact exposure-time SLERP;
- stronger stabilization response;
- schema v5 algorithm identity and detailed diagnostics.


## PanoPilot 0.31 additions
- opt-in hybrid gyro + visual residual stabilization;
- KLT/RANSAC image-motion estimation;
- clip-boundary-aware path smoothing;
- crop-constrained final affine correction.


## PanoPilot 0.32 additions

- explicit Extreme visual-stabilization mode;
- iterative residual re-analysis rather than single-pass path filtering;
- forward/backward KLT validation and high-confidence RANSAC;
- translation/rotation/scale residual correction;
- crop reserve up to 60% in Extreme mode;
- one final full-resolution image warp despite multiple analysis passes.


## PanoPilot 0.33 additions

- Locked translation-only residual stabilization;
- no visual rotation or scale correction in Locked mode;
- per-Clip global crop feasibility instead of per-frame crop clipping;
- robust low-order camera path;
- corrected 60% Extreme/Locked crop CLI validation.


## PanoPilot 0.34 additions

- anchored spatially-variant residual mesh;
- keyframe-regularized local deformation;
- bundled global/local camera-path smoothing;
- minimum-required crop under a User-defined maximum budget;
- removal of scale/zoom wobble from the recommended residual path.


## 0.34 stabilization architecture correction

- dominant visual walking correction moved from post-frame translation/crop into
  the virtual camera on the captured 360 sphere;
- second original-source render consumes visual camera offsets;
- post-render mesh is residual/local only and capped to a small crop budget.


## PanoPilot 0.35 additions

- rigid 3-axis spherical visual lock (yaw/pitch/roll);
- robust separation of visual rotation from center translation;
- visual scale explicitly treated as diagnostic-only nuisance motion;
- automatic post-spherical local mesh removed from the default path;
- crop-free spherical residual stabilization permitted;
- spatial rotation-disagreement diagnostics for rolling-shutter/parallax gating.


## PanoPilot 0.36 additions

- source-sensor row-time gyro rectification for direct rendering;
- automatic signed rolling-shutter readout calibration;
- automatic frame/gyro-anchor versus sensor-readout-midpoint offset fitting;
- source-row iterative inverse mapping;
- spatial-coherence gating of visual roll authority.


## PanoPilot 0.37 additions

- Project-level 720p / 1080p final output size;
- Standard / High / Very High H.264 quality presets;
- schema-v6 persistence and legacy migration to 1080p / High;
- Organizer controls and CLI export overrides.


## PanoPilot 0.38 additions

- export confirmation summary;
- determinate progress with elapsed/remaining-time presentation;
- candidate-level rolling-shutter calibration progress;
- render-pass-aware progress events;
- final file-size reporting;
- completion screen and Open Folder action;
- recoverable desktop export-error presentation.


## PanoPilot 0.39 additions

- on-screen 360 View Direction arrow pad;
- fine/normal/coarse deterministic angular nudge steps;
- Shift+Arrow keyboard equivalents;
- press-and-hold continuous directional adjustment;
- transient navigation semantics preserved until Set Camera.


## PanoPilot 0.40 additions

- explicit clockwise/counter-clockwise Virtual Camera roll controls;
- persisted Camera Position roll in schema v7;
- shortest-route roll interpolation through the Clip View Path;
- precise roll keyboard controls and shared angular-step semantics.


## PanoPilot 0.41 additions

- Project schema v8 Source Identity;
- supported-source import acceptance;
- mismatch blocking/no silent substitution;
- draggable Camera Position timeline markers;
- normalized requirement IDs and traceability matrix.


## PanoPilot 0.42 additions

- bounded background job manager with cooperative cancellation;
- per-Clip preview preparation isolation and explicit Clip readiness state;
- background source validation from Add OSV Files;
- responsive Project Organizer during final export;
- safe export cancellation without partial final-output replacement;
- closure of SYS-PREV-004, SYS-PERF-003, and SYS-PERF-004.


## PanoPilot 0.43 additions

- resolves the supported OSV profile and all remaining quantitative constants;
- adds `panopilot acceptance-run` for repeatable reference-system verification;
- verifies preview/final camera geometry at 720p/1080p and both aspect ratios;
- adds ready-preview camera-response and random-scrub latency benchmarks;
- adds preview A/V stream timing measurement;
- changes Project Preview playback to use Qt Multimedia audio position as the
  playback clock when audio is available;
- RTM static state becomes 205 PASS / 3 PARTIAL / 0 OPEN pending one real
  reference-system acceptance report.


## PanoPilot 0.44 additions

- accepts the successful 0.43 Fedora / Radeon 890M reference-system evidence;
- closes `SYS-AUDIO-003`, `SYS-PERF-001`, and `SYS-PERF-002`;
- final RTM becomes **208 PASS / 0 PARTIAL / 0 OPEN**;
- adds sanitized machine-readable Iteration-1 acceptance certification;
- adds `panopilot acceptance-certify REPORT`;
- adds the formal Iteration-1 verification report;
- freezes the Iteration-1 requirements baseline for future development.


## PanoPilot 0.45 additions — Iteration 2 begins

- preserves the closed Iteration-1 baseline at 208/208 PASS;
- creates a separate Iteration-2 requirements and traceability baseline;
- adds saved final-output FPS selection: Auto, 24, 25, 30, 50, or 60 fps;
- new Projects default to Auto, resolving to 60 fps for the qualified 100 fps
  DJI source profile;
- pre-v9 Projects migrate to explicit 30 fps to preserve prior export behavior;
- final frame rate appears in the Organizer and export confirmation;
- `project-export --fps` provides a one-export override;
- the Project Organizer remains alive while Clip editing is open and reloads
  the saved Project when the Clip Editor closes;
- embeds the proven Clip Editor into the right-hand side of the Project workspace while the Clip sequence remains visible.


## PanoPilot 0.46 additions — focus-first desktop refactor

- removes the permanent Project/Editor horizontal splitter;
- makes the reframed output the dominant workspace surface again;
- replaces the vertical Clip-management pane with a compact horizontal Clip
  strip backed by a GUI-independent presentation mapping and lazy Qt model;
- moves Project/export configuration behind Project Settings;
- moves precise direction, roll, and easing controls behind Fine Camera
  Controls;
- adds Focus mode for maximum viewer real estate;
- centralizes desktop styling in `desktop_theme.py`;
- moves workspace summary/view-state composition into
  `workspace_presenter.py`;
- removes the nested event loop from embedded Clip editing while preserving the
  standalone `explore` contract;
- leaves all accepted rendering, stabilization, trim, View Path, and export
  behavior unchanged.


## PanoPilot 0.47 additions

- explicit dark-theme foreground/control colors for host-palette-independent
  contrast;
- maximized-by-default but restorable/resizable Project and standalone Clip
  windows;
- responsive reframed-preview scaling instead of fixed display-pixmap sizing;
- explicit Reframe and Trim workflow modes;
- camera-only timeline annotations while reframing and trim-only annotations
  while trimming;
- visible Camera Position action renamed to Save Camera Position with direct
  explanation of its View Path role;
- compact Clip thumbnails derived from disposable preview cache;
- lazy source-thumbnail rail in Trim mode;
- new I2-UX-005 through I2-UX-008 requirements and 0.47 regression checks.


## PanoPilot 0.48 additions

- native `QMainWindow` Project shell;
- classic File/Edit/Clip/View/Settings command menus;
- fixed bottom Project/background-work status bar;
- modeless Project Settings dialog;
- central top action/settings/work panels removed;
- Clip strip hidden automatically during Clip editing;
- full-container reframed preview surface with aspect-preserving letterboxing;
- embedded Save/Undo/Redo routed through the parent menu bar.
