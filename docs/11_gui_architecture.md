# PanoPilot — Desktop GUI Architecture

Baseline: GUI-ARCH-0.5 / PanoPilot 0.51.0

## 1. Architectural Direction

PanoPilot uses **Qt Model/View plus MVP-style presentation boundaries** for the
desktop shell. Classic MVC is not adopted literally because Qt already combines
controller behavior into its view/delegate interaction model, while the media
editor benefits from explicit presentation/application boundaries around the
Project domain.

The intended dependency direction is:

```text
Qt Views
   ↓ intents / view-state consumption
Presentation
   ↓ application operations
ProjectSession / application services
   ↓
Project / Clip / ViewPath / Camera domain

Media preview/render/export services remain beside the application layer and do
not depend on Qt views.
```

## 2. 0.46 Realization

### Domain / application

Existing authoritative components remain unchanged:

- `project.py`
- `session.py`
- `timeline.py`
- `view_path.py`
- `virtual_camera.py`
- preview/cache/export/rendering modules
- `jobs.py`

### Presentation

`workspace_presenter.py` builds immutable, GUI-independent workspace view state:

- ordered Clip rows;
- Project-duration availability;
- compact output/stabilization status;
- status-bar project summary.

`clip_strip.py` maps Clip rows to compact presentation entries. The module is
importable without PySide6. Its Qt adapter is created lazily when the desktop
workspace opens.

### View / desktop shell

`project_editor.py` remains the current composition root for the Project
workspace. PanoPilot 0.46 changes its layout from a permanent horizontal splitter
to a focus-first workspace. PanoPilot 0.48 further refines that shell to:

```text
Native menu bar: File / Edit / Clip / View / Settings
Compact Clip strip (organizer context only)
Dominant embedded Clip Editor / preview canvas
Native fixed status bar: Project info + background work/progress
```

Project Settings is a modeless dialog opened from the Settings menu rather than
a persistent central panel. During Clip editing the Clip strip is hidden by
default so the active editing task owns the central workspace.

`explore.py` continues to own the proven interactive Clip Editor widget while
secondary fine controls are progressively disclosed.

## 3. Event-loop Policy

There shall be one Qt application event loop for the Project workspace.

Embedded Clip editing is non-blocking and reports completion through a callback.
The standalone single-Clip `explore` command keeps the established blocking
contract by running its normal local desktop wait only when it owns the editing
workflow.

## 4. Model Ownership Rules

1. `Project` / `ProjectSession` are authoritative edit state.
2. Qt list models contain presentation projections only.
3. A view must not become the persistence authority for Clips, trim, Camera
   Positions, View Paths, stabilization, or output settings.
4. Preview caches remain derived/disposable state.
5. Rendering modules must not import desktop Qt presentation modules.

## 5. Testing Strategy

High-value desktop tests should target boundaries rather than widget source
strings where practical:

- pure presenter/model tests without Qt;
- ProjectSession transaction tests;
- preview/render golden-frame tests;
- lightweight GUI architecture/lifecycle checks;
- real Fedora/Wayland demonstration for final visual acceptance.

PanoPilot 0.46 adds pure presentation tests. Existing source-inspection tests are
retained only where the headless CI environment cannot instantiate PySide6.

## 6. Next Refactoring Boundary

The next GUI-architecture increment should extract the remaining large local Qt
classes from `project_editor.py` and `explore.py` into normal importable view
classes, then move mutation orchestration behind presenter/application-service
methods. That work should not be mixed with rendering or Camera algorithm
changes.

## 7. 0.47 Workflow/Responsive Refinement

PanoPilot 0.47 keeps the 0.46 Model/View + MVP direction but tightens the view
contract after real-desktop visual review.

### Theme contract

Dark PanoPilot surfaces shall define foreground colors explicitly for child Qt
controls. The desktop must not rely on an inherited GNOME/Qt palette for text
contrast because a light host palette can otherwise render dark text on the
application's dark media surfaces.

### Window contract

The main Project workspace and standalone Clip Editor open maximized by default,
but remain ordinary restorable/resizable Qt windows. Media pixmaps scale to the
available viewer canvas and must not impose the rendered frame dimensions as a
fixed widget size.

### Workflow modes

The Clip Editor exposes two task states:

```text
Reframe -> Camera Position actions + camera timeline markers
Trim    -> Trim actions + source thumbnails + IN/OUT timeline annotations
```

This is a presentation-state decision only. `ProjectSession`, trim state, Camera
Positions, View Path evaluation, and rendering remain the same domain/application
objects as before.

### Thumbnail boundary

Thumbnail generation consumes only the disposable panoramic preview cache. Clip
and timeline thumbnails are presentation artifacts and are never serialized into
the Project. The Project workspace prepares a compact cached Clip thumbnail in a
background preview job; the Clip Editor lazily samples a thin source thumbnail rail used as timeline context in both Reframe and Trim.


## 8. 0.48 Classic Desktop Shell

PanoPilot 0.48 applies the standard desktop command/surface split:

- **Menu bar:** persistent global commands and keyboard shortcuts;
- **Central workspace:** only current media/task context;
- **Status bar:** non-editable Project information and background-work state;
- **Dialogs:** infrequent settings that should not consume permanent canvas area.

The Project shell is a Qt `QMainWindow`. File owns media/save/export/close; Edit
owns undo/redo; Clip owns Clip-instance operations; View owns Project Preview,
Focus Viewer and Clip-strip visibility; Settings owns Project Settings.

Embedded Clip editing delegates Save/Undo/Redo to the active Editor widget from
the parent menu. This keeps one visible command surface while preserving the
existing editor/session implementation boundary.

The reframed media `QLabel` expands to the entire canvas. `KeepAspectRatio` is
applied only to the pixmap, so unused area becomes deliberate dark letterboxing
rather than unused layout space around a smaller preview widget.


## 9. 0.49 Media-First Editor Composition

0.49 keeps the Qt Model/View + MVP-style boundary and changes presentation only.
The key composition rule is that the preview and timeline form the dominant edit
surface while controls are contextual to the active workflow.

```text
EditorWidget
  mode/navigation row
    Back to Project
    Reframe | Trim

  preview row
    full expanding media canvas
    contextual Reframe rail (hidden in Trim)

  timeline context
    thin cached-media filmstrip
    Play + TimeSlider + timecode
```

The Reframe rail owns Camera Position creation/deletion and precise direction,
roll, and camera-motion controls. It does not own Camera/View Path state; it only
invokes the existing editor/application callbacks.

`TimeSlider` now renders Camera Positions as diamonds. Marker hit-testing remains
source-time based. A click is navigation (`seek`); a drag crossing the movement
threshold invokes the existing transactional Camera Position move callback. This
preserves one gesture/one edit transaction while making saved positions directly
addressable.

The media filmstrip remains derived cache state and does not enter Project
serialization.


## 10. 0.50 Segment-Oriented Reframe Presentation

0.50 keeps Camera Position persistence in `ProjectSession`; the Qt view only
selects the edit target and batches gesture boundaries.

```text
current Source Time
        ↓
closest Camera Position <= Source Time
        ↓
mouse drag / wheel burst / fine-control burst
        ↓ one logical gesture
commit existing Camera Position
        ↓
autosave Project
```

`ExploreWindow.camera_position_anchor_time()` is GUI-independent selection logic.
The view uses it both for persistence targeting and for highlighting the active
diamond. Before the first Camera Position the selector returns `None`, preserving
preview-only exploration rather than silently creating a keyframe.

Mouse drag commits on release. Wheel/trackpad and auto-repeat button events use a
single-shot debounce timer so one physical gesture creates one history entry.
Pending reframing is flushed before seek, mode change, playback, or close so the
commit cannot accidentally target a later Camera Position.

The timeline filmstrip is presentation/cache state. `thumbnails.py` computes a
responsive discrete-tile geometry independently from Qt. The Qt layer preloads a
bounded set of representative cache frames, then lays out as many tiles as fit
the current width. Pixmaps use aspect-preserving expansion plus center crop; Qt
`scaledContents` is deliberately disabled.

Initial preview geometry is also presentation-only: the image label ignores
pixmap size hints in both dimensions, the canvas is the sizing authority, and a
post-show event-loop refit handles maximized/embedded geometry assignment.


## 11. 0.51 Shared Timeline Navigation and Arrange Presentation

`timeline_navigation.py` introduces a Qt-independent `TimelineViewport`. It is
the authoritative presentation model for visible time range, cursor-anchored
zoom, horizontal pan, Fit, scrollbar mapping, and keep-playhead-visible
autoscroll. Reframe/Trim and Arrange consume the same semantics.

The media timeline remains source-time based. When zoomed, the GUI asks
`thumbnails.py` for discrete representative frames from only the visible cached
preview interval. Thumbnail density therefore follows available pixels and
visible duration while Project state remains unaffected.

`arrange_presenter.py` creates immutable Project-order rows from the canonical
Project timeline. `ArrangeTimelineWidget` renders those rows with duration-
proportional widths and sends drag/drop reorder intents back through
`ProjectSession.move_clip()`. It owns no authoritative Clip order.

Project identity is domain state in schema v10 (`Project.name`). The Home view
and Project Settings edit that value through `ProjectSession`; Save As changes
the active persistence path but does not create a second simultaneous Project
session.

For Clip playback, the editor monotonic clock is authoritative for visual Source
Time. Qt Multimedia remains synchronized as the audio transport/follower. This
separates visual progression from backend media-position stalls while preserving
the canonical View Path rule that the final Camera Position is held through
Clip Out.
