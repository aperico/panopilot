# PanoPilot — Use Cases

Status: Draft  
Baseline: UC-0.6  
Scope: Iteration 1  
Parent: `01_system_definition.md`  
Requirements: `03_system_requirements.md`

---

# 1. Purpose

This document defines the minimum complete user-level use cases for the first
usable iteration of PanoPilot.

The end-to-end workflow is:

```text
Create Project
      ↓
Add panoramic recordings
      ↓
Arrange and trim Clips
      ↓
Choose output
      ↓
Explore panorama
      ↓
Commit Camera Positions
      ↓
Preview Clip / Project
      ↓
Undo/Redo as required
      ↓
Save / Reopen
      ↓
Export
```

---

# 2. Primary Actor

## ACT-01 — User

The User:

- creates a Project;
- adds panoramic recordings;
- arranges and trims Clips;
- navigates panoramic content;
- positions the Virtual Camera;
- commits Camera Positions;
- previews the edit;
- saves and reopens work;
- exports conventional video.

The User is not expected to understand panoramic projection mathematics or
DJI-specific media internals.

---

# 3. Core UX and Domain Invariants

## UXI-01 — Exploring Is Not Editing

Dragging, zooming, or resetting the exploratory Virtual Camera does not
modify the committed View Path.

A Camera Position changes only through an explicit commit/update action.

---

## UXI-02 — Source Media Is Immutable

Editing operations do not modify original Source Recordings.

---

## UXI-03 — View Path Belongs to Clip

Each Clip owns an independent View Path.

Reordering the Clip does not change that View Path.

---

## UXI-04 — Camera Positions Are Source-Time Anchored

A Camera Position is stored relative to Source Time in the Clip's Source
Recording.

The interface may display Clip Time derived from:

```text
clip_time = source_time - source_in
```

---

## UXI-05 — Trimming Does Not Retime Reframing

Changing a Clip In/Out range does not move Camera Positions relative to the
underlying source content.

A Camera Position outside the current trim range remains stored but inactive
until that source time becomes included again.

---

## UXI-06 — One Project Output Profile

All Clips in an Iteration 1 Project use one Output Profile.

---

## UXI-07 — One Gesture, One Edit Transaction

A continuous direct-manipulation gesture such as dragging a trim handle or
moving a Camera Position is committed as one logical undoable edit.

---

# 4. Use Case Overview

| ID | Use Case | User Goal |
|---|---|---|
| UC-01 | Start New Project | Begin an editing session |
| UC-02 | Add Panoramic Recordings | Add one or more OSV recordings |
| UC-03 | Manage Clip Sequence | Select, reorder, or remove Clips |
| UC-04 | Trim Clip | Select the useful continuous portion |
| UC-05 | Select Output Profile | Choose landscape or vertical output |
| UC-06 | Explore and Reframe Clip | Visually position the Virtual Camera |
| UC-07 | Define and Edit View Path | Define camera behavior over source time |
| UC-08 | Preview Reframed Clip | Evaluate one Clip with audio |
| UC-09 | Preview Project Sequence | Evaluate the complete ordered Project |
| UC-10 | Undo or Redo Edit | Recover from an editing action |
| UC-11 | Save Project | Preserve editing work safely |
| UC-12 | Reopen Project | Continue a previous edit |
| UC-13 | Export Project | Produce final conventional video |

---

# 5. UC-01 — Start New Project

## Goal

Establish a new PanoPilot editing session.

## Preconditions

PanoPilot is installed.

## Main Flow

1. The User launches PanoPilot.
2. PanoPilot displays its desktop application window.
3. The User creates a new Project.
4. PanoPilot creates an empty Project Timeline.
5. PanoPilot exposes the operation for adding recordings.

## Postconditions

An empty Project is active.

---

# 6. UC-02 — Add Panoramic Recordings

## Goal

Add one or more supported DJI Osmo 360 recordings.

## Preconditions

- A Project exists.
- Source files are accessible locally.

## Main Flow

1. The User invokes Add Media.
2. PanoPilot displays local file selection.
3. The User selects one or more `.OSV` files.
4. PanoPilot evaluates each selected recording.
5. PanoPilot establishes Source Identity for each accepted recording.
6. PanoPilot creates a Clip for each accepted recording.
7. New Clips are appended sequentially.
8. PanoPilot begins preview preparation where required.
9. Each Clip becomes available for reframing when ready.

## Alternate Flow A — Unsupported Recording

1. One recording cannot be processed.
2. PanoPilot identifies that recording.
3. Other valid selected recordings continue.

## Alternate Flow B — Preview Preparation

1. The Clip remains visible while preview media is preparing.
2. PanoPilot shows its preparation state.
3. Ready Clips remain usable.

## Alternate Flow C — Preview Preparation Failure

1. Preparation fails for one Clip.
2. PanoPilot identifies the affected Clip.
3. Other ready Clips remain usable.

## Postconditions

Accepted recordings are represented as Clips and original media remains
unchanged.

---

# 7. UC-03 — Manage Clip Sequence

## Goal

Define the sequential Project order.

## Main Flow — Select

1. The User selects a Clip.
2. PanoPilot makes it active for editing.

## Main Flow — Reorder

1. The User drags a Clip to another timeline location.
2. PanoPilot commits the reorder as one edit transaction.
3. Project playback order changes.
4. The Clip's trim range and View Path remain unchanged.

## Main Flow — Remove

1. The User removes a Clip.
2. PanoPilot removes only the Project Clip instance.
3. The Source Recording remains unchanged.

## Postconditions

The timeline reflects the desired Project sequence.

---

# 8. UC-04 — Trim Clip

## Goal

Select the continuous source interval used by a Clip.

## Main Flow

1. The User selects a Clip.
2. PanoPilot displays the available source interval.
3. The User adjusts the In point.
4. The User adjusts the Out point.
5. Each continuous handle drag is committed as one editing transaction.
6. Playback/export uses only the resulting source range.

## Alternate Flow A — Existing Camera Positions

1. The User changes the trim range after reframing already exists.
2. PanoPilot keeps every Camera Position attached to its original Source Time.
3. Camera Positions outside the new trim become inactive.
4. Camera Positions remaining inside the trim keep framing the same source
   events.

## Alternate Flow B — Expand Trim Again

1. The User expands the trim range.
2. Previously inactive Camera Positions whose Source Time is now inside the
   range become applicable again.

## Postconditions

The Clip has one valid continuous source interval.

The Source Recording and source-time anchors of Camera Positions remain
unchanged.

---

# 9. UC-05 — Select Output Profile

## Goal

Choose the conventional Project output orientation.

## Main Flow — Landscape

1. The User selects 16:9.
2. PanoPilot applies the corresponding Project Output Profile.
3. Preview uses that output geometry.

## Alternate Flow — Vertical

1. The User selects 9:16.
2. PanoPilot applies the corresponding Project Output Profile.

## Notes

Iteration 1 may determine output resolution and frame rate automatically
according to the Project output policy.

## Postconditions

One Output Profile applies to the Project.

---

# 10. UC-06 — Explore and Reframe Clip

## Goal

Visually explore the 360 recording and compose a possible output view.

## Preconditions

The selected Clip preview is ready.

## Main Flow

1. PanoPilot displays the Clip through the Virtual Camera.
2. The User drags horizontally and vertically.
3. PanoPilot updates exploratory camera orientation.
4. The User uses the mouse wheel.
5. PanoPilot updates field of view.
6. PanoPilot continuously displays the conventional Output Frame.

## Alternate Flow — Reset View

1. The User invokes Reset View.
2. PanoPilot restores the defined default exploratory Camera State.
3. Existing Camera Positions remain unchanged.

## Important Behavior

Exploration does not change the View Path.

## Postconditions

A possible visual composition exists in temporary session state.

---

# 11. UC-07 — Define and Edit View Path

## Goal

Specify where the Virtual Camera looks over the Clip's source content.

## Main Flow — Create Camera Positions

1. The User seeks to a desired point in the Clip.
2. PanoPilot maps the displayed Clip Time to Source Time.
3. The User visually composes the desired frame.
4. The User invokes Use This View.
5. PanoPilot stores a Camera Position anchored to the current Source Time.
6. The User moves to another point and repeats the operation.
7. PanoPilot evaluates intermediate Camera State between positions.
8. PanoPilot visualizes Camera Positions in the Clip timeline.

## Alternate Flow A — Modify

1. The User selects a Camera Position.
2. PanoPilot restores its Camera State.
3. The User adjusts the composition.
4. The User commits the update.
5. The entire direct manipulation is one logical edit transaction.

## Alternate Flow B — Delete

The User deletes a Camera Position and the effective View Path is reevaluated.

## Alternate Flow C — Move in Time

1. The User moves a Camera Position in the Clip timeline.
2. PanoPilot maps the selected displayed time to a new Source Time.
3. The Camera Position receives the new Source Time.
4. The drag is one undoable transaction.

## Alternate Flow D — Panoramic Wrap

PanoPilot evaluates camera movement across the 360-degree seam without an
unintended long rotation.

## Postconditions

The Clip owns a source-time-anchored View Path.

---

# 12. UC-08 — Preview Reframed Clip

## Goal

Evaluate one reframed Clip with audio.

## Main Flow

1. The User starts Clip playback.
2. Playback is limited to the Clip trim range.
3. PanoPilot maps current playback time to Source Time.
4. PanoPilot evaluates the View Path at that Source Time.
5. The canonical Virtual Camera produces the preview frame.
6. Corresponding source audio plays in synchronization.
7. The User may pause, seek, and refine the edit.

---

# 13. UC-09 — Preview Project Sequence

## Goal

Evaluate the complete Project.

## Main Flow

1. The User starts Project playback.
2. PanoPilot maps Project Time to the active Clip and Source Time.
3. The active Clip's trim and View Path are applied.
4. Corresponding audio plays.
5. At the Clip Out point, playback advances to the next Clip.
6. Playback continues until the Project ends or the User pauses.

## Alternate Flows

The User may pause and return to:

- UC-03 to reorder;
- UC-04 to trim;
- UC-06/UC-07 to reframe.

---

# 14. UC-10 — Undo or Redo Edit

## Goal

Recover from an editing action.

## Main Flow — Undo

1. The User invokes Undo.
2. PanoPilot restores the state before the most recent supported logical
   editing transaction.

## Main Flow — Redo

1. The User invokes Redo.
2. PanoPilot reapplies the previously undone transaction when still valid.

## Minimum Undoable Operations

- Clip reorder;
- Clip removal;
- trim adjustment;
- Camera Position creation;
- Camera Position modification;
- Camera Position deletion;
- Camera Position movement in time.

## Transaction Rule

A continuous gesture is one Undo step.

---

# 15. UC-11 — Save Project

## Goal

Preserve the edit safely.

## Main Flow

1. The User invokes Save.
2. For a new Project, the User selects a Project-file location.
3. PanoPilot writes sufficient state to reproduce the edit.
4. PanoPilot marks the Project as saved.

## Minimum Persisted State

- Project format/version;
- Source Recording references and expected Source Identities;
- Clip instances and order;
- trim ranges;
- Output Profile;
- Camera Positions and View Paths.

## Alternate Flow — Save Interrupted or Failed

1. Saving does not complete.
2. PanoPilot reports the failure.
3. The last successfully saved Project remains usable.

## Postconditions

The Project can be reopened without modifying source media.

---

# 16. UC-12 — Reopen Project

## Goal

Continue a saved edit.

## Main Flow

1. The User selects a saved PanoPilot Project.
2. PanoPilot restores Project state.
3. PanoPilot resolves referenced Source Recordings.
4. PanoPilot verifies expected Source Identity.
5. Clip order, trim, Output Profile, and View Paths are restored.
6. Preview media is prepared/reused as necessary.

## Alternate Flow A — Missing Source

PanoPilot identifies the missing source rather than silently substituting
another file.

## Alternate Flow B — Source Identity Mismatch

1. A file exists at the expected location but does not match the expected
   Source Identity.
2. PanoPilot identifies the mismatch.
3. PanoPilot does not silently treat that file as the original source.

---

# 17. UC-13 — Export Project

## Goal

Produce one conventional video.

## Main Flow

1. The User selects an export destination.
2. PanoPilot processes Clips in Project Timeline order.
3. Each Clip is limited to its trim range.
4. Final-quality source media is read.
5. The same logical Camera/ViewPath semantics used by preview are applied.
6. Each frame follows the Project Output Profile.
7. Corresponding source audio is included.
8. PanoPilot produces H.264 video in an MP4 container.
9. PanoPilot reports success.

## Alternate Flow — Export Failure

1. Export fails.
2. PanoPilot does not report success.
3. Original source media remains unchanged.
4. The saved Project remains usable.

---

# 18. Minimum Functional Coverage

| Capability | Use Case |
|---|---|
| New Project | UC-01 |
| Multi-file OSV add | UC-02 |
| Preview preparation state | UC-02 |
| Clip select/reorder/remove | UC-03 |
| Source-time-preserving trim | UC-04 |
| 16:9 / 9:16 output | UC-05 |
| Direct panoramic exploration | UC-06 |
| Reset without editing | UC-06 |
| Explicit Camera Position commit | UC-07 |
| Source-time Camera Positions | UC-07 |
| View Path interpolation | UC-07 |
| 360-wrap handling | UC-07 |
| Clip preview + audio | UC-08 |
| Project preview + audio | UC-09 |
| Transactional Undo/Redo | UC-10 |
| Safe Project save | UC-11 |
| Source identity verification | UC-12 |
| Project restore | UC-12 |
| Final MP4 export | UC-13 |

---

# 19. Explicitly Excluded Use Cases

Iteration 1 does not include:

- Split Clip;
- multiple source ranges inside one Clip;
- overlapping/multi-track editing;
- transitions;
- titles/overlays;
- picture-in-picture;
- color grading;
- audio mixing/replacement;
- playback-speed changes;
- stabilization controls;
- automatic subject tracking;
- AI-assisted reframing;
- advanced curve editing;
- user-managed proxy/cache configuration;
- user-managed codec profiles;
- cloud processing;
- collaboration.

---

# 20. Iteration 1 Acceptance Journey

```text
Launch
  ↓
Create Project
  ↓
Add several OSV recordings
  ↓
Observe preview preparation
  ↓
Reorder Clips
  ↓
Trim a Clip
  ↓
Select 16:9 or 9:16
  ↓
Explore panorama without editing
  ↓
Commit Camera Position
  ↓
Commit additional Camera Position
  ↓
Preview View Path + audio
  ↓
Change trim and confirm Camera Positions remain attached to source events
  ↓
Undo / Redo
  ↓
Preview complete Project
  ↓
Save
  ↓
Close and reopen
  ↓
Verify source identities and restored edit
  ↓
Export MP4
```


---

# 20. Use-Case Clarifications — PanoPilot 0.19

## UC-07 Clarification — Set Camera and Camera Motion

The explicit View Path edit action is **Set Camera**.

1. The User explores the panoramic scene.
2. Exploration alone does not modify the Project.
3. The User invokes Set Camera.
4. PanoPilot creates or updates a Camera Position at the current Source Time.
5. The Camera Position is made durable through atomic Project save.
6. Between Camera Positions, PanoPilot evaluates the configured Project Camera
   Motion preset and Amount.
7. The User may change Camera Motion and immediately preview the resulting View
   Path.
8. Camera Motion changes participate in Undo/Redo and normal Project Save
   semantics.

When a Clip has zero Camera Positions, the Clip View Path evaluates to the
default camera. A manually explored camera may be previewed transiently without
creating an edit.

## UC-09 Clarification — Project Preview

Current Project Preview flow:

1. The User invokes Preview Project from the Project Organizer, or runs
   `panopilot project-preview`.
2. If Project edits are unsaved, PanoPilot requires an explicit Save before
   opening the read-only Project preview.
3. PanoPilot ensures a disposable panoramic preview exists for each Clip.
4. PanoPilot displays a Project Timeline playhead.
5. Project Time is mapped to the active Clip and Source Time.
6. The active Clip's trim, View Path, Project Camera Motion, and Output Frame
   aspect are applied.
7. When source audio is available, corresponding audio for the active Clip is
   played.
8. At Clip Out, playback changes to the next Clip in Project order.
9. At Project end, playback stops.
10. If the User presses Play at Project end, playback restarts from Project
    Time zero.
11. The User may pause or seek anywhere on the Project Timeline.
12. Closing Project Preview returns to the Project Organizer.

Project Preview is non-authoritative: it creates no editing state.


---

# 21. UC-13 Implementation Clarification — Final Project Export

Current final export flow:

1. The User invokes Export Project in the Project Organizer or runs
   `panopilot project-export`.
2. PanoPilot requires saved Project state before export begins.
3. The User selects one MP4 destination.
4. PanoPilot verifies that every referenced original Source Recording exists.
5. PanoPilot resolves the Project Output Profile from the saved aspect.
6. PanoPilot builds the ordered Project Timeline and one global CFR frame plan.
7. For each active Clip, PanoPilot decodes the original synchronized OSV lens
   streams, applies DJI factory calibration, horizon correction, the Clip View
   Path, Project Camera Motion, and Output Profile geometry.
8. PanoPilot encodes all resulting frames as one continuous H.264 video stream.
9. PanoPilot assembles corresponding source audio trims in Project order.
10. PanoPilot inserts silence for a no-audio Clip only when other Project Clips
    contain audio and Timeline continuity must be preserved.
11. PanoPilot muxes the final video and audio into MP4.
12. PanoPilot verifies the resulting codec, geometry, expected audio presence,
    frame count when available, duration, and A/V stream-duration delta.
13. Only after verification does PanoPilot replace the requested output path.
14. PanoPilot reports export completion.

Failure before step 13 leaves any pre-existing requested output unchanged.
