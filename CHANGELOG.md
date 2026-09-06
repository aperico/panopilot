# Changelog

## 0.15.0

- Adds a disposable panoramic editing-preview cache keyed by source identity and
  preview profile.
- `panopilot explore` automatically prepares/reuses the cache.
- Adds `panopilot prepare-preview` for explicit preview preparation.
- Changes editor preview defaults to 1280x640 at 20 fps.
- Adds real-time Play/Pause in the desktop editor; Space is now Play/Pause and
  Enter/Return is the explicit Camera Position commit action.
- Uses Qt Multimedia audio/media position as the playback clock when available,
  with a monotonic silent fallback.
- Playback follows the persisted View Path and pauses automatically when the
  user begins exploratory drag/zoom/seek/edit actions.
- Adds cache validity, frame-time, playback-state, and CLI regression tests.

## 0.14.0

- Adds Source-Time navigation to the PySide6 desktop editor.
- Adds a timeline slider with Camera Position markers.
- Adds deterministic left/right arrow seeking.
- Seeking restores the persisted View Path at the selected Source Time.
- Multiple Camera Positions can be authored in one editor session.
- `R` resets to the persisted View Path at the current Source Time.
- Fixes the 0.13.1 `explore --yaw/--pitch` defaults so persisted View Path
  values are actually used.
- Keeps seek processing synchronous by design; playback/cache is deferred.
- Adds time-navigation and CLI regression tests.

## 0.13.1

- Fixes `NameError: Path is not defined` when `panopilot explore` closes.
- Adds parser-level regression coverage for the `camera-at` and
  `reframe-path` subcommands so packaging cannot silently omit them.
- Retains the 0.13 View Path model and project format unchanged.

## 0.13.0

- Adds UI-independent View Path evaluation.
- Adds deterministic zero/one/before-first/after-last Camera Position behavior.
- Adds shortest-route panoramic yaw interpolation.
- Adds linear pitch and horizontal-FOV interpolation.
- Adds `panopilot camera-at`.
- Adds `panopilot reframe-path`.
- Explorer initializes from the persisted View Path when engineering camera
  overrides are not supplied.
- Adds View Path regression tests.

## 0.12.0

- Adds the minimal PanoPilot Project domain model.
- Adds persisted `CameraPosition` records owned by a source Clip.
- Adds explicit "Use this view" via Enter/Return/Space in the explorer.
- Preserves Explore != Edit: drag, wheel, reset, and aspect changes are transient.
- Re-committing at the same Source Time updates the existing Camera Position.
- Saves the project atomically without modifying source media.
- Adds `--project` to `panopilot explore`.
- Adds `panopilot project-info`.
- HUD distinguishes saved state from new uncommitted exploration.
- Adds project persistence and explicit-commit regression tests.

## 0.11.1

- Replaces OpenCV HighGUI explorer window with PySide6/Qt.
- Switches runtime image dependency to `opencv-python-headless`.
- Removes the OpenCV-bundled Qt/Wayland conflict from the desktop explorer.
- Keeps OpenCV for media/remapping and Qt for UI/event handling.
- Preserves transient Explore semantics and all existing mouse/keyboard controls.

## 0.11.0

- Adds `panopilot explore` for local interactive Virtual Camera navigation.
- Opens a dedicated desktop window; no browser or remote server is used.
- Adds left-drag panoramic navigation and mouse-wheel FOV zoom.
- Adds `R` reset and runtime 16:9 / 9:16 switching.
- Adds an explicit on-screen `EXPLORE — changes are not saved` state.
- Keeps all interaction transient: no Camera Position or View Path is created.
- Prepares the OSV panorama once, then reprojects in memory during navigation.
- Uses an 800-pixel preview long edge by default for responsive CPU validation.
- Adds regression tests for drag, zoom, reset, yaw wrapping, wheel decoding, and aspect rendering.

## 0.10.0

- Starts SPIKE-02: Virtual Camera.
- Adds `panopilot reframe`.
- Adds PanoPilot-owned equirectangular -> rectilinear projection.
- Defines Virtual Camera yaw, pitch, and horizontal FOV semantics.
- Adds Iteration-1 16:9 and 9:16 Output Frame handling.
- Adds in-memory `render_osv_panorama_frame()`.
- Reframe uses calibrated reconstruction and horizon leveling directly.
- Adds Virtual Camera geometry regression tests and reference images.

## 0.9.0

- Adds extraction of the ~1 kHz DJI high-rate quaternion stream.
- Aligns high-rate quaternions to per-frame DJI timestamps by matching the
  duplicated per-frame quaternion inside each high-rate block.
- Adds actual source-frame PTS lookup for preview horizon timing.
- Adds `--imu-source highrate|perframe`.
- Adds `--imu-offset-ms`.
- Adds `panopilot imu-sweep` for visual timing-offset experiments.
- Changes default gravity smoothing from 150 ms to 100 ms for timing tests.
- Adds high-rate and PTS alignment diagnostics and tests.

## 0.8.2

- Adds centered zero-phase smoothing of the gravity/horizon trajectory.
- Default preview smoothing sigma is 150 ms.
- Adds `--level-smoothing-ms`; use 0 to reproduce unsmoothed 0.8.1 behavior.
- Smooths only gravity/pitch/roll correction; yaw remains untouched.
- Reports raw versus smoothed gravity step statistics.
- Adds smoothing regression tests.

## 0.8.1

- Fixes the direction of spherical horizon correction during inverse image mapping.
- The IMU correction matrix now moves image content in the intended direction instead of applying its inverse.
- Adds a regression test using a synthetic equirectangular direction marker.
- Keeps temporal smoothing disabled until the corrected geometric baseline is evaluated.

## 0.8.0

- Adds `panopilot preview`.
- Decodes both lens streams in one synchronized FFmpeg filter graph.
- Loads DJI orientation metadata once per preview.
- Interpolates quaternion by Source Time for every preview frame.
- Applies dynamic spherical horizon leveling frame-by-frame.
- Includes source audio by default.
- Reports processing throughput and horizon-correction statistics.
- Keeps the correctness-first two-resample pipeline pending visual validation.

## 0.7.0

- Adds `panopilot imu`.
- Extracts/interpolates per-frame DJI orientation directly from `djmd`.
- Adds `panopilot stitch --level-horizon`.
- Defines the canonical IMU → factory-equirect coordinate mapping.
- Rejects the old v0.4 transform that produced ~90-degree false corrections.
- Adds spherical equirectangular horizon rotation.
- Adds `--level-strength` for validation.
- Keeps leveling as a second remap temporarily; single-resample folding is deferred until the geometry is accepted.

## 0.6.0

- `panopilot stitch` now accepts an `.OSV` directly.
- Automatically discovers the two lens streams.
- Automatically extracts DJI factory calibration from `djmd`.
- Uses memory mapping for metadata access.
- Decodes both lens frames at one Source Time.
- Scales 3840-space factory intrinsics/LUT coordinates to actual stream size.
- Produces the calibrated equirectangular frame without intermediate files.
- Adds `panopilot inspect`.
- Adds debug-only `extract-calibration` and `stitch-lenses`.
- Horizon/IMU leveling remains deliberately deferred to the next increment.

## 0.5.0

- Factory-calibrated two-PNG stitching.
- Explicit calibration coordinate scaling.
