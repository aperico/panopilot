# PanoPilot 0.20 Acceptance Gate

Status: READY FOR USER VALIDATION

Validate on a representative multi-Clip Project:
- Export Project opens a save-file flow;
- export loading state remains visible until completion;
- resulting MP4 is H.264 at the policy resolution and 30 fps;
- Clips appear in Project order;
- Clip trims are respected;
- persisted Camera Positions and Camera Motion match preview behavior;
- final image source quality is visibly higher than the disposable preview;
- source audio follows Clip order;
- no-audio Clip intervals preserve later audio alignment;
- output A/V synchronization is acceptable at Clip boundaries;
- a failed export does not replace an existing requested output;
- project-export CLI produces the same semantic result as GUI export.
