# PanoPilot 0.16 Acceptance Gate

Status: READY FOR USER VALIDATION

Validate:
- Enter creates/updates a Camera Position in memory only;
- Ctrl+Z / Ctrl+Shift+Z undo and redo it;
- Delete removes a marker at the current preview frame;
- Delete is undoable;
- 16:9 / 9:16 output changes are undoable;
- Ctrl+S atomically saves and clears dirty state;
- save does not erase Undo history;
- new edit after Undo clears Redo;
- seek/play/mouse exploration do not create history;
- closing dirty project offers Save / Discard / Cancel.
