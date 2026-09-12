# Workspace UX review — 2026-09-12

The revised flow is **Add recordings → Edit each clip → Arrange → Preview → Export**.
These are available actions, not a wizard: users can revisit any step without
changing the project's trim, camera, save, or export semantics.

| Problem observed | Implemented improvement |
|---|---|
| Empty Home showed disabled Arrange/Export actions above a large empty browser. | A prominent Add your first clips action, short workflow guidance, and no empty browser. |
| Editing required discovering double-click or a context menu. | An explicit Edit Selected Clip button alongside the existing entry points. |
| Selection updates changed menu visibility but could leave availability stale. | Edit, Remove, and reorder actions update immediately; earlier/later are disabled at sequence boundaries. |
| Preview and output settings were hidden in menus. | Preview Project and Project Settings on Home, with the current output size/FPS nearby. |
| Generic ready instructions did not distinguish preparation failure or missing media. | Contextual guidance explains automatic opening, retry, or View Clip Info; unavailable sources disable Edit. |
| Logo, repeated project name, and full file path competed with work. | Smaller branding on empty Home; selected-clip guidance on populated Home; full project path retained in tooltips. |
| General button rules overrode primary-action styling. | More specific theme rules, a darker blue primary action, disabled styling, and visible keyboard focus. |
| A populated Home squashed controls at 720×480. | A scrollable Home panel with minimum layout sizing and a smaller, independently scrolling Clip browser. |
| Editing instructions existed in a hidden label. | Short visible Reframe/Trim instructions, including the saved-view update behavior. |

Project source data, export algorithms, save/discard prompts, and transactional
editing boundaries remain authoritative. Existing architecture tests that required
Edit and Settings to be absent were revised to reflect the requested workflow.

## Validation

`tests/test_056_home_workflow.py` instantiates real Qt windows with media decoding
stubbed. It checks empty/populated state, selected-clip dispatch, reorder boundaries,
return from Arrange, preview guidance, missing-source recovery, minimum control
size, non-overlapping labels, and scrolling every action into view at 720×480.

Offscreen screenshots of both Home states were inspected. This caught overlap
that initial button-bounds checks missed; the test now checks non-overlap and
minimum control size as well. Native Fedora/Wayland, actual clip playback, keyboard
navigation through the entire editor, and screen-reader acceptance still require
interactive verification. I2-UX-025/026 remain PARTIAL for those field checks.

## Browser ChatGPT handoff

No browser-control tool or connection to the user's existing ChatGPT conversation
was exposed in this session, so no browser-generated code draft was requested or
used. If that connection becomes available, this is a focused follow-up prompt
for the conversation that already holds the source:

> Review the current PanoPilot workspace changes against this flow: Add clips,
> Edit, Arrange, Preview, Export. Draft a focused usability review and small PySide6
> patches for remaining interaction problems. Preserve ProjectSession transactions,
> Source-Time camera positions, asynchronous preview preparation, explicit Save,
> and atomic background exports. Do not change rendering algorithms. Prioritize
> keyboard navigation, preparation cancellation, and a coherent export-settings
> dialog. Treat project_editor.py, explore.py, and desktop_theme.py as the primary
> files. List assumptions and useful behavioral tests. The current local changes
> already add explicit Home Edit/Preview/Settings actions, contextual preparation
> guidance, synchronized selection actions, and a scrollable Home panel; request
> their latest diffs before drafting patches against your older source context.
