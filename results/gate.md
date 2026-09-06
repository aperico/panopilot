# v0.5 Gate

Status: READY FOR VISUAL REVIEW

Key finding:
- factory calibration uses 3840x3840 pixel coordinates;
- tested lens streams are 1920x1920;
- v0.5 scales all pixel-domain calibration values before remapping.

IMU leveling remains deliberately disabled until the calibrated panorama
coordinate frame is accepted.
