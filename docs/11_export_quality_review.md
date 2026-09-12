# Export quality review — 2026-09-12

Reference application: DJI Mimo, confirmed by the user. Status: color correction
verified; overall Mimo parity remains unverified.

## Findings and changes

| Finding | Impact | Disposition |
|---|---|---|
| The base encoder supplied BT.709 command options without explicitly setting filtered-frame color properties. FFmpeg 8.1.2 output lacked transfer and primary tags in the reproduced test. | Players cannot reliably identify the intended color interpretation. | Explicit RGB-to-YCbCr conversion, filtered-frame signaling, and output tags in `video_encoding.py`. |
| Four optional residual stabilizers built separate encoders without a color policy. | Export color behavior depended on the selected stabilization mode. | All five renderers now use the same encoder builder. |
| Final verification checked structure and timing but not color. | Missing or incorrect color properties could reach the destination. | Verify pixel format, range, matrix, transfer, and primaries after final mux and before atomic replacement. Report measured properties. |
| Tests checked encoder arguments, not decoded pixels. | Correct-looking flags could pass despite an incorrect file. | Encode/decode regression at 256×128, 128×256, and 1920×1080; independent BT.709 luma oracle and BGR round trip. |
| Current High/Very High/Master are already CRF 16/13/10 with slow encoding. | Lowering CRF again does not repair upstream sampling, color, or stitching defects. | Preserve the existing compression choices. |

On this FFmpeg version, the old test image's luma samples already matched BT.709;
the reproduced defect was missing metadata, not a demonstrated luma-matrix error.
The explicit conversion also removes reliance on automatic matrix selection.

FFmpeg documents conversion control separately from frame-property tagging:
[scale](https://ffmpeg.org/ffmpeg-filters.html#scale) and
[setparams](https://ffmpeg.org/ffmpeg-filters.html#setparams).
The shared policy assumes already gamma-encoded SDR BGR. It does not perform
HDR tone mapping, wide-gamut conversion, or a DJI D-Log M transform.

## Remaining limits

The bundled OSV contains two 1920×1920, 100 fps, 10-bit, limited-range BT.709
lens streams. The renderer decodes into 8-bit BGR and delivers 8-bit 4:2:0 H.264.
This can lose smooth-gradient precision before compression; selecting Master
cannot recover those values. Supporting a true 10-bit workflow requires changes
through decode, blending, warping, and delivery, plus separate color acceptance.

The default renderer stitches a 3840×1920 panorama and then samples the final
view. That adds two image interpolation stages; outputting 2160p does not by
itself supply native 4K reframed detail. The existing direct renderer samples
the lenses at delivery coordinates and avoids the intermediate image. It stays
opt-in under SYS-PERF-026 until image acceptance is completed. Automatic
sharpness enhancement would need evaluation for halos and temporal shimmer.

Factory calibration and feathered overlap blending do not establish parity
with Mimo's treatment of parallax, occlusions, exposure differences, or moving
objects near seams. Existing geometry and stabilization tests do not measure
those perceptual differences. Likewise, Auto 60 fps from the supported 100 fps
source has uneven frame-selection cadence; explicit 50 fps is available for
even source-frame spacing. Existing Auto requirements are preserved.

The older requirements restricted delivery to 720p/1080p and three quality
levels, while code already offered 1440p/2160p and Master. I2-QUALITY-005 now
records that extension explicitly. The frozen Iteration-1 certificate measures
its historical requirements, not comparative Mimo image quality.

## Verification

- Full regression suite: **485 passed** on FFmpeg 8.1.2 / OpenCV 5.0.0.
- New decoded color tests: luma error ≤2 code values, reconstructed BGR error
  ≤4 code values, with actual limited-range BT.709 metadata.
- Original-media smoke: first 0.2 seconds of `samples/osmosample.OSV`, six frames,
  1280×720 at 30 fps, High, software decode, panorama rendering, rolling-shutter
  correction off. Final video and audio durations both 0.2 seconds; A/V stream
  delta 0.0 seconds. Report: `results/export-quality-smoke.json`.
- The short smoke establishes pipeline integration, not perceptual acceptance
  or long-duration performance. The generated MP4 is temporary at
  `/tmp/panopilot-quality-smoke.mp4`.

Run automated checks with:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
```

The suite uses the normal project-backup directory under the user's data
directory; a sandbox denying those writes requires the corresponding permission.

## Matched Mimo acceptance protocol

1. Retain the original OSV and a Mimo export, recording phone model, OS/app
   version, source recording mode, color mode, output dimensions, frame rate,
   quality selection, stabilization setting, and exact trim range. DJI describes
   its app export workflow in the
   [Osmo 360 manual](https://dl.djicdn.com/downloads/Osmo_360/20250724/Osmo_360_User_Manual_v1.0_en.pdf).
2. Match camera direction, field of view, aspect, and camera motion. Start with
   fixed camera positions, then a moving View Path. Test panorama and direct
   PanoPilot renderers separately at the same delivery profile.
3. Include daylight fine texture, smooth sky/shadow gradients, skin tones,
   walking motion, rapid rotation, and nearby objects crossing a lens seam.
   Use at least one 5–10 second sequence per condition; retain exact timestamps.
4. Inspect randomized A/B playback at native size on the same phone/display,
   then compare synchronized crops for softness, halos, ghosting, seam doubling,
   banding, color shifts, shimmer, wobble, and motion cadence. Record each defect
   by timestamp and severity: absent, visible on inspection, or distracting.
5. Proposed release gate: PanoPilot has no additional distracting defect and no
   worse severity in any listed category on every matched sequence, confirmed
   by the user. Confirm this criterion before closing I2-QUALITY-004. Record
   file size and export time separately from image-quality judgments.

Do not treat PSNR/SSIM against Mimo as ground-truth quality: different color
processing, framing, stabilization, or exposure timing can lower those scores
without establishing which image looks better. They are useful only as
supplementary diagnostics after alignment.
