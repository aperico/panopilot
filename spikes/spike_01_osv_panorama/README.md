# PanoPilot — SPIKE-01: OSV to Navigable Panorama

Status: Ready to Execute  
Parent: `05_technical_spikes.md`  
Risk coverage: RISK-01, RISK-02, RISK-05

---

# 1. Objective

Prove that one representative DJI Osmo 360 `.OSV` recording can be:

1. inspected on Fedora;
2. interpreted without manual preconversion;
3. used to produce or expose a usable panoramic representation;
4. opened in a minimal navigable 360 viewer.

This is a technical experiment, not production application code.

---

# 2. Required Input

Place or reference one real DJI Osmo 360 `.OSV` file.

Recommended local layout:

```text
spike_01_osv_panorama/
├── sample/
│   └── representative.OSV
├── scripts/
└── results/
```

Large source media should not normally be committed to Git.

If a corresponding `.LRF` exists, keep it beside the `.OSV` for later
comparison.

---

# 3. First Execution

From the spike directory:

```bash
chmod +x scripts/*.sh

./scripts/capture_environment.sh

./scripts/inspect_osv.sh /path/to/representative.OSV
```

This produces:

```text
results/environment.txt
results/ffprobe.json
results/ffmpeg_probe.txt
results/stream_summary.txt
```

Do not begin stitching code until these files have been reviewed.

---

# 4. Investigation Sequence

## Phase A — Container and Stream Inspection

Determine:

- number of video streams;
- codec and pixel format;
- dimensions;
- frame rates and time bases;
- audio streams;
- data/metadata streams;
- duration and start timestamps;
- DJI-specific metadata visibility.

Expected decision output:

```text
Can the file structure be understood reliably?
YES / NO / PARTIAL
```

---

## Phase B — DJI / PanoForge Compatibility

Compare the inspected stream structure with the assumptions used by
PanoForge.

Determine:

- whether the expected dual-fisheye video structure is present;
- where DJI metadata is exposed;
- whether calibration extraction works;
- whether the existing PanoForge path can be reused unchanged;
- which adaptations, if any, are necessary.

Record findings in:

```text
results/panoforge_compatibility.md
```

---

## Phase C — Panoramic Reconstruction

Attempt the smallest possible reconstruction path.

Preferred order:

```text
1. PanoForge calibrated stitching path
2. PanoForge/geometric fallback path
3. minimal FFmpeg v360/remap experiment if required
```

The purpose is to establish feasibility, not to optimize quality yet.

Store a short resulting panoramic sample in:

```text
results/panorama_preview.*
```

---

## Phase D — Preview Representation

Evaluate at least one interaction-oriented representation.

Record:

- resolution;
- codec;
- frame rate;
- generation time;
- file size;
- seek behavior.

Do not prematurely freeze the production preview format.

---

## Phase E — Minimal Navigable Viewer

Use the reconstructed panoramic sample to prove:

```text
drag horizontally → look left/right
drag vertically   → look up/down
wheel             → zoom
```

This viewer can be disposable.

Production desktop-shell decisions remain out of scope.

---

# 5. Success Gate

SPIKE-01 is PASS when:

- the `.OSV` is inspected successfully;
- source timing is understood;
- audio availability is understood;
- source video structure is understood;
- a panoramic representation is produced or exposed;
- the panoramic result is visually usable;
- the surrounding view can be navigated;
- DJI-specific behavior can remain behind the future Panoramic Source Adapter;
- open issues are documented.

---

# 6. Result Template

At the end of the spike, complete `notes.md` with:

```text
Status: PASS | PARTIAL | FAIL

What was demonstrated:
- ...

Measurements:
- ...

PanoForge reuse:
- ...

Architecture implications:
- ...

Open risks:
- ...

Recommendation:
Proceed | Repeat | Change assumption
```

---

# 7. Immediate Action

Run the two inspection scripts against one real `.OSV`.

The resulting `ffprobe.json` is the next artifact that should be reviewed
before writing panoramic reconstruction code.
