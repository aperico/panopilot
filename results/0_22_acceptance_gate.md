# PanoPilot 0.22 Acceptance Gate

Status: READY FOR USER PERFORMANCE BASELINE

Run the same representative Project used for the accepted 0.20/0.21 export:

panopilot project-export \
  results/panopilot_project.json \
  -o results/final-022.mp4 \
  --report results/export-performance.json

Validate:
- final visual/audio output remains correct;
- terminal prints a timing breakdown;
- report contains performance.video_stage_timings;
- report contains performance.dominant_video_stage;
- capture the dominant stage and total export time for the next optimization.
