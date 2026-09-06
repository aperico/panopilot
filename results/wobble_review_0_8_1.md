# 0.8.1 Wobble Review

The uploaded raw and IMU-leveled previews were compared frame-by-frame.

Observed behavior:

- the leveled video substantially improves average horizon orientation;
- coarse horizon samples are much closer to horizontal in the leveled output;
- however, frame-to-frame correction is still visibly too active.

This means the primary coordinate/sign issue was fixed in 0.8.1, but direct
per-frame gravity correction is too reactive for this dynamic water footage.

Decision for 0.8.2:

- keep the current canonical coordinate model;
- keep yaw unmodified;
- smooth the gravity trajectory using a centered zero-phase Gaussian filter;
- start with 150 ms and validate 100/150/250 ms on the golden clip.
