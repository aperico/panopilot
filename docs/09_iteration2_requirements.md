# PanoPilot — Iteration-2 Requirements

Status: Active baseline  
Baseline: I2-SYS-0.6

Product release: PanoPilot 0.54.0 + export color and workspace improvements

Parent baseline: Iteration 1 — **208/208 PASS, closed**

---

# 1. Scope

Iteration 2 begins product evolution after formal Iteration-1 closure. It does
not modify accepted Iteration-1 requirements or quantitative limits.

Iteration 2 currently focuses on:

- device-friendly final-video frame-rate selection;
- preserving previous Project export behavior during migration;
- a persistent single-window Clip-editing workspace;
- focus-first visual hierarchy around the reframed output;
- progressive disclosure of secondary controls;
- testable Qt Model/View + MVP-style presentation boundaries.

# 2. Output Frame Rate

## I2-OUT-001 — User Frame-Rate Selection

The PanoPilot system shall allow the User to select `24`, `25`, `30`, `50`, or
`60` progressive frames per second for final conventional-video export.

**Priority:** MUST  
**Verification:** Test


## I2-OUT-002 — Automatic Frame-Rate Mode

When the User selects `Auto`, the PanoPilot system shall select the highest
qualified device-friendly final frame rate not greater than 60 fps and not
greater than the qualified source frame rate when that source rate is known.

**Priority:** MUST  
**Verification:** Test


## I2-OUT-003 — New-Project Default Frame Rate

When creating a new Project, the PanoPilot system shall default final frame-rate
selection to `Auto`.

For the current qualified DJI source profile
`dji-osmo360-dual-1920-hevc-100fps-v1`, `Auto` shall resolve to **60 fps**.

**Priority:** MUST  
**Verification:** Test


## I2-OUT-004 — Device-Friendly Automatic Ceiling

When resolving `Auto`, the PanoPilot system shall not automatically select a
final frame rate greater than **60 fps**.

**Rationale:** 60 fps is a common high-frame-rate H.264 delivery target while
remaining broadly practical for current phones, TVs, and computers. User
selection remains available for 24/25/30/50/60 fps.

**Priority:** MUST  
**Verification:** Test


## I2-OUT-005 — Legacy Project Reproducibility

When loading a Project created before schema v9, the PanoPilot system shall
initialize the saved output frame-rate selection to `30` fps so that opening an
older Project does not silently change its previous fixed-30-fps export
behavior.

**Priority:** MUST  
**Verification:** Test


## I2-OUT-006 — Persisted Frame Rate

When saving a schema-v9-or-later Project, the PanoPilot system shall persist the selected
output frame-rate value under `output_frame.fps`.

**Priority:** MUST  
**Verification:** Test


## I2-OUT-007 — Export Frame-Rate Consistency

For one final export, the PanoPilot system shall use the resolved output frame
rate consistently for Project frame planning, Clip-boundary frame allocation,
video encoding, stabilization timing, duration verification, and exported
Output Profile reporting.

**Priority:** MUST  
**Verification:** Test, Analysis


## I2-OUT-008 — FPS Export Summary

Before final export, the PanoPilot system shall show the resolved frame rate in
the export summary and shall indicate when the value was selected by `Auto`.

**Priority:** SHOULD  
**Verification:** Inspection, Test


# 3. Project Workspace Continuity

## I2-UX-001 — Persistent Organizer During Clip Editing

When opening a Clip Editor from the Project workspace, the PanoPilot system
shall keep the Project Organizer application window alive instead of closing
and reconstructing it after Clip editing.

**Priority:** MUST  
**Verification:** Inspection, Demonstration


## I2-UX-002 — Project Reload After Clip Editor

When the Clip Editor closes, the PanoPilot system shall reload the saved Project
into the existing Organizer workspace and preserve selection of the edited
Clip.

**Priority:** MUST  
**Verification:** Test, Demonstration


## I2-UX-003 — Focused Single-Window Clip Editing

The PanoPilot system shall provide Clip editing inside the Project workspace
without a separate top-level Clip Editor window. Project Clip context shall
remain immediately accessible without materially reducing the primary reframed
output viewport.

**Priority:** SHOULD  
**Verification:** Demonstration, Inspection

**Status:** Implemented in PanoPilot 0.46; automated architecture checks pass.
Fedora/Wayland visual acceptance remains pending. The reframed output owns the
dominant workspace area while the Clip sequence remains available as a compact
horizontal strip. The previous permanent left/right splitter is removed.


## I2-UX-004 — Progressive Disclosure for Secondary Controls

Project/export settings and other infrequent global controls shall not consume
permanent primary editing space when they are not being used. Controls that are
primary to the active workflow may remain visible contextually; in Reframe, the
precise camera-direction/motion controls are considered active-task controls.

**Priority:** SHOULD  
**Verification:** Demonstration, Inspection

**Status:** Refined through PanoPilot 0.50: Project Settings remain off-canvas
behind the Settings menu and Focus viewer mode remains available, while Fine
Camera Controls are intentionally persistent only inside Reframe. Fedora/Wayland
visual acceptance remains pending.


## I2-ARCH-001 — Single Qt Application Event Loop for Embedded Editing

Embedded Clip editing shall use the existing Qt application event loop rather
than starting a nested local event loop inside the Project workspace.

**Priority:** SHOULD  
**Verification:** Inspection, Test

**Status:** Implemented in PanoPilot 0.46 using a non-blocking embedded-editor
completion callback. Standalone single-Clip `explore` retains its established
blocking desktop contract.


# 4. Desktop Visual/Workflow Acceptance

## I2-UX-005 — Explicit Dark-Surface Contrast

PanoPilot shall explicitly define readable foreground colors for text and
interactive controls rendered on its dark desktop surfaces and shall not depend
on a light host Qt/GNOME palette for contrast.

**Priority:** MUST  
**Verification:** Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.47; automated stylesheet checks pass.
Fedora/Wayland visual acceptance remains pending.


## I2-UX-006 — Maximized-by-Default, Resizable Desktop

The Project workspace and standalone Clip Editor shall open maximized by default
while remaining restorable and resizable. The reframed preview shall scale to the
available canvas rather than force the window to the render-frame dimensions.

**Priority:** MUST  
**Verification:** Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.47; automated architecture checks pass.
Fedora/Wayland visual acceptance remains pending.


## I2-UX-007 — Task-Focused Clip Editing Modes

The Clip Editor shall separate Reframe and Trim workflows so controls and timeline
annotations unrelated to the active task are hidden. Reframe shall expose Camera
Position operations; Trim shall expose trim operations.

**Priority:** SHOULD  
**Verification:** Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.47 using explicit Reframe/Trim presentation
states.


## I2-UX-008 — Contextual Media Thumbnails

The Project Clip strip should show compact representative thumbnails when the
disposable preview cache is ready. The Clip Editor should show a thin source
filmstrip across the recording in both Reframe and Trim so the timeline retains
visual media context. Thumbnail generation shall not decode original dual-lens
media on the GUI path and shall not alter Project state.

**Priority:** SHOULD  
**Verification:** Test, Inspection, Demonstration

**Status:** Implemented from PanoPilot 0.47 and refined in 0.49 so the thin timeline filmstrip is shared by Reframe and Trim. Fedora/Wayland visual acceptance remains pending.


## I2-UX-009 — Classic Desktop Command Menus

The Project workspace shall expose persistent application commands through a
classic desktop menu bar rather than permanent button rows. At minimum, File,
Edit, View, and Settings command groups shall be available; Clip-specific
operations may use a dedicated Clip menu. Export and Close shall be File
commands, while Undo and Redo shall be Edit commands.

**Priority:** SHOULD  
**Verification:** Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.48 using a native Qt `QMainWindow` menu
bar. Fedora/Wayland visual acceptance remains pending.


## I2-UX-010 — Fixed Project/Background Status Bar

Project information such as Clip count, duration, output profile, stabilization,
and save state shall be presented in a fixed bottom status/information bar.
Background preview/import/export state and export progress shall use the same
status region rather than consume central editing space.

**Priority:** SHOULD  
**Verification:** Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.48 with Qt `QStatusBar`.


## I2-UX-011 — Full-Container Reframed Preview Surface

The reframed preview surface shall expand to all space allocated to the media
container. The conventional output aspect ratio shall be preserved inside that
surface, using dark letterboxing where container and output aspect ratios differ.

**Priority:** MUST  
**Verification:** Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.48; Fedora/Wayland visual acceptance
remains pending.


# 5. Media-First Clip Editor Refinement

## I2-UX-012 — Timeline-Coupled Transport

Play/Pause and authoritative clip/source time shall be presented adjacent to the
seek timeline rather than in a separate transport row.

**Priority:** SHOULD  
**Verification:** Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.49. Fedora/Wayland visual acceptance remains pending.


## I2-UX-013 — Contextual Reframe Control Rail

In Reframe mode, Camera Position and fine camera controls should occupy a compact
contextual rail beside the preview rather than stack beneath it. The rail shall be
hidden in Trim mode so the preview reclaims its width.

**Priority:** SHOULD  
**Verification:** Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.49. Fedora/Wayland visual acceptance remains pending.


## I2-UX-014 — Addressable Diamond Camera Positions

Saved Camera Positions shall be represented on the Reframe timeline using compact
diamond/keyframe markers. Clicking a marker shall seek directly to that Source
Time; dragging a marker shall retain the existing move-in-time transaction.

**Priority:** MUST  
**Verification:** Test, Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.49.


## I2-UX-015 — Explicit Return to Project

Embedded Clip editing shall expose a visible control that closes edit mode and
returns the user to the Project organizer without requiring the application menu
or keyboard shortcut. Existing save/discard/cancel close semantics shall apply.

**Priority:** SHOULD  
**Verification:** Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.49 using `← Project`.


## I2-UX-016 — Segment-Oriented Camera Position Editing

In Reframe mode, direct manipulation of the Virtual Camera shall update the saved
Camera Position closest to and not later than the current Source Time. Clicking a
Camera Position diamond shall seek to that exact Source Time; subsequent drag,
zoom, reset, or fine-direction edits therefore update that selected Camera
Position automatically. If no Camera Position exists at or before the playhead,
reframing shall remain preview-only and shall not create an implicit marker.

Continuous input gestures shall remain one logical undoable edit transaction.

**Priority:** MUST  
**Verification:** Test, Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.50. Behavioral verification is automated.


## I2-UX-017 — Responsive Aspect-Safe Timeline Filmstrip

Timeline visual context shall be represented as multiple discrete sampled frames
from the disposable panoramic preview cache. A single thumbnail shall not be
non-uniformly stretched to consume timeline width. The visible tile count shall
adapt to the available timeline width; every tile shall preserve source aspect
ratio and may center-crop to its allocated rectangle.

**Priority:** SHOULD  
**Verification:** Test, Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.50. Fedora/Wayland visual acceptance remains pending.


## I2-UX-018 — Correct First-Show Preview Fit

When Clip editing first becomes visible, the reframed preview shall occupy the
available media canvas without requiring a click, resize, or mode change. Initial
pixmap size hints shall not determine the editor layout.

**Priority:** MUST  
**Verification:** Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.50. Fedora/Wayland visual acceptance remains pending.


## I2-UX-019 — Persistent Fine Camera Controls in Reframe

The precise direction, roll, angular-step, and motion controls shall remain
visible throughout Reframe mode without an additional disclosure toggle. They
shall disappear together with the complete Reframe rail in Trim mode. Editor
margins and inter-control spacing shall remain compact and consistent.

**Priority:** SHOULD  
**Verification:** Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.50. Fedora/Wayland visual acceptance remains pending.


# 6. Navigable Timelines and Project Arrangement

## I2-UX-020 — Playback Continuity Beyond Final Camera Position

Clip playback shall continue from the final Camera Position to Clip Out. After
the last Camera Position, the View Path shall hold the final saved Camera state
while Source Time continues to advance. A stalled or quantized audio-player
position shall not freeze visual playback.

**Priority:** MUST  
**Verification:** Test, Demonstration

**Status:** Implemented in PanoPilot 0.51 using a monotonic visual playback clock
with Qt Multimedia acting as an audio follower.


## I2-UX-021 — Zoomable and Horizontally Scrollable Media Timeline

Reframe and Trim timelines shall support a visible time window smaller than the
complete source range. Mouse-wheel input over the timeline shall zoom around the
pointer position. Shift+wheel or native horizontal wheel/trackpad input shall
pan the visible range. A horizontal scrollbar and explicit Zoom Out, Fit, and
Zoom In controls shall be available when useful. Playback shall keep the
playhead visible as it crosses the current viewport.

Timeline thumbnails shall be sampled from the visible source range and adapt
their density to the viewport rather than stretching a fixed image set.

**Priority:** MUST  
**Verification:** Test, Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.51 through the shared
`TimelineViewport` presentation model.


## I2-UX-022 — Persisted Project Identity and Save As

The Project Home screen shall allow the User to edit a persisted human-readable
Project name and access Project Settings. The File menu shall provide Save As so
a Project can be written to a different Project file without overwriting the
original. After Save As, the newly written file becomes the active Project for
the current single-project editing session.

**Priority:** MUST  
**Verification:** Test, Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.51. Project schema v10 persists `name`.


## I2-UX-023 — Arrange Clips Workflow

PanoPilot shall provide a Project-level Arrange workflow for Clip sequencing.
Reframe and Trim remain Clip Editor modes and shall not be presented as Arrange
workspace modes. Arrange shall present one compact horizontal Project Clip timeline
without requiring a playback monitor. Clip visual width shall be proportional to
the active trimmed Clip duration. Each Clip shall use one centered representative
thumbnail rather than repeated thumbnail slices. The User shall be able to drag and
drop Clips to reorder Project sequence. The Arrange timeline shall share zoom, Fit,
horizontal scrolling, and panning semantics with other PanoPilot timelines.

**Priority:** MUST  
**Verification:** Test, Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.51 and refined in 0.51.1 using
`ArrangeTimelineWidget`, `arrange_presenter.py`, and the shared `TimelineViewport`.


## I2-UX-024 — Explicit Home Clip Editing and Final Export

Project Home shall expose an explicit Edit Selected Clip action in addition to
double-click Clip editing. Double-click shall resolve the Clip represented by the
clicked model index directly. Project Home and the classic menu bar shall both
expose Final Video Export without requiring the User to infer it from another
workflow.

**Priority:** MUST  
**Verification:** Test, Inspection, Demonstration

**Status:** Implemented in PanoPilot 0.51.1.


# 7. Final Export Quality

## I2-QUALITY-001 — Explicit SDR Color Conversion and Signaling

Final export shall convert full-range rendered BGR to limited-range BT.709
YCbCr and persist BT.709 matrix, primaries, and transfer-function signaling.
Final-file verification shall reject missing or incompatible color properties
before replacing the destination. The report shall include verified properties.
This requirement applies to the qualified SDR source profile; it does not imply
HDR or D-Log color management.

**Priority:** MUST

**Verification:** Test

## I2-QUALITY-002 — Stabilization Encoding Consistency

The base renderer and visual, locked, extreme, and anchored stabilization
renderers shall share the same final encoder/color policy, preserving requested
resolution, frame rate, CRF, and preset.

**Priority:** MUST

**Verification:** Test, Inspection

## I2-QUALITY-003 — Decoded Color Regression

Regression tests shall encode and decode synthetic color patches at landscape,
portrait, and HD dimensions. Interior luma samples shall differ by no more than
2 code values from the independent limited-range BT.709 calculation; reconstructed
BGR channels shall differ by no more than 4 code values at High quality.
Tests shall verify the actual encoded metadata, not merely command arguments.

**Priority:** MUST

**Verification:** Test

## I2-QUALITY-004 — Measured Mobile Comparison

A claim of quality comparable to DJI Mimo shall require matched-source exports
with recorded app version, phone, source mode, trim, framing/FOV, resolution,
FPS, color mode, and stabilization settings. Comparison shall cover fine detail,
stitching, motion cadence, stabilization, skin tones, and smooth gradients using
the protocol in `11_export_quality_review.md`. Encoder settings alone shall not
constitute acceptance evidence.

**Priority:** MUST

**Verification:** Demonstration, Analysis

**Status:** OPEN — no matched DJI Mimo export is available in the repository.

## I2-QUALITY-005 — Extended Delivery Profiles

Iteration 2 shall permit 720p, 1080p, 1440p, and 2160p in landscape and portrait,
with Standard, High, Very High, and Master quality settings. Master remains
lossy 8-bit H.264 delivery, not a source-bit-depth-preserving master format.
This extends the closed Iteration-1 resolution/quality scope without modifying
its historical acceptance record. Output dimensions do not guarantee equivalent
source detail after reframing.

**Priority:** MUST

**Verification:** Test, Inspection


# 8. Guided Project Workflow

## I2-UX-025 — Discoverable Next Action

An empty Project shall offer a prominent Add Clips action and explain the editing
sequence. With Clips present, Home shall expose Edit Selected Clip, Arrange,
Preview, and Export, with Project Settings available before export. Selection
changes shall immediately update Edit and reorder availability; editing shall
target the selected Clip. Preview preparation, preparation failure, and unavailable
recordings shall explain the next action without requiring a failed edit attempt.

**Priority:** MUST

**Verification:** Test, Demonstration

**Status:** Implemented; Qt interaction tests pass. User workflow acceptance pending.

## I2-UX-026 — Reachable Controls at Small Window Sizes

At the supported 720×480 minimum workspace size, Home controls shall retain their
usable size and shall not overlap. When content exceeds available height, the Home
panel shall scroll and permit each action to be brought into view. Primary actions
and keyboard focus shall have visible styling. Reframe and Trim shall display
short instructions describing the active editing behavior.

**Priority:** MUST

**Verification:** Test, Inspection, Demonstration

**Status:** Offscreen Qt layout and interaction checks pass; Fedora/Wayland and
assistive-technology acceptance remain pending.
