# Dynamic Horizon Preview Diagnostic

Observed input: first PanoPilot 0.8.0 IMU-leveled 3-second preview.

## Finding

The dominant problem was not ordinary IMU jitter.

The spherical resampler applied the correction matrix in the wrong inverse
direction. At approximately 1.0 s, the IMU estimated about 18.8 degrees of
camera tilt. The old renderer moved the image farther in that direction,
rather than counter-rotating it.

A local reconstruction test using the opposite mapping direction produced a
substantially more level horizon across the sample.

Approximate feature-motion diagnostic on the uploaded preview:

```text
Old 0.8.0 preview:
  mean absolute inter-frame apparent rotation ≈ 1.03°
  maximum observed inter-frame rotation       ≈ 5.97°

Direction-fixed diagnostic reconstruction:
  mean absolute inter-frame apparent rotation ≈ 0.20°
  maximum observed inter-frame rotation       ≈ 1.12°
```

The diagnostic reconstruction was generated from an already compressed and
already corrected preview, so these are not production benchmark values.
They are evidence that correction direction was the primary defect.

## Decision

Fix correction direction first.

Do not introduce temporal smoothing until a fresh 0.8.1 preview generated
directly from the OSV is visually assessed.
