# PanoPilot

Current internal version: `0.41.0`

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

# 0.21 — Faster, Cleaner Final Projection

0.20 final export has now passed user acceptance.

0.21 starts performance/quality optimization without changing editing
semantics.

The previous final frame path was:

```text
factory panorama 3840×1920
    ↓
horizon correction remap
    ↓
rotated panorama 3840×1920
    ↓
Virtual Camera remap
    ↓
1920×1080 or 1080×1920 frame
```

The new path mathematically composes horizon correction with the Virtual Camera:

```text
factory panorama 3840×1920
    ↓
combined horizon + camera mapping
    ↓
1920×1080 or 1080×1920 frame
```

That removes **one complete 3840×1920 remap per exported frame**.

The reusable final projector also caches the normalized Output Profile pixel
grid for the complete export.

This optimization preserves:

- Camera Positions;
- Source-Time View Paths;
- Camera Motion easing;
- shortest-route yaw;
- DJI horizon correction;
- final Output Profile geometry.

The export JSON diagnostics now include:

```text
projection_pipeline:
  factory-panorama -> composed-horizon-camera -> rectilinear

post_stitch_resamples_per_frame: 1
```

SPIKE-03 is now formally closed as PASS for Iteration 1.

# 0.22 — Final Export Performance Profiler

The Iteration-1 functionality and final-render semantics are now frozen enough
to optimize from measurements rather than assumptions.

Every final Project export now records cumulative wall-clock time for:

```text
decoder_read_wait
factory_stitch
horizon_rotation_math
view_path_evaluation
composed_projection
encoder_write_wait

plus:
video_render
audio_assembly
final_mux
final_verification
```

After export, PanoPilot prints the dominant video stage and a compact timing
breakdown.

To preserve the full benchmark:

```bash
panopilot project-export \
  results/panopilot_project.json \
  -o results/final-022.mp4 \
  --report results/export-performance.json
```

The report also includes:

```text
total export seconds
effective output-frame fps
real-time factor
per-stage call count
per-stage average milliseconds
per-stage percentage of video render time
```

The next optimization should be selected from this report.

# 0.22.1 — Project Data Safety

PanoPilot Project JSON is user data and must survive replacement of the source
checkout.

Every successful Project save now creates a durable external backup under:

```text
$XDG_DATA_HOME/panopilot/project-backups/
```

or, on a normal Linux desktop:

```text
~/.local/share/panopilot/project-backups/
```

This includes Set Camera auto-saves because they use the normal Project save
boundary.

If a checkout-local Project file is accidentally removed, use:

```bash
panopilot project-backups \
  results/panopilot_project.json
```

then:

```bash
panopilot project-recover \
  results/panopilot_project.json
```

The distributable `panopilot.zip` also no longer contains a `results/`
directory. Examples are under `examples/`. This prevents an ordinary overlay
update from overwriting runtime output/project files.

Historical snapshots are retained in addition to `latest.json`.

# 0.22.2 — Lost-Project Reconstruction Aid

A deleted Project cannot be reconstructed completely from the panoramic
preview cache because the cache intentionally does not own trims, Camera
Positions, Clip order, or Camera Motion edits.

It can, however, recover the original source-recording paths.

List candidates:

```bash
panopilot cache-sources --existing-only
```

Create a fresh Project shell interactively:

```bash
panopilot project-rebuild-from-cache \
  results/panopilot_project.json
```

PanoPilot lists the recoverable recordings and asks for their numbers in the
desired Clip order:

```text
Enter source numbers in desired Clip order (example: 2,1):
```

For non-interactive use:

```bash
panopilot project-rebuild-from-cache \
  results/panopilot_project.json \
  --indexes 2,1 \
  --camera-motion ease-in-out \
  --motion-amount 70
```

The rebuilt Project is immediately saved through the durable external-backup
boundary introduced in 0.22.1.

After reconstruction, open it with `project-edit` and recreate the lost trims
and Camera Positions.

# 0.22.3 — Interactive Recovery Fix

Fixes the interactive `project-rebuild-from-cache` flow.

0.22.2 correctly discovered cached source recordings but the interactive
selection path referenced `sys.stdin.isatty()` without importing `sys`,
resulting in:

```text
NameError: name 'sys' is not defined
```

0.22.3 restores the intended prompt:

```text
Enter source numbers in desired Clip order (example: 2,1):
```

Non-interactive `--indexes` behavior is unchanged.

# 0.22.4 — CFR End-of-Clip Export Fix

Fixes a real export failure observed on the 6.016 s DJI sample:

```text
FFmpeg lens decoder ended before the expected frame count
for clip-1: 180/181
```

The cause was Project CFR allocation at a non-frame-aligned Clip boundary.

A 6.016 s Clip at 30 fps has an exact boundary at frame 180.48. The previous
frame-start classification gave that Clip frames `0..180` (181 frames), which
effectively rounded the boundary upward. FFmpeg correctly produced only 180
30-fps frames from that source interval.

0.22.4 now quantizes **cumulative Clip boundaries** to the nearest global CFR
frame:

```text
round(6.016 × 30) = 180
```

The next Clip therefore begins at Project frame 180. This preserves the
Project-wide frame clock while limiting Clip-boundary timing error to about
half one output frame.

The lens decoder also adds a bounded two-frame EOF clone pad. This handles
normal FFmpeg source-duration/time-base rounding at the final source frame
without masking larger decode failures.

# 0.23 — Benchmark-Driven Hotspot Optimization

The 0.22 benchmark on representative user media established:

```text
Total export:            148.04 s
Render throughput:         4.80 fps
Real-time factor:          6.25×

factory_stitch:           56.30 s  / 38.2%
composed_projection:      43.27 s  / 29.3%
clip_setup_source_pts:    39.48 s  / 26.8%
decoder_read_wait:         3.81 s  /  2.6%
encoder_write_wait:        2.02 s  /  1.4%
```

0.23 targets two high-cost stages with low semantic risk.

## CFR source-time fast path

DJI OSV lens streams expose matching `avg_frame_rate` and `r_frame_rate`.
When those values agree, PanoPilot now generates the regular source exposure
grid directly from stream metadata.

This removes the expensive second per-frame FFprobe scan used only to recover
timestamps that are already implied by the CFR stream cadence.

For sources that cannot safely be classified as CFR, the existing FFprobe
frame-PTS scan remains the fallback.

Per-Clip export diagnostics now report:

```text
source_pts.method = cfr-stream-metadata
source_pts.ffprobe_frame_scan = false
```

when the fast path is active.

## Native factory seam blending

The factory stitch still performs the same two calibrated lens remaps and uses
the same normalized overlap weights.

The final per-pixel blend has moved from large NumPy float32 temporaries to
OpenCV `blendLinear`, preserving the spatial blend while executing the
operation in optimized native code.

No calibration, seam weighting, Camera, horizon, or View Path semantics change.

Run the same benchmark again after updating:

```bash
panopilot project-export \
  results/panopilot_project.json \
  -o results/final-023-benchmark.mp4 \
  --report results/export-performance-023.json
```

The next optimization will be chosen from the new measurements. If
factory-stitch plus composed projection remain dominant, the next candidate is
a direct original-lens-to-conventional-frame mapper that avoids constructing a
complete intermediate panorama for final export.

# 0.24 — Composed Projection Kernel Optimization

The representative 0.23 benchmark established:

```text
69.64 s total export
10.21 output frames/s
2.94× real-time factor

composed_projection   50.63 s / 73.2%
factory_stitch         9.19 s / 13.3%
decoder_read_wait      4.19 s /  6.1%
encoder_write_wait     2.17 s /  3.1%
source PTS setup       ~0.00 s
```

The 0.23 CFR timing fast path therefore worked: source PTS setup fell from
39.48 seconds to approximately zero.

0.24 targets the now-dominant composed projection without changing panoramic
or Camera semantics.

The previous projector built a full `H × W × 3` float64 ray tensor for every
output frame and performed two per-pixel 3×3 transformations.

The new kernel:

```text
cached float32 NDC X/Y axes
    ↓
Camera rotation × horizon rotation
    ↓ one 3×3 matrix per frame
analytical rotated X/Y/Z components
    ↓
longitude / latitude
    ↓
one panorama remap
```

Important algebraic simplification:

```text
longitude = atan2(x, z)
```

does not require a normalized ray because a positive common scale cancels.
Only the rotated Y component is normalized for latitude.

This removes:

- the per-frame `H × W × 3` ray allocation;
- one per-pixel matrix multiplication;
- most float64 panoramic-map arithmetic;
- several large temporary arrays.

The accepted geometric model remains unchanged.

The performance report now also splits composed projection into:

```text
projection_breakdown.map_generation
projection_breakdown.panorama_remap
```

so the next step can distinguish mathematical map generation from OpenCV image
sampling.

Benchmark:

```bash
panopilot project-export \
  results/panopilot_project.json \
  -o results/final-024-benchmark.mp4 \
  --report results/export-performance-024.json
```

# 0.25 — Equirectangular Seam-Wrap Hot-Path Optimization

The representative 0.24 benchmark established:

```text
Total export:             41.39 s
Render throughput:         17.18 fps
Real-time factor:           1.75×

composed_projection:       19.76 s / 48.3%
factory_stitch:            10.40 s / 25.4%
decoder_read_wait:          4.96 s / 12.1%
encoder_write_wait:         2.86 s /  7.0%

projection map generation: 18.88 s
panorama remap:             0.86 s
```

The important result is that almost the complete remaining composed-projection
cost is map generation rather than OpenCV panorama sampling.

Profiling of the 0.24 projector identified a general floating-point
`np.remainder()` across every output pixel as a disproportionately expensive
part of the map hot path.

The projector does not need general modulo arithmetic. `atan2()` constrains the
longitude to one revolution, so the converted panorama X coordinate is bounded
to approximately:

```text
[-0.5, panorama_width - 0.5]
```

0.25 therefore replaces:

```text
map_x = map_x % panorama_width
```

with the equivalent bounded operation:

```text
if map_x < 0:
    map_x += panorama_width

if map_x >= panorama_width:
    map_x -= panorama_width
```

implemented as vectorized in-place NumPy operations.

This is an arithmetic optimization only. It preserves the exact wrapped X map
produced by the accepted modulo implementation for the projector's valid
coordinate range.

No Camera, horizon, seam, panorama, trim, or View Path semantics change.

Benchmark with:

```bash
panopilot project-export \
  results/panopilot_project.json \
  -o results/final-025-benchmark.mp4 \
  --report results/export-performance-025.json
```

If map generation falls as expected, the next dominant stage should move
toward factory stitching and/or media decode. That measurement will determine
whether 0.26 should fuse factory geometry toward the delivery frame or address
another measured hotspot.

# 0.26 — Runtime-Tested VAAPI Lens Decode

The representative 0.25 benchmark established a new hotspot order:

```text
39.01 s total export
18.23 output frames/s
1.65× real-time factor

decoder_read_wait       12.94 s / 33.6%
factory_stitch           9.68 s / 25.1%
composed_projection      9.60 s / 24.9%
encoder_write_wait       3.46 s /  9.0%
```

0.26 therefore targets lens decoding.

The default is:

```text
--decoder auto
```

PanoPilot discovers VAAPI render nodes but never selects one from advertised
capability alone. For each source Clip it runs the exact dual-lens-to-BGR
pipeline for one frame. Only a successful execution enables VAAPI.

```text
render-node candidate
    ↓
actual OSV + both lens streams
    ↓
VAAPI decode + software frame transfer
    ↓
fps/tpad + BGR + hstack
    ↓
pass?
    ├─ yes → VAAPI
    └─ no  → software fallback
```

Explicit modes are also available:

```bash
--decoder software
--decoder vaapi --vaapi-device /dev/dri/renderD128
```

Explicit VAAPI fails if the runtime smoke test fails; it does not silently
fall back.

The export report records backend, device, fallback state, and selection reason
for every Clip.



# 0.27 — One-Frame-Ahead Projection Map Pipeline

The 0.26 A/B benchmark showed that runtime-tested VAAPI is useful:

```text
VAAPI auto: 37.46 s, 18.98 fps, decoder wait 5.29 s
software:   41.35 s, 17.19 fps, decoder wait 13.50 s
```

VAAPI remains the default automatic choice when its exact source-specific
runtime smoke test passes.

The remaining large CPU stages are projection-map generation and factory
stitching. 0.27 overlaps those independent operations instead of changing
geometry.

```text
worker:
    map N+1
       │
       │ overlaps
       ▼
main:
    decode N → stitch N → consume map N → remap N → encode N
```

The pipeline is deliberately bounded to one worker and one outstanding pair of
output-resolution maps.

Rendering semantics are unchanged: every map still comes from the canonical
`RectilinearProjector.map()` function.

The report now distinguishes concurrent map CPU time from actual critical-path
wait:

```text
projection_breakdown.map_generation_worker
projection_map_wait
projection_breakdown.panorama_remap
```

For a controlled A/B run:

```bash
--no-projection-prefetch
```

Benchmark:

```bash
panopilot project-export \
  results/panopilot_project.json \
  -o results/final-027-benchmark.mp4 \
  --report results/export-performance-027.json
```


# 0.28 — Direct Dual-Lens Final-Render Spike

0.28 adds an experimental final renderer that removes the full 3840×1920
intermediate panorama from final export. The accepted panorama renderer remains
the default.

```text
Accepted: lens0/lens1 -> full panorama -> Camera/horizon remap -> delivery
Direct:   Camera/horizon map -> compose factory lens maps -> lens0/lens1
          remap directly to delivery -> seam blend
```

Run the experimental path with:

```bash
panopilot project-export \
  results/panopilot_project.json \
  -o results/final-028-direct.mp4 \
  --render-pipeline direct \
  --report results/export-performance-028-direct.json
```

The direct path changes sampling order, so promotion to the default requires a
representative visual comparison plus a material wall-time improvement.


# 0.29 — Adjustable 3-Axis Motion Stabilization

PanoPilot now persists a Project-wide **Stabilization Amount** from 0% to 100%.
The previous horizon correction removes gravity tilt but does not suppress all
high-frequency physical camera yaw/pitch/roll motion.

0.29 adds a centered, zero-phase 400 ms quaternion trajectory and applies the
raw-to-smoothed 3-axis orientation delta before horizon leveling:

```text
raw DJI orientation -> centered smoothed orientation
        -> 3-axis correction × Stabilization Amount
        -> horizon leveling -> final content rotation
```

0% preserves the previous horizon-only behavior. 100% applies the full
correction toward the smoothed trajectory. A practical first setting for rough
handheld/water footage is 60–80%.

The Project Organizer exposes the slider. Save the Project before Preview or
Clip editing; stabilization is part of preview-cache identity, so a matching
preview is prepared automatically.

CLI override:

```bash
panopilot project-export results/panopilot_project.json \
  -o results/stabilized.mp4 \
  --render-pipeline direct \
  --stabilization-amount 70
```


# 0.30 — High-Precision Adaptive Gyro Stabilization

0.29 showed that fixed Gaussian quaternion smoothing after downsampling to the output-frame cadence was not sufficient for rough-water shake. 0.30 replaces that stabilizer with a native-IMU-rate adaptive trajectory filter.

```text
DJI high-rate orientation (~1 kHz)
        ↓
angular velocity estimate + zero-phase smoothing
        ↓
velocity-adaptive quaternion time constant
        ↓
two-pass quaternion trajectory smoothing
        ↓
exact SLERP at every video exposure time
        ↓
strong nonlinear Stabilization Amount gain
        ↓
existing horizon leveling
```

Low/medium angular velocity receives long, gimbal-like smoothing. Sustained fast turns receive a shorter time constant so deliberate movement remains followable. 70% is intentionally much stronger than in 0.29. The implementation is clean-room and has no Gyroflow runtime dependency.

Timing uses PanoPilot's existing DJI high-rate timeline: the matching high-rate quaternion in each metadata packet is anchored to the per-frame DJI timestamp, and the stabilized trajectory is then SLERPed at the selected source exposure time.


# 0.31 — Hybrid Visual Residual Stabilization Spike

0.30's high-rate gyro stabilization removes rotational shake, but walking/bobbing, parallax and residual timing/calibration error can still move the final image. 0.31 adds an opt-in image-space residual stage based on sparse KLT optical flow, RANSAC similarity motion, centered clip-local camera-path smoothing, and a crop-constrained affine correction.

The stage resets at Project Clip boundaries and never treats a hard cut as shake. A 25% crop retains 75% of each linear frame dimension (1.333x zoom reserve). Correction is automatically reduced on frames that would otherwise exceed the crop envelope.

Use:

```bash
panopilot project-export \
  results/panopilot_project.json \
  -o results/final-031-hybrid.mp4 \
  --render-pipeline direct \
  --stabilization-amount 100 \
  --visual-stabilization \
  --stabilization-crop 25 \
  --report results/export-performance-031.json
```

The visual stage is deliberately opt-in in 0.31 because Project Preview does not yet execute the same second pass. Once representative footage passes the visual gate, the next increment can integrate the residual path into preview/project semantics.


# 0.32 — Extreme Crop-Backed Stabilization

0.31/0.30 representative footage still retained visible shake even with gyro
stabilization and a 30% crop. 0.32 adds a deliberately aggressive offline
stabilizer.

The standard 0.31 visual stabilizer remains available. Extreme mode adds:

```text
rendered gyro-stabilized video
        ↓
high-resolution KLT tracks
        ↓
forward/backward consistency rejection
        ↓
RANSAC similarity motion
        ↓
long centered camera-path smoothing
        ↓
compose correction
        ↓
re-render analysis view virtually
        ↓
measure residual motion again
        ↓
repeat 3 times
        ↓
one final source-image warp
        ↓
large fixed crop reserve
```

This differs materially from simply increasing a Gaussian strength. Each pass
measures the motion left after the previous correction and removes that residual
in a second/third optimization pass.

Extreme mode also stabilizes short-term uniform scale change in addition to
translation and rotation.

Recommended strong test:

```bash
panopilot project-export \
  results/panopilot_project.json \
  -o results/final-032-extreme.mp4 \
  --render-pipeline direct \
  --stabilization-amount 100 \
  --visual-stabilization \
  --visual-stabilization-mode extreme \
  --stabilization-crop 45 \
  --report results/export-performance-032.json
```

For an intentionally very aggressive test:

```text
--stabilization-crop 50
```

Extreme mode permits up to 60% linear crop. A 50% crop corresponds to a 2.0x
effective zoom.

The final 1920x1080 image is still warped only once. Iterative passes operate on
analysis images and compose their transforms before final rendering, avoiding
three full-resolution resampling generations.


# 0.33 — Locked Anti-Wobble Stabilization

The 0.32 Extreme mode proved that large crop-backed correction can remove much
more shake, but its iterative per-frame similarity model could create visible
wobble/zoom breathing. The representative report showed 1.3–2.2% p95 scale
changes in the visual estimator and later passes whose crop-limited correction
ratio fell to zero on some frames.

0.33 adds `locked` mode for the case where steadiness matters more than
retaining all image motion:

```text
high-rate gyro rotation stabilization
        ↓
robust visual motion measurement
        ↓
TRANSLATION ONLY residual path
        ↓
robust quadratic path per Clip
        ↓
one crop-feasibility gain for the whole Clip/pass
        ↓
fixed crop + one final image warp
```

Locked mode deliberately disables visual rotation and scale correction. The
high-rate gyro remains responsible for orientation. This prevents optical-flow
parallax from being converted into frame rotation or zoom breathing.

Unlike 0.32, the crop limiter never changes correction strength independently
from one frame to the next. One gain is solved for the complete Clip/pass, so
crop constraints cannot introduce correction pulses.

Recommended test:

```bash
panopilot project-export \
  results/panopilot_project.json \
  -o results/final-033-locked.mp4 \
  --render-pipeline direct \
  --stabilization-amount 100 \
  --visual-stabilization \
  --visual-stabilization-mode locked \
  --stabilization-crop 50 \
  --locked-stabilization-passes 2 \
  --report results/export-performance-033.json
```

0.33 also fixes the CLI validation bug that incorrectly rejected >40% crop even
when Extreme mode supported up to 60%. Extreme and Locked now both accept up to
60%; Standard remains capped at 40%.

# 0.34 — 360-Aware Spherical Visual Lock

The stabilization review identified the core architectural mistake in
0.31–0.33: the dominant walking correction was being applied *after* reframing
as a 2D crop/warp. That throws away the key advantage of a 360 source and forces
translation/parallax disagreement into one image transform, which is exactly
how wobble and excessive crop are created.

0.34 changes the recommended path to a two-stage 360-aware architecture:

```text
original OSV + high-rate gyro
        ↓
first gyro/direct render (analysis only)
        ↓
robust coarse-mesh optical-flow motion
        ↓
extract dominant high-frequency walking/bobbing velocity
        ↓
convert rejected image motion to virtual-camera yaw/pitch offsets
        ↓
RE-RENDER FROM THE ORIGINAL 360 SPHERE
        ↓
small anchored local mesh for parallax / rolling-shutter / stitch residual
        ↓
minimum-required crop, capped at 12% in spherical mode
```

The dominant global correction therefore costs **zero crop**. PanoPilot steers
the virtual camera into pixels that already exist elsewhere on the captured
sphere instead of translating/cropping the finished 16:9 image.

Only the remaining spatially varying residual is allowed to use a coarse 6×4
mesh. The local mesh has zero global authority, is periodically anchored to the
gyro-backed geometry, has no scale parameter and no per-frame zoom.

`--stabilization-crop` is a maximum budget. In spherical mode the local residual
stage is additionally capped at 12%, because a large crop is treated as a sign
that the residual model is trying to solve motion that belongs in the spherical
camera path.

Recommended walking test:

```bash
panopilot project-export \
  results/panopilot_project.json \
  -o results/final-034-spherical.mp4 \
  --render-pipeline direct \
  --stabilization-amount 100 \
  --visual-stabilization \
  --visual-stabilization-mode spherical \
  --stabilization-crop 12 \
  --report results/export-performance-034.json
```

Spherical mode is now the default visual residual mode.


# 0.35 — Rigid 3-Axis Spherical Visual Lock

Review of the representative 0.34 walking output identified a missing degree of
freedom in the spherical correction itself: visual analysis measured X/Y
motion, but **discarded residual image rotation**. The second spherical render
therefore corrected yaw/pitch while visible roll oscillation remained.

Measured on the representative 0.34 output, the walking Clip contained roughly:

```text
pairwise visual roll p95              ~1.26 deg/frame
pairwise visual roll max              ~3.68 deg/frame
required smooth roll correction       up to ~7 deg
spatial rotation disagreement p95     ~1.30 deg
```

The last value is also an important diagnostic: different image regions do not
always agree on one rotation, which is consistent with some combination of
parallax, rolling-shutter wobble, stitching residual, or a flexible post-warp.

0.35 changes the global 360-aware analysis to a rigid three-channel model:

```text
forward/backward KLT tracks
          ↓
RANSAC partial-affine fit
          ↓
throw away fitted SCALE
          ↓
separate center translation from rotation
          ↓
[dx velocity, dy velocity, roll velocity]
          ↓
channel-aware zero-phase smoothing
          ↓
integrate only the rejected high-frequency band
          ↓
Virtual Camera yaw + pitch + roll
          ↓
re-render from original 360 source
```

Scale is measured only as a diagnostic nuisance variable; it is never a visual
stabilization control.

## Spherical mode is rigid by default

The 0.34 spherical path automatically added a small local mesh after the sphere
re-render. On walking footage that flexibility can re-introduce local shear and
rotation wobble. 0.35 therefore returns the rigid spherical re-render directly.

The local mesh remains available only as an explicit advanced experiment:

```bash
--spherical-local-mesh
```

and its authority/crop budget are intentionally reduced.

## Crop-free global stabilization

Pure spherical yaw/pitch/roll correction needs no crop. Therefore this now
works and still performs global visual stabilization:

```bash
--visual-stabilization \
--visual-stabilization-mode spherical \
--stabilization-crop 0
```

Recommended validation command:

```bash
panopilot project-export \
  results/panopilot_project.json \
  -o results/final-035-rigid-spherical.mp4 \
  --render-pipeline direct \
  --stabilization-amount 100 \
  --visual-stabilization \
  --visual-stabilization-mode spherical \
  --stabilization-crop 0 \
  --report results/export-performance-035.json
```

The report now includes visual-roll statistics plus top/bottom and left/right
rotation disagreement. If the rigid output is globally stable but still shows
intra-frame bending/jello, that is the acceptance signal for the next layer:
source-lens rolling-shutter correction using row-specific high-rate IMU times,
not another stronger global warp.


# 0.36 — Source-Row Gyro Rolling-Shutter Rectification

The 0.35 result isolated a remaining failure mode: after strong frame-level
gyro stabilization, walking footage can still show intra-frame rotation wobble
or "jello". A rolling-shutter sensor does not expose the whole fisheye frame at
one instant; each source row is captured at a slightly different time.

PanoPilot 0.36 moves correction to the correct domain: **the original two
fisheye lens streams before final direct sampling**.

For a source row captured at orientation `R_row` and a synthetic global-shutter
reference orientation `R_ref`, the desired factory-equirectangular direction is
mapped to the source-row direction using the DJI BODY→WORLD trajectory:

```text
d_row =
  A · R_rowᵀ · R_ref · Aᵀ · d_ref

A = DJI IMU BODY → PanoPilot factory-equirectangular axes
```

The ~1 kHz DJI trajectory therefore provides intra-frame orientation, not just
one quaternion per output frame.

## Continuous source-row correction

The direct renderer:

```text
Virtual Camera + gyro/horizon correction
          ↓
nominal factory-equirectangular source ray
          ↓
initial DJI factory map → source lens Y
          ↓
sensor-row exposure time
          ↓
~1 kHz row-time quaternion
          ↓
row-specific 3-axis ray correction
          ↓
DJI factory map again
          ↓
original lens sample
```

The row-time rotation is represented by **11 exact samples from the native ~1 kHz DJI trajectory** across the sensor readout and continuously interpolated between those samples. Two map iterations resolve the small dependency between corrected direction and source row.

This is different from a global shear, homography, or post-render mesh. The
correction follows the actual fisheye sensor row used for each output pixel.

## Automatic readout calibration

Rolling-shutter duration and timing are sensitive parameters. PanoPilot does
not blindly assume a fixed DJI readout value.

`--rolling-shutter auto` is the default for direct rendering. For each source
Clip it:

1. finds high-angular-motion frame pairs from the high-rate DJI trajectory;
2. decodes those original lens frames once;
3. searches signed readout durations bounded by one source-frame period;
4. searches both top→bottom and bottom→top scan directions;
5. also searches the sensor-readout midpoint offset relative to the DJI/frame
   timing anchor;
6. re-renders each candidate at analysis resolution from the original lenses;
7. scores rigid-fit residual, spatial rotational disagreement,
   forward/backward tracking error, and nuisance scale;
8. accepts a non-zero solution only when it materially beats the zero-readout
   baseline.

The first-pass calibration is reused for the spherical visual re-render.

Manual engineering controls remain available:

```bash
--rolling-shutter manual
--rolling-shutter-readout-ms 8.0
--rolling-shutter-reference-offset-ms -1.5
--rolling-shutter-direction top-to-bottom
```

Disable the new stage for an A/B reference with:

```bash
--rolling-shutter off
```

## Rotation-wobble guard

0.36 also changes the spherical visual roll correction. A full-frame visual
roll estimate is trusted only when top/bottom and left/right image regions agree
on that rotation.

If the bands disagree, that is evidence for rolling shutter, parallax, stitch
deformation, or local foreground motion. In those frames the ~1 kHz gyro stays
authoritative and the visual roll correction is smoothly attenuated instead of
turning spatially inconsistent motion into whole-frame rocking.

Recommended test:

```bash
panopilot project-export \
  results/panopilot_project.json \
  -o results/final-036-rowtime.mp4 \
  --render-pipeline direct \
  --stabilization-amount 100 \
  --visual-stabilization \
  --visual-stabilization-mode spherical \
  --stabilization-crop 0 \
  --rolling-shutter auto \
  --report results/export-performance-036.json
```

The performance report records the selected signed readout, scan direction,
reference offset, calibration score improvement, and candidate scores for each
Clip.
\n\n# 0.37 — Final Export Size and Quality\n\nPanoPilot now exposes final delivery settings as Project-level output choices.\n\n**Size** is deliberately bounded to:\n\n- `720p` — 1280×720 for 16:9, 720×1280 for 9:16;\n- `1080p` — 1920×1080 for 16:9, 1080×1920 for 9:16.\n\nThere are no lower-than-720p or higher-than-1080p final-export options in this\nrelease. Preview/cache resolution remains an independent implementation detail.\n\n**Quality** presets are:\n\n- `Standard` — H.264 CRF 23, smaller file;\n- `High` — H.264 CRF 18, recommended and equivalent to the previous default;\n- `Very High` — H.264 CRF 15, higher fidelity/larger file.\n\nResolution and quality are persisted in Project schema v6 and are undoable in\nthe Project Organizer. Existing v1–v5 Projects migrate to `1080p / High`, so\nopening an older Project does not silently change its previous final-render\ngeometry or encoder quality.\n\nThe Project Organizer now contains an **Export** row with Size and Quality\nselectors. `Export Project…` automatically uses those saved settings.\n\nCLI overrides are available without changing the Project:\n\n```bash\npanopilot project-export project.json \\\n  -o output.mp4 \\\n  --resolution 720p \\\n  --quality high\n```\n\n`--crf` and `--preset` remain advanced engineering overrides. When omitted they\nare derived from the quality preset.\n

# 0.38 — Export Experience

0.38 turns final rendering into a first-class desktop workflow instead of a
modal spinner followed by terminal output.

Before export, the Project Organizer now shows one explicit confirmation with:

```text
file name + destination folder
resolution / aspect / FPS
quality preset / H.264 MP4
Project duration
Clip count
stabilization amount
```

The suggested output filename includes the saved resolution and quality, for
example:

```text
panopilot_project-1080p-high.mp4
```

The export dialog is determinate and displays:

```text
current operation
percentage
elapsed time
estimated remaining time
```

The exporter now emits structured progress for source inspection,
rolling-shutter calibration candidates, frame rendering, audio assembly, mux,
verification, and completion. Frame events also identify the render pass so a
future two-pass/spherical export does not reset the progress bar.

After a successful export PanoPilot shows:

```text
file name
resolution / FPS / quality
video duration
final file size
export time
full destination path
[Open Folder] [Close]
```

Export errors are reported in the desktop UI and return the User to the Project
Organizer rather than terminating the editing session.

No Project schema change is required for 0.38; export size and quality remain
schema-v6 Project settings.


# 0.39 — Precise 360 View Direction Controls

Mouse drag remains the fastest way to explore a 360 recording, but precise
Virtual Camera framing no longer depends on the pointer alone.

The Clip Editor now provides an explicit directional pad:

```text
             [ ↑ ]
        [ ← ]     [ → ]
             [ ↓ ]

Step: [ Fine 0.25° | Normal 1° | Coarse 5° ]
```

Each click changes only the transient exploratory camera. Hold an arrow button
for continuous rotation. The view becomes a persisted Camera Position only
when **Set Camera** is selected, preserving PanoPilot's exploration-versus-edit
invariant.

Keyboard equivalents are:

```text
Shift + Left   look left
Shift + Right  look right
Shift + Up     look up
Shift + Down   look down
```

Bare Left/Right remain timeline seek controls, so the established transport
workflow is preserved.


# 0.40 — Explicit Camera Roll Controls

PanoPilot now exposes all three Virtual Camera orientation axes in the Clip
Editor.

```text
                 ↑
            ←         →
                 ↓

Roll        ↺       ↻
          CCW       CW

Step:  0.25° / 1° / 5°
```

The same angular step selector is shared by yaw, pitch, and roll.

- `↺` rotates the conventional output view counter-clockwise.
- `↻` rotates it clockwise.
- holding either button continuously rolls the view;
- `[` is the counter-clockwise keyboard shortcut;
- `]` is the clockwise keyboard shortcut;
- roll navigation remains transient until **Set Camera** is pressed.

Camera Position roll is persisted in Project schema v7 and is interpolated
between Camera Positions using the shortest angular route, just like yaw.

Existing schema-v6 and older Projects migrate with `roll_deg = 0.0`, preserving
their previous framing exactly.


# 0.41 — Requirements Closure, Source Integrity, and Camera-Time Editing

Projects now persist a sampled SHA-256 expected Source Identity. Mismatched media is blocked rather than silently substituted. Multi-file import validates each OSV independently. Camera Position markers are draggable on the source timeline and preserve yaw/pitch/roll/FOV while changing Source Time. `docs/06_requirements_traceability.md` maps every normative requirement to implementation, verification evidence, and status; duplicate requirement IDs are now a test failure.
