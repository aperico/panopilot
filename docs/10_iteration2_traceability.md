# PanoPilot — Iteration-2 Requirements Traceability

Baseline: I2-RTM-0.7 / PanoPilot 0.51.0

Iteration-1 traceability remains frozen in `06_requirements_traceability.md`
at **208 PASS / 0 PARTIAL / 0 OPEN**.

| Requirement | Status | Implementation | Verification |
|---|---|---|---|
| I2-OUT-001 | PASS | `output_profile.py / project.py / project_editor.py / cli.py` | `tests/test_045_output_fps.py / tests/test_045_cli_fps.py` |
| I2-OUT-002 | PASS | `output_profile.resolve_output_fps()` | `tests/test_045_output_fps.py` |
| I2-OUT-003 | PASS | `Project.output_fps / output_profile.py` | `tests/test_045_output_fps.py` |
| I2-OUT-004 | PASS | `output_profile.resolve_output_fps()` | `tests/test_045_output_fps.py` |
| I2-OUT-005 | PASS | `Project.from_dict()` schema migration | `tests/test_045_output_fps.py` |
| I2-OUT-006 | PASS | `Project.to_dict() / Project.from_dict()` | `tests/test_045_output_fps.py` |
| I2-OUT-007 | PASS | `project_export.py / output_profile.py` | existing export frame-plan/verification suite + `tests/test_045_output_fps.py` |
| I2-OUT-008 | PASS | `export_ui.py / project_editor.py` | `tests/test_045_workspace_continuity.py` |
| I2-UX-001 | PASS | `project_editor.py` | `tests/test_045_workspace_continuity.py` |
| I2-UX-002 | PASS | `project_editor.py / ProjectSession` | `tests/test_045_workspace_continuity.py` |
| I2-UX-003 | PARTIAL | `project_editor.py compact Clip strip / embedded explore.py` | `tests/test_045_workspace_continuity.py / tests/test_047_workflow_ui.py` |
| I2-UX-004 | PARTIAL | `project_editor.py settings/focus disclosure / explore.py contextual Reframe rail` | `tests/test_045_workspace_continuity.py / tests/test_047_workflow_ui.py` |
| I2-ARCH-001 | PASS | `explore.py on_closed embedded mode / project_editor.py callback lifecycle` | `tests/test_045_workspace_continuity.py` |
| I2-UX-005 | PARTIAL | `desktop_theme.py explicit scoped dark theme` | `tests/test_047_workflow_ui.py` |
| I2-UX-006 | PARTIAL | `project_editor.py / explore.py maximized + scalable viewer` | `tests/test_047_workflow_ui.py` |
| I2-UX-007 | PARTIAL | `explore.py Reframe/Trim presentation modes` | `tests/test_047_workflow_ui.py` |
| I2-UX-008 | PARTIAL | `thumbnails.py / clip_strip.py / project_editor.py / explore.py` | `tests/test_047_workflow_ui.py` |
| I2-UX-009 | PARTIAL | `project_editor.py QMainWindow/QAction menus` | `tests/test_048_classic_shell.py` |
| I2-UX-010 | PARTIAL | `project_editor.py QStatusBar / workspace_presenter.py` | `tests/test_048_classic_shell.py` |
| I2-UX-011 | PARTIAL | `explore.py full-size media canvas` | `tests/test_048_classic_shell.py` |
| I2-UX-012 | PARTIAL | `explore.py timeline_row transport` | `tests/test_049_mimo_inspired_editor.py` |
| I2-UX-013 | PARTIAL | `explore.py Reframe side control rail` | `tests/test_049_mimo_inspired_editor.py` |
| I2-UX-014 | PARTIAL | `explore.py TimeSlider diamond markers + seek/drag` | `tests/test_041_timeline_marker_drag.py / tests/test_049_mimo_inspired_editor.py` |
| I2-UX-015 | PARTIAL | `explore.py backToProjectAction / closeEvent` | `tests/test_049_mimo_inspired_editor.py` |
| I2-UX-016 | PASS | `explore.py nearest-left Camera Position + gesture batching` | `tests/test_050_reframe_autosave_and_filmstrip.py` |
| I2-UX-017 | PARTIAL | `thumbnails.py / explore.py adaptive sampled filmstrip` | `tests/test_047_workflow_ui.py / tests/test_050_reframe_autosave_and_filmstrip.py` |
| I2-UX-018 | PARTIAL | `explore.py showEvent / canvas-authoritative preview fit` | implementation inspection; Fedora/Wayland demonstration pending |
| I2-UX-019 | PARTIAL | `explore.py always-visible Reframe rail / desktop_theme.py` | `tests/test_045_workspace_continuity.py` |
| I2-UX-020 | PASS | `explore.py monotonic visual clock / hold-last View Path` | `tests/test_051_playback_past_last_camera.py` |
| I2-UX-021 | PARTIAL | `timeline_navigation.py / explore.py / thumbnails.py` | `tests/test_051_timeline_navigation.py / tests/test_051_gui_architecture.py` |
| I2-UX-022 | PASS | `project.py schema v10 / session.py / project_editor.py Save As + Home` | `tests/test_051_project_metadata.py / tests/test_051_gui_architecture.py` |
| I2-UX-023 | PARTIAL | `arrange_presenter.py / project_editor.py ArrangeTimelineWidget` | `tests/test_051_arrange_presenter.py / tests/test_051_gui_architecture.py` |

Current Iteration-2 state:

```text
32 requirements

PASS       14
PARTIAL    18
OPEN        0
```

All 0.47/0.48/0.49/0.50/0.51 changes have automated implementation checks. Visual/user-facing UX
requirements remain PARTIAL until they are demonstrated on the Fedora/Wayland
reference desktop with real PanoPilot media.
