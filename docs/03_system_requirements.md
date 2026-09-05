# PanoPilot — System Requirements

Status: Draft  
Baseline: SYS-0.7  
Scope: Iteration 1  
Parent: `01_system_definition.md`  
Use Cases: `02_use_cases.md`

---

# 1. Purpose

This document defines the minimum system requirements for the first usable
iteration of PanoPilot.

PanoPilot is a desktop application focused on reframing 360-degree panoramic
video into conventional video.

---

# 2. Requirement Conventions

Each normative requirement:

- contains one primary obligation;
- uses `shall`;
- is externally verifiable or defines an essential system constraint;
- avoids implementation technology unless required by the product definition;
- traces to one or more Iteration 1 use cases.

Verification methods:

- Inspection
- Analysis
- Demonstration
- Test
- Performance Test

All requirements are MUST unless explicitly marked SHOULD.

---

# 3. Desktop Application

## SYS-APP-001 — Desktop Operation

PanoPilot shall operate as a locally installed desktop application.

**Verification:** Demonstration  
**Trace:** UC-01


## SYS-APP-002 — Fedora Reference Environment

PanoPilot shall operate on the designated Fedora Linux reference environment.

**Verification:** Test  
**Trace:** UC-01


## SYS-APP-003 — Local Primary Workflow

PanoPilot shall perform the Iteration 1 primary workflow on the local
computer.

**Verification:** Demonstration  
**Trace:** UC-01 through UC-13


## SYS-APP-004 — Offline Primary Workflow

The Iteration 1 primary workflow shall permit completion without Internet
access.

**Verification:** Test  
**Trace:** UC-01 through UC-13

---

# 4. Project

## SYS-PROJ-001 — New Project

PanoPilot shall permit the User to create a new Project.

**Verification:** Test  
**Trace:** UC-01


## SYS-PROJ-002 — Empty Initial Timeline

A newly created Project shall contain an empty Project Timeline.

**Verification:** Test  
**Trace:** UC-01

---

# 5. Source Media

## SYS-MEDIA-001 — Supported OSV

PanoPilot shall accept supported DJI Osmo 360 `.OSV` files as Source
Recordings.

**Verification:** Test  
**Trace:** UC-02


## SYS-MEDIA-002 — Multiple Source Selection

PanoPilot shall permit multiple `.OSV` files to be selected in one Add Media
operation.

**Verification:** Test  
**Trace:** UC-02


## SYS-MEDIA-003 — No Manual Conversion

PanoPilot shall permit a supported Source Recording to enter the reframing
workflow without User-performed source conversion.

**Verification:** Demonstration  
**Trace:** UC-02


## SYS-MEDIA-004 — Unsupported Source Notification

PanoPilot shall identify a selected Source Recording that cannot be
processed.

**Verification:** Test  
**Trace:** UC-02


## SYS-MEDIA-005 — Independent Source Acceptance

Failure to accept one selected Source Recording shall not prevent other
supported recordings selected in the same operation from being added.

**Verification:** Test  
**Trace:** UC-02


## SYS-MEDIA-006 — Source Immutability

PanoPilot shall not modify the contents of an original Source Recording.

**Verification:** Test  
**Trace:** UC-02, UC-03, UC-04, UC-13


## SYS-MEDIA-007 — Source Identity

PanoPilot shall maintain sufficient identity information for a Source
Recording to detect when a Project reference resolves to different media.

**Verification:** Test  
**Trace:** UC-02, UC-12

---

# 6. Clip Management

## SYS-CLIP-001 — Clip Creation

PanoPilot shall create one Clip for each Source Recording successfully added
to the Project.

**Verification:** Test  
**Trace:** UC-02


## SYS-CLIP-002 — Sequential Timeline

PanoPilot shall represent Project Clips sequentially on one non-overlapping
Project Timeline.

**Verification:** Test  
**Trace:** UC-02, UC-03


## SYS-CLIP-003 — Clip Selection

PanoPilot shall permit the User to select a Clip from the Project Timeline.

**Verification:** Test  
**Trace:** UC-03


## SYS-CLIP-004 — Clip Reordering

PanoPilot shall permit the User to change Clip order through direct timeline
interaction.

**Verification:** Demonstration  
**Trace:** UC-03


## SYS-CLIP-005 — Clip Removal

PanoPilot shall permit the User to remove a Clip from the Project.

**Verification:** Test  
**Trace:** UC-03


## SYS-CLIP-006 — Remove Does Not Delete Source

Removing a Clip shall not delete or modify its Source Recording.

**Verification:** Test  
**Trace:** UC-03


## SYS-CLIP-007 — Independent Clip State

PanoPilot shall maintain trim and View Path state independently for each
Clip.

**Verification:** Test  
**Trace:** UC-03, UC-04, UC-07


## SYS-CLIP-008 — Reorder Preservation

Reordering a Clip shall preserve its trim range and View Path.

**Verification:** Test  
**Trace:** UC-03

---

# 7. Trim

## SYS-TRIM-001 — In Point

PanoPilot shall permit the User to define a Source Time In point for a Clip.

**Verification:** Test  
**Trace:** UC-04


## SYS-TRIM-002 — Out Point

PanoPilot shall permit the User to define a Source Time Out point for a Clip.

**Verification:** Test  
**Trace:** UC-04


## SYS-TRIM-003 — Valid Range

PanoPilot shall enforce:

```text
0 ≤ source_in < source_out ≤ source_duration
```

**Verification:** Test  
**Trace:** UC-04


## SYS-TRIM-004 — Trimmed Playback

Clip and Project playback shall use only the Source Time interval bounded by
the Clip In and Out points.

**Verification:** Test  
**Trace:** UC-04, UC-08, UC-09


## SYS-TRIM-005 — Trimmed Export

Project export shall use only the Source Time interval bounded by each Clip
In and Out point.

**Verification:** Test  
**Trace:** UC-04, UC-13


## SYS-TRIM-006 — Non-Destructive Trim

Changing Clip trim shall not modify the Source Recording.

**Verification:** Test  
**Trace:** UC-04


## SYS-TRIM-007 — Preserve Camera Source Anchors

Changing a Clip In or Out point shall not change the Source Time stored by an
existing Camera Position.

**Verification:** Test  
**Trace:** UC-04


## SYS-TRIM-008 — Out-of-Range Camera Position Retention

A Camera Position outside the current Clip trim range shall remain in the
Clip's View Path data.

**Verification:** Test  
**Trace:** UC-04


## SYS-TRIM-009 — Out-of-Range Camera Position Inactivity

A Camera Position outside the current Clip trim range shall not affect
playback or export while it remains outside that range.

**Verification:** Test  
**Trace:** UC-04

---

# 8. Preview Preparation

## SYS-PREV-001 — Navigable Panoramic Preview

PanoPilot shall provide a navigable panoramic preview for each supported
Clip.

**Verification:** Demonstration  
**Trace:** UC-02, UC-06


## SYS-PREV-002 — Automatic Preview Preparation

PanoPilot shall prepare/select media required for interactive preview without
requiring the User to manually generate a proxy.

**Verification:** Demonstration  
**Trace:** UC-02


## SYS-PREV-003 — Preparation State

While a Clip is not ready for interactive preview, PanoPilot shall indicate
its preparation state.

**Verification:** Demonstration  
**Trace:** UC-02


## SYS-PREV-004 — Per-Clip Preparation Isolation

Preview preparation failure for one Clip shall not prevent use of another
Clip whose preview is ready.

**Verification:** Test  
**Trace:** UC-02

---

# 9. Output Profile

## SYS-OUT-001 — 16:9

PanoPilot shall support a 16:9 Project Output Profile.

**Verification:** Test  
**Trace:** UC-05


## SYS-OUT-002 — 9:16

PanoPilot shall support a 9:16 Project Output Profile.

**Verification:** Test  
**Trace:** UC-05


## SYS-OUT-003 — Project-Wide Profile

One Output Profile shall apply to all Clips in an Iteration 1 Project.

**Verification:** Test  
**Trace:** UC-05, UC-09, UC-13


## SYS-OUT-004 — Output Resolution

PanoPilot shall determine Project output width and height according to
`OUTPUT-PROFILE-001`.

**Verification:** Test  
**Trace:** UC-05, UC-13


## SYS-OUT-005 — Output Frame Rate

PanoPilot shall determine one Project output frame rate according to
`OUTPUT-PROFILE-001`.

**Verification:** Test  
**Trace:** UC-05, UC-13


## SYS-OUT-006 — Preview Geometry

PanoPilot shall display the selected Output Profile geometry during
reframing.

**Verification:** Demonstration  
**Trace:** UC-05, UC-06

---

# 10. Virtual Camera

## SYS-CAM-001 — Complete Horizontal Orientation

The Virtual Camera shall support horizontal orientation throughout the full
360-degree panoramic representation.

**Verification:** Test  
**Trace:** UC-06


## SYS-CAM-002 — Vertical Orientation

The Virtual Camera shall support vertical viewing orientation.

**Verification:** Test  
**Trace:** UC-06


## SYS-CAM-003 — Field of View

The Virtual Camera shall support adjustable field of view.

**Verification:** Test  
**Trace:** UC-06


## SYS-CAM-004 — Mouse Orientation

While the pointer is over the preview, PanoPilot shall change exploratory
Virtual Camera orientation in response to a mouse drag.

**Verification:** Test  
**Trace:** UC-06


## SYS-CAM-005 — Mouse-Wheel Zoom

While the pointer is over the preview, PanoPilot shall change exploratory
Virtual Camera field of view in response to mouse-wheel input.

**Verification:** Test  
**Trace:** UC-06


## SYS-CAM-006 — Coordinate-Free Primary Workflow

The primary reframing workflow shall permit completion without numerical
orientation or field-of-view entry.

**Verification:** Demonstration  
**Trace:** UC-06, UC-07


## SYS-CAM-007 — Reset View

PanoPilot shall provide an operation that restores the defined default
exploratory Camera State for the active Clip.

**Verification:** Test  
**Trace:** UC-06


## SYS-CAM-008 — Canonical Camera Semantics

PanoPilot shall apply one defined logical Camera State interpretation to
preview and final rendering.

**Verification:** Analysis / Test  
**Trace:** UC-08, UC-13


## SYS-CAM-009 — Preview/Render Camera Equivalence

For the same Source Time, Camera State, and Output Profile, preview and final
rendering shall produce geometrically equivalent framing within
`CAMERA-EQUIVALENCE-001`.

**Verification:** Test  
**Trace:** UC-08, UC-13

---

# 11. Exploration and Commit

## SYS-EDIT-001 — Non-Committing Exploration

Changing exploratory Camera State shall not modify a persisted Camera
Position unless the User explicitly commits the view.

**Verification:** Test  
**Trace:** UC-06


## SYS-EDIT-002 — Explicit Commit

PanoPilot shall provide an explicit User action for storing the displayed
composition as a Camera Position.

**Verification:** Demonstration  
**Trace:** UC-07


## SYS-EDIT-003 — Reset Does Not Modify View Path

Reset View shall not modify existing Camera Positions.

**Verification:** Test  
**Trace:** UC-06

---

# 12. Time Navigation

## SYS-TIME-001 — Clip Playback

PanoPilot shall permit playback of the selected Clip.

**Verification:** Test  
**Trace:** UC-08


## SYS-TIME-002 — Pause

PanoPilot shall permit active playback to be paused.

**Verification:** Test  
**Trace:** UC-08, UC-09


## SYS-TIME-003 — Seek

PanoPilot shall permit the User to select a time within the active Clip.

**Verification:** Test  
**Trace:** UC-07


## SYS-TIME-004 — Scrub Preview

PanoPilot shall display corresponding preview imagery while the User scrubs.

**Verification:** Demonstration  
**Trace:** UC-07


## SYS-TIME-005 — Project Playback

PanoPilot shall permit playback of the complete Project Timeline.

**Verification:** Demonstration  
**Trace:** UC-09


## SYS-TIME-006 — Sequential Playback

Project playback shall advance through Clips according to Timeline order.

**Verification:** Test  
**Trace:** UC-09


## SYS-TIME-007 — Deterministic Time Mapping

PanoPilot shall deterministically map Project Time to active Clip, Clip Time,
and Source Time.

**Verification:** Test  
**Trace:** UC-08, UC-09

---

# 13. Camera Positions

## SYS-POS-001 — Source-Time Anchor

PanoPilot shall associate each Camera Position with Source Time in its
owning Clip's Source Recording.

**Verification:** Test  
**Trace:** UC-07


## SYS-POS-002 — Derived Clip-Time Display

When PanoPilot displays a Camera Position relative to the Clip, it shall
derive that displayed Clip Time from the Camera Position Source Time and the
current Clip In point.

**Verification:** Test  
**Trace:** UC-04, UC-07


## SYS-POS-003 — Create

PanoPilot shall permit the User to create a Camera Position from the current
Virtual Camera composition.

**Verification:** Demonstration  
**Trace:** UC-07


## SYS-POS-004 — Modify

PanoPilot shall permit the User to modify an existing Camera Position.

**Verification:** Test  
**Trace:** UC-07


## SYS-POS-005 — Delete

PanoPilot shall permit the User to delete an existing Camera Position.

**Verification:** Test  
**Trace:** UC-07


## SYS-POS-006 — Move in Time

PanoPilot shall permit the User to move an existing Camera Position to a
different Source Time through timeline interaction.

**Verification:** Test  
**Trace:** UC-07


## SYS-POS-007 — Visualize

PanoPilot shall visually identify Camera Positions relative to the active
Clip.

**Verification:** Demonstration  
**Trace:** UC-07

---

# 14. View Path

## SYS-PATH-001 — Per-Clip View Path

PanoPilot shall maintain an independent View Path for each Clip.

**Verification:** Test  
**Trace:** UC-07


## SYS-PATH-002 — State Evaluation

PanoPilot shall determine effective Camera State for Source Times within the
active Clip range.

**Verification:** Test  
**Trace:** UC-07, UC-08


## SYS-PATH-003 — Continuous Default Motion

PanoPilot shall provide continuous default camera motion between consecutive
active Camera Positions.

**Verification:** Demonstration  
**Trace:** UC-07, UC-08


## SYS-PATH-004 — Panoramic Wrap

PanoPilot shall avoid unintended full-circle rotation when evaluating camera
motion across the horizontal panoramic wrap boundary.

**Verification:** Test  
**Trace:** UC-07


## SYS-PATH-005 — Playback Application

PanoPilot shall apply the active Clip's View Path during Clip and Project
playback.

**Verification:** Test  
**Trace:** UC-08, UC-09


## SYS-PATH-006 — Reorder Independence

Changing a Clip's Project Timeline position shall not alter its View Path.

**Verification:** Test  
**Trace:** UC-03, UC-07

---

# 15. Audio Preview

## SYS-AUDIO-001 — Clip Preview Audio

When source audio is available, PanoPilot shall play corresponding audio
during Clip preview.

**Verification:** Test  
**Trace:** UC-08


## SYS-AUDIO-002 — Project Preview Audio

When source audio is available, PanoPilot shall play corresponding audio
during Project playback.

**Verification:** Test  
**Trace:** UC-09


## SYS-AUDIO-003 — Preview AV Sync

Preview audio/video synchronization error shall not exceed
`PREVIEW-AV-SYNC-001`.

**Verification:** Test  
**Trace:** UC-08, UC-09

---

# 16. Undo and Redo

## SYS-HIST-001 — Undo

PanoPilot shall permit the User to undo the most recent supported logical
editing transaction.

**Verification:** Test  
**Trace:** UC-10


## SYS-HIST-002 — Redo

PanoPilot shall permit redo of an undone transaction when no intervening
edit invalidates the redo state.

**Verification:** Test  
**Trace:** UC-10


## SYS-HIST-003 — Gesture Transaction

A continuous direct-manipulation gesture that changes one logical edit shall
create no more than one Undo history entry when committed.

**Verification:** Test  
**Trace:** UC-03, UC-04, UC-07, UC-10


## SYS-HIST-004 — Core Edit Coverage

Clip reorder/removal, trim change, and Camera Position create/modify/delete/
move operations shall be undoable.

**Verification:** Test  
**Trace:** UC-10

---

# 17. Project Persistence

## SYS-SAVE-001 — Save Project

PanoPilot shall permit the User to save the current Project.

**Verification:** Test  
**Trace:** UC-11


## SYS-SAVE-002 — Persist Source References

Saved Project state shall preserve each Source Recording reference and
expected Source Identity.

**Verification:** Test  
**Trace:** UC-11


## SYS-SAVE-003 — Persist Clip State

Saved Project state shall preserve Clip order and trim ranges.

**Verification:** Test  
**Trace:** UC-11


## SYS-SAVE-004 — Persist View Paths

Saved Project state shall preserve Camera Positions and View Paths.

**Verification:** Test  
**Trace:** UC-11


## SYS-SAVE-005 — Persist Output Profile

Saved Project state shall preserve the Project Output Profile.

**Verification:** Test  
**Trace:** UC-11


## SYS-SAVE-006 — Open Project

PanoPilot shall permit the User to open a previously saved Project.

**Verification:** Test  
**Trace:** UC-12


## SYS-SAVE-007 — Restore Project

Opening a valid saved Project shall restore its Clip order, trim ranges,
Output Profile, and View Paths.

**Verification:** Test  
**Trace:** UC-12


## SYS-SAVE-008 — Missing Source Detection

PanoPilot shall identify a referenced Source Recording that cannot be
located.

**Verification:** Test  
**Trace:** UC-12


## SYS-SAVE-009 — Source Identity Mismatch

PanoPilot shall identify a resolved source file that does not match the
expected Source Identity.

**Verification:** Test  
**Trace:** UC-12


## SYS-SAVE-010 — No Silent Source Substitution

PanoPilot shall not silently substitute mismatched media for a referenced
Source Recording.

**Verification:** Test  
**Trace:** UC-12


## SYS-SAVE-011 — Save Failure Safety

An interrupted or failed save shall not invalidate the last successfully
saved Project.

**Verification:** Test  
**Trace:** UC-11


## SYS-SAVE-012 — Source Separation

Saving a Project shall not modify referenced Source Recordings.

**Verification:** Test  
**Trace:** UC-11

---

# 18. Export

## SYS-EXP-001 — Conventional Project Export

PanoPilot shall export the Project Timeline as one conventional non-360 video
file.

**Verification:** Test  
**Trace:** UC-13


## SYS-EXP-002 — Timeline Order

The exported video shall contain Clips in Project Timeline order.

**Verification:** Test  
**Trace:** UC-13


## SYS-EXP-003 — Trim

The exported video shall use each Clip's configured trim interval.

**Verification:** Test  
**Trace:** UC-13


## SYS-EXP-004 — View Path

The exported video shall apply each Clip's View Path.

**Verification:** Test  
**Trace:** UC-13


## SYS-EXP-005 — Output Profile

The exported video shall use the Project Output Profile.

**Verification:** Test  
**Trace:** UC-13


## SYS-EXP-006 — Final-Quality Source

PanoPilot shall derive exported image content from original source media or
an equivalent final-quality representation.

**Verification:** Test  
**Trace:** UC-13


## SYS-EXP-007 — H.264 MP4

PanoPilot shall export Iteration 1 output as H.264 video in an MP4 container.

**Verification:** Test  
**Trace:** UC-13


## SYS-EXP-008 — Source Audio

When corresponding source audio is available, PanoPilot shall include it in
the exported Project.

**Verification:** Test  
**Trace:** UC-13


## SYS-EXP-009 — Export AV Sync

Export audio/video synchronization error shall not exceed
`EXPORT-AV-SYNC-001`.

**Verification:** Test  
**Trace:** UC-13


## SYS-EXP-010 — Failed Export Status

PanoPilot shall not report an incomplete export as successfully completed.

**Verification:** Test  
**Trace:** UC-13


## SYS-EXP-011 — Export Source Integrity

Export shall not modify an original Source Recording.

**Verification:** Test  
**Trace:** UC-13

---

# 19. Performance and Work Isolation

## SYS-PERF-001 — Camera Response

When preview is ready, visible response to Virtual Camera manipulation shall
occur within `CAMERA-RESPONSE-001` on the reference system.

**Verification:** Performance Test  
**Trace:** UC-06


## SYS-PERF-002 — Scrub Response

When preview is ready, visual feedback for Clip scrubbing shall occur within
`SCRUB-RESPONSE-001` on the reference system.

**Verification:** Performance Test  
**Trace:** UC-07


## SYS-PERF-003 — Ready-Clip Isolation

Preview preparation for one Clip shall not prevent interaction with another
Clip whose preview is ready.

**Verification:** Test  
**Trace:** UC-02, UC-06


## SYS-PERF-004 — Long-Running Work

Long-running media processing shall not prevent unrelated available editing
operations.

**Verification:** Test  
**Trace:** UC-02 through UC-13

---

# 20. TBD / TBR Register

## SUPPORTED-OSV-PROFILE-001

Validated DJI Osmo 360 source configurations.

**Status:** TBD


## OUTPUT-PROFILE-001

Iteration 1 output resolution and frame-rate policy for 16:9 and 9:16.

**Status:** TBD


## CAMERA-EQUIVALENCE-001

Maximum accepted geometric difference between preview and final rendering for
the same Source Time and Camera State.

**Status:** TBD


## CAMERA-RESPONSE-001

Maximum accepted direct-manipulation response latency.

**Status:** TBD


## SCRUB-RESPONSE-001

Maximum accepted timeline scrub response latency.

**Status:** TBD


## PREVIEW-AV-SYNC-001

Maximum preview audio/video synchronization error.

**Status:** TBD


## EXPORT-AV-SYNC-001

Maximum exported audio/video synchronization error.

**Status:** TBD


## SOURCE-IDENTITY-001

Minimum media identity semantics used to detect mismatched referenced media.

**Status:** TBD

---

# 21. Iteration 1 Boundaries

Iteration 1 does not require:

- Clip splitting;
- multiple source ranges per Clip;
- multiple/overlapping video tracks;
- transitions;
- titles/overlays;
- color correction;
- audio mixing;
- speed changes;
- stabilization controls;
- tracking or AI reframing;
- advanced motion curves;
- manual proxy/cache configuration;
- user-configurable codec profiles;
- cloud processing;
- collaboration.

---

# 22. Iteration 1 Acceptance Scenario

Iteration 1 shall be considered functionally complete when the User can:

1. launch PanoPilot;
2. create a Project;
3. add multiple supported `.OSV` recordings;
4. reorder Clips;
5. trim a Clip;
6. select 16:9 or 9:16;
7. explore a panorama without changing the View Path;
8. commit multiple Camera Positions;
9. preview smooth reframing with audio;
10. change trim and verify Camera Positions remain attached to the same source
    content;
11. undo and redo an editing gesture;
12. preview the complete Project;
13. save the Project safely;
14. reopen it and verify referenced source identity;
15. export a conventional H.264/MP4 with synchronized audio.

The workflow shall require no manual source conversion, proxy generation,
stitch configuration, panoramic filter configuration, or numerical camera
orientation entry.