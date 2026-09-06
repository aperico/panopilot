# PanoPilot 0.18.1 Acceptance Gate

Status: READY FOR USER VALIDATION

Layout:
- preview centered in a dark expanding canvas;
- no long time/trim labels force a wide white window;
- transport and editing controls are separated into compact rows;
- Source Time, Clip-local Time, trim values, project state, and camera state
  remain readable without duplication;
- HUD contains only state + camera data.

Preparation:
- --rebuild-preview opens a PanoPilot loading dialog;
- preparation work executes off the Qt UI thread;
- loading dialog closes when cache is ready;
- Clip Editor then opens normally.
