# PanoPilot

Current internal version: `0.15.0`

# 0.15 — Prepared panoramic preview + real-time playback

The desktop editor no longer reconstructs the original dual-fisheye OSV on
every seek.  PanoPilot prepares a disposable lower-resolution panoramic editing
representation and reuses it until the source or preview profile changes.

```text
original OSV (immutable)
      ↓ one-time preparation
cached stitched + leveled panorama MP4
      ↓
fast seek / sequential decode
      ↓
View Path
      ↓
Virtual Camera
      ↓
interactive conventional preview
```

The cache lives under the user's XDG cache directory by default and is never
part of the authoritative project state.

## Update

```bash
cd ~/workspace/osmo360
source .venv/bin/activate
pip install -e .

panopilot --version
```

Expected:

```text
PanoPilot 0.15.0
```

## Run

```bash
panopilot explore \
  samples/osmosample.OSV \
  --project results/panopilot_project.json
```

On the first run PanoPilot will prepare the panoramic editing preview.  Later
runs reuse it automatically when the source identity and preview profile still
match.

Default editing representation:

```text
1280 × 640 panoramic
20 fps
H.264
source audio included
DJI horizon leveling included
```

## Playback controls

```text
Space              Play / Pause
Enter / Return     Use this view (commit Camera Position)
left drag          Explore camera direction
mouse wheel        Zoom / FOV
timeline slider    Seek
Left / Right       Seek -/+ 100 ms
R                  Reset to persisted View Path at current time
1 / 2              16:9 / 9:16
H                  HUD
Esc / Q            Close
```

Space is intentionally no longer a commit shortcut.  It follows the desktop
video convention of Play/Pause.  The explicit edit boundary remains Enter or
Return.

## Audio synchronization

When Qt Multimedia is available, PanoPilot plays audio from the cached MP4 and
uses the media player's position as the playback clock.  The Virtual Camera
frames therefore follow the audio/media clock rather than an independently
running UI timer.

If Qt Multimedia audio cannot initialize, PanoPilot falls back to a monotonic
playback clock and continues silently rather than failing the editor.

## Prepare explicitly

You normally do not need this command because `explore` prepares automatically:

```bash
panopilot prepare-preview samples/osmosample.OSV
```

Force a rebuild:

```bash
panopilot prepare-preview \
  samples/osmosample.OSV \
  --rebuild
```

or from the editor command:

```bash
panopilot explore \
  samples/osmosample.OSV \
  --project results/panopilot_project.json \
  --rebuild-preview
```

## Cache validity

The cache key includes:

```text
absolute source path
source file size
source modification time
preview dimensions
preview fps
horizon/stabilization settings
IMU timing settings
audio setting
encoding profile
```

Changing any of those produces a new disposable preview.  The project and OSV
are untouched.

## 0.15 acceptance gate

Pass if:

1. first open prepares a panoramic preview;
2. second open reuses it without rebuilding;
3. timeline seeks are materially faster than 0.14 original-source seeks;
4. Space starts and pauses real-time playback;
5. the timeline and current Source Time advance during playback;
6. the persisted View Path drives the camera while playing;
7. playback audio is audible and reasonably synchronized when Qt Multimedia is available;
8. dragging/zooming pauses playback and returns to transient exploration;
9. Enter commits at the currently displayed Source Time;
10. changing/replacing the source invalidates the cache automatically.

## Performance note

The default cache is 20 fps rather than 30 fps intentionally.  The current CPU
Virtual Camera path is already comfortably above 20 fps on the development
baseline, while 20 fps keeps preview generation/storage modest.  This is an
editing representation, not final export.

## Next increment

After this passes, `0.16` should focus on editing operations rather than more
media plumbing:

```text
Camera Position selection / delete / update
Undo / Redo transaction model
project dirty state
Save semantics
```

Final-quality export continues to use the original OSV rather than this cache.
