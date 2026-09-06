# Changelog

## 0.26.0

- Targets the measured 0.25 dominant stage: lens decoder read/wait.
- Adds `--decoder auto|software|vaapi`, defaulting to `auto`.
- Adds optional `--vaapi-device`.
- Runtime smoke-tests the exact dual-lens OSV-to-BGR pipeline before automatic
  VAAPI selection.
- Falls back safely to software decoding in automatic mode.
- Explicit VAAPI mode fails when the runtime smoke test fails.
- Records selected decoder backend, device, fallback state, and reason per Clip.
- Adds `decoder_backend_probe` performance measurement.
- Updates engineering documentation through 0.26.

## 0.25.0

- Targets the measured 0.24 map-generation hotspot.
- Replaces general full-array `np.remainder()` in the final composed projector
  with a bounded one-period in-place seam wrap.
- Preserves exact modulo semantics for the projector's atan2-derived X range.
- Avoids changing Camera, horizon, factory stitch, or View Path semantics.
- Adds dense equivalence regression tests for seam-wrap coordinates.
- Retains the 0.24 map-generation versus panorama-remap performance split.
- Updates engineering documentation through 0.25.

## 0.24.0

- Targets the measured 0.23 dominant stage: composed projection at 73.2% of
  video-render time.
- Replaces the per-frame H×W×3 float64 ray tensor with analytical component
  rotation.
- Combines Camera and horizon rotations into one 3×3 matrix per frame.
- Stores reusable Output Profile NDC axes and squared axes in float32.
- Normalizes only the rotated Y component required for latitude.
- Reuses map arrays in-place for trigonometric and coordinate transforms.
- Preserves the accepted composed horizon + Virtual Camera geometry.
- Adds projection sub-profiling for map generation versus panorama remap.
- Adds geometric and rendered-image equivalence regression tests.
- Updates engineering documentation through 0.24.

## 0.23.0

- Uses the measured 0.22 user benchmark to select optimization work.
- Adds a safe CFR source-exposure-time fast path when stream
  `avg_frame_rate` and `r_frame_rate` agree.
- Avoids the expensive per-frame FFprobe PTS scan for DJI CFR lens streams.
- Preserves FFprobe frame-PTS scanning as the VFR/unknown-cadence fallback.
- Exposes source-PTS method diagnostics in each rendered Clip.
- Replaces NumPy float32 factory seam blending with OpenCV `blendLinear`.
- Preserves factory calibration maps and normalized seam weights.
- Adds regression tests for the observed 100 fps → 30 fps exposure mapping.
- Updates engineering documentation through 0.23.

## 0.22.4

- Fixes final export ending one frame short on non-frame-aligned source/Clip
  boundaries such as the 6.016 s sample at 30 fps.
- Changes final frame allocation to rounded cumulative Project Clip boundaries.
- Prevents the previous asymmetric ceil-like 181-frame allocation for a
  180.48-frame Clip duration.
- Keeps one Project-wide CFR clock and minimizes each boundary quantization
  error to approximately half one output frame.
- Adds a bounded two-frame FFmpeg EOF clone pad for normal time-base/duration
  rounding.
- Adds regression tests for the exact 6.016 s / 30 fps failure case.

## 0.22.3

- Fixes `NameError: sys is not defined` in interactive
  `project-rebuild-from-cache`.
- Adds a regression check for the interactive recovery path.
- Keeps cache source discovery and explicit Clip-order semantics unchanged.

## 0.22.2

- Adds preview-cache source discovery for lost-Project recovery.
- Adds `panopilot cache-sources`.
- Adds `panopilot project-rebuild-from-cache`.
- Rebuild flow requires explicit Clip order rather than guessing from cache
  timestamps.
- Rebuilt Projects use normal durable external backups immediately.
- Recovery output states explicitly that trims and Camera Positions cannot be
  recovered from disposable preview metadata.
- Adds source-discovery and Project-reconstruction regression tests.

## 0.22.1

- Treats Project JSON as durable user data rather than build output.
- Every successful Project save now creates an external backup under the
  user's XDG data directory.
- Adds retained timestamped Project backup history plus `latest.json`.
- Adds `panopilot project-backups`.
- Adds `panopilot project-recover`.
- `project-edit` warns when the requested Project is missing but a backup is
  available.
- Moves packaged example JSON files to `examples/`.
- The distributable ZIP no longer contains `results/`, preventing overlay
  updates from colliding with runtime Project/output data.
- Adds Project backup and recovery regression tests.

## 0.22.0

- Adds evidence-driven final-export performance profiling.
- Measures original lens decoder read/wait time.
- Measures factory stitch, horizon math, View Path evaluation, composed
  projection, and H.264 encoder write/wait time.
- Measures overall video render, audio assembly, final mux, and verification.
- Reports effective export-frame throughput and real-time factor.
- Identifies the dominant measured video stage after export.
- Adds `project-export --report` for a complete local JSON benchmark report.
- Keeps performance instrumentation outside editing/rendering domain semantics.
- Updates engineering documentation through 0.22.

## 0.21.0

- Closes SPIKE-03 as PASS after successful user validation of final Project
  export.
- Adds a reusable `RectilinearProjector`.
- Composes DJI horizon correction with the Virtual Camera inverse projection.
- Removes the intermediate full-resolution rotated equirectangular frame from
  final export.
- Reduces final export from two post-stitch image resamples per frame to one.
- Caches normalized Output Profile pixel coordinates across the complete
  export.
- Preserves canonical Camera Position, View Path, Camera Motion, and horizon
  semantics.
- Adds geometric equivalence regression tests against the previous two-stage
  projection path.
- Updates engineering documentation through 0.21.

## 0.20.0

- Adds final sequential Project export to H.264 MP4.
- Adds `Export Project…` to the Project Organizer.
- Adds `panopilot project-export`.
- Final image rendering uses original OSV lens streams and DJI calibration;
  the disposable panoramic preview cache is not used as a final render source.
- Resolves Iteration-1 Output Profile policy to 1920×1080/30 fps for 16:9 and
  1080×1920/30 fps for 9:16.
- Allocates final CFR frames on one Project-wide clock to avoid accumulated
  per-Clip frame rounding drift.
- Applies Clip trims, persisted View Paths, and configurable Camera Motion to
  final frames.
- Assembles original source audio in Project order and inserts silence for
  no-audio Clips when needed to preserve Timeline alignment.
- Verifies the completed MP4 before atomically promoting it to the requested
  output path.
- Defines exported A/V stream-duration tolerance at 50 ms.
- Updates numbered engineering documentation through 0.20.

## 0.19.0

- Adds read-only sequential Project Timeline preview.
- Adds `Preview Project` to the Project Organizer.
- Adds `panopilot project-preview`.
- Maps Project Time deterministically to active Clip and Source Time.
- Applies each active Clip's persisted trim and View Path during Project
  playback.
- Applies persisted project Camera Motion easing and Amount consistently.
- Switches preview audio to the active Clip at Clip boundaries.
- Adds full-Project seeking with visible Clip boundaries.
- Pressing Play at Project end restarts from Project Time zero.
- Uses the existing derived panoramic cache; original OSV remains authoritative
  for future final rendering.
- Refreshes numbered engineering documentation through 0.19 and includes it
  under `docs/`.
- Adds Project playback mapping, restart, CLI, and architecture regression
  tests.

## 0.18.8

- Adds configurable project-level Camera Motion easing.
- Adds easing presets: Smooth, Ease In + Out, Ease In, Ease Out, Linear.
- Adds a 0–100% Amount control that blends the selected easing curve with
  linear timing.
- Adds compact Camera Motion controls to the Clip Editor.
- Camera Motion changes are Undo/Redo project transactions.
- Persists Camera Motion in project schema v3.
- Migrates schema-v1/v2 projects to Smooth / 100% to preserve 0.18.7 behavior.
- Interactive playback, camera-at, and reframe-path share the same settings.
- Adds easing, strength, migration, persistence, and editor-state tests.

## 0.18.7

- Replaces piecewise-linear Camera Position timing with quintic
  ease-in/ease-out (`smootherstep`) by default.
- Camera motion now reaches each Camera Position with zero velocity and zero
  acceleration, reducing harsh reframing-point hits.
- Applies the same eased timing to yaw, pitch, and horizontal FOV.
- Preserves shortest-route yaw interpolation across the panoramic seam.
- Keeps exact Camera Position values and Source Times unchanged.
- Interactive playback and project-aware rendering share the same smoothed
  View Path evaluator.
- Adds `eased_alpha` and `interpolation` to View Path diagnostics.
- Retains internal linear interpolation mode for engineering comparison.
- Adds regression tests for gentle arrival/departure and seam behavior.

## 0.18.6

- Fixes loading dialogs that remained visible after panoramic preparation
  completed.
- Replaces cross-thread nested-event-loop quit signaling with GUI-thread
  polling of `QThread.isFinished()`.
- Uses `QDialog.exec()` as the single modal loading event loop.
- Makes immediate cached-preview completion race-safe.
- Transfers progress text through a thread-safe queue; worker code never
  touches Qt widgets.
- Preserves the 0.18.5 Organizer / Clip Editor local-event-loop lifecycle.

## 0.18.5

- Fixes a fast-cache race in the panoramic loading screen.
- Starts loading workers via a queued zero-delay timer after the nested Qt
  event loop begins dispatching.
- Routes worker progress/completion through a GUI-thread QObject receiver.
- Removes worker-thread widget updates.
- Keeps one QApplication alive across Project Organizer / Clip Editor
  transitions.
- Replaces mixed QApplication.exec/manual processEvents polling with local Qt
  QEventLoop instances for both editor windows.
- Prevents intentional closing of the Organizer from terminating the app while
  a Clip Editor is about to open.
- Adds lifecycle regression checks.

## 0.18.4

- Renames Set In / Set Out buttons to Trim In / Trim Out to distinguish Clip
  trimming from Camera Positions.
- When a Clip has zero Camera Positions, pressing Play after manually
  reframing now preserves the explored camera as a preview-only hold instead
  of snapping to the default camera.
- Preview-only playback does not create or save a Camera Position.
- Shows `Preview-only camera — Set Camera to save this view` while relevant.
- Once a Clip has Camera Positions, playback continues to use the persisted
  View Path exclusively.
- Adds explicit transient-hold vs persisted-path playback diagnostics.
- Adds regression tests for zero-View-Path explored-camera playback.

## 0.18.3

- Renames the primary Camera Position action from `Use View` to `Set Camera`.
- Setting/updating a Camera Position now atomically saves the project
  immediately in the desktop Clip Editor.
- Keeps Undo/Redo history after Camera Position auto-save.
- Adds explicit timestamped Camera Position save feedback.
- Adds a compact `CAM N` count to the Clip Editor toolbar.
- Camera Position commit/save failures now show a desktop error dialog.
- Project Organizer explicitly warns when a Clip has zero saved Camera
  Positions and therefore uses the default camera.
- Adds regression tests for Camera Position auto-save and update persistence.

## 0.18.2

- Makes stable Clip id the canonical identity inside the multi-Clip Clip Editor.
- Project Organizer passes the selected Clip id into the Clip Editor.
- Camera Position create/update, delete, trim, seek, and playback target the
  exact Clip instance.
- Adds clip-id-native ProjectSession Camera Position operations.
- `camera-at` and `reframe-path` accept Clip id or source path.
- Source selector resolution tolerates unambiguous relative/absolute path
  aliases.
- Rendering uses the resolved Clip's persisted source reference.
- Resolver errors list available Clip ids and source paths.
- Adds regression tests proving one setpoint holds the entire selected Clip and
  two setpoints interpolate without affecting other Clips.

## 0.18.1

- Reorganizes the Clip Editor into a compact transport row, editing row,
  trim-summary row, and full-width timeline.
- Centers the reframed video in a dark expanding media canvas.
- Removes the white unused area caused by long horizontal text labels.
- Replaces secondary action labels with icon tool buttons and tooltips.
- Keeps `Use View`, Set In, and Set Out explicit as primary editing actions.
- Separates Source Time, Clip-local Time, project save state, and camera state.
- Replaces the long trim sentence with compact In / Clip / Out value chips.
- Reduces the video HUD to two concise lines.
- Stops calling `adjustSize()` for every rendered frame.
- Adds a reusable Qt loading dialog backed by a worker thread.
- Panoramic preview preparation now stays inside the desktop application
  instead of appearing to revert to terminal-only feedback.

## 0.18.0

- Adds the desktop multi-Clip Project Organizer.
- Adds native multi-select OSV import.
- Adds ordered Clip list with Move Up / Move Down.
- Adds transactional Clip add, remove, and reorder operations.
- Adds Undo/Redo and explicit Save for project-structure changes.
- Adds Edit Selected Clip, returning to the Project Organizer afterward.
- Adds robust Clip-id allocation after removals.
- Adds first-class Project helpers: clip-by-id, index, add, remove, move.
- Preserves Camera Position Source Times across Clip reordering.
- Calculates sequential active Project duration in the organizer.
- Keeps repeated source instances out of scope; duplicates are skipped.
- Adds `panopilot project-edit`.
- Keeps the proven 0.17.1 Clip Editor unchanged for per-Clip reframing.

## 0.17.1

- Strengthens Clip trim visualization without changing schema-v2 semantics.
- Adds large, explicit `IN` and `OUT` flags to the source timeline.
- Adds a visually prominent active-Clip band between In and Out.
- Adds an always-visible Clip trim summary with In, Out, and duration.
- Adds immediate timestamp feedback after Set In / Set Out / Clear Trim.
- Renames the user-facing transient-camera diagnostic from
  `has_uncommitted_changes` to `camera_exploration_changed`.
- Keeps `project_dirty` exclusively for actual unsaved Project edits.
- Retains the Play-at-Out -> restart-at-In behavior from 0.17.

## 0.17.0

- Adds schema-v2 Clip trim metadata: Source-Time In and Out.
- Automatically migrates schema-v1 projects in memory without implicit save.
- Adds transactional Set Clip In, Set Clip Out, and Clear Trim operations.
- Trim operations are Undo/Redo-aware and use explicit Save semantics.
- Guarantees trim changes never retime persisted Camera Positions.
- Camera Positions outside trim become dormant rather than being deleted.
- View Path evaluation now uses only active Camera Positions.
- Adds Clip-local Time mapping while preserving Source Time persistence.
- Adds blue trim boundaries, red active markers, and gray dormant markers.
- Playback is constrained to Clip In/Out.
- Pressing Play at Clip Out restarts from Clip In; with full-source trim this restarts from zero at the media end.
- Preserves logical end-of-timeline state even when the cached preview snaps to an earlier final frame.
- Adds UI-independent sequential Project Timeline spans.
- Adds `panopilot timeline-info`.
- Adds migration, trim, dormant-path, timeline, and playback-restart regression tests.

## 0.16.0

- Adds transactional `ProjectSession` history.
- Adds Undo/Redo for Camera Position create, update, delete, and Output Frame.
- Adds Delete/Backspace Camera Position editing at the current preview frame.
- Adds Ctrl+Z, Ctrl+Shift+Z, Ctrl+Y, and editor Undo/Redo buttons.
- Changes Camera Position commits from auto-save to in-memory edits.
- Adds explicit Ctrl+S / Save button with atomic project persistence.
- Adds project dirty state and modified-window indicator.
- Adds Save / Discard / Cancel close confirmation.
- Save establishes a clean baseline without clearing Undo history.
- New edits after Undo clear the Redo branch.
- Exploration, seek, and playback remain outside project history.
- Adds transactional history, dirty-state, delete, save, and UI callback tests.

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
