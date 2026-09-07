# PanoPilot — Documentation Change Summary

Status: Updated  
Release alignment: PanoPilot 0.37.0
Date: 2026-09-06

## Documents

- `01_system_definition.md` → SD-0.6
- `02_use_cases.md` → UC-0.5
- `03_system_requirements.md` → SYS-0.8
- `04_functional_architecture.md` → FA-0.3
- `05_technical_spikes.md` → TS-0.2

## Changes incorporated

The documentation now reflects executable behavior through PanoPilot 0.19:

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
