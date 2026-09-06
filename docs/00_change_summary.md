# PanoPilot — Documentation Change Summary

Status: Updated  
Release alignment: PanoPilot 0.20.0
Date: 2026-09-06

## Documents

- `01_system_definition.md` → SD-0.6
- `02_use_cases.md` → UC-0.5
- `03_system_requirements.md` → SYS-0.8
- `04_functional_architecture.md` → FA-0.3
- `05_technical_spikes.md` → TS-0.2

## Changes incorporated

The documentation now reflects executable behavior through PanoPilot 0.19:

- Project Organizer / Clip Editor split;
- multi-Clip sequential Project model;
- stable Clip identity;
- non-destructive Source-Time trim;
- Camera Position persistence through Set Camera;
- configurable Camera Motion presets:
  Smooth, Ease In + Out, Ease In, Ease Out, Linear;
- configurable easing Amount from 0% to 100%;
- Project schema v3 Camera Motion persistence;
- Clip playback and preview-only exploration behavior;
- desktop loading-state lifecycle;
- sequential Project Preview;
- Project Time → Clip → Source Time mapping;
- active-Clip View Path application across Project playback;
- active-Clip source audio switching;
- Play-at-Project-end restart;
- technical-spike closure status.

## Remaining Iteration-1 gap

Final sequential MP4 export from original OSV media remains the principal
unimplemented end-to-end capability.


## PanoPilot 0.20 additions

- final sequential H.264 MP4 Project export;
- original OSV sources are authoritative export image inputs;
- Project Timeline order and Clip trims are applied to final video;
- persisted Clip View Paths and Project Camera Motion are applied per frame;
- Iteration-1 Output Profile policy resolved to 1920×1080/30 fps for 16:9 and
  1080×1920/30 fps for 9:16;
- original source audio is assembled in Clip order, with silence for a no-audio
  Clip only when required to preserve a Project that otherwise contains audio;
- export is written transactionally through a `.preparing.mp4` artifact and is
  verified before replacing the requested output;
- Export Project is available from the Project Organizer and through
  `panopilot project-export`;
- exported A/V stream-duration delta acceptance policy is 50 ms.
