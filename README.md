# PanoPilot

Current internal version: `0.20.0`

# 0.18 — Multi-Clip sequential project editing

PanoPilot now has two explicit editing scales:

```text
PROJECT ORGANIZER
    ordered Clip instances
    import / reorder / remove
            ↓
EDIT SELECTED CLIP
    trim + View Path + Camera Positions
```

This preserves the core domain rule:

> Timeline position belongs to the Clip instance. Camera Position time belongs
> to Source Media.

Reordering Clips therefore changes where a Clip appears in the Project
Timeline but never changes its Camera Position `source_time` values.

## Update

```bash
cd ~/workspace/osmo360
source .venv/bin/activate
pip install -e .

panopilot --version
```

Expected:

```text
PanoPilot 0.18.0
```

## Open the Project Organizer

For your existing project:

```bash
panopilot project-edit \
  --project results/panopilot_project.json
```

Or import several OSV recordings in one operation:

```bash
panopilot project-edit \
  samples/clip01.OSV \
  samples/clip02.OSV \
  samples/clip03.OSV \
  --project results/panopilot_project.json
```

You can also use **Add OSV Files…** inside the desktop window for native
multi-select import.

## Project Organizer operations

The organizer provides:

```text
Add OSV Files…
Remove
Move Up
Move Down
Edit Selected Clip

Undo
Redo
Save
Close
```

Double-clicking a Clip also opens its Clip Editor.

All project-structure changes are transactions:

```text
Add Clip
Remove Clip
Reorder Clip
```

They participate in Undo/Redo and explicit Save semantics.

Removing a Clip removes only the project instance. It never deletes or
modifies the `.OSV` source.

## Edit Selected Clip

Selecting **Edit Selected Clip** opens the existing proven reframing editor for
that Clip.

Per-Clip state remains independent:

```text
Clip A
  ├─ its In / Out
  └─ its Camera Positions / View Path

Clip B
  ├─ its In / Out
  └─ its Camera Positions / View Path
```

After closing the Clip Editor, PanoPilot returns to the Project Organizer.

Project-order edits must be saved before launching a Clip Editor so both
windows operate from one deterministic project state. PanoPilot asks before
doing this; it does not silently save.

## Sequential Project Timeline

The Project Organizer calculates the sequential active duration:

```text
Clip 1 active range = 3 s
Clip 2 active range = 5 s
Clip 3 active range = 2 s

Project Timeline
0s ─── 3s ──────── 8s ── 10s
    C1       C2        C3
```

Use the existing diagnostic command for exact values:

```bash
panopilot timeline-info \
  results/panopilot_project.json
```

## Critical reordering invariant

Suppose:

```text
Clip 1 Camera Position = Source Time 2.300 s
Clip 2 Camera Position = Source Time 4.100 s
```

Move Clip 2 before Clip 1.

Result:

```text
Project Timeline positions change.
Camera Position Source Times stay:

Clip 1 -> 2.300 s
Clip 2 -> 4.100 s
```

This is covered by regression tests.

## Repeated source instances

0.18 intentionally does **not** allow adding the same source recording twice.

If a selected OSV is already in the project, it is skipped and PanoPilot tells
you why.

The internal architecture is now Clip-id based enough for repeated source
instances to be introduced later without changing the Source-Time View Path
invariant, but that use case is not required for Iteration 1.

## Existing single-Clip workflow remains valid

You can still directly edit one source:

```bash
panopilot explore \
  samples/osmosample.OSV \
  --project results/panopilot_project.json
```

For multi-Clip work, `project-edit` is the primary entry point.

## 0.18 acceptance gate

Validate:

1. open `project-edit`;
2. add two or more OSVs using multi-select;
3. confirm the list preserves selection/import order;
4. Move Up / Move Down and Undo / Redo;
5. save and reopen; order must reproduce;
6. Edit Selected Clip and create/change trim or Camera Positions;
7. close the Clip Editor and confirm the organizer still has all Clips;
8. edit another Clip and confirm its View Path is independent;
9. remove one Clip and Undo it;
10. run `timeline-info` and confirm sequential spans follow current order;
11. verify reordering never changes any Camera Position `source_time`.

## Next increment

After this passes, the next milestone should be the first **Project Timeline
playback/export path** across Clip boundaries.

That can be split cleanly:

```text
0.19
Project Timeline playback
    Clip 1 -> Clip 2 -> Clip 3
    source audio follows active Clip

0.20
Final sequential MP4 export
    original OSV sources
    persisted per-Clip View Paths
    Project Output Profile
```

This avoids prematurely adding transitions, titles, multitrack editing, or
other general-NLE concepts.

# 0.18.1 — Editor layout and loading UX

The Clip Editor layout has been reorganized after validating the 0.18 workflow
on a normal Fedora desktop window.

The previous UI allowed long text labels to determine the top-level window
width. That produced a large white area beside the 16:9 preview.

The editor now uses:

```text
┌─────────────────────────────────────────────────────────┐
│                 centered dark media canvas              │
│                                                         │
│                    reframed preview                     │
│                                                         │
├─────────────────────────────────────────────────────────┤
│ ▶  Use View          00:03.250 / 00:06.016   Saved  ↶ ↷ 💾 │
│ Set In  Set Out  Clear  🗑   Clip 00:02.200   camera info │
│           IN 01.050   CLIP 04.000   OUT 05.050          │
│  IN ▼  ═════════════ timeline ═══════════════  ▼ OUT    │
└─────────────────────────────────────────────────────────┘
```

Key UX changes:

- the media canvas fills available width with a dark background;
- the preview is centered instead of leaving white unused space;
- transport/project actions use compact icon buttons with tooltips;
- `Use View` remains explicit because it is the key edit boundary;
- Source Time is a compact authoritative timecode;
- Clip-local Time and camera state are separated onto the second row;
- trim values are compact chips rather than one long sentence;
- transient trim feedback appears only when useful;
- the image HUD is reduced to editing state + camera state;
- the editor no longer calls `adjustSize()` on every video frame.

## Loading screen

Panoramic preview preparation now happens behind a PanoPilot loading dialog:

```text
PanoPilot
Preparing panoramic view
osmosample.OSV

[ indeterminate progress ]

Preparing panoramic editing preview…
```

The expensive preparation runs on a Qt worker thread, so the application stays
visible instead of appearing to return to the terminal.

The loading screen is intentionally non-cancellable for now because preview
cache preparation does not yet have a transaction-safe cancellation path.

## 0.18.1 validation

Open an existing Clip and verify:

1. no large white area is created by the control labels;
2. the preview remains centered on a dark canvas;
3. controls fit in a compact two-row toolbar;
4. the timecode remains readable while resizing the window;
5. trim In / Out / duration remain obvious above the timeline;
6. the HUD no longer covers a large portion of the video with shortcut text;
7. Play/Pause, Undo, Redo, Save, and Delete show icon buttons with tooltips;
8. rebuilding a preview shows a PanoPilot loading dialog rather than leaving
   only terminal feedback.

Force the preparation path with:

```bash
panopilot explore \
  samples/osmosample.OSV \
  --project results/panopilot_project.json \
  --rebuild-preview
```

# 0.18.2 — Clip-owned View Path correction

The multi-Clip editor now carries the **selected Clip id** through the entire
reframing workflow.

This is the canonical ownership model:

```text
Project Organizer
    ↓ selected Clip id
Clip Editor
    ↓
Camera Positions / View Path
    ↓
seek + playback + reframe
```

The editor no longer has to rediscover the selected Clip by source-path string
after each operation.

## Expected setpoint behavior

One Camera Position:

```text
Clip In ───────── CP1 ───────── Clip Out

CP1 is held across the whole active Clip.
```

Two or more Camera Positions:

```text
CP1 ───── interpolate ───── CP2 ───── interpolate ───── CP3
```

The initial/default camera is used only when the selected Clip has zero active
Camera Positions.

## Multi-Clip diagnostics

Prefer stable Clip ids:

```bash
panopilot camera-at \
  results/panopilot_project.json \
  clip-1 \
  --time 2.0
```

```bash
panopilot reframe-path \
  results/panopilot_project.json \
  clip-1 \
  --time 2.0 \
  -o results/test.jpg
```

`camera-at` and `reframe-path` still accept source paths. An unambiguous
absolute/relative spelling difference is resolved automatically.

## Validation

1. Open `project-edit`.
2. Edit one Clip.
3. Compose a clearly non-default view and click **Use View**.
4. Seek elsewhere. With one Camera Position, framing must stay on that view.
5. Add a second Camera Position.
6. Playback must interpolate between the two rather than reset.
7. Save and close.
8. `project-info` must show Camera Positions under that exact Clip.
9. `reframe-path PROJECT clip-N --time ...` must reproduce the View Path.

# 0.18.3 — Durable Camera Positions

The latest diagnostic proved the saved Clip had no Camera Positions:

```text
camera_position_count: 0
mode: default
yaw/pitch/FOV: 0 / 0 / 90
```

The renderer was therefore correctly using the default camera. The problem was
that a visually created Camera Position could still end the Clip Editor session
without becoming durable in the project file.

0.18.3 changes that interaction.

## `Set Camera`

The primary reframing action is now called:

```text
Set Camera
```

Clicking it, or pressing Enter, performs:

```text
current Source Time
+ yaw / pitch / FOV
        ↓
Camera Position transaction
        ↓
atomic project save
        ↓
durable Camera Position
```

A separate Ctrl+S is no longer required just to preserve a Camera Position.

The editor immediately reports:

```text
Camera Position 01 created and saved @ 00:02.000
```

and the toolbar counter changes:

```text
CAM 0 -> CAM 1
```

Undo/Redo remains available. Undoing an auto-saved Camera Position makes the
working project Modified; saving or redoing resolves that state normally.

## Validation

After installing 0.18.3:

```bash
panopilot project-edit \
  --project results/panopilot_project.json
```

Edit `clip-1`, create one clearly non-default framing, then click **Set Camera**.

You should immediately see `CAM 1`.

Close the editor and run:

```bash
panopilot camera-at \
  results/panopilot_project.json \
  clip-1 \
  --time 2.0
```

Expected:

```text
camera_position_count: 1
mode: hold-single
```

and the camera values should match your chosen framing rather than 0/0/90.

With a single Camera Position, that view is held across the active Clip. Add a
second Camera Position to validate interpolation.

# 0.18.4 — Reframe preview behavior

The latest diagnostic:

```text
camera_position_count: 0
mode: default
camera: 0 / 0 / 90
```

means the Clip has **no saved Camera Positions**. `Trim In` / `Trim Out` are
Clip-range markers; they are not camera setpoints.

0.18.4 makes that distinction explicit and removes the surprising playback
reset when no Camera Position has been saved yet.

## Two different concepts

```text
Trim In / Trim Out
    define which Source Time range belongs to the Clip

Set Camera
    saves yaw / pitch / FOV as a Camera Position
```

The trim buttons are now named `Trim In` and `Trim Out` to make this harder to
confuse.

## Explore, preview, and edit

The original invariant remains:

```text
mouse drag / wheel
    exploration only
    project unchanged
```

But pressing Play after exploring no longer has to snap immediately back to
the default camera when the Clip has zero Camera Positions.

New behavior:

```text
CAM 0
drag to a different view
        ↓
Play
        ↓
PREVIEW PLAYBACK
current explored camera is held
        ↓
project is still unchanged
```

The editor displays:

```text
Preview-only camera — Set Camera to save this view
```

If you want the view to become part of the edited video:

```text
Set Camera
        ↓
CAM 1
        ↓
Camera Position saved immediately
```

Once a Clip has one or more Camera Positions, playback always follows the
persisted View Path rather than a transient camera hold.

## Validation

1. Open `clip-1`.
2. Confirm `CAM 0`.
3. Drag to a clearly different view.
4. Press Play **without** Set Camera.
5. The video must keep that view instead of resetting to 0/0/90.
6. Pause. The project must still be Saved because this was preview-only.
7. Click **Set Camera**.
8. Confirm `CAM 1`.
9. Now seek/play anywhere: the persisted View Path must hold/use that Camera
   Position.
10. Verify with:

```bash
panopilot camera-at \
  results/panopilot_project.json \
  clip-1 \
  --time 2.0
```

Expected after Set Camera:

```text
camera_position_count: 1
mode: hold-single
```

# 0.18.5 — Project/Clip window lifecycle fix

0.18.5 fixes the hang that could occur after double-clicking a Clip in the
Project Organizer.

Two Qt lifecycle issues were involved.

## Cached-preview loading race

A prepared preview can return almost instantly. The prior loading dialog could
start its worker before the nested loading event loop was actually active.

That allowed this race:

```text
worker starts
    ↓
cached preview returns immediately
    ↓
loop.quit()
    ↓
loop.exec() starts afterward
    ↓
window waits indefinitely
```

The worker now starts through a zero-delay Qt timer. That timer is dispatched
only after the loading event loop is active.

Worker progress/completion also passes through a QObject that lives on the GUI
thread, so Qt widgets are never updated from the worker thread.

## Organizer -> Clip Editor -> Organizer

The previous implementation mixed `QApplication.exec()` for the first window
with a Python `processEvents()` polling loop for later windows.

That is fragile for:

- QMediaPlayer;
- QThread queued signals;
- timers;
- GNOME/Wayland top-level window switching.

PanoPilot now keeps one QApplication alive and gives the Project Organizer and
Clip Editor their own normal local `QEventLoop`.

## Validation

```bash
panopilot project-edit \
  --project results/panopilot_project.json
```

Repeat several times:

1. double-click a Clip;
2. Clip Editor opens;
3. close it;
4. Project Organizer returns;
5. double-click another Clip.

Test both an already-cached recording and a recording that needs panoramic
preview preparation.

# 0.18.6 — Loading completion fix

0.18.5 made the loading screen visible and stabilized Organizer / Clip Editor
window switching, but the loading screen could remain open after preparation
had actually finished.

0.18.6 simplifies the loading lifecycle.

Previous architecture:

```text
worker thread
    ↓ cross-thread finished signal
GUI receiver
    ↓
nested event-loop quit
```

The new architecture has one completion authority:

```text
Preparation QThread
    ↓
worker.isFinished()

GUI QTimer (50 ms)
    ↓
dialog.accept()

QDialog.exec()
    ↓
returns normally
    ↓
Clip Editor opens
```

This is deliberately safe for both extremes:

```text
cached preview returns immediately
```

and:

```text
full panoramic preview takes many seconds
```

If the worker completes before `QDialog.exec()` begins, no completion signal is
lost. The first GUI timer tick sees `worker.isFinished()` and closes the
loading screen.

Progress text is passed through a thread-safe queue; the worker never modifies
Qt widgets directly.

## Validation

Run:

```bash
panopilot project-edit \
  --project results/panopilot_project.json
```

Test an already-cached Clip first:

1. double-click Clip;
2. loading screen may appear only briefly;
3. it must close automatically;
4. Clip Editor must open.

Then force a rebuild:

```bash
panopilot explore \
  /path/to/source.OSV \
  --project results/panopilot_project.json \
  --rebuild-preview
```

The loading screen should remain visible while preparation runs and close as
soon as the preview is ready.

# 0.18.7 — Smooth Camera Position transitions

Camera movement between persisted Camera Positions now uses eased timing rather
than constant-speed piecewise-linear movement.

Previous behavior:

```text
CP1 --------------------> CP2 --------------------> CP3
           constant speed     instant velocity/direction change
```

The camera reached each Camera Position with full movement velocity, then
immediately changed velocity/direction for the next segment. Position was
continuous, but the motion could look like a harsh hit at the reframing point.

0.18.7 applies quintic ease-in/ease-out to each segment:

```text
CP1   .... accelerate .... cruise .... decelerate ....   CP2
                                                        ↓
                                                zero velocity
                                                zero acceleration
                                                        ↓
CP2   .... accelerate .... cruise .... decelerate ....   CP3
```

The easing function is:

```text
6t^5 - 15t^4 + 10t^3
```

It preserves:

- exact Camera Position values;
- exact Source Times;
- shortest-route yaw across the ±180° seam;
- the same interpolation semantics in interactive preview and project-aware
  rendering;
- one-Camera-Position hold behavior.

Yaw, pitch, and FOV all use the same eased segment timing so reframing and zoom
remain synchronized.

`camera-at` diagnostics now expose both:

```text
alpha         raw Source-Time position in the segment
eased_alpha   camera interpolation position after smoothing
interpolation smooth
```

A linear engineering mode remains available internally for comparison, but
`smooth` is now the product default.

## Validation

Create at least three clearly different Camera Positions and play through them.

The camera should:

1. accelerate smoothly away from a Camera Position;
2. decelerate as it approaches the next Camera Position;
3. arrive exactly on the selected framing;
4. avoid the previous abrupt direction/speed change;
5. transition smoothly into the next movement.

If this feels too much like the camera briefly "rests" at each point, the next
refinement would be a flow-through spline mode that keeps non-zero velocity
through intermediate Camera Positions. That should be introduced only after
this eased behavior is visually evaluated.

# 0.18.8 — Configurable Camera Motion

Camera transition behavior is now a persisted project setting and can be
changed directly in the Clip Editor.

The new controls are:

```text
Camera Motion  [ Smooth ▼ ]    Amount [────────●] 100%
```

## Easing presets

```text
Smooth
    quintic ease-in/ease-out
    gentlest arrival and departure
    this is the 0.18.7 behavior

Ease In + Out
    cubic ease-in/ease-out
    smoother than linear but less "resting" than Smooth

Ease In
    slow departure from a Camera Position
    faster arrival at the next Camera Position

Ease Out
    faster departure
    gentle deceleration into the next Camera Position

Linear
    constant-speed interpolation
    original behavior
```

## Amount

`Amount` controls how strongly the easing curve affects the transition:

```text
0%      linear timing
50%     halfway between linear and the selected easing curve
100%    full selected easing curve
```

This lets you keep a preset such as `Smooth` but reduce the effect if 100%
feels too slow around Camera Positions.

A practical starting point:

```text
Smooth          60–80%   cinematic, soft reframing
Ease In + Out   60–80%   natural general-purpose movement
Ease Out        50–70%   good when arriving at a subject matters most
Linear           0%      engineering/reference behavior
```

## Persistence and rendering

Camera Motion is stored at Project level:

```json
"camera_motion": {
  "easing": "ease-in-out",
  "strength": 0.7
}
```

Existing schema-v1/v2 projects automatically migrate to schema v3 with:

```text
Smooth / 100%
```

so existing 0.18.7 projects preserve their current appearance.

Interactive playback, `camera-at`, and `reframe-path` all consume the same
persisted Camera Motion configuration.

Changing Camera Motion is an Undo/Redo project edit. Save the project normally
with Ctrl+S when you want to persist the chosen settings.

# 0.19 — Sequential Project Preview

PanoPilot can now preview the complete ordered Project Timeline across Clip
boundaries.

From the Project Organizer use:

```text
Preview Project
```

or run:

```bash
panopilot project-preview \
  results/panopilot_project.json
```

The playback path is:

```text
Project Time
    ↓
active Clip
    ↓
Source Time
    ↓
cached panoramic preview
    +
Clip View Path
    +
Project Camera Motion
    ↓
conventional preview frame
    +
active Clip source audio
```

At a Clip boundary, playback automatically advances to the next Clip and
switches to that Clip's audio.

The Project Timeline slider shows Clip boundaries and supports seeking across
the complete sequence.

At Project end, playback stops. Pressing Play again restarts from Project Time
zero.

Project Preview is read-only. It creates no editing state.

## Documentation

The numbered engineering baseline is now included in `docs/` and aligned with
0.19:

```text
docs/00_change_summary.md
docs/01_system_definition.md
docs/02_use_cases.md
docs/03_system_requirements.md
docs/04_functional_architecture.md
docs/05_technical_spikes.md
```

The principal remaining Iteration-1 milestone is final sequential MP4 export
from original OSV sources.

# 0.20 — Final Sequential Project Export

PanoPilot can now render the complete Project to a conventional H.264 MP4 from
the **original OSV recordings**.

From the Project Organizer use:

```text
Export Project…
```

or run:

```bash
panopilot project-export \
  results/panopilot_project.json \
  -o results/final.mp4
```

## Iteration-1 delivery profile

```text
16:9  → 1920 × 1080 @ 30 fps
9:16  → 1080 × 1920 @ 30 fps
```

These are automatic Project Output Profile policies derived from the saved
aspect ratio.

## Final image path

```text
original OSV lens streams
→ DJI factory stitch
→ DJI horizon correction
→ persisted Clip View Path
→ Project Camera Motion
→ 1920×1080 or 1080×1920 conventional frame
→ H.264
```

The disposable editing preview cache is not used as final image input.

## Audio

Source audio is trimmed and assembled in Project order. If some Clips have
audio and another Clip does not, PanoPilot inserts silence for the no-audio
Clip so later audio remains aligned to Project Time.

## Safe completion

Export is first written as a preparing artifact. PanoPilot verifies codec,
geometry, expected audio presence, frame count when available, and duration.
Only a verified MP4 replaces the requested output path.

The correctness-first final renderer uses a 3840×1920 internal panoramic
representation by default. Final rendering will therefore be substantially
slower than interactive preview.

