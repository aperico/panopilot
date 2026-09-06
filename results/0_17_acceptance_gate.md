# PanoPilot 0.17 Acceptance Gate

Status: READY FOR USER VALIDATION

Validate:
- I/O set Clip trim and are Undo/Redo operations;
- trim does not change Camera Position Source Times;
- positions outside trim become dormant, not deleted;
- active View Path ignores dormant positions;
- playback stops at Clip Out;
- Play at Clip Out restarts at Clip In;
- with full-source trim, Play at source end restarts at zero;
- logical end survives cached-frame snapping;
- Save/reopen reproduces trim;
- `timeline-info` reports sequential Clip spans.
