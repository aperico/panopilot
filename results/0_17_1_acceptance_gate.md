# PanoPilot 0.17.1 Acceptance Gate

Status: READY FOR USER VALIDATION

The trim data model and persistence were already confirmed correct from the
user's saved project.

Validate UX:
- IN / OUT labels are unmistakable;
- active Clip band is visually obvious;
- status line shows exact In / Out / duration;
- setting I or O produces immediate timestamp feedback;
- undo updates the labels/status;
- camera_exploration_changed is clearly separate from project_dirty;
- Play at Out restarts at In.
