# PanoPilot — Functional Architecture

Status: Draft  
Baseline: FA-0.1  
Scope: Iteration 1  
Parent: `01_system_definition.md`  
Use Cases: `02_use_cases.md`  
Requirements: `03_system_requirements.md`

---

# 1. Purpose

This document defines the functional architecture for the first usable
iteration of PanoPilot.

PanoPilot is a desktop application focused on reframing 360-degree panoramic
video into conventional video.

This document defines:

- the logical system functions;
- the responsibilities of each function;
- the principal domain entities;
- the information exchanged between functions;
- the functional behavior needed to satisfy the Iteration 1 use cases and
  system requirements.

This document intentionally does **not** select:

- programming languages;
- UI frameworks;
- desktop shell technology;
- media-processing libraries;
- GPU APIs;
- process boundaries;
- deployment packaging.

Those decisions belong to software architecture after the architecture-driving
technical risks have been demonstrated.

---

# 2. Architecture Objective

The functional architecture shall support the minimum complete PanoPilot
workflow:

```text
Create Project
      ↓
Add panoramic recordings
      ↓
Prepare panoramic previews
      ↓
Arrange and trim Clips
      ↓
Explore panoramic scene
      ↓
Define Camera Positions
      ↓
Generate View Path
      ↓
Preview Clip / Project
      ↓
Save and reopen Project
      ↓
Render final conventional video
```

The architecture shall remain focused on panoramic reframing.

It shall not introduce general-purpose nonlinear-editor functions that are not
required by Iteration 1.

---

# 3. First-Principles Functional Model

PanoPilot can be reduced to five fundamental transformations.

## 3.1 Source Recording → Panoramic Scene

The system interprets a supported camera recording and produces a usable
360-degree representation.

```text
Source Recording
       ↓
Panoramic Media Interpretation
       ↓
Panoramic Scene
```

---

## 3.2 Panoramic Scene + Camera State → Output Frame

A Virtual Camera selects a conventional view from the panoramic scene.

```text
Panoramic Scene
      +
Camera State
      ↓
Output Frame
```

---

## 3.3 Camera Positions → View Path

The User defines desired camera compositions at specific clip-local times.

```text
Camera Position A
Camera Position B
Camera Position C
       ↓
View Path Evaluation
       ↓
Camera State at time t
```

---

## 3.4 Source Recording + Trim + View Path → Reframed Clip

A Clip references a portion of a Source Recording and applies a View Path.

```text
Source Recording
      +
Trim Range
      +
View Path
      ↓
Reframed Clip
```

---

## 3.5 Ordered Reframed Clips → Project Output

The Project Timeline determines the sequential order of Clips.

```text
Reframed Clip A
Reframed Clip B
Reframed Clip C
       ↓
Project Timeline
       ↓
Conventional Project Video
```

These transformations form the core of the Iteration 1 architecture.

---

# 4. System Functional Context

```text
                         ┌─────────────────────┐
                         │        User         │
                         └──────────┬──────────┘
                                    │
                                    │ direct interaction
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PanoPilot                                      │
│                                                                             │
│  ┌───────────────┐     ┌────────────────┐     ┌─────────────────────────┐  │
│  │ Project & Clip│     │ Timeline &     │     │ Reframing Interaction  │  │
│  │ Management    │◄───►│ Time Mapping   │◄───►│                         │  │
│  └──────┬────────┘     └───────┬────────┘     └──────────┬──────────────┘  │
│         │                      │                         │                 │
│         │                      │                         ▼                 │
│         │              ┌───────▼────────┐      ┌──────────────────────┐  │
│         │              │ View Path      │◄────►│ Virtual Camera       │  │
│         │              │ Management     │      │                      │  │
│         │              └───────┬────────┘      └──────────┬───────────┘  │
│         │                      │                          │              │
│         ▼                      │                          ▼              │
│  ┌───────────────┐             │                ┌──────────────────────┐ │
│  │ Persistence & │             │                │ Panoramic Preview    │ │
│  │ Edit History  │             │                │ and Playback         │ │
│  └───────────────┘             │                └──────────┬───────────┘ │
│                                │                           │             │
│                                │                           ▼             │
│                       ┌────────▼──────────────────────────────────────┐  │
│                       │ Panoramic Media Services                     │  │
│                       │ - source inspection                          │  │
│                       │ - panoramic reconstruction                   │  │
│                       │ - preview preparation                        │  │
│                       │ - source audio access                        │  │
│                       └──────────────────┬────────────────────────────┘  │
│                                          │                               │
│                                          ▼                               │
│                               ┌──────────────────────┐                   │
│                               │ Final Render & Export│                   │
│                               └──────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                         Local Source / Project / Video Files
```

---

# 5. Functional Decomposition

The Iteration 1 system is decomposed into the following logical functions.

| ID | Functional Area | Primary Responsibility |
|---|---|---|
| FA-01 | Application Session | Establish and maintain the active desktop editing session |
| FA-02 | Project Management | Maintain Project-level state |
| FA-03 | Source Media Management | Accept and identify supported panoramic recordings |
| FA-04 | Clip Management | Maintain Clip instances and per-Clip state |
| FA-05 | Timeline Management | Maintain Clip order and project/clip time mapping |
| FA-06 | Trim Management | Maintain per-Clip source In/Out range |
| FA-07 | Preview Preparation | Produce/select media suitable for interactive operation |
| FA-08 | Panoramic Scene | Provide a navigable 360-degree scene |
| FA-09 | Virtual Camera | Define the conventional view into the panoramic scene |
| FA-10 | Reframing Interaction | Translate direct User input into temporary camera state |
| FA-11 | Camera Position Management | Create, modify, move, and delete committed Camera Positions |
| FA-12 | View Path Evaluation | Determine camera state over clip-local time |
| FA-13 | Playback | Preview Clips and the complete Project with audio |
| FA-14 | Edit History | Undo and redo supported editing operations |
| FA-15 | Project Persistence | Save and reopen Project state |
| FA-16 | Final Rendering | Apply trim and View Path to final-quality source media |
| FA-17 | Export Assembly | Produce the final sequential H.264/MP4 output |

---

# 6. FA-01 — Application Session

## Responsibility

Provide the functional context in which a User creates or opens a Project and
performs editing operations.

## Inputs

- User launch request;
- New Project request;
- Open Project request.

## Outputs

- active Project context;
- application state available to other functional areas.

## Key Behavior

The application session owns at most one active editing Project in Iteration 1.

Multi-project simultaneous editing is outside scope.

---

# 7. FA-02 — Project Management

## Responsibility

Maintain the top-level editing state of the current Project.

## Project Contains

```text
Project
├── project_id
├── output_frame
├── clips[]
└── project metadata required for persistence
```

## Responsibilities

- create a new Project;
- maintain Project Output Frame;
- provide ordered access to Clip instances;
- identify whether Project state has changed;
- provide Project state to persistence;
- provide Project state to playback and export.

## Architectural Rule

The Project contains editing metadata.

It does not contain destructive modifications to Source Recordings.

---

# 8. FA-03 — Source Media Management

## Responsibility

Accept local panoramic source media and expose the source information required
by the rest of the system.

## Source Recording Model

```text
SourceRecording
├── source_id
├── file_reference
├── duration
├── supported_state
├── video_media_descriptor
├── audio_media_descriptor
└── panoramic_metadata
```

The exact internal media descriptor format is a software architecture concern.

## Responsibilities

- accept one or more `.OSV` file selections;
- determine whether each selected recording is processable;
- determine source duration;
- expose media required for panoramic reconstruction;
- expose available audio;
- keep Source Recordings immutable.

## Failure Isolation

Failure to accept one recording shall not prevent other valid selected
recordings from becoming usable Clips.

---

# 9. FA-04 — Clip Management

## Responsibility

Represent each use of source media in the Project.

## Clip Model

```text
Clip
├── clip_id
├── source_recording_id
├── source_in
├── source_out
└── view_path
```

## Architectural Rule

A Clip is not the source file.

A Clip is a non-destructive Project instance that references a Source
Recording.

## Responsibilities

- create Clip instances;
- select an active Clip;
- remove a Clip from the Project;
- maintain Clip-local editing state;
- preserve the Clip's state when Project order changes.

---

# 10. FA-05 — Timeline Management

## Responsibility

Maintain the sequential order of Clips and map Project Time to Clip Time.

## Iteration 1 Timeline Model

```text
[ Clip A ][ Clip B ][ Clip C ]
```

The timeline is:

- sequential;
- single-track;
- non-overlapping.

## Required Time Domains

The architecture shall distinguish:

### Source Time

Timestamp in the original Source Recording.

### Clip-Local Time

Time within the active Clip after applying the Clip's In point.

### Project Time

Time within the complete ordered Project sequence.

## Mapping

Conceptually:

```text
Project Time
     ↓
Timeline Mapping
     ↓
Active Clip
     +
Clip-Local Time
     ↓
Source Time
```

For an unmodified-speed Clip:

```text
Source Time = source_in + clip_local_time
```

## Critical Architectural Rule

Camera Positions are expressed in **clip-local time**.

They shall not use Project Time.

Therefore:

```text
[A][B][C]
```

can become:

```text
[C][A][B]
```

without modifying any Camera Position inside A, B, or C.

---

# 11. FA-06 — Trim Management

## Responsibility

Define the continuous source interval represented by a Clip.

## Trim Model

```text
TrimRange
├── source_in
└── source_out
```

with:

```text
0 ≤ source_in < source_out ≤ source_duration
```

## Responsibilities

- set Clip In point;
- set Clip Out point;
- validate the range;
- provide effective Clip duration;
- constrain playback;
- constrain final rendering.

## Iteration 1 Constraint

A Clip has one continuous source range.

Split Clips and multiple source ranges are outside scope.

---

# 12. FA-07 — Preview Preparation

## Responsibility

Ensure each supported Clip can provide sufficiently responsive media for
interactive editing.

## Functional Model

```text
Source Recording
       ↓
Preview Preparation
       ↓
Preview Representation
```

The preview representation may be generated or selected.

The architecture does not prescribe whether it is:

- `.LRF`;
- a generated proxy;
- a stitched lower-resolution representation;
- another optimized representation.

## Required States

At minimum:

```text
NOT_READY
PREPARING
READY
FAILED
```

## Responsibilities

- initiate preparation;
- expose preparation state;
- allow ready Clips to remain usable while others prepare;
- expose a ready preview representation to panoramic preview functions.

## Architectural Rule

Preview media is derived data.

It is not the Project's source of truth.

---

# 13. FA-08 — Panoramic Scene

## Responsibility

Provide a navigable 360-degree representation of the selected source frame.

## Functional Input

```text
Source/Preview media
+
source timestamp
+
panoramic calibration/metadata
```

## Functional Output

```text
Panoramic Scene at time t
```

## Responsibilities

- reconstruct or expose the surrounding panoramic environment;
- abstract raw lens imagery from the User;
- provide panoramic scene data to the Virtual Camera.

## Architecture Boundary

The User interacts with a conventional framed view.

The raw equirectangular or fisheye representation is not the primary editing
surface.

---

# 14. FA-09 — Virtual Camera

## Responsibility

Define the view extracted from the Panoramic Scene.

## Camera State

Conceptually:

```text
CameraState
├── orientation
├── field_of_view
└── horizon_orientation
```

The internal representation of orientation may use:

- yaw/pitch/roll;
- quaternion;
- rotation matrix;
- another representation.

That decision belongs to software architecture.

## Functional Relationship

```text
Panoramic Scene
      +
Camera State
      +
Output Frame
      ↓
Conventional Frame
```

## Responsibilities

- represent complete horizontal orientation;
- represent vertical orientation;
- represent zoom/FOV;
- support reset/default state;
- provide the same logical camera semantics to preview and final rendering.

---

# 15. FA-10 — Reframing Interaction

## Responsibility

Translate direct User interaction into an exploratory Virtual Camera state.

## Inputs

- mouse drag;
- mouse wheel;
- Reset View;
- current Virtual Camera state.

## Outputs

- updated exploratory Camera State.

## Critical Interaction Invariant

```text
User explores panorama
        ↓
temporary Camera State changes
        ↓
View Path remains unchanged
```

Only an explicit commit operation transfers the displayed Camera State into a
Camera Position.

## Functional Model

```text
             mouse drag / zoom
                     ↓
            Exploratory Camera
                     │
                     │ explicit "Use this view"
                     ▼
             Camera Position
```

This separation prevents ordinary scene exploration from accidentally changing
the final edit.

---

# 16. FA-11 — Camera Position Management

## Responsibility

Maintain explicit User-defined camera states at selected clip-local times.

## Camera Position Model

```text
CameraPosition
├── position_id
├── clip_local_time
└── camera_state
```

## Responsibilities

- create a Camera Position from the current displayed composition;
- select a Camera Position;
- modify its Camera State;
- move its clip-local time;
- delete it;
- expose Camera Positions for timeline visualization.

## Architectural Rule

Camera Position state is committed editing metadata.

Exploratory Camera State is not.

---

# 17. FA-12 — View Path Evaluation

## Responsibility

Determine the effective Virtual Camera state for any clip-local time.

## Input

```text
clip_local_time
+
ordered Camera Positions
```

## Output

```text
CameraState(t)
```

## Functional Behavior

For time between Camera Positions:

```text
Position A                 Position B
    ●--------------------------●
             ↓
        CameraState(t)
```

## Responsibilities

- order Camera Positions by clip-local time;
- determine intermediate orientation;
- determine intermediate FOV;
- determine intermediate horizon orientation;
- provide deterministic state before/after defined Camera Positions;
- handle panoramic wrap without unintended full-circle movement.

## Iteration 1 Motion Model

One default interpolation behavior is sufficient.

Advanced easing and curve editing are outside scope.

---

# 18. FA-13 — Playback

## Responsibility

Provide audio/video preview of a Clip or complete Project.

## Clip Playback

```text
Clip-local time
      ↓
Source Time
      ↓
Panoramic Scene
      +
View Path CameraState(t)
      ↓
Output Frame
      +
Source Audio
```

## Project Playback

```text
Project Time
      ↓
Timeline Mapping
      ↓
Active Clip + Clip-Local Time
      ↓
Clip Playback
```

## Responsibilities

- play;
- pause;
- seek;
- scrub;
- apply trim range;
- apply View Path;
- present the selected Output Frame;
- play corresponding source audio;
- transition sequentially between Clips.

## Architecture Rule

Playback is a consumer of Timeline, View Path, Virtual Camera, and Media
functions.

Playback does not own the edit state.

---

# 19. FA-14 — Edit History

## Responsibility

Provide Undo and Redo for supported editing operations.

## Undoable Operation Categories

Iteration 1 includes:

- Clip reorder;
- Clip removal;
- trim change;
- Camera Position creation;
- Camera Position modification;
- Camera Position deletion;
- Camera Position time movement.

## Functional Model

```text
Project State N
     ↓ edit
Project State N+1
     ↓ undo
Project State N
     ↓ redo
Project State N+1
```

## Architectural Requirement

Editing operations shall be represented in a way that allows their previous
state to be restored.

The exact implementation pattern is deferred to software architecture.

---

# 20. FA-15 — Project Persistence

## Responsibility

Persist sufficient Project metadata to reproduce the User's edit.

## Persisted Information

At minimum:

```text
Project
├── project format/version
├── output frame
├── Source Recording references
└── Clips
    ├── order
    ├── source reference
    ├── source_in
    ├── source_out
    └── View Path
        └── Camera Positions
            ├── clip_local_time
            └── Camera State
```

## Save Flow

```text
Active Project State
       ↓
Serialization
       ↓
Project File
```

## Open Flow

```text
Project File
       ↓
Deserialization
       ↓
Resolve Source Recordings
       ↓
Restored Project State
```

## Missing Source Behavior

A missing source shall be represented explicitly.

The system shall not silently replace it with another media file.

Automatic relinking is outside Iteration 1 unless later promoted.

---

# 21. FA-16 — Final Rendering

## Responsibility

Produce final-quality reframed media for each Clip.

## Functional Input

```text
Source Recording
+
Trim Range
+
View Path
+
Output Frame
```

## Functional Output

```text
Rendered conventional Clip
```

## Rendering Model

For every output time `t` within the Clip:

```text
clip-local time t
        ↓
source time
        ↓
read original-quality panoramic source
        ↓
evaluate View Path CameraState(t)
        ↓
apply Virtual Camera
        ↓
produce output frame
```

## Architectural Rule

Final rendering shall not derive final-quality image content from a
reduced-quality interactive preview representation.

Preview and final rendering may use different media representations, but both
shall apply equivalent Virtual Camera and View Path semantics.

---

# 22. FA-17 — Export Assembly

## Responsibility

Combine rendered Clips and corresponding audio into the final Project output.

## Functional Model

```text
Rendered Clip A + Audio A
Rendered Clip B + Audio B
Rendered Clip C + Audio C
             ↓
        Sequential Assembly
             ↓
         H.264 / MP4
```

## Responsibilities

- preserve Project Timeline order;
- include only each Clip's trim range;
- preserve the rendered View Path;
- preserve corresponding source audio;
- generate one conventional non-360 output file;
- report success or failure.

---

# 23. Core Domain Model

The minimum domain model is:

```text
Project
│
├── output_frame
│
└── clips[]
      │
      └── Clip
            ├── clip_id
            ├── source_recording_id
            ├── source_in
            ├── source_out
            │
            └── view_path
                  │
                  └── CameraPosition[]
                        ├── position_id
                        ├── clip_local_time
                        └── camera_state
                              ├── orientation
                              ├── field_of_view
                              └── horizon_orientation
```

Supporting media model:

```text
SourceRecording
├── source_id
├── file_reference
├── duration
├── panoramic media information
└── audio information
```

Derived preview information is associated with the Source Recording but is not
part of the authoritative Project edit model.

---

# 24. Ownership Rules

The following ownership rules are architecture invariants.

## AR-OWN-001 — Source Ownership

SourceRecording owns source-media identity.

It does not own Project editing decisions.

---

## AR-OWN-002 — Clip Ownership

Clip owns:

- trim range;
- View Path.

---

## AR-OWN-003 — View Path Ownership

View Path owns Camera Positions for one Clip.

---

## AR-OWN-004 — Project Ownership

Project owns:

- Clip sequence;
- Project Output Frame.

---

## AR-OWN-005 — Preview Ownership

Preview data is derived from source media.

It does not own authoritative editing state.

---

# 25. State Separation

PanoPilot shall distinguish three categories of state.

## 25.1 Source State

Immutable information originating from camera media.

Examples:

- video;
- audio;
- calibration;
- duration.

---

## 25.2 Project State

Persistent non-destructive editing decisions.

Examples:

- Clip order;
- trim range;
- Output Frame;
- Camera Positions;
- View Paths.

---

## 25.3 Session State

Temporary runtime interaction state.

Examples:

- currently selected Clip;
- current playhead position;
- exploratory Camera State;
- temporary drag state;
- active UI selection.

## Architectural Rule

Session state shall not become persistent Project state unless an editing
operation explicitly commits it.

---

# 26. Primary Functional Flows

## 26.1 Add Media Flow

```text
User selects OSV files
        ↓
Source Media Management
        ↓
validate each source
        ↓
create Clip
        ↓
append Clip to Timeline
        ↓
Preview Preparation
        ↓
Clip READY
```

---

## 26.2 Reframe Flow

```text
User selects Clip
        ↓
Timeline identifies clip-local time
        ↓
Panoramic Scene
        ↓
Virtual Camera
        ↓
User drags / zooms
        ↓
Exploratory Camera State
        ↓
User selects "Use this view"
        ↓
Camera Position
        ↓
View Path updated
```

---

## 26.3 Playback Flow

```text
Playhead
   ↓
Timeline Mapping
   ↓
Active Clip + Clip-Local Time
   ↓
Trim Mapping
   ↓
Source Time
   ↓
Panoramic Scene + Source Audio
   ↓
View Path Camera State
   ↓
Virtual Camera
   ↓
Output Frame + synchronized audio
```

---

## 26.4 Reorder Flow

```text
User moves Clip C
      ↓
Timeline updates order
      ↓
Project Time offsets change
      ↓
Clip C source_in/source_out unchanged
      ↓
Clip C Camera Positions unchanged
      ↓
Clip C View Path unchanged
```

---

## 26.5 Save / Open Flow

```text
Project State
    ↓ save
Project File

Project File
    ↓ open
Project State
    ↓
resolve Source Recordings
    ↓
prepare previews as required
```

---

## 26.6 Export Flow

```text
Project
  ↓
for Clip in Timeline order
  ↓
Trim Range
  ↓
Original-quality Source
  +
View Path
  +
Output Frame
  ↓
Rendered Clip
  +
Source Audio
  ↓
Sequential Assembly
  ↓
MP4
```

---

# 27. Functional Interfaces

The following logical interfaces shall exist independent of implementation
technology.

## FI-01 — Project ↔ Timeline

Provides:

- ordered Clip collection;
- Clip reorder operation;
- current Project duration.

---

## FI-02 — Timeline ↔ Clip

Provides:

- active Clip;
- clip-local time;
- trim-aware source-time mapping.

---

## FI-03 — Clip ↔ Source Media

Provides:

- Source Recording reference;
- source duration;
- source media access.

---

## FI-04 — Clip ↔ View Path

Provides:

- Camera Positions;
- CameraState(t).

---

## FI-05 — Preview ↔ Panoramic Scene

Provides:

- panoramic scene at source time.

---

## FI-06 — Reframing Interaction ↔ Virtual Camera

Provides:

- temporary camera orientation;
- temporary FOV;
- Reset View.

---

## FI-07 — Camera Position ↔ Virtual Camera

Provides:

- commit current Camera State;
- restore stored Camera State.

---

## FI-08 — Playback ↔ Audio

Provides:

- source audio corresponding to active source time.

---

## FI-09 — Persistence ↔ Project Model

Provides:

- serialize Project state;
- restore Project state.

---

## FI-10 — Final Renderer ↔ Project Model

Provides:

- ordered Clips;
- trim ranges;
- View Paths;
- Output Frame.

---

# 28. Functional Traceability to Use Cases

| Use Case | Principal Functional Areas |
|---|---|
| UC-01 Start New Project | FA-01, FA-02 |
| UC-02 Add Panoramic Recordings | FA-03, FA-04, FA-07, FA-08 |
| UC-03 Manage Clip Sequence | FA-04, FA-05, FA-14 |
| UC-04 Trim Clip | FA-05, FA-06, FA-14 |
| UC-05 Select Output Frame | FA-02, FA-09 |
| UC-06 Explore and Reframe Clip | FA-08, FA-09, FA-10 |
| UC-07 Define and Edit View Path | FA-05, FA-09, FA-11, FA-12, FA-14 |
| UC-08 Preview Reframed Clip | FA-05, FA-08, FA-09, FA-12, FA-13 |
| UC-09 Preview Project Sequence | FA-05, FA-08, FA-09, FA-12, FA-13 |
| UC-10 Undo or Redo Edit | FA-14 |
| UC-11 Save Project | FA-02, FA-04, FA-15 |
| UC-12 Reopen Project | FA-03, FA-04, FA-07, FA-15 |
| UC-13 Export Project | FA-05, FA-06, FA-12, FA-16, FA-17 |

---

# 29. Functional Traceability to Requirement Areas

| Requirement Area | Allocated Functional Areas |
|---|---|
| SYS-APP | FA-01 |
| SYS-PROJ | FA-02 |
| SYS-MEDIA | FA-03 |
| SYS-CLIP | FA-04, FA-05 |
| SYS-TRIM | FA-06 |
| SYS-PREV | FA-07, FA-08 |
| SYS-FRAME | FA-02, FA-09 |
| SYS-CAM | FA-09, FA-10 |
| SYS-EDIT | FA-10, FA-11 |
| SYS-TIME | FA-05, FA-13 |
| SYS-POS | FA-11 |
| SYS-PATH | FA-12 |
| SYS-AUDIO | FA-13 |
| SYS-HIST | FA-14 |
| SYS-SAVE | FA-15 |
| SYS-EXP | FA-16, FA-17 |
| SYS-PERF | FA-07, FA-08, FA-09, FA-13 |

---

# 30. Architecture Invariants

These rules shall remain true regardless of software technology.

## AI-01 — Original Media Is Immutable

The application does not edit Source Recording files in place.

---

## AI-02 — Editing Is Metadata

Clip ordering, trim, Camera Positions, and View Paths are Project data.

---

## AI-03 — Reframing Is Clip-Local

Camera Positions and View Paths use clip-local time.

---

## AI-04 — Timeline Order Is Independent

Changing Project Timeline order does not change the internal View Path of a
Clip.

---

## AI-05 — Explore and Commit Are Separate

Direct panoramic exploration does not change the View Path until the User
explicitly commits a Camera Position.

---

## AI-06 — Preview Is Derived

Preview media may be regenerated without losing Project editing state.

---

## AI-07 — Preview and Export Share Camera Semantics

The preview path and final-render path may use different media quality, but
must interpret the same Camera State and View Path consistently.

---

## AI-08 — One Project Output Frame

Iteration 1 applies one Project Output Frame to every Clip.

---

## AI-09 — Timeline Is Sequential

Iteration 1 contains one sequential non-overlapping Clip sequence.

---

# 31. Functional Architecture Decisions

The following decisions are baselined by this document.

| ID | Decision |
|---|---|
| FAD-001 | PanoPilot is Project-based rather than Source-Recording-based |
| FAD-002 | Multiple Clip instances exist within one Project |
| FAD-003 | Clip order and reframing are independent concerns |
| FAD-004 | Trim range belongs to Clip |
| FAD-005 | View Path belongs to Clip |
| FAD-006 | Camera Position time is clip-local |
| FAD-007 | Exploration state is temporary |
| FAD-008 | Camera Position creation is an explicit commit |
| FAD-009 | Preview representation is derived and disposable |
| FAD-010 | Final rendering uses final-quality source media |
| FAD-011 | Preview and rendering share one logical camera model |
| FAD-012 | Undo/Redo applies to editing metadata rather than source media |
| FAD-013 | Project persistence stores editing metadata and source references |

---

# 32. Architecture-Driving Risks

The following risks are not resolved by functional decomposition and require
technical demonstration before software architecture is frozen.

## RISK-01 — DJI OSV Interpretation

Can supported `.OSV` media be reliably interpreted and reconstructed from
actual camera files?

**Impact:** Critical

---

## RISK-02 — Interactive Panoramic Preview

Can a prepared panoramic representation support sufficiently responsive
mouse-driven reframing on the Fedora reference system?

**Impact:** Critical

---

## RISK-03 — Preview / Render Equivalence

Can the same logical Camera State and View Path reproduce equivalent
composition in interactive preview and final-quality rendering?

**Impact:** Critical

---

## RISK-04 — Panoramic Camera Interpolation

Can camera interpolation avoid discontinuities and unintended long rotations
across panoramic wrap boundaries?

**Impact:** High

---

## RISK-05 — Timeline Audio Synchronization

Can clip-local trim, View Path playback, sequential Project playback, and
source audio remain synchronized?

**Impact:** High

---

# 33. Required Technical Spikes

Before baselining software architecture, perform the following three spikes.

## SPIKE-01 — OSV to Navigable Panorama

### Objective

Demonstrate that one representative DJI Osmo 360 `.OSV` can produce a usable
panoramic scene on Fedora.

### Demonstration

```text
OSV
 ↓
source inspection
 ↓
panoramic reconstruction
 ↓
navigable 360 preview
```

### Success Criteria

- representative `.OSV` is accepted;
- panoramic scene is visually usable;
- User can inspect the full surrounding scene;
- no manual preconversion is required.

---

## SPIKE-02 — Interactive Virtual Camera

### Objective

Demonstrate responsive direct manipulation of the panoramic scene.

### Demonstration

```text
Panoramic Scene
      ↓
Virtual Camera
      ↓
16:9 / 9:16 frame
      ↑
mouse drag / mouse wheel
```

### Success Criteria

- horizontal drag changes viewing direction;
- vertical drag changes viewing direction;
- mouse wheel changes FOV;
- interaction is subjectively usable and can be measured against the future
  performance requirement;
- exploration does not commit Camera Positions.

---

## SPIKE-03 — View Path to Final MP4

### Objective

Demonstrate that committed Camera Positions can be rendered consistently from
the original source.

### Demonstration

```text
Original OSV
   +
Camera Position A
   +
Camera Position B
   +
Trim Range
      ↓
View Path
      ↓
Final Render
      ↓
H.264 MP4 + audio
```

### Success Criteria

- two or more Camera Positions are rendered;
- panoramic wrap behavior is correct;
- exported framing corresponds to preview framing;
- output is conventional non-360 MP4;
- source audio remains synchronized.

---

# 34. Software Architecture Questions Deliberately Deferred

The following shall be decided only after the functional architecture and
technical spikes provide evidence.

- Python versus Rust ownership boundaries;
- desktop shell technology;
- native UI versus web-rendered UI;
- Three.js/WebGL versus native GPU panoramic rendering;
- FFmpeg subprocess versus bindings/library integration;
- PanoForge module reuse boundaries;
- preview storage format;
- preview cache lifecycle;
- project serialization format;
- threading/process model;
- GPU acceleration strategy;
- packaging and application distribution.

---

# 35. Iteration 1 Functional Baseline

The minimum Iteration 1 system can therefore be summarized as:

```text
                        PanoPilot
                           │
            ┌──────────────┴──────────────┐
            │                             │
       Project Model                 Media Model
            │                             │
     ┌──────┴───────┐              Source Recording
     │              │                     │
 Timeline         Clips              Panoramic Scene
     │              │                     │
     │        ┌─────┴─────┐               │
     │        │           │               │
   Order    Trim       View Path           │
                         │                 │
                  Camera Positions         │
                         │                 │
                         └──────┬──────────┘
                                │
                         Virtual Camera
                                │
                     ┌──────────┴──────────┐
                     │                     │
                  Preview              Final Render
                     │                     │
                Project Playback        MP4 Export
```

---

# 36. Exit Criteria for Functional Architecture

This functional architecture is ready to proceed to software architecture
when:

1. the Iteration 1 use cases are represented by functional flows;
2. every Iteration 1 requirement area is allocated to at least one functional
   area;
3. the ownership of Project, Clip, Trim Range, View Path, Camera Position,
   and Source Recording is unambiguous;
4. Project Time, Clip-Local Time, and Source Time are explicitly separated;
5. exploration and committed reframing state are explicitly separated;
6. preview and final rendering share a defined logical Virtual Camera model;
7. the three architecture-driving technical spikes have been executed or
   accepted as the next implementation activity.
