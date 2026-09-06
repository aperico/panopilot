# PanoPilot — System Definition

Status: Draft  
Baseline: SD-0.15
Scope: Iteration 1

---

# 1. Purpose

PanoPilot is a locally installed desktop application focused on reframing
360-degree panoramic video into conventional video.

The initial supported source format is DJI Osmo 360 `.OSV`.

PanoPilot enables a User to:

- add multiple panoramic recordings to a Project;
- arrange and trim those recordings as sequential Clips;
- visually control a Virtual Camera inside each panoramic recording;
- define how the Virtual Camera changes over time;
- preview the complete sequence with source audio;
- save and reopen the Project;
- export one conventional video.

PanoPilot is specialized for panoramic reframing.

It is not intended to be a general-purpose nonlinear video editor.

---

# 2. Problem Statement

A 360-degree camera captures substantially more visual information than can
appear in a conventional output frame.

The primary editing problem is therefore:

> At each important moment, which direction should the viewer see?

For a Project containing multiple recordings, two additional questions exist:

> Which portions of the recordings should be used?

> In what order should those portions appear?

Existing Linux workflows expose implementation concepts such as:

- DJI-specific `.OSV` media;
- dual-lens imagery;
- stitching;
- calibration;
- equirectangular projection;
- proxy generation;
- yaw;
- pitch;
- roll;
- field of view;
- media filters and codec configuration.

These are implementation concerns rather than the User's editing goal.

PanoPilot shall present the workflow primarily through:

- Source Recordings;
- Clips;
- Trim Ranges;
- Project Timeline;
- Camera Positions;
- View Paths;
- Output Profile.

---

# 3. Mission

PanoPilot shall enable a User to transform multiple supported panoramic
recordings into one ordered conventional video sequence.

The intended workflow is:

```text
Add panoramic recordings
        ↓
Arrange Clips
        ↓
Trim Clips
        ↓
Select a Clip
        ↓
Explore the panorama
        ↓
Define desired views over time
        ↓
Preview the reframed Clip
        ↓
Repeat for other Clips
        ↓
Preview the complete Project
        ↓
Save / reopen
        ↓
Export conventional video
```

The User shall not be required to manually preprocess supported source
recordings before beginning the reframing workflow.

---

# 4. First-Principles System Model

## 4.1 Source Recording

A Source Recording is immutable original camera media.

For Iteration 1, a supported Source Recording is a validated DJI Osmo 360
`.OSV` recording and associated source information required to interpret it.

A Source Recording has a persistent Source Identity sufficient for PanoPilot
to detect whether a referenced file still corresponds to the media expected
by a saved Project.

The exact Source Identity mechanism is an architecture decision.

---

## 4.2 Panoramic Video Representation

PanoPilot interprets a Source Recording into a time-varying panoramic visual
representation suitable for viewing the surrounding recorded environment.

This document calls that representation the **Panoramic Video Representation**.

It is conceptually spherical visual media.

The term does **not** imply:

- 3D geometry reconstruction;
- depth estimation;
- SLAM;
- point-cloud reconstruction.

The primary workflow shall not require the User to manipulate:

- individual lens imagery;
- raw fisheye imagery;
- an equirectangular projection;
- stitching parameters.

---

## 4.3 Virtual Camera

A Virtual Camera selects a conventional view from the Panoramic Video
Representation.

```text
Panoramic Video Representation
             +
        Camera State
             +
        Output Profile
             ↓
        Output Frame
```

The Virtual Camera determines at least:

- viewing orientation;
- field of view;
- horizon orientation.

The primary User interaction is visual rather than numerical.

---

## 4.4 Canonical Camera Semantics

PanoPilot shall have one logical definition of Camera State used by both
interactive preview and final rendering.

The logical Camera Model shall define, independent of implementation
technology:

- the reference orientation;
- orientation-axis conventions;
- positive rotation direction;
- field-of-view convention;
- horizon/roll convention;
- angle units or normalized representation;
- panoramic wrap behavior;
- relationship to the selected Output Profile.

The internal representation may use quaternions, Euler angles, matrices, or
another suitable representation.

That implementation choice is not part of the System Definition.

---

## 4.5 Camera Position

A Camera Position represents:

> At this moment in the source recording, use this camera view.

A Camera Position:

- is owned by a Clip;
- stores a Camera State;
- is anchored to **Source Time** within the referenced Source Recording.

The User interface may display its position as time relative to the Clip.

Displayed Clip Time is derived from the Clip trim:

```text
clip_time = source_time - source_in
```

This source-time anchoring ensures the desired camera view remains attached to
the same recorded event when the User changes the Clip In point.

---

## 4.6 View Path

A View Path defines Virtual Camera behavior for one Clip.

It consists of:

- committed Camera Positions;
- deterministic behavior between Camera Positions;
- deterministic behavior outside the range of explicit Camera Positions.

Each Clip has an independent View Path.

---

## 4.7 Clip

A Clip is a non-destructive Project instance referencing a Source Recording.

A Clip contains:

```text
Clip
├── Source Recording reference
├── source_in
├── source_out
└── View Path
```

The same Source Recording may later be referenced by multiple Clip instances
without modifying the original source.

---

## 4.8 Trim Semantics

A Clip represents one continuous interval of Source Time:

```text
source_in ≤ source_time ≤ source_out
```

Changing a Clip trim range changes which portion of the Source Recording
participates in Project playback and export.

Changing trim shall not retime Camera Positions relative to the underlying
source content.

A Camera Position outside the current trim range becomes inactive for
playback/export but is not deleted merely because of trimming.

If the trim is later expanded to include that Source Time again, the Camera
Position becomes applicable again.

---

## 4.9 Project Timeline

The Project Timeline defines sequential Clip playback order.

Iteration 1 uses a single non-overlapping sequence:

```text
[ Clip A ][ Clip B ][ Clip C ]
```

The User may reorder it:

```text
[ Clip C ][ Clip A ][ Clip B ]
```

without altering the internal trim range or View Path of any Clip.

---

## 4.10 Time Domains

PanoPilot distinguishes three time domains.

### Source Time

Timestamp in the original Source Recording.

### Clip Time

Time displayed relative to the Clip's current In point.

```text
clip_time = source_time - source_in
```

### Project Time

Timestamp in the complete sequential Project.

Project Time maps to:

```text
Project Time
     ↓
Active Clip
     ↓
Clip Time
     ↓
Source Time
```

Camera Positions are source-time anchored and owned by their Clip.

Project Time is never used as the authoritative timestamp for a Camera
Position.

---

## 4.11 Output Profile

A Project has one Output Profile.

Conceptually:

```text
OutputProfile
├── aspect_ratio
├── width
├── height
└── frame_rate
```

Iteration 1 shall expose at least:

- 16:9;
- 9:16.

The User interface does not need to expose every Output Profile parameter in
Iteration 1.

Resolution and frame-rate policy may be selected automatically according to a
defined Project output policy.

All Clips in an Iteration 1 Project use the same Output Profile.

---

## 4.12 Preview and Final Rendering

Preview and final rendering serve different purposes.

### Preview

Optimized for:

- interactive camera movement;
- seeking;
- scrubbing;
- playback responsiveness.

### Final Rendering

Optimized for:

- final image quality;
- deterministic reproduction of the edit;
- delivery-file generation.

PanoPilot may use:

- reduced-resolution media;
- cached representations;
- `.LRF`;
- generated proxies;
- other optimized representations

for preview.

Preview media is disposable derived data.

Final rendering shall use original source media or an equivalent
final-quality representation.

Both paths shall consume the same logical Camera Model and View Path
semantics.

---

# 5. Product Form

PanoPilot shall be:

- a locally installed desktop application;
- Linux-first;
- validated initially on a designated Fedora reference environment;
- capable of completing the Iteration 1 workflow without Internet access.

The primary workflow shall execute locally.

A separately launched browser or remote processing service is not required.

---

# 6. Product Focus

PanoPilot shall prioritize:

1. panoramic source ingestion;
2. responsive panoramic navigation;
3. direct Virtual Camera manipulation;
4. Clip trimming and ordering;
5. Camera Position and View Path creation;
6. project persistence;
7. high-quality conventional video export.

Capabilities unrelated to panoramic reframing shall be introduced only when
they directly support this mission.

---

# 7. Primary User

The primary User is a 360-camera owner who wants to create conventional video
from panoramic recordings.

Typical content includes:

- travel;
- family activities;
- swimming;
- cycling;
- sports;
- outdoor activities;
- social-media footage.

The User may understand conventional video concepts but shall not be assumed
to understand panoramic-video mathematics or DJI-specific media internals.

---

# 8. UX Principles

## 8.1 Direct Manipulation

The primary Virtual Camera interaction occurs directly on the preview.

```text
mouse drag
    → look around

mouse wheel
    → change zoom/FOV

timeline interaction
    → navigate in time
```

---

## 8.2 Explore Before Commit

Exploring the panorama is temporary.

```text
Explore
  ↓
drag / zoom / reset
  ↓
temporary Camera State
  ↓
explicit "Use this view"
  ↓
committed Camera Position
```

Exploration shall not silently modify the View Path.

---

## 8.3 Visual Composition

The User shall compose the conventional Output Frame directly.

The normal workflow shall not require the User to infer the output from a raw
panoramic projection.

---

## 8.4 Simple Clip Sequencing

The User shall be able to:

- add multiple recordings;
- select a Clip;
- reorder Clips;
- remove a Clip;
- trim the start and end of a Clip.

The timeline remains sequential in Iteration 1.

---

## 8.5 Safe Editing

Editing shall be non-destructive.

Supported editing operations shall be undoable during the active session.

A continuous direct-manipulation gesture should be treated as one logical
editing transaction rather than many separate undo steps.

---

## 8.6 Progressive Disclosure

The default interface shall prioritize:

- Add Clips;
- Timeline;
- Trim;
- Play/Pause;
- Reframe Preview;
- Camera Positions;
- Output Profile;
- Save;
- Export.

Technical media details and numerical camera controls remain secondary.

---

# 9. Primary Operational Scenarios

## OS-01 — Create Project

The User creates an empty Project.

---

## OS-02 — Add Recordings

The User selects one or more supported `.OSV` recordings.

PanoPilot:

1. validates each source;
2. determines Source Identity;
3. creates Clips for accepted recordings;
4. adds Clips sequentially;
5. prepares preview media as required.

---

## OS-03 — Arrange Clips

The User reorders or removes Clips.

Reordering does not alter trim ranges or View Paths.

---

## OS-04 — Trim Clip

The User defines one continuous In/Out range.

Camera Positions remain attached to Source Time.

Positions outside the new trim range remain stored but inactive.

---

## OS-05 — Select Output Profile

The User selects 16:9 or 9:16.

PanoPilot applies the corresponding Project Output Profile.

---

## OS-06 — Explore Panorama

The User drags and zooms the preview.

The exploratory Camera State changes.

The committed View Path does not.

---

## OS-07 — Define Camera Position

The User explicitly commits the displayed composition.

PanoPilot stores a Camera Position at the current Source Time.

---

## OS-08 — Define View Path

The User creates multiple Camera Positions.

PanoPilot determines the effective Camera State over time.

---

## OS-09 — Preview Clip

The selected Clip plays using:

- its trim range;
- its View Path;
- the Project Output Profile;
- synchronized source audio.

---

## OS-10 — Preview Project

Clips play sequentially in Project Timeline order.

---

## OS-11 — Undo/Redo

The User reverses or reapplies a supported logical editing transaction.

---

## OS-12 — Save Project

PanoPilot saves Project metadata and Source Recording references without
modifying source media.

An interrupted save shall not invalidate the last successfully saved Project.

---

## OS-13 — Reopen Project

PanoPilot restores the Project and verifies that referenced media still
matches the expected Source Identity.

Missing or mismatched media is reported rather than silently substituted.

---

## OS-14 — Export Project

PanoPilot renders each Clip from final-quality source media using:

- Clip trim;
- Clip View Path;
- Project Output Profile;
- corresponding source audio.

The rendered Clips are assembled sequentially into one conventional video.

---

# 10. Top-Level Capabilities

- CAP-01 — Project Management
- CAP-02 — Panoramic Source Ingestion
- CAP-03 — Preview Preparation
- CAP-04 — Clip Management
- CAP-05 — Timeline Sequencing
- CAP-06 — Clip Trimming
- CAP-07 — Panoramic Navigation
- CAP-08 — Virtual Camera
- CAP-09 — Camera Position Management
- CAP-10 — View Path Evaluation
- CAP-11 — Audio/Video Playback
- CAP-12 — Undo/Redo
- CAP-13 — Project Persistence
- CAP-14 — Final Rendering and Export
- CAP-15 — Background Work Coordination

---

# 11. Iteration 1 Scope

Iteration 1 includes:

- desktop application;
- Fedora reference environment;
- multiple supported `.OSV` recordings;
- automatic preview preparation;
- sequential single-track timeline;
- Clip selection, reorder, removal;
- one continuous In/Out range per Clip;
- 16:9 and 9:16 Project output;
- direct mouse panoramic navigation;
- mouse-wheel zoom;
- Reset View;
- explicit Camera Position creation;
- Camera Position modification, deletion, and time movement;
- default View Path interpolation;
- panoramic wrap handling;
- Clip preview with source audio;
- Project preview with source audio;
- Undo/Redo for core editing operations;
- Project save/open;
- H.264/MP4 export with source audio.

---

# 12. Explicit Iteration 1 Boundaries

Iteration 1 does not require:

- Clip splitting;
- multiple ranges inside one Clip;
- overlapping Clips;
- multiple simultaneous video tracks;
- transitions;
- titles;
- overlays;
- picture-in-picture;
- color correction;
- audio mixing;
- speed changes;
- panoramic stabilization controls;
- subject tracking;
- AI-assisted reframing;
- advanced interpolation-curve editing;
- manual proxy management;
- manual codec configuration;
- cloud processing;
- collaboration.

---

# 13. Quality Attributes

## QA-01 — Usability

The primary workflow does not require knowledge of panoramic projection
mathematics.

## QA-02 — Responsiveness

Ready preview media supports direct Virtual Camera manipulation and seeking
within defined performance targets.

## QA-03 — Determinism

The same Source Time, Camera State, and Output Profile produce equivalent
framing in preview and final rendering.

## QA-04 — Reliability

A failure in preview preparation, rendering, or saving does not modify
original source media.

## QA-05 — Persistence Safety

An interrupted save does not invalidate the last successfully saved Project.

## QA-06 — Modifiability

Support for another panoramic source format should not require changes to the
semantics of Project, Clip, Timeline, Trim Range, Camera Position, or View
Path.

## QA-07 — Work Isolation

Background preparation for one Clip should not prevent interaction with a
different ready Clip.

---

# 14. Design Principles

- DP-01 — Panorama First
- DP-02 — Source Media Is Immutable
- DP-03 — Editing Is Metadata
- DP-04 — Source-Time Anchored Reframing
- DP-05 — View Path Belongs to Clip
- DP-06 — Timeline Order Is Independent of Reframing
- DP-07 — Explore and Commit Are Separate
- DP-08 — Preview Is Disposable Derived Data
- DP-09 — One Canonical Camera Model
- DP-10 — Preview and Export Share Camera/ViewPath Semantics
- DP-11 — Optimize Interaction Separately from Export
- DP-12 — Isolate Source-Format Complexity
- DP-13 — Long-Running Media Work Shall Not Own UI Responsiveness
- DP-14 — Remain Focused on Panoramic Reframing

---

# 15. Mission Success Criteria

Iteration 1 is successful when a User can:

1. launch PanoPilot;
2. create a Project;
3. add several supported `.OSV` recordings at once;
4. reorder the resulting Clips;
5. trim unwanted beginning/end footage;
6. select 16:9 or 9:16 output;
7. freely explore a Clip panorama;
8. commit Camera Positions;
9. preview smooth reframing with audio;
10. modify trim without moving Camera Positions away from their source events;
11. reframe multiple Clips;
12. preview the complete sequence;
13. undo/redo a normal editing mistake;
14. save and reopen the Project;
15. detect missing or mismatched referenced source media;
16. export one conventional H.264/MP4 video with synchronized audio;

without manually:

- converting `.OSV`;
- generating proxies;
- configuring lens stitching;
- entering media-processing commands;
- configuring projection filters;
- entering numerical camera orientation values.


---

# 18. Iteration-1 Implementation Alignment — PanoPilot 0.19

The following domain behavior is now validated in the executable prototype.

## 18.1 Desktop Editing Structure

PanoPilot currently exposes two editing scales:

```text
Project Organizer
    ordered Clips
    add / remove / reorder
    Project Preview
        ↓
Clip Editor
    trim
    Camera Positions
    View Path
    Camera Motion
```

The Project Organizer and Clip Editor use stable Clip identity. Source Recording
path is media identity/reference information; it is not the ownership key for a
Clip's View Path.

## 18.2 Camera Position Persistence

The User action **Set Camera** creates or updates a Camera Position at the
current authoritative Source Time.

In the desktop workflow, Set Camera is an explicit persistence boundary and the
Camera Position is atomically saved immediately.

Exploratory camera movement remains transient and does not modify Project state.

## 18.3 Camera Motion

A Project owns one Camera Motion configuration used when evaluating View Paths.

Iteration-1 configurable easing presets are:

- Smooth;
- Ease In + Out;
- Ease In;
- Ease Out;
- Linear.

The Project also stores a normalized Amount from `0.0` to `1.0`.

`0.0` produces linear segment timing. `1.0` applies the selected easing curve
fully. Intermediate values blend linear timing with the selected easing.

This setting applies consistently to Clip preview, Project preview, diagnostic
View Path evaluation, and project-aware frame rendering.

## 18.4 Project Preview

Project Preview is a read-only evaluation of the complete ordered Project
Timeline.

```text
Project Time
    ↓
Active Clip Instance
    ↓
Source Time
    ↓
Panoramic Preview + View Path
    ↓
Conventional Preview Frame + Source Audio
```

At Clip Out, Project preview advances to the next Clip according to Project
Timeline order.

At Project end, pressing Play again restarts from Project Time zero.

Preview media remains derived and disposable. The original OSV remains the
authoritative source for final rendering.


---

# 19. Iteration-1 Final Export Realization — PanoPilot 0.20

PanoPilot now realizes the complete Iteration-1 delivery pipeline:

```text
Original OSV Source Recordings
    ↓
Clip trim in Source Time
    ↓
DJI factory-calibrated panoramic reconstruction
    + DJI IMU horizon correction
    ↓
Clip View Path
    + Project Camera Motion
    ↓
Project Output Profile
    ↓
ordered conventional video frames
    + ordered source audio
    ↓
H.264 MP4
```

## 19.1 Iteration-1 Output Profile Policy

`OUTPUT-PROFILE-001` is resolved as:

```text
16:9  → 1920 × 1080 @ 30 fps
9:16  → 1080 × 1920 @ 30 fps
```

Width, height, and frame rate are automatic policy derived from the saved
Project aspect ratio. The User interface therefore does not require additional
resolution/FPS controls in Iteration 1.

## 19.2 Final Source Authority

Final export reconstructs image content from original OSV lens streams and DJI
metadata. The disposable panoramic editing cache is not used as an export image
source.

## 19.3 Project Frame Clock

Final export uses one continuous constant-frame-rate Project clock. Frames are
allocated globally across the Project Timeline before rendering Clips. This
prevents independent per-Clip frame rounding from accumulating duration drift.

## 19.4 Audio

When at least one Clip contains source audio, PanoPilot produces one continuous
Project audio stream in Timeline order. A Clip with no audio contributes silence
for its active duration so later Clip audio remains aligned to Project Time.

When no Clip contains source audio, the exported Project is video-only.

## 19.5 Transactional Completion

PanoPilot does not replace the requested output with an incomplete render.
Export is first written to a preparing artifact, probed and verified, and only
then atomically promoted to the requested MP4 path.


---

# 20. Iteration-1 Architecture Gate — CLOSED

Representative user media has validated PanoPilot 0.20 final sequential export
for the Iteration-1 workflow.

The end-to-end architecture gate is therefore closed for:

- original OSV source authority;
- Clip ordering and trim;
- Camera Position persistence;
- View Path evaluation;
- configurable Camera Motion;
- Project Preview;
- final conventional H.264 MP4 export.

PanoPilot 0.21 begins optimization without changing these semantics.

## 20.1 Final Projection Optimization

The 0.20 correctness-first final path performed:

```text
factory panorama
→ spherical horizon remap (3840×1920)
→ Virtual Camera remap (delivery frame)
```

0.21 composes the two inverse spherical mappings:

```text
factory panorama
→ [horizon correction + Virtual Camera]
→ delivery frame
```

This removes one full-resolution post-stitch image resampling operation from
every final output frame.

No Camera Position, Source Time, horizon-correction, or Output Profile semantic
is changed by this optimization.


---

# 21. Performance Optimization Method — PanoPilot 0.22

With the Iteration-1 semantic architecture closed, subsequent performance work
shall be evidence-driven.

PanoPilot now measures final-export wall-clock cost at the following semantic
boundaries:

```text
Clip setup
    calibration/map construction
    source PTS inspection
    IMU preparation

Per output frame
    decoder read/wait
    factory stitch
    horizon rotation math
    View Path evaluation
    composed rectilinear projection
    encoder write/wait

Project completion
    video render
    audio assembly
    final mux
    final verification
```

The purpose is not to create a general telemetry subsystem. The measurements
exist to identify the dominant final-export cost on representative user media
before selecting the next optimization.

No user media or project content is transmitted; performance information is
local process data.


---

# 22. Project Data Safety — PanoPilot 0.22.1

A PanoPilot Project is user-authored persistent data and is not part of the
application distribution.

Every successful Project save produces a durable backup outside the source
checkout using the user's XDG data directory. This protects edit state from
accidental checkout replacement or deletion of a local development `results/`
folder.

Application distributions shall not contain a runtime `results/` directory.


---

# 23. Lost-Project Reconstruction Boundary — PanoPilot 0.22.2

Disposable preview metadata may be used as a recovery aid for Source Recording
references only.

PanoPilot shall not represent Clip order, trim, Camera Positions, or Camera
Motion as recovered unless those values came from an authoritative Project
snapshot.

When rebuilding from preview cache, the User explicitly selects source order
and the resulting Project begins with default full-source trims and no Camera
Positions.


---

# 24. Measured Export Hotspots — PanoPilot 0.23

The accepted representative benchmark established that video rendering consumes
approximately 99.7% of total export time.

The largest measured video stages were:

```text
factory stitch         38.2%
composed projection    29.3%
source PTS setup       26.8%
```

PanoPilot 0.23 first removes avoidable work while keeping the accepted
original-source rendering architecture intact.

DJI lens streams classified as CFR no longer require frame-by-frame FFprobe PTS
enumeration. Factory overlap blending executes in optimized native OpenCV code
using the existing calibrated maps and overlap weights.


---

# 25. Final Projection Kernel — PanoPilot 0.24

The 0.23 representative benchmark reduced export from 148.04 seconds to
69.64 seconds and moved the dominant stage to composed projection.

0.24 preserves the accepted spherical mapping while changing its computational
form.

For each output pixel the unnormalized Camera ray is:

```text
u = [x, y, 1]
```

Camera and horizon transforms are combined once:

```text
M = CameraInverse · HorizonInverse
```

and source components are evaluated directly:

```text
[sx, sy, sz] = u · M
```

Ray normalization is required only for `sy` before latitude calculation.
Longitude uses `atan2(sx, sz)` directly.

This removes a three-component normalized ray image and one full per-pixel
matrix transformation from every final frame.


---

# 26. Final Projection Seam-Wrap Optimization — PanoPilot 0.25

The 0.24 user benchmark measured map generation at 18.88 seconds of a
41.39-second export, while actual panorama remap consumed only 0.86 seconds.

Within the final projection map, longitude originates from `atan2` and is
therefore bounded to one spherical revolution. General modulo is not required
to wrap the resulting panorama X coordinate.

PanoPilot 0.25 replaces general floating-point remainder with one-period
conditional wrapping while preserving the same accepted source map.


---

# 27. Hardware Decode Selection — PanoPilot 0.26

PanoPilot may use VAAPI for original OSV lens decoding, but hardware selection
is based on executable source-specific evidence.

A discovered hardware capability shall not be treated as usable until the exact
one-frame dual-lens decode path successfully completes.

Automatic failure returns to the software compatibility baseline. Project,
Camera, trim, View Path, stitch, and output semantics are independent from the
selected decoder backend.
