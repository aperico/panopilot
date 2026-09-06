# PanoPilot — Functional Architecture

Status: Draft  
Baseline: FA-0.4  
Scope: Iteration 1  
Parent: `01_system_definition.md`  
Use Cases: `02_use_cases.md`  
Requirements: `03_system_requirements.md`

---

# 1. Purpose

This document defines the functional architecture for the first usable
iteration of PanoPilot.

It defines:

- architecture concerns;
- logical functional decomposition;
- domain ownership;
- time and state semantics;
- logical interfaces;
- quality-attribute scenarios;
- architecture decisions and invariants;
- architecture-driving risks;
- technical spikes and verification assets.

It intentionally does **not** select:

- programming languages;
- desktop/UI frameworks;
- process/thread boundaries;
- GPU APIs;
- media libraries;
- packaging technology.

Those choices belong to software architecture after the architecture-driving
technical spikes provide evidence.

---

# 2. Architecture Concerns

The functional architecture addresses the following concerns.

| Concern | Architectural Response |
|---|---|
| Panoramic-source variability | Isolate source-specific behavior behind a Panoramic Source Port |
| Interactive performance | Separate preview media from final-quality media and coordinate background work |
| Editing correctness | Keep source immutable and editing state explicit |
| Trim/reframe stability | Anchor Camera Positions to Source Time |
| Preview/export consistency | One canonical Camera/ViewPath semantic core |
| Multi-clip correctness | Separate Project Time, Clip Time, and Source Time |
| Persistence safety | Versioned Project state, Source Identity, safe save semantics |
| Maintainability | Keep Editing Domain independent of DJI/FFmpeg/UI technology |
| Undo usability | Treat continuous editing gestures as transactions |
| Output determinism | Define one Project Output Profile |

---

# 3. Architectural Viewpoints

This document uses four lightweight viewpoints.

## 3.1 Domain View

Defines Project, Clip, Source Recording, Trim, Camera Position, View Path, and
Output Profile semantics.

## 3.2 Functional View

Defines logical responsibilities required to satisfy the use cases.

## 3.3 Information-Flow View

Defines how media time, camera state, project state, and derived media flow
between responsibilities.

## 3.4 Quality View

Defines architecture-driving quality scenarios and risks.

Functional Areas are **responsibilities**, not prescribed software modules.

There is no requirement for a one-to-one mapping between FA identifiers and
classes, services, processes, packages, or executables.

---

# 4. First-Principles Functional Model

PanoPilot reduces to five primary transformations.

## 4.1 Source → Panoramic Representation

```text
Source Recording
       ↓
Panoramic Source Adapter
       ↓
Panoramic Video Representation
```

## 4.2 Panorama + Camera → Conventional Frame

```text
Panoramic Video Representation
             +
        Camera State
             +
        Output Profile
             ↓
        Output Frame
```

## 4.3 Camera Positions → Camera State Over Time

```text
source-time Camera Positions
             ↓
      View Path Evaluator
             ↓
      CameraState(source_time)
```

## 4.4 Source + Trim + View Path → Reframed Clip

```text
Source Recording
      +
Trim Range
      +
View Path
      +
Output Profile
      ↓
Reframed Clip
```

## 4.5 Ordered Reframed Clips → Project Output

```text
Reframed Clips
      ↓
Project Timeline Order
      ↓
Conventional Project Video
```

---

# 5. Level-1 Functional Decomposition

```text
PanoPilot
│
├── A. Application / Editing Domain
│     ├── Project
│     ├── Clip
│     ├── Timeline
│     ├── Trim
│     ├── Camera Positions
│     ├── View Path
│     └── Undo/Redo
│
├── B. Panoramic Media
│     ├── Source Adapter
│     ├── Source Identity
│     ├── Preview Preparation
│     └── Panoramic Representation
│
├── C. Reframing
│     ├── Canonical Camera Model
│     └── Direct Interaction
│
├── D. Playback / Work Coordination
│     ├── Clip Playback
│     ├── Project Playback
│     └── Background Work Coordination
│
└── E. Persistence / Delivery
      ├── Project Persistence
      ├── Final Rendering
      └── Export Assembly
```

---

# 6. Level-2 Functional Areas

| ID | Functional Area | Primary Responsibility |
|---|---|---|
| FA-01 | Application Session | Maintain active desktop editing session |
| FA-02 | Project Management | Maintain Project-level state |
| FA-03 | Panoramic Source Adapter | Isolate source-format-specific interpretation |
| FA-04 | Source Identity | Determine whether referenced media is the expected source |
| FA-05 | Clip Management | Maintain Clip instances and per-Clip ownership |
| FA-06 | Timeline Management | Maintain Clip order and time mappings |
| FA-07 | Trim Management | Maintain source In/Out range |
| FA-08 | Preview Preparation | Produce/select media suitable for interaction |
| FA-09 | Panoramic Representation | Provide spherical visual media at Source Time |
| FA-10 | Canonical Camera Model | Define camera semantics for preview and render |
| FA-11 | Reframing Interaction | Maintain exploratory Camera State |
| FA-12 | Camera Position Management | Maintain committed Camera Positions |
| FA-13 | View Path Evaluation | Compute Camera State at Source Time |
| FA-14 | Playback | Preview Clips/Project with audio |
| FA-15 | Edit History | Undo/Redo logical editing transactions |
| FA-16 | Project Persistence | Save/reopen Project safely |
| FA-17 | Work Coordination | Coordinate long-running media work |
| FA-18 | Final Rendering | Render final-quality reframed Clips |
| FA-19 | Export Assembly | Produce final sequential MP4 |

---

# 7. Core Domain Model

```text
Project
├── project_id
├── output_profile
├── sources[]
└── clips[]

OutputProfile
├── aspect_ratio
├── width
├── height
└── frame_rate

SourceRecording
├── source_id
├── source_identity
├── file_reference
├── duration
└── panoramic/audio descriptors

Clip
├── clip_id
├── source_recording_id
├── source_in
├── source_out
└── view_path

ViewPath
└── CameraPosition[]
      ├── position_id
      ├── source_time
      └── camera_state

CameraState
├── orientation
├── field_of_view
└── horizon_orientation
```

Derived preview data is not part of authoritative Project edit state.

---

# 8. Ownership Rules

## AR-OWN-001 — Project

Project owns:

- Source references used by the Project;
- Clip sequence;
- Output Profile.

## AR-OWN-002 — Source Recording

SourceRecording owns media identity and immutable source metadata.

It does not own editing decisions.

## AR-OWN-003 — Clip

Clip owns:

- trim range;
- View Path.

## AR-OWN-004 — View Path

ViewPath owns Camera Positions for one Clip.

## AR-OWN-005 — Preview

Preview data is derived from source media and owns no authoritative editing
state.

---

# 9. Time Model

PanoPilot distinguishes:

## 9.1 Source Time

Timestamp in the immutable Source Recording.

## 9.2 Clip Time

Displayed time relative to the current Clip In point.

```text
clip_time = source_time - source_in
```

## 9.3 Project Time

Time in the complete sequential Project.

```text
Project Time
      ↓
Timeline Mapping
      ↓
Active Clip
      ↓
Clip Time
      ↓
Source Time
```

## 9.4 Camera Position Time Rule

Camera Positions are stored using Source Time.

This is an architecture invariant.

Rationale:

- Clip reordering must not retime reframing;
- changing `source_in` must not move a Camera Position away from the source
  event it was created to frame;
- trim expansion should restore previously out-of-range Camera Positions.

---

# 10. Trim Semantics

A Clip has one continuous Source Time interval.

```text
0 ≤ source_in < source_out ≤ source_duration
```

Changing trim:

- changes Clip duration;
- changes Project Time offsets of subsequent Clips;
- changes displayed Clip Time for source-anchored Camera Positions;
- does not change Camera Position Source Time.

A Camera Position outside the trim range:

- remains persisted;
- remains owned by the Clip;
- is ignored by playback/export while outside the range.

---

# 11. Canonical Camera Model Contract

FA-10 defines one logical Camera Model consumed by both preview and final
rendering.

The contract shall define:

- panoramic reference frame;
- axis orientation;
- handedness;
- zero/reference view;
- positive rotation direction;
- field-of-view convention;
- horizon/roll convention;
- unit/normalization rules;
- panoramic seam/wrap semantics;
- mapping from Camera State + Output Profile to Output Frame.

The implementation may use quaternions, matrices, Euler angles, or another
representation.

The representation is secondary to semantic consistency.

## Authoritative Evaluation Rule

There shall be one authoritative logical View Path evaluator:

```text
ViewPath + Source Time
        ↓
CameraState(source_time)
        ↓
 ┌───────────────┬───────────────┐
 ▼               ▼               ▼
Preview       Tests         Final Render
```

Preview and final rendering shall not define independent camera-motion
semantics.

---

# 12. Panoramic Source Port

Source-format-specific behavior shall be isolated behind a logical
Panoramic Source interface.

Conceptually:

```text
            PanoPilot Editing / Reframing Domain
                         ▲
                         │ canonical source interface
                         │
                 Panoramic Source Port
                         ▲
                         │
                  DJI OSV Adapter
                         ▲
                         │
                     .OSV media
```

A future source adapter should be able to provide the same logical
capabilities without changing Project, Timeline, Trim, CameraPosition, or
ViewPath semantics.

The Panoramic Source Port conceptually provides:

- source inspection;
- source duration/timing;
- panoramic calibration information;
- source video access;
- source audio access;
- source identity information.

The exact API belongs to software architecture.

---

# 13. FA-01 — Application Session

Responsibilities:

- create/open one active Project;
- maintain active application context;
- route User operations to the appropriate application/domain functions.

Iteration 1 supports one active Project at a time.

---

# 14. FA-02 — Project Management

Responsibilities:

- create Project;
- maintain Output Profile;
- expose ordered Clips;
- track changed/saved state;
- provide Project state to persistence, playback, and export.

---

# 15. FA-03 — Panoramic Source Adapter

Responsibilities:

- accept candidate source files;
- determine whether the source is supported;
- expose panoramic/audio source information through the Panoramic Source Port;
- isolate DJI/OSV-specific interpretation from the Editing Domain.

---

# 16. FA-04 — Source Identity

Responsibilities:

- establish expected identity for accepted source media;
- compare a later resolved file with the expected identity;
- distinguish missing media from mismatched media.

The identity mechanism is a software-architecture decision.

---

# 17. FA-05 — Clip Management

Responsibilities:

- create Clip instances;
- select active Clip;
- remove Clip;
- maintain reference to Source Recording;
- preserve trim/View Path when timeline order changes.

---

# 18. FA-06 — Timeline Management

Responsibilities:

- maintain sequential Clip order;
- determine Project duration;
- map Project Time to active Clip;
- map Project Time to Clip Time and Source Time.

Iteration 1 timeline is:

- single-track;
- sequential;
- non-overlapping.

---

# 19. FA-07 — Trim Management

Responsibilities:

- set/validate Source Time In/Out;
- determine Clip duration;
- constrain playback/export;
- identify which Camera Positions are active in the current trim.

Trim changes do not mutate Camera Position Source Time.

---

# 20. FA-08 — Preview Preparation

Responsibilities:

- initiate or select an interactive preview representation;
- expose preparation state;
- make ready Clips usable independently;
- expose preview media to Panoramic Representation.

Minimum states:

```text
NOT_READY
PREPARING
READY
FAILED
```

Preview media is derived and disposable.

---

# 21. FA-09 — Panoramic Representation

Responsibility:

Provide spherical visual media corresponding to a Source Time.

Inputs conceptually include:

- source/preview media;
- Source Time;
- panoramic calibration/metadata.

Output:

```text
Panoramic Video Representation at source_time
```

This is not 3D scene reconstruction.

---

# 22. FA-10 — Canonical Camera Model

Responsibilities:

- interpret Camera State;
- map Camera State + Output Profile to a conventional view;
- define default/reset state;
- provide identical logical semantics to preview and final render.

---

# 23. FA-11 — Reframing Interaction

Responsibilities:

- translate mouse drag into exploratory orientation;
- translate mouse wheel into exploratory FOV;
- support Reset View;
- maintain temporary Camera State.

Invariant:

```text
exploration != persisted edit
```

Only explicit commit/update operations affect Camera Positions.

---

# 24. FA-12 — Camera Position Management

Responsibilities:

- create Camera Position at current Source Time;
- select/restore a Camera Position;
- modify Camera State;
- move it to another Source Time;
- delete it;
- expose its derived Clip Time for timeline visualization.

---

# 25. FA-13 — View Path Evaluation

Responsibility:

```text
ViewPath + Source Time → CameraState(source_time)
```

Responsibilities:

- order active Camera Positions by Source Time;
- interpolate orientation;
- interpolate FOV;
- interpolate horizon orientation;
- define behavior before/after active positions;
- handle panoramic wrap without unintended long rotation.

Iteration 1 requires one default interpolation model.

---

# 26. FA-14 — Playback

## Clip Playback

```text
Clip playback position
       ↓
Source Time
       ↓
Panoramic Representation
       +
CameraState(source_time)
       ↓
Canonical Camera Model
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
Active Clip + Source Time
    ↓
Clip Playback
```

Playback owns no authoritative edit state.

---

# 27. FA-15 — Edit History

Responsibilities:

- undo;
- redo;
- restore Project metadata state for supported editing transactions.

Minimum transaction types:

- Clip reorder;
- Clip removal;
- trim change;
- Camera Position create;
- Camera Position modify;
- Camera Position delete;
- Camera Position move.

## Gesture Transaction Rule

```text
mouse-down
  ↓
temporary interactive changes
  ↓
mouse-up / commit
  ↓
ONE logical history transaction
```

The implementation pattern is deferred.

---

# 28. FA-16 — Project Persistence

Responsibilities:

- serialize Project metadata;
- restore Project metadata;
- preserve Project format/version;
- preserve expected Source Identity;
- report missing/mismatched sources;
- protect the last successfully saved Project from an interrupted save.

Conceptual safe-save semantics:

```text
current saved Project
       ↓ save attempt
new candidate state
       ↓ successful durable completion
replace current saved Project
```

Exact file-system mechanics belong to software architecture.

---

# 29. FA-17 — Work Coordination

Responsibility:

Coordinate long-running work without assigning thread/process mechanisms at
this architecture level.

Work categories may include:

- source inspection;
- preview preparation;
- decoding;
- thumbnail/preview generation;
- final rendering;
- export assembly.

Responsibilities:

- submit work;
- track work state;
- prevent unnecessary duplicate work;
- allow interactive work to remain responsive;
- expose completion/failure;
- coordinate competing heavy operations.

Conceptual priority:

```text
Highest: interactive playback / reframing
        ↓
        seeking / scrub support
        ↓
        preview preparation
        ↓
Lowest: non-interactive background work
```

Exact scheduling belongs to software architecture.

---

# 30. FA-18 — Final Rendering

Input:

```text
Source Recording
+
Trim Range
+
View Path
+
Output Profile
```

For each output frame time:

```text
output/project timing
       ↓
Source Time
       ↓
final-quality source
       ↓
ViewPath.evaluate(source_time)
       ↓
Canonical Camera Model
       ↓
Output Frame
```

Final rendering shall not use reduced-quality preview media as the source of
final image quality.

---

# 31. FA-19 — Export Assembly

Responsibilities:

- process rendered Clips in timeline order;
- preserve trim;
- preserve source audio;
- conform to Output Profile;
- produce conventional H.264/MP4;
- report success/failure.

---

# 32. State Separation

## 32.1 Source State

Immutable:

- source video;
- source audio;
- calibration;
- duration;
- Source Identity.

## 32.2 Project State

Persistent editing metadata:

- source references;
- Clip order;
- trim;
- Output Profile;
- Camera Positions;
- View Paths.

## 32.3 Session State

Temporary runtime state:

- selected Clip;
- playhead;
- exploratory Camera State;
- active drag;
- UI selection;
- preparation progress.

Session state becomes Project state only through an explicit edit commit.

---

# 33. Primary Information Flows

## 33.1 Add Media

```text
OSV selection
    ↓
DJI OSV Adapter
    ↓
Panoramic Source Port
    ↓
Source Identity
    ↓
SourceRecording
    ↓
Clip
    ↓
Timeline
    ↓
Preview Preparation
```

## 33.2 Reframe

```text
Clip + Source Time
    ↓
Panoramic Representation
    ↓
Canonical Camera Model
    ↑
exploratory Camera State
    ↑
mouse drag / zoom

explicit Use This View
    ↓
Camera Position(source_time)
    ↓
View Path
```

## 33.3 Trim Change

```text
new source_in/source_out
      ↓
Clip duration changes
      ↓
Project Time offsets change
      ↓
Camera Position source_time unchanged
      ↓
active/inactive Camera Positions recalculated
```

## 33.4 Playback

```text
Project Time
  ↓
Timeline
  ↓
Source Time
  ↓
Panoramic Representation + Audio
  ↓
ViewPath.evaluate(source_time)
  ↓
Canonical Camera Model
  ↓
Output Frame + synchronized audio
```

## 33.5 Save/Open

```text
Project State
  ↓
safe serialization
  ↓
Project File

Project File
  ↓
restore state
  ↓
resolve source paths
  ↓
verify Source Identity
  ↓
prepare preview as needed
```

## 33.6 Export

```text
Project
  ↓
Timeline order
  ↓
Clip trim
  ↓
Source Time
  ↓
final-quality source
  +
View Path
  +
Output Profile
  ↓
Canonical Camera Model
  ↓
Rendered Clips + audio
  ↓
MP4
```

---

# 34. Logical Interfaces

## FI-01 — Application ↔ Project

Provides Project commands and current state.

## FI-02 — Project ↔ Timeline

Provides ordered Clips and Project duration.

## FI-03 — Timeline ↔ Clip

Provides active Clip and deterministic time mapping.

## FI-04 — Clip ↔ Panoramic Source Port

Provides source identity, duration, media, and calibration.

## FI-05 — Clip ↔ View Path

Provides Camera Positions and CameraState at Source Time.

## FI-06 — Reframing Interaction ↔ Camera Model

Provides temporary Camera State and Reset View.

## FI-07 — Camera Position ↔ Camera Model

Commits/restores Camera State.

## FI-08 — Playback ↔ Audio

Provides source audio at mapped Source Time.

## FI-09 — Persistence ↔ Project Model

Serializes/restores authoritative Project state.

## FI-10 — Renderer ↔ Camera/ViewPath Core

Provides the same CameraState semantics used by preview.

## FI-11 — Work Coordinator ↔ Long-Running Functions

Provides submit/state/completion/failure semantics.

---

# 35. Traceability to Use Cases

| Use Case | Principal Functional Areas |
|---|---|
| UC-01 | FA-01, FA-02 |
| UC-02 | FA-03, FA-04, FA-05, FA-08, FA-09, FA-17 |
| UC-03 | FA-05, FA-06, FA-15 |
| UC-04 | FA-06, FA-07, FA-12, FA-15 |
| UC-05 | FA-02, FA-10 |
| UC-06 | FA-09, FA-10, FA-11 |
| UC-07 | FA-06, FA-10, FA-12, FA-13, FA-15 |
| UC-08 | FA-06, FA-09, FA-10, FA-13, FA-14 |
| UC-09 | FA-06, FA-09, FA-10, FA-13, FA-14 |
| UC-10 | FA-15 |
| UC-11 | FA-04, FA-16 |
| UC-12 | FA-03, FA-04, FA-08, FA-16 |
| UC-13 | FA-06, FA-10, FA-13, FA-17, FA-18, FA-19 |

---

# 36. Architecture Invariants

- AI-01 — Original media is immutable.
- AI-02 — Editing is metadata.
- AI-03 — View Path belongs to Clip.
- AI-04 — Camera Positions are Source-Time anchored.
- AI-05 — Timeline order is independent of reframing.
- AI-06 — Trim does not retime Camera Positions.
- AI-07 — Explore and commit are separate.
- AI-08 — Preview is derived and disposable.
- AI-09 — One canonical Camera Model exists.
- AI-10 — One authoritative View Path evaluator exists.
- AI-11 — Preview and final rendering consume equivalent Camera/ViewPath semantics.
- AI-12 — One Output Profile applies to the Project.
- AI-13 — Timeline is sequential and non-overlapping in Iteration 1.
- AI-14 — Source-format-specific behavior is isolated behind a Panoramic Source Port.
- AI-15 — Continuous editing gestures commit as logical transactions.
- AI-16 — Failed save does not invalidate the previous successfully saved Project.

---

# 37. Quality-Attribute Scenarios

## QAS-01 — Camera Responsiveness

**Stimulus:** User drags the mouse while the active Clip preview is READY.  
**Response:** PanoPilot displays the updated camera composition.  
**Measure:** `CAMERA-RESPONSE-001`.

## QAS-02 — Seek Responsiveness

**Stimulus:** User scrubs a prepared Clip.  
**Response:** Corresponding preview imagery is displayed.  
**Measure:** `SCRUB-RESPONSE-001`.

## QAS-03 — Background Work Isolation

**Stimulus:** Clip B preview is being prepared while Clip A is READY.  
**Response:** User can continue reframing Clip A without Clip B preparation
owning the UI interaction path.

## QAS-04 — Persistence Safety

**Stimulus:** Save is interrupted or fails.  
**Response:** Last successfully saved Project remains usable.

## QAS-05 — Render Correctness

**Stimulus:** Preview and final renderer receive the same Source Time,
Camera State, and Output Profile.  
**Response:** Both represent geometrically equivalent framing within
`CAMERA-EQUIVALENCE-001`.

## QAS-06 — Source-Format Modifiability

**Stimulus:** A future panoramic source format is added.  
**Response:** Project, Clip, Timeline, Trim, CameraPosition, and ViewPath
semantics require no source-format-specific changes.

## QAS-07 — Trim Stability

**Stimulus:** User changes Clip In after Camera Positions exist.  
**Response:** Camera Positions remain attached to the same Source Time and
source content.

---

# 38. Functional Architecture Decisions

| ID | Decision | Rationale |
|---|---|---|
| FAD-001 | PanoPilot is Project-based | Multi-clip sequencing is core |
| FAD-002 | Clip owns Trim and View Path | Reframing belongs to a Project use of media |
| FAD-003 | Camera Position is Source-Time anchored | Trim must not shift reframing away from content |
| FAD-004 | Project Time, Clip Time, Source Time are distinct | Prevent temporal coupling |
| FAD-005 | Preview is derived | Interaction optimization must not own edit state |
| FAD-006 | Canonical Camera Model is shared | Prevent preview/render divergence |
| FAD-007 | One View Path evaluator is authoritative | Prevent duplicate motion semantics |
| FAD-008 | Source formats use adapters | Protect domain from DJI/FFmpeg coupling |
| FAD-009 | Output Profile is Project-wide | Deterministic multi-source rendering |
| FAD-010 | Edit gestures are transactions | Usable Undo/Redo |
| FAD-011 | Persistence verifies Source Identity | Prevent silent media substitution |
| FAD-012 | Work coordination is explicit | Media work must not accidentally own UI responsiveness |

---

# 39. Lightweight ADR Candidates

The following should become small ADR records when software architecture
begins:

- ADR-001 — Source media is immutable.
- ADR-002 — View Path belongs to Clip.
- ADR-003 — Camera Positions are Source-Time anchored.
- ADR-004 — Preview media is derived.
- ADR-005 — One canonical Camera/ViewPath core.
- ADR-006 — Panoramic sources are isolated behind adapters.
- ADR-007 — Project output uses one Output Profile.
- ADR-008 — Save semantics protect the last valid Project.

Each ADR should record:

```text
Context
Decision
Rationale
Alternatives
Consequences
```

---

# 40. Architecture-Driving Risks

## RISK-01 — DJI OSV Interpretation — Critical

Can representative `.OSV` recordings be interpreted reliably?

## RISK-02 — Interactive Panoramic Preview — Critical

Can the prepared panorama support responsive mouse-driven reframing?

## RISK-03 — Preview/Render Equivalence — Critical

Can one canonical Camera/ViewPath model drive both paths accurately?

## RISK-04 — Camera Interpolation — High

Can interpolation remain continuous across the panoramic seam?

## RISK-05 — Audio/Time Mapping — High

Can trim, Project Time mapping, source audio, and sequential playback remain
synchronized?

## RISK-06 — Output Normalization — High

Can mixed source frame rates/resolutions be rendered deterministically into
one Project Output Profile?

---

# 41. Required Technical Spikes

## SPIKE-01 — OSV to Navigable Panorama

Demonstrate:

```text
representative OSV
  ↓
DJI OSV Adapter
  ↓
Panoramic Representation
  ↓
navigable preview
```

Success:

- supported source accepted;
- panoramic representation visually usable;
- no manual preconversion;
- source timing and audio discoverable.

---

## SPIKE-02 — Interactive Canonical Camera

Demonstrate:

```text
Panoramic Representation
      +
Canonical Camera Model
      ↑
mouse drag / wheel
      ↓
16:9 / 9:16 preview
```

Success:

- horizontal/vertical navigation;
- zoom/FOV;
- Reset View;
- interaction is measurable against `CAMERA-RESPONSE-001`;
- exploration does not create Camera Positions.

---

## SPIKE-03 — Source-Time View Path to Final MP4

Demonstrate:

```text
Original OSV
  +
Trim
  +
source-time Camera Positions
  +
Output Profile
  ↓
Canonical View Path / Camera
  ↓
H.264 MP4 + audio
```

Success:

- two or more Camera Positions;
- correct panoramic-wrap motion;
- trim change does not retime Camera Positions;
- preview/final framing equivalence;
- mixed source timing assumptions are understood;
- synchronized audio.

---

# 42. Architecture Verification Assets

Create and maintain:

- representative/golden `.OSV` samples;
- source-inspection tests;
- Source Identity tests;
- Project/Clip/Source Time mapping tests;
- trim-preserves-source-anchor tests;
- out-of-trim Camera Position tests;
- camera-math unit tests;
- panoramic-wrap interpolation tests;
- Output Profile normalization tests;
- Project save/open round-trip tests;
- interrupted-save test;
- preview/render framing comparison;
- audio synchronization test.

Critical regression property:

```text
Given:
  Source Time = T
  Camera State = C
  Output Profile = P

Preview(T, C, P)
and
FinalRender(T, C, P)

shall represent equivalent framing within CAMERA-EQUIVALENCE-001.
```

---

# 43. Software Architecture Questions Deliberately Deferred

- Python versus Rust boundaries;
- Tauri versus Qt/other desktop shell;
- native versus web-rendered UI;
- Three.js/WebGL versus native GPU rendering;
- FFmpeg subprocess versus bindings;
- PanoForge reuse boundaries;
- preview representation format;
- cache lifecycle;
- project serialization format;
- thread/process/worker model;
- hardware acceleration strategy;
- packaging/distribution.

---

# 44. Exit Criteria

The functional architecture is ready for software architecture when:

1. use cases and requirements are aligned to this FA baseline;
2. Source Time anchoring is accepted across all documents;
3. Camera Model semantics required for preview/render equivalence are defined
   sufficiently for a technical spike;
4. Project Output Profile policy is defined or explicitly TBD;
5. Source Adapter boundary is accepted;
6. work coordination responsibility is accepted;
7. the three technical spikes have been executed or explicitly approved as
   implementation work;
8. architecture verification assets have been identified.


---

# 39. Architecture Realization Update — PanoPilot 0.19

## 39.1 Current Responsibility Mapping

The prototype currently realizes the functional architecture approximately as:

```text
Editing Domain
    project.py
    session.py
    timeline.py
    view_path.py

Panoramic Media
    dji.py
    source.py
    factory.py
    attitude.py
    pipeline.py
    preview.py
    cache.py

Reframing
    virtual_camera.py
    explore.py
    path_render.py

Project Playback
    project_player.py

Desktop Coordination
    project_editor.py
    loading.py

Command Boundary
    cli.py
```

This mapping is informative, not normative.

## 39.2 View Path Evaluation

FA-13 now includes two Project-level Camera Motion inputs:

```text
View Path
+ Source Time
+ Easing Preset
+ Easing Amount
        ↓
Camera State
```

The easing Amount blends raw linear segment time with the selected normalized
easing curve.

The same View Path evaluator is consumed by:

- Clip Editor seek/playback;
- Project Preview;
- `camera-at`;
- `reframe-path`.

This continues to enforce one semantic camera-motion core.

## 39.3 Project Preview Realization

FA-14 Project Playback is now executable:

```text
Project Time
    ↓
timeline_time_to_source()
    ↓
ClipTimelineSpan + Source Time
    ↓
PanoramaCacheReader(active Clip)
    +
evaluate_clip_view_path()
    ↓
reframe_equirectangular()
    ↓
Conventional Preview Frame

Active Clip
    ↓
cached preview audio
    ↓
QMediaPlayer
```

The monotonic Project clock is authoritative for preview progression. Cached
audio follows the active Clip and changes source when Project Time crosses a
Clip boundary.

The Project Player owns no authoritative edit state.

## 39.4 Preview Cache Boundary

Derived panoramic preview remains explicitly outside authoritative Project
state.

Cache identity is based on source identity and preview preparation profile.
Cache regeneration shall not alter Clip trim, Camera Positions, View Paths,
Camera Motion, Clip order, or Output Profile.

## 39.5 Desktop Window Lifecycle

The desktop prototype keeps one QApplication alive while switching among:

```text
Project Organizer
Clip Editor
Project Preview
Loading state
```

Top-level windows use local Qt event loops. Long-running preview preparation
executes on a worker thread while the GUI thread owns loading-state lifecycle.

## 39.6 Remaining Iteration-1 Architecture Gap

The major remaining path is:

```text
Original OSV sources
+ per-Clip trim
+ per-Clip View Path
+ Project Camera Motion
+ Project Output Profile
+ Project Timeline order
        ↓
final-quality sequential conventional MP4
```

Final rendering shall not treat the disposable panoramic preview cache as the
authoritative render source.


---

# 40. Final Export Architecture — PanoPilot 0.20

## 40.1 Functional Allocation

```text
FA-15 Project Export
    ↓
Output Profile Policy
    ↓
Global Project Frame Planner
    ↓
per-Clip Original-Source Renderer
    ↓
Continuous H.264 Video Encoder

Project Timeline
    ↓
per-Clip Source Audio / Silence
    ↓
Continuous Project Audio Assembler

Video + Audio
    ↓
MP4 Mux
    ↓
Export Verifier
    ↓
Atomic Output Promotion
```

The current implementation is realized primarily by:

```text
output_profile.py
project_export.py
```

## 40.2 Original-Source Render Context

For each Clip, final image rendering constructs one reusable Clip render
context containing:

- original source probe;
- synchronized lens-stream indexes;
- DJI factory calibration mapper;
- DJI orientation trajectory;
- output-frame exposure-time mapping.

These resources are independent from the disposable preview cache.

## 40.3 Frame Allocation

Project frame allocation occurs globally before per-Clip rendering. Each output
frame has exactly one Project frame index and maps to one active Clip and Source
Time. Contiguous frame groups are then rendered per Clip to avoid repeated
source initialization while preserving Project clock authority.

## 40.4 Audio Assembly

Audio is decoded from original Source Recordings. Every active Clip contributes
one Timeline-ordered audio segment. When Project audio exists overall, a Clip
without audio contributes generated stereo silence at 48 kHz.

All segments are concatenated and encoded once as AAC before final mux.

## 40.5 Export Transaction Boundary

```text
render → preparing MP4 → ffprobe verification → atomic replace → success
```

Any exception before atomic replace shall leave the requested output path
unchanged.

## 40.6 Known Optimization Opportunity

The correctness-first final renderer currently performs:

```text
factory stitch
→ spherical horizon resample
→ rectilinear Virtual Camera resample
```

A later optimization may combine attitude and Virtual Camera projection into a
single final source-to-output remap. Such optimization shall not change the
canonical Camera Model or View Path semantics.
