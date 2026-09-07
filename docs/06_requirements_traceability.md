# PanoPilot Requirements Traceability

Baseline: RTM-0.4 / PanoPilot 0.44.0

Status semantics: **PASS** = implemented with mapped verification; **PARTIAL** = behavior exists but a quantitative/validation gate remains; **OPEN** = implementation closure is scheduled.

| Requirement | Title | Status | Implementation | Verification evidence |
|---|---|---|---|---|
| SYS-APP-001 | Desktop Operation | PASS | `cli.py / project_editor.py` | `tests/test_014_cli.py` |
| SYS-APP-002 | Fedora Reference Environment | PASS | `cli.py / project_editor.py` | `tests/test_014_cli.py` |
| SYS-APP-003 | Local Primary Workflow | PASS | `cli.py / project_editor.py` | `tests/test_014_cli.py` |
| SYS-APP-004 | Offline Primary Workflow | PASS | `cli.py / project_editor.py` | `tests/test_014_cli.py` |
| SYS-PROJ-001 | New Project | PASS | `project.py / project_editor.py` | `tests/test_project.py` |
| SYS-PROJ-002 | Empty Initial Timeline | PASS | `project.py / project_editor.py` | `tests/test_project.py` |
| SYS-MEDIA-001 | Supported OSV | PASS | `source_validation.py / acceptance.py / source.py / dji.py` | `tests/test_043_supported_osv_profile.py / tests/test_041_source_integrity.py` |
| SYS-MEDIA-002 | Multiple Source Selection | PASS | `source_validation.py / media_identity.py / source.py / dji.py` | `tests/test_041_source_integrity.py` |
| SYS-MEDIA-003 | No Manual Conversion | PASS | `source_validation.py / media_identity.py / source.py / dji.py` | `tests/test_041_source_integrity.py` |
| SYS-MEDIA-004 | Unsupported Source Notification | PASS | `source_validation.py / media_identity.py / source.py / dji.py` | `tests/test_041_source_integrity.py` |
| SYS-MEDIA-005 | Independent Source Acceptance | PASS | `source_validation.py / media_identity.py / source.py / dji.py` | `tests/test_041_source_integrity.py` |
| SYS-MEDIA-006 | Source Immutability | PASS | `source_validation.py / media_identity.py / source.py / dji.py` | `tests/test_041_source_integrity.py` |
| SYS-MEDIA-007 | Source Identity | PASS | `source_validation.py / media_identity.py / source.py / dji.py` | `tests/test_041_source_integrity.py` |
| SYS-CLIP-001 | Clip Creation | PASS | `project.py / project_editor.py / session.py` | `tests/test_018_multiclip.py` |
| SYS-CLIP-002 | Sequential Timeline | PASS | `project.py / project_editor.py / session.py` | `tests/test_018_multiclip.py` |
| SYS-CLIP-003 | Clip Selection | PASS | `project.py / project_editor.py / session.py` | `tests/test_018_multiclip.py` |
| SYS-CLIP-004 | Clip Reordering | PASS | `project.py / project_editor.py / session.py` | `tests/test_018_multiclip.py` |
| SYS-CLIP-005 | Clip Removal | PASS | `project.py / project_editor.py / session.py` | `tests/test_018_multiclip.py` |
| SYS-CLIP-006 | Remove Does Not Delete Source | PASS | `project.py / project_editor.py / session.py` | `tests/test_018_multiclip.py` |
| SYS-CLIP-007 | Independent Clip State | PASS | `project.py / project_editor.py / session.py` | `tests/test_018_multiclip.py` |
| SYS-CLIP-008 | Reorder Preservation | PASS | `project.py / project_editor.py / session.py` | `tests/test_018_multiclip.py` |
| SYS-TRIM-001 | In Point | PASS | `project.py / session.py / explore.py` | `tests/test_trim.py` |
| SYS-TRIM-002 | Out Point | PASS | `project.py / session.py / explore.py` | `tests/test_trim.py` |
| SYS-TRIM-003 | Valid Range | PASS | `project.py / session.py / explore.py` | `tests/test_trim.py` |
| SYS-TRIM-004 | Trimmed Playback | PASS | `project.py / session.py / explore.py` | `tests/test_trim.py` |
| SYS-TRIM-005 | Trimmed Export | PASS | `project.py / session.py / explore.py` | `tests/test_trim.py` |
| SYS-TRIM-006 | Non-Destructive Trim | PASS | `project.py / session.py / explore.py` | `tests/test_trim.py` |
| SYS-TRIM-007 | Preserve Camera Source Anchors | PASS | `project.py / session.py / explore.py` | `tests/test_trim.py` |
| SYS-TRIM-008 | Out-of-Range Camera Position Retention | PASS | `project.py / session.py / explore.py` | `tests/test_trim.py` |
| SYS-TRIM-009 | Out-of-Range Camera Position Inactivity | PASS | `project.py / session.py / explore.py` | `tests/test_trim.py` |
| SYS-PREV-001 | Navigable Panoramic Preview | PASS | `cache.py / preview.py / loading.py` | `tests/test_cache.py` |
| SYS-PREV-002 | Automatic Preview Preparation | PASS | `cache.py / preview.py / loading.py` | `tests/test_cache.py` |
| SYS-PREV-003 | Preparation State | PASS | `cache.py / preview.py / loading.py` | `tests/test_cache.py` |
| SYS-PREV-004 | Per-Clip Preparation Isolation | PASS | `jobs.py / cache.py / preview.py / project_editor.py` | `tests/test_042_background_jobs.py / tests/test_042_work_isolation_architecture.py` |
| SYS-OUT-001 | 16:9 | PASS | `output_profile.py / project.py / project_editor.py` | `tests/test_037_output_options.py` |
| SYS-OUT-002 | 9:16 | PASS | `output_profile.py / project.py / project_editor.py` | `tests/test_037_output_options.py` |
| SYS-OUT-003 | Project-Wide Profile | PASS | `output_profile.py / project.py / project_editor.py` | `tests/test_037_output_options.py` |
| SYS-OUT-004 | Output Resolution | PASS | `output_profile.py / project.py / project_editor.py` | `tests/test_037_output_options.py` |
| SYS-OUT-005 | Output Frame Rate | PASS | `output_profile.py / project.py / project_editor.py` | `tests/test_037_output_options.py` |
| SYS-OUT-006 | Preview Geometry | PASS | `output_profile.py / project.py / project_editor.py` | `tests/test_037_output_options.py` |
| SYS-CAM-001 | Complete Horizontal Orientation | PASS | `virtual_camera.py / explore.py` | `tests/test_virtual_camera.py` |
| SYS-CAM-002 | Vertical Orientation | PASS | `virtual_camera.py / explore.py` | `tests/test_virtual_camera.py` |
| SYS-CAM-003 | Field of View | PASS | `virtual_camera.py / explore.py` | `tests/test_virtual_camera.py` |
| SYS-CAM-004 | Mouse Orientation | PASS | `virtual_camera.py / explore.py` | `tests/test_virtual_camera.py` |
| SYS-CAM-005 | Mouse-Wheel Zoom | PASS | `virtual_camera.py / explore.py` | `tests/test_virtual_camera.py` |
| SYS-CAM-006 | Coordinate-Free Primary Workflow | PASS | `virtual_camera.py / explore.py` | `tests/test_virtual_camera.py` |
| SYS-CAM-007 | Reset View | PASS | `virtual_camera.py / explore.py` | `tests/test_virtual_camera.py` |
| SYS-CAM-008 | Canonical Camera Semantics | PASS | `virtual_camera.py / explore.py` | `tests/test_virtual_camera.py` |
| SYS-CAM-009 | Preview/Render Camera Equivalence | PASS | `virtual_camera.py / acceptance.py / explore.py` | `tests/test_043_acceptance_metrics.py / tests/test_virtual_camera.py` |
| SYS-EDIT-001 | Non-Committing Exploration | PASS | `explore.py / session.py` | `tests/test_explore_commit.py` |
| SYS-EDIT-002 | Explicit Commit | PASS | `explore.py / session.py` | `tests/test_explore_commit.py` |
| SYS-EDIT-003 | Reset Does Not Modify View Path | PASS | `explore.py / session.py` | `tests/test_explore_commit.py` |
| SYS-TIME-001 | Clip Playback | PASS | `explore.py / project_player.py / timeline.py` | `tests/test_time_navigation.py` |
| SYS-TIME-002 | Pause | PASS | `explore.py / project_player.py / timeline.py` | `tests/test_time_navigation.py` |
| SYS-TIME-003 | Seek | PASS | `explore.py / project_player.py / timeline.py` | `tests/test_time_navigation.py` |
| SYS-TIME-004 | Scrub Preview | PASS | `explore.py / project_player.py / timeline.py` | `tests/test_time_navigation.py` |
| SYS-TIME-005 | Project Playback | PASS | `explore.py / project_player.py / timeline.py` | `tests/test_time_navigation.py` |
| SYS-TIME-006 | Sequential Playback | PASS | `explore.py / project_player.py / timeline.py` | `tests/test_time_navigation.py` |
| SYS-TIME-007 | Deterministic Time Mapping | PASS | `explore.py / project_player.py / timeline.py` | `tests/test_time_navigation.py` |
| SYS-POS-001 | Source-Time Anchor | PASS | `project.py / session.py / explore.py` | `tests/test_041_camera_position_move.py` |
| SYS-POS-002 | Derived Clip-Time Display | PASS | `project.py / session.py / explore.py` | `tests/test_041_camera_position_move.py` |
| SYS-POS-003 | Create | PASS | `project.py / session.py / explore.py` | `tests/test_041_camera_position_move.py` |
| SYS-POS-004 | Modify | PASS | `project.py / session.py / explore.py` | `tests/test_041_camera_position_move.py` |
| SYS-POS-005 | Delete | PASS | `project.py / session.py / explore.py` | `tests/test_041_camera_position_move.py` |
| SYS-POS-006 | Move in Time | PASS | `project.py / session.py / explore.py` | `tests/test_041_camera_position_move.py` |
| SYS-POS-007 | Visualize | PASS | `project.py / session.py / explore.py` | `tests/test_041_camera_position_move.py` |
| SYS-PATH-001 | Per-Clip View Path | PASS | `view_path.py / project.py` | `tests/test_view_path.py` |
| SYS-PATH-002 | State Evaluation | PASS | `view_path.py / project.py` | `tests/test_view_path.py` |
| SYS-PATH-003 | Continuous Default Motion | PASS | `view_path.py / project.py` | `tests/test_view_path.py` |
| SYS-PATH-004 | Panoramic Wrap | PASS | `view_path.py / project.py` | `tests/test_view_path.py` |
| SYS-PATH-005 | Playback Application | PASS | `view_path.py / project.py` | `tests/test_view_path.py` |
| SYS-PATH-006 | Reorder Independence | PASS | `view_path.py / project.py` | `tests/test_view_path.py` |
| SYS-AUDIO-001 | Clip Preview Audio | PASS | `cache.py / project_player.py / project_export.py` | `tests/test_playback.py` |
| SYS-AUDIO-002 | Project Preview Audio | PASS | `cache.py / project_player.py / project_export.py` | `tests/test_playback.py` |
| SYS-AUDIO-003 | Preview AV Sync | PASS | `cache.py / project_player.py / acceptance.py` | `tests/test_043_preview_av_sync.py / tests/test_043_acceptance_metrics.py`; reference evidence: `docs/iteration1_acceptance_certificate.json` |
| SYS-HIST-001 | Undo | PASS | `session.py` | `tests/test_session.py` |
| SYS-HIST-002 | Redo | PASS | `session.py` | `tests/test_session.py` |
| SYS-HIST-003 | Gesture Transaction | PASS | `session.py` | `tests/test_session.py` |
| SYS-HIST-004 | Core Edit Coverage | PASS | `session.py` | `tests/test_session.py` |
| SYS-SAVE-001 | Save Project | PASS | `project.py / media_identity.py` | `tests/test_041_source_integrity.py` |
| SYS-SAVE-002 | Persist Source References | PASS | `project.py / media_identity.py` | `tests/test_041_source_integrity.py` |
| SYS-SAVE-003 | Persist Clip State | PASS | `project.py / media_identity.py` | `tests/test_041_source_integrity.py` |
| SYS-SAVE-004 | Persist View Paths | PASS | `project.py / media_identity.py` | `tests/test_041_source_integrity.py` |
| SYS-SAVE-005 | Persist Output Profile | PASS | `project.py / media_identity.py` | `tests/test_041_source_integrity.py` |
| SYS-SAVE-006 | Open Project | PASS | `project.py / media_identity.py` | `tests/test_041_source_integrity.py` |
| SYS-SAVE-007 | Restore Project | PASS | `project.py / media_identity.py` | `tests/test_041_source_integrity.py` |
| SYS-SAVE-008 | Missing Source Detection | PASS | `project.py / media_identity.py` | `tests/test_041_source_integrity.py` |
| SYS-SAVE-009 | Source Identity Mismatch | PASS | `project.py / media_identity.py` | `tests/test_041_source_integrity.py` |
| SYS-SAVE-010 | No Silent Source Substitution | PASS | `project.py / media_identity.py` | `tests/test_041_source_integrity.py` |
| SYS-SAVE-011 | Save Failure Safety | PASS | `project.py / media_identity.py` | `tests/test_041_source_integrity.py` |
| SYS-SAVE-012 | Source Separation | PASS | `project.py / media_identity.py` | `tests/test_041_source_integrity.py` |
| SYS-EXP-001 | Conventional Project Export | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-002 | Timeline Order | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-003 | Trim | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-004 | View Path | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-005 | Output Profile | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-006 | Final-Quality Source | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-007 | H.264 MP4 | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-008 | Source Audio | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-009 | Export AV Sync | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-010 | Failed Export Status | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-011 | Export Source Integrity | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-PERF-001 | Camera Response | PASS | `acceptance.py / cache.py / explore.py` | `tests/test_043_acceptance_metrics.py`; reference evidence: `docs/iteration1_acceptance_certificate.json` |
| SYS-PERF-002 | Scrub Response | PASS | `acceptance.py / cache.py / explore.py` | `tests/test_043_acceptance_metrics.py`; reference evidence: `docs/iteration1_acceptance_certificate.json` |
| SYS-PERF-003 | Ready-Clip Isolation | PASS | `jobs.py / project_editor.py / cache.py` | `tests/test_042_background_jobs.py / tests/test_042_work_isolation_architecture.py` |
| SYS-PERF-004 | Long-Running Work | PASS | `jobs.py / project_editor.py / project_export.py` | `tests/test_042_background_jobs.py / tests/test_042_work_isolation_architecture.py` |
| SYS-POS-008 | Durable Set Camera | PASS | `project.py / session.py / explore.py` | `tests/test_041_camera_position_move.py` |
| SYS-PATH-007 | Configurable Easing Preset | PASS | `view_path.py / project.py` | `tests/test_view_path.py` |
| SYS-PATH-008 | Configurable Easing Amount | PASS | `view_path.py / project.py` | `tests/test_view_path.py` |
| SYS-PATH-009 | Camera Motion Persistence | PASS | `view_path.py / project.py` | `tests/test_view_path.py` |
| SYS-PATH-010 | Camera Motion Preview/Render Equivalence | PASS | `view_path.py / project.py` | `tests/test_view_path.py` |
| SYS-TIME-008 | Project Seek | PASS | `explore.py / project_player.py / timeline.py` | `tests/test_time_navigation.py` |
| SYS-TIME-009 | Project-End Replay | PASS | `explore.py / project_player.py / timeline.py` | `tests/test_time_navigation.py` |
| SYS-TIME-010 | Clip-Boundary Continuation | PASS | `explore.py / project_player.py / timeline.py` | `tests/test_time_navigation.py` |
| SYS-AUDIO-004 | Clip-Boundary Audio Selection | PASS | `cache.py / project_player.py / project_export.py` | `tests/test_playback.py` |
| SYS-WORK-001 | Preview Preparation Feedback | PASS | `loading.py / explore.py / project_player.py` | `tests/test_0186_loading_completion.py` |
| SYS-WORK-002 | Preview Preparation Completion | PASS | `loading.py / explore.py / project_player.py` | `tests/test_0186_loading_completion.py` |
| SYS-EXP-012 | Global CFR Frame Allocation | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-013 | No-Audio Clip Continuity | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-014 | Transactional Export Promotion | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-015 | Export Verification | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-PERF-027 | Composed Final Projection | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-005 | Single Post-Stitch Sampling | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-006 | Projection Semantic Equivalence | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-007 | Export Stage Measurements | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-008 | Dominant Stage Identification | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-009 | Local Performance Report | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERSIST-009 | External Project Backup | PASS | `project.py / recovery.py / cache.py` | `tests/test_0221_project_backups.py` |
| SYS-PERSIST-010 | Project Backup Recovery | PASS | `project.py / recovery.py / cache.py` | `tests/test_0221_project_backups.py` |
| SYS-PERSIST-011 | Distribution/User-Data Separation | PASS | `project.py / recovery.py / cache.py` | `tests/test_0221_project_backups.py` |
| SYS-PERSIST-012 | Cache Source Discovery | PASS | `project.py / recovery.py / cache.py` | `tests/test_0221_project_backups.py` |
| SYS-PERSIST-013 | Explicit Reconstruction Order | PASS | `project.py / recovery.py / cache.py` | `tests/test_0221_project_backups.py` |
| SYS-PERSIST-014 | Recovery Authority Boundary | PASS | `project.py / recovery.py / cache.py` | `tests/test_0221_project_backups.py` |
| SYS-EXP-016 | Cumulative CFR Clip Boundary Quantization | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-017 | Decoder EOF Quantization Tolerance | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-PERF-010 | CFR Exposure-Time Fast Path | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-011 | Unknown/VFR Timing Fallback | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-012 | Factory Blend Semantic Preservation | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-013 | Combined Camera/Horizon Transform | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-014 | Projection Geometry Preservation | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-015 | Projection Substage Measurement | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-016 | Bounded Longitude Wrap | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-017 | Wrap Semantic Equivalence | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-018 | Executable Hardware Decoder Test | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-019 | Automatic Software Fallback | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-020 | Explicit VAAPI Failure | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-021 | Decoder Selection Diagnostics | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-022 | One-Frame Projection Prefetch | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-023 | Bounded Projection Prefetch | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-024 | Prefetch Semantic Equivalence | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-025 | Direct Lens Final Rendering | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-PERF-026 | Accepted Renderer Preservation | PASS | `performance.py / project_export.py / projection_prefetch.py` | `tests/test_022_performance_profiler.py` |
| SYS-STAB-001 | Persisted Amount | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-002 | Legacy Compatibility | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-003 | 3-Axis Shake Correction | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-004 | Zero-Amount Equivalence | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-005 | Preview/Final Consistency | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-006 | Native-Rate Trajectory Stabilization | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-007 | Velocity-Adaptive Smoothing | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-008 | Exposure-Time Quaternion Sampling | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-009 | Stabilization Diagnostics | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-011 | Robust Visual Motion Estimate | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-012 | Clip Boundary Reset | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-013 | Crop Inclusion Constraint | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-023 | Iterative Residual Measurement | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-024 | Forward/Backward Track Validation | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-025 | Extreme Crop Reserve | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-026 | Single Final Image Warp | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-027 | Locked Translation-Only Residual | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-028 | Temporally Constant Crop Constraint | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-029 | Spatially Variant Residual Motion | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-030 | Local Deformation Anchoring | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-031 | Crop Budget Semantics | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-032 | No Per-Frame Crop Gain | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-014 | Visual Roll Correction | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-015 | No Visual Scale Authority | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-016 | Crop-Free Spherical Global Correction | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-017 | Rigid Spherical Default | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-018 | Source-Row Orientation | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-019 | Signed Readout Calibration | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-020 | Timing-Offset Calibration | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-021 | Zero-Readout Safety Baseline | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-STAB-022 | Visual Roll Coherence | PASS | `stabilization.py / spherical_stabilization.py / rolling_shutter.py` | `tests/test_036_rolling_shutter_math.py` |
| SYS-OUT-007 | Final Resolution Classes | PASS | `output_profile.py / project.py / project_editor.py` | `tests/test_037_output_options.py` |
| SYS-OUT-008 | Aspect-Aware Dimensions | PASS | `output_profile.py / project.py / project_editor.py` | `tests/test_037_output_options.py` |
| SYS-OUT-009 | Export Quality Presets | PASS | `output_profile.py / project.py / project_editor.py` | `tests/test_037_output_options.py` |
| SYS-OUT-010 | Legacy Output Equivalence | PASS | `output_profile.py / project.py / project_editor.py` | `tests/test_037_output_options.py` |
| SYS-EXP-018 | Export Confirmation | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-019 | Determinate Export Progress | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-020 | Export Time Status | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-021 | Export Completion Facts | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-022 | Open Export Folder | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-EXP-023 | Recoverable Export Failure | PASS | `project_export.py / export_ui.py` | `tests/test_038_export_progress.py` |
| SYS-UI-021 | Directional View Controls | PASS | `explore.py` | `tests/test_039_view_direction_controls.py` |
| SYS-UI-022 | Angular Nudge Resolution | PASS | `explore.py` | `tests/test_039_view_direction_controls.py` |
| SYS-UI-023 | Direction Button Auto-Repeat | PASS | `explore.py` | `tests/test_039_view_direction_controls.py` |
| SYS-UI-024 | Navigation/Edit Separation | PASS | `explore.py` | `tests/test_039_view_direction_controls.py` |
| SYS-UI-025 | Keyboard Direction Navigation | PASS | `explore.py` | `tests/test_039_view_direction_controls.py` |
| SYS-CAM-014 | Explicit Roll Controls | PASS | `virtual_camera.py / explore.py` | `tests/test_virtual_camera.py` |
| SYS-CAM-015 | Roll Persistence | PASS | `virtual_camera.py / explore.py` | `tests/test_virtual_camera.py` |
| SYS-CAM-016 | Roll Path Interpolation | PASS | `virtual_camera.py / explore.py` | `tests/test_virtual_camera.py` |
| SYS-CAM-017 | Legacy Roll Migration | PASS | `virtual_camera.py / explore.py` | `tests/test_virtual_camera.py` |
| SYS-MEDIA-008 | Import Processing Validation | PASS | `source_validation.py / media_identity.py / source.py / dji.py` | `tests/test_041_source_integrity.py` |
| SYS-SAVE-013 | Persistent Expected Source Fingerprint | PASS | `project.py / media_identity.py` | `tests/test_041_source_integrity.py` |
| SYS-SAVE-014 | Identity Mismatch Processing Block | PASS | `project.py / media_identity.py` | `tests/test_041_source_integrity.py` |
| SYS-POS-009 | Timeline Marker Drag | PASS | `project.py / session.py / explore.py` | `tests/test_041_camera_position_move.py` |
| SYS-REQ-001 | Unique Requirement Identity | PASS | `docs/03_system_requirements.md / docs/06_requirements_traceability.md` | `tests/test_041_requirements_lint.py` |
| SYS-REQ-002 | Requirement Traceability Coverage | PASS | `docs/03_system_requirements.md / docs/06_requirements_traceability.md` | `tests/test_041_requirements_lint.py` |

## Iteration-1 closure

The PanoPilot 0.43 quantitative acceptance run passed on the designated Fedora
/ AMD Radeon 890M reference system.

The final field evidence closes:

- `SYS-AUDIO-003` — worst measured cached-preview A/V timing error:
  **35.000 ms**, limit **100 ms**;
- `SYS-PERF-001` — worst measured ready-preview Camera-response p95:
  **12.769 ms**, limit **100 ms**;
- `SYS-PERF-002` — worst measured random-scrub p95:
  **101.393 ms**, limit **250 ms**.

The previously static gates also remained PASS:

- `SYS-MEDIA-001` — all three reference Source Recordings conformed to the
  supported DJI OSV profile;
- `SYS-CAM-009` — maximum Preview/final source-map difference:
  **0.043536 source pixel**, limit **0.05**.

Final Iteration-1 RTM state: **208 PASS / 0 PARTIAL / 0 OPEN**.

```text
208 normative requirements

PASS       208
PARTIAL      0
OPEN         0
```

Sanitized machine-readable evidence:

```text
docs/iteration1_acceptance_certificate.json
```

Human-readable verification report:

```text
docs/08_iteration1_verification_report.md
```

The Iteration-1 requirements baseline is closed. Subsequent product work shall
be introduced through a new requirements baseline.
