# PanoPilot 0.18.4 Acceptance Gate

Status: READY FOR USER VALIDATION

Validate:
- Trim In/Out are visually distinct from Set Camera;
- CAM 0 + manual reframe + Play keeps the explored view;
- preview-only playback does not dirty/save the project;
- Set Camera changes CAM 0 -> CAM 1 and saves;
- CAM 1 playback follows the persisted View Path;
- camera-at reports hold-single after Set Camera.
