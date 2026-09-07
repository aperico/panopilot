# Third-Party Notice

PanoPilot currently contains isolated code derived from or based on the
reverse-engineered DJI Osmo 360 work in:

PanoForge  
https://github.com/Belenos-Toutatis/PanoForge

License: MIT

Relevant upstream concepts/files include:

- `app/core/osv_meta/mp4parse.py`
- `app/core/osv_meta/extract_djmd.py`
- `app/core/maps.py`
- `app/core/stabilize.py`

PanoPilot-specific changes include:

- memory-mapped OSV metadata access;
- direct OSV → calibrated panorama orchestration;
- explicit scaling from factory calibration coordinates to decoded stream size;
- in-memory OpenCV remapping;
- PanoPilot's canonical IMU → factory-equirect coordinate mapping;
- direct spherical horizon rotation in OpenCV;
- separation of DJI parsing, optical calibration, attitude, and project-domain concerns.

The DJI metadata field map remains reverse-engineered and must be validated
for each supported camera firmware/source profile.


PanoPilot 0.9.0 also uses PanoForge's documented discovery that the DJI djmd packet contains a repeated high-rate quaternion block (approximately 1 kHz on the tested Osmo 360 profile). PanoPilot's exposure-time anchoring strategy is PanoPilot-specific.

## Stabilization research references

PanoPilot 0.30's adaptive gyro-stabilization design was informed by publicly
documented stabilization concepts used in projects such as Gyroflow, including
velocity-adaptive orientation smoothing and bidirectional trajectory filtering.

Gyroflow
https://github.com/gyroflow/gyroflow
License: GPL-3.0-or-later

No Gyroflow source code is copied, translated, linked, vendored, or used as a
runtime dependency by PanoPilot. The 0.30 stabilizer is a clean-room
implementation using PanoPilot's own quaternion math, timing model, and DJI
metadata pipeline.
