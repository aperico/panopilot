import argparse
import json
import sys
from pathlib import Path

import cv2

from . import __version__
from .cache import PreviewProfile, ensure_preview_cache
from .explore import explore_osv
from .dji import (
    extract_calibration,
    extract_orientation_samples,
)
from .factory import FactoryCalibratedMapper, load_calibration
from .pipeline import stitch_osv_frame
from .preview import render_preview
from .path_render import render_project_view_at
from .project import (
    latest_project_backup,
    list_project_backups,
    load_project,
    recover_project_backup,
    resolve_project_clip,
)
from .project_editor import run_project_editor
from .project_player import run_project_preview
from .project_export import export_project_video
from .loading import run_with_loading_screen
from .performance import format_performance_summary
from .cache import discover_cached_sources
from .recovery import (
    parse_candidate_indexes,
    rebuild_project_from_cache,
)
from .reframe import reframe_osv_frame
from .sweep import render_imu_offset_sweep
from .source import audio_streams, lens_streams, probe_source
from .view_path import evaluate_clip_view_path
from .timeline import build_project_timeline, project_duration


def _cmd_stitch(args):
    result = stitch_osv_frame(
        args.source,
        args.output,
        source_time=args.time,
        width=args.width,
        height=args.height,
        level_horizon=args.level_horizon,
        level_strength=args.level_strength,
        imu_source=args.imu_source,
        imu_offset_ms=args.imu_offset_ms,
    )

    print(f"Wrote: {result['output']}")
    print(json.dumps(result, indent=2))


def _cmd_stitch_lenses(args):
    frame0 = cv2.imread(args.lens0, cv2.IMREAD_COLOR)
    frame1 = cv2.imread(args.lens1, cv2.IMREAD_COLOR)

    if frame0 is None or frame1 is None:
        raise SystemExit("Could not read both lens images")

    if frame0.shape[:2] != frame1.shape[:2]:
        raise SystemExit("Lens images have different dimensions")

    h, w = frame0.shape[:2]
    calibration = load_calibration(args.calibration)

    mapper = FactoryCalibratedMapper(
        calibration,
        w,
        h,
        out_w=args.width,
        out_h=args.height,
    )

    panorama = mapper.stitch(frame0, frame1)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if not cv2.imwrite(str(output), panorama):
        raise SystemExit(f"Could not write {output}")

    print(f"Wrote: {output}")
    print(json.dumps(mapper.diagnostics.__dict__, indent=2))


def _cmd_calibration(args):
    calibration = extract_calibration(args.source)

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(calibration, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote: {output}")
    else:
        print(json.dumps(calibration, indent=2))


def _cmd_imu(args):
    from .dji import extract_orientation_data

    data = extract_orientation_data(args.source)

    perframe = data["perframe"]
    highrate = data["highrate"]

    result = {
        "perframe_sample_count": len(perframe),
        "highrate_sample_count": len(highrate),
        "highrate_diagnostics": data["highrate_diagnostics"],
        "perframe_first_source_time": (
            perframe[0].get("source_time") if perframe else None
        ),
        "perframe_last_source_time": (
            perframe[-1].get("source_time") if perframe else None
        ),
        "highrate_first_source_time": (
            highrate[0].get("source_time") if highrate else None
        ),
        "highrate_last_source_time": (
            highrate[-1].get("source_time") if highrate else None
        ),
    }

    print(json.dumps(result, indent=2))


def _cmd_inspect(args):
    probe = probe_source(args.source)
    lenses = lens_streams(probe)
    audio = audio_streams(probe)
    calibration = extract_calibration(args.source)

    fmt = probe.get("format", {})

    result = {
        "source": str(args.source),
        "duration": (
            float(fmt["duration"])
            if fmt.get("duration") is not None
            else None
        ),
        "camera_model": calibration.get("model"),
        "camera_firmware": calibration.get("fw_b") or calibration.get("fw_a"),
        "proto_version": calibration.get("proto_ver"),
        "calibration_lens_blocks": len(calibration.get("lenses", [])),
        "lens_streams": [
            {
                "index": int(s["index"]),
                "codec": s.get("codec_name"),
                "width": int(s["width"]),
                "height": int(s["height"]),
                "fps": s.get("avg_frame_rate"),
                "pixel_format": s.get("pix_fmt"),
            }
            for s in lenses
        ],
        "audio_streams": [
            {
                "index": int(s["index"]),
                "codec": s.get("codec_name"),
                "channels": s.get("channels"),
                "sample_rate": s.get("sample_rate"),
            }
            for s in audio
        ],
    }

    print(json.dumps(result, indent=2))



def _cmd_preview(args):
    summary = render_preview(
        args.source,
        args.output,
        start=args.start,
        duration=args.duration,
        fps=args.fps,
        width=args.width,
        height=args.height,
        level_horizon=not args.no_level_horizon,
        level_strength=args.level_strength,
        level_smoothing_ms=args.level_smoothing_ms,
        imu_source=args.imu_source,
        imu_offset_ms=args.imu_offset_ms,
        use_actual_video_pts=not args.no_actual_video_pts,
        with_audio=not args.no_audio,
        crf=args.crf,
        preset=args.preset,
    )

    print(f"Wrote: {summary['output']}")
    print(json.dumps(summary, indent=2))



def _cmd_imu_sweep(args):
    offsets = [
        float(value.strip())
        for value in args.offsets.split(",")
        if value.strip()
    ]

    if not offsets:
        raise ValueError("--offsets must contain at least one value")

    manifest = render_imu_offset_sweep(
        args.source,
        args.output_dir,
        offsets_ms=offsets,
        start=args.start,
        duration=args.duration,
        fps=args.fps,
        width=args.width,
        height=args.height,
        smoothing_ms=args.level_smoothing_ms,
        imu_source=args.imu_source,
        with_audio=args.with_audio,
    )

    print(json.dumps(manifest, indent=2))



def _cmd_reframe(args):
    result = reframe_osv_frame(
        args.source,
        args.output,
        source_time=args.time,
        yaw_deg=args.yaw,
        pitch_deg=args.pitch,
        fov_deg=args.fov,
        aspect=args.aspect,
        width=args.width,
        height=args.height,
        level_horizon=not args.no_level_horizon,
        level_strength=args.level_strength,
        imu_source=args.imu_source,
        imu_offset_ms=args.imu_offset_ms,
        panorama_width=args.panorama_width,
        panorama_height=args.panorama_height,
    )

    print(f"Wrote: {result['output']}")
    print(json.dumps(result, indent=2))



def _cmd_explore(args):
    result = explore_osv(
        args.source,
        source_time=args.time,
        yaw_deg=args.yaw,
        pitch_deg=args.pitch,
        fov_deg=args.fov,
        aspect=args.aspect,
        level_horizon=not args.no_level_horizon,
        level_strength=args.level_strength,
        imu_source=args.imu_source,
        imu_offset_ms=args.imu_offset_ms,
        panorama_width=args.panorama_width,
        panorama_height=args.panorama_height,
        view_long_edge=args.view_long_edge,
        show_hud=not args.no_hud,
        project_path=args.project,
        seek_step_seconds=args.seek_step_ms / 1000.0,
        preview_fps=args.preview_fps,
        level_smoothing_ms=args.level_smoothing_ms,
        cache_dir=args.cache_dir,
        rebuild_preview=args.rebuild_preview,
        use_preview_cache=not args.no_preview_cache,
        audio_enabled=not args.no_playback_audio,
    )

    state = result["explore_state"]

    if state.get("project_dirty"):
        print(
            "Editor ended with unsaved in-memory project changes."
        )
    elif state.get("saved_this_session"):
        print(
            f"Project saved: {result['project_path']} | "
            f"Camera Positions: {result['camera_position_count']}"
        )
    else:
        print(
            f"Editor ended cleanly | "
            f"Camera Positions: {result['camera_position_count']}"
        )

    print(json.dumps(state, indent=2))



def _cmd_prepare_preview(args):
    profile = PreviewProfile(
        width=args.width,
        height=args.height,
        fps=args.fps,
        level_horizon=not args.no_level_horizon,
        level_strength=args.level_strength,
        level_smoothing_ms=args.level_smoothing_ms,
        imu_source=args.imu_source,
        imu_offset_ms=args.imu_offset_ms,
        with_audio=not args.no_audio,
        crf=args.crf,
        preset=args.preset,
    )

    def progress(event):
        print(event["message"] + "...", flush=True)

    entry = ensure_preview_cache(
        args.source,
        profile=profile,
        cache_dir=args.cache_dir,
        rebuild=args.rebuild,
        progress_callback=progress,
    )

    print(json.dumps(entry.to_dict(), indent=2))


def _cmd_project_edit(args):
    project_path = Path(
        args.project
    )

    if not project_path.exists():
        backup = latest_project_backup(
            project_path
        )

        if backup is not None:
            print(
                "Project file is missing, but a durable PanoPilot backup exists:"
            )
            print(
                f"  {backup}"
            )
            print(
                "Recover it with:"
            )
            print(
                "  panopilot project-recover "
                f"{args.project}"
            )
            print()

    pending_sources = list(
        args.sources
    )

    while True:
        action = run_project_editor(
            args.project,
            import_sources=pending_sources,
        )
        pending_sources = []

        action_name = action.get(
            "action"
        )

        if action_name == "export":
            output = action.get(
                "output"
            )

            if not output:
                raise RuntimeError(
                    "Project editor returned export without output path"
                )

            def export_task(progress):
                def on_progress(event):
                    progress(
                        event.get(
                            "message",
                            "Exporting Project",
                        )
                    )

                return export_project_video(
                    args.project,
                    output,
                    progress_callback=(
                        on_progress
                    ),
                )

            result = run_with_loading_screen(
                export_task,
                title="PanoPilot",
                message="Exporting Project",
                detail=Path(output).name,
            )

            print(
                "Project export complete | "
                f"{result['output']} | "
                f"{result['encoded_duration']:.3f}s"
            )
            print(
                format_performance_summary(
                    result.get(
                        "performance",
                        {}
                    )
                )
            )
            continue

        if action_name == "preview":
            result = run_project_preview(
                args.project,
                view_long_edge=args.view_long_edge,
                preview_fps=args.preview_fps,
                cache_dir=args.cache_dir,
                rebuild_preview=args.rebuild_preview,
                audio_enabled=not args.no_playback_audio,
            )

            print(
                "Project preview closed | "
                f"Time: {result['project_time']:.3f}s / "
                f"{result['project_duration']:.3f}s"
            )
            continue

        if action_name != "edit":
            print(
                f"Project editor closed | "
                f"Clips: {action.get('clip_count', 0)}"
            )
            return

        project = load_project(
            args.project
        )
        clip = project.clip_for_id(
            action["clip_id"]
        )

        if clip is None:
            raise RuntimeError(
                "Selected Clip no longer exists in the saved project"
            )

        result = explore_osv(
            clip.source,
            project_path=args.project,
            clip_id=clip.id,
            source_time=clip.trim_in_source_time,
            view_long_edge=args.view_long_edge,
            preview_fps=args.preview_fps,
            cache_dir=args.cache_dir,
            rebuild_preview=args.rebuild_preview,
            audio_enabled=not args.no_playback_audio,
        )

        state = result["explore_state"]

        camera_count = int(
            result["camera_position_count"]
        )

        print(
            f"Clip editor closed | "
            f"{clip.id} | "
            f"Camera Positions: "
            f"{camera_count} | "
            f"{'Modified' if state.get('project_dirty') else 'Clean'}"
        )

        if camera_count == 0:
            print(
                "Note: this Clip has no saved Camera Positions; "
                "its View Path therefore uses the default camera."
            )




def _cmd_project_export(args):
    def progress(event):
        message = event.get(
            "message",
            "Exporting Project",
        )
        print(
            message,
            flush=True,
        )

    result = export_project_video(
        args.project,
        args.output,
        panorama_width=(
            args.panorama_width
        ),
        panorama_height=(
            args.panorama_height
        ),
        level_horizon=(
            not args.no_level_horizon
        ),
        level_strength=(
            args.level_strength
        ),
        level_smoothing_ms=(
            args.level_smoothing_ms
        ),
        imu_source=args.imu_source,
        imu_offset_ms=(
            args.imu_offset_ms
        ),
        crf=args.crf,
        preset=args.preset,
        decoder=args.decoder,
        vaapi_device=(
            args.vaapi_device
        ),
        projection_prefetch=(
            args.projection_prefetch
        ),
        render_pipeline=(
            args.render_pipeline
        ),
        progress_callback=progress,
    )

    print(
        f"Wrote: {result['output']}"
    )
    print()
    print(
        format_performance_summary(
            result.get(
                "performance",
                {}
            )
        )
    )

    if args.report:
        report_path = Path(
            args.report
        )
        report_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        report_path.write_text(
            json.dumps(
                result,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(
            f"Performance report: {report_path}"
        )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )


def _cmd_project_preview(args):
    result = run_project_preview(
        args.project,
        view_long_edge=args.view_long_edge,
        preview_fps=args.preview_fps,
        cache_dir=args.cache_dir,
        rebuild_preview=args.rebuild_preview,
        audio_enabled=not args.no_playback_audio,
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )





def _print_cached_source_candidates(
    candidates,
):
    if not candidates:
        print(
            "No PanoPilot preview-cache source recordings found."
        )
        return

    print(
        "Recoverable source recordings from preview cache:"
    )

    for index, candidate in enumerate(
        candidates,
        start=1,
    ):
        duration = (
            f"{candidate.source_duration:.3f}s"
            if candidate.source_duration is not None
            else "duration unknown"
        )
        status = (
            "OK"
            if candidate.exists
            else "MISSING"
        )

        print(
            f"{index:02d}  [{status}]  "
            f"{duration:>16}  "
            f"{candidate.source}"
        )


def _cmd_cache_sources(args):
    candidates = discover_cached_sources(
        cache_dir=args.cache_dir,
        existing_only=(
            args.existing_only
        ),
    )

    _print_cached_source_candidates(
        candidates
    )


def _cmd_project_rebuild_from_cache(
    args,
):
    candidates = discover_cached_sources(
        cache_dir=args.cache_dir,
        existing_only=True,
    )

    if not candidates:
        raise RuntimeError(
            "No existing source recordings were found in the "
            "PanoPilot preview cache."
        )

    _print_cached_source_candidates(
        candidates
    )
    print()
    print(
        "Preview cache can recover source paths only; "
        "prior trims and Camera Positions must be recreated."
    )

    selection = args.indexes

    if selection is None:
        if not sys.stdin.isatty():
            raise RuntimeError(
                "Use --indexes with source numbers in the desired Clip order."
            )

        print()
        selection = input(
            "Enter source numbers in desired Clip order "
            "(example: 2,1): "
        ).strip()

    indexes = parse_candidate_indexes(
        selection,
        candidate_count=len(
            candidates
        ),
    )

    result = rebuild_project_from_cache(
        args.project,
        indexes=indexes,
        cache_dir=args.cache_dir,
        output_aspect=args.aspect,
        camera_motion_easing=(
            args.camera_motion
        ),
        camera_motion_strength=(
            args.motion_amount
            / 100.0
        ),
    )

    print()
    print(
        "Fresh Project created:"
    )
    print(
        json.dumps(
            result,
            indent=2,
        )
    )
    print()
    print(
        "Next:"
    )
    print(
        "  panopilot project-edit "
        f"--project {args.project}"
    )



def _cmd_project_backups(args):
    backups = list_project_backups(
        args.project
    )
    latest = latest_project_backup(
        args.project
    )

    print(
        f"Project: {args.project}"
    )

    if latest is None:
        print(
            "No durable PanoPilot backups found."
        )
        return

    print(
        f"Latest: {latest}"
    )

    for index, backup in enumerate(
        backups,
        start=1,
    ):
        print(
            f"{index:02d}  {backup}"
        )


def _cmd_project_recover(args):
    result = recover_project_backup(
        args.project,
        backup=args.backup,
    )

    print(
        "Recovered Project:"
    )
    print(
        json.dumps(
            result,
            indent=2,
        )
    )



def _cmd_project_info(args):
    project = load_project(args.project)

    result = project.to_dict()
    result["project_path"] = str(args.project)

    print(json.dumps(result, indent=2))




def _cmd_timeline_info(args):
    project = load_project(args.project)
    source_durations = {}

    for clip in project.clips:
        probe = probe_source(clip.source)
        value = probe.get("format", {}).get("duration")
        if value is None:
            raise RuntimeError(
                f"Could not determine duration for {clip.source}"
            )
        source_durations[clip.id] = float(value)

    spans = build_project_timeline(project, source_durations)
    print(
        json.dumps(
            {
                "project": str(args.project),
                "project_duration": project_duration(
                    project, source_durations
                ),
                "clips": [span.to_dict() for span in spans],
            },
            indent=2,
        )
    )

def _cmd_camera_at(args):
    project = load_project(args.project)
    clip = resolve_project_clip(
        project,
        args.source,
    )

    sample = evaluate_clip_view_path(
        clip,
        args.time,
        interpolation=project.camera_motion_easing,
        strength=project.camera_motion_strength,
    )

    print(
        json.dumps(
            {
                "project": str(args.project),
                "clip_id": clip.id,
                "source": clip.source,
                "camera_position_count": len(
                    clip.camera_positions
                ),
                "camera_motion": {
                    "easing": project.camera_motion_easing,
                    "strength": float(
                        project.camera_motion_strength
                    ),
                },
                **sample.to_dict(),
            },
            indent=2,
        )
    )


def _cmd_reframe_path(args):
    result = render_project_view_at(
        args.project,
        args.source,
        args.output,
        source_time=args.time,
        width=args.width,
        height=args.height,
        level_horizon=not args.no_level_horizon,
        level_strength=args.level_strength,
        imu_source=args.imu_source,
        imu_offset_ms=args.imu_offset_ms,
        panorama_width=args.panorama_width,
        panorama_height=args.panorama_height,
    )

    print(f"Wrote: {result['output']}")
    print(json.dumps(result, indent=2))


def build_parser():
    parser = argparse.ArgumentParser(
        prog="panopilot",
        description="PanoPilot panoramic-video reframing prototype",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"PanoPilot {__version__}",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    cache_sources = sub.add_parser(
        "cache-sources",
        help="List source recordings recoverable from panoramic preview cache",
    )
    cache_sources.add_argument(
        "--cache-dir",
        default=None,
    )
    cache_sources.add_argument(
        "--existing-only",
        action="store_true",
        help="Hide cached source paths that no longer exist",
    )
    cache_sources.set_defaults(
        func=_cmd_cache_sources
    )

    rebuild_cache = sub.add_parser(
        "project-rebuild-from-cache",
        help="Create a fresh Project shell from selected preview-cache sources",
    )
    rebuild_cache.add_argument(
        "project",
        help="New Project JSON path to create",
    )
    rebuild_cache.add_argument(
        "--indexes",
        default=None,
        help="1-based source numbers in desired Clip order, e.g. 2,1",
    )
    rebuild_cache.add_argument(
        "--cache-dir",
        default=None,
    )
    rebuild_cache.add_argument(
        "--aspect",
        choices=("16:9", "9:16"),
        default="16:9",
    )
    rebuild_cache.add_argument(
        "--camera-motion",
        choices=(
            "smooth",
            "ease-in-out",
            "ease-in",
            "ease-out",
            "linear",
        ),
        default="smooth",
    )
    rebuild_cache.add_argument(
        "--motion-amount",
        type=float,
        default=100.0,
        help="Camera Motion Amount percentage (0..100)",
    )
    rebuild_cache.set_defaults(
        func=_cmd_project_rebuild_from_cache
    )

    project_backups = sub.add_parser(
        "project-backups",
        help="List durable backups for a PanoPilot project path",
    )
    project_backups.add_argument(
        "project",
        help="Original/intended PanoPilot project JSON path",
    )
    project_backups.set_defaults(
        func=_cmd_project_backups
    )

    project_recover = sub.add_parser(
        "project-recover",
        help="Restore a missing/damaged Project from its durable backup",
    )
    project_recover.add_argument(
        "project",
        help="Project JSON path to restore",
    )
    project_recover.add_argument(
        "--backup",
        default=None,
        help="Optional specific backup JSON; default is latest",
    )
    project_recover.set_defaults(
        func=_cmd_project_recover
    )

    project_info = sub.add_parser(
        "project-info",
        help="Show the current prototype project and committed Camera Positions",
    )
    project_info.add_argument("project")
    project_info.set_defaults(func=_cmd_project_info)

    project_edit = sub.add_parser(
        "project-edit",
        help="Open the multi-Clip sequential project organizer",
    )
    project_edit.add_argument(
        "sources",
        nargs="*",
        help=(
            "Optional OSV recordings to import in the given order; "
            "additional recordings can be added in the GUI"
        ),
    )
    project_edit.add_argument(
        "--project",
        default="results/panopilot_project.json",
        help="PanoPilot project JSON path",
    )
    project_edit.add_argument(
        "--view-long-edge",
        type=int,
        default=800,
        help="Clip-editor preview long edge (default: 800)",
    )
    project_edit.add_argument(
        "--preview-fps",
        type=float,
        default=20.0,
        help="Prepared panoramic preview frame rate (default: 20)",
    )
    project_edit.add_argument(
        "--cache-dir",
        default=None,
    )
    project_edit.add_argument(
        "--rebuild-preview",
        action="store_true",
    )
    project_edit.add_argument(
        "--no-playback-audio",
        action="store_true",
    )
    project_edit.set_defaults(
        func=_cmd_project_edit
    )

    project_export = sub.add_parser(
        "project-export",
        help="Render the complete Project from original OSV sources to H.264 MP4",
    )
    project_export.add_argument(
        "project",
        help="PanoPilot project JSON path",
    )
    project_export.add_argument(
        "-o",
        "--output",
        default="results/panopilot_export.mp4",
        help="Final H.264 MP4 output path",
    )
    project_export.add_argument(
        "--panorama-width",
        type=int,
        default=3840,
        help="Internal final panoramic width (default: 3840)",
    )
    project_export.add_argument(
        "--panorama-height",
        type=int,
        default=1920,
        help="Internal final panoramic height (default: 1920)",
    )
    project_export.add_argument(
        "--no-level-horizon",
        action="store_true",
    )
    project_export.add_argument(
        "--level-strength",
        type=float,
        default=1.0,
    )
    project_export.add_argument(
        "--level-smoothing-ms",
        type=float,
        default=100.0,
    )
    project_export.add_argument(
        "--imu-source",
        choices=("highrate", "perframe"),
        default="highrate",
    )
    project_export.add_argument(
        "--imu-offset-ms",
        type=float,
        default=0.0,
    )
    project_export.add_argument(
        "--crf",
        type=int,
        default=18,
        help="libx264 quality (default: 18)",
    )
    project_export.add_argument(
        "--preset",
        default="medium",
        help="libx264 preset (default: medium)",
    )
    project_export.add_argument(
        "--decoder",
        choices=(
            "auto",
            "software",
            "vaapi",
        ),
        default="auto",
        help=(
            "Lens decoder backend; auto runtime-tests VAAPI and falls back "
            "to software (default: auto)"
        ),
    )
    project_export.add_argument(
        "--vaapi-device",
        default=None,
        help=(
            "Optional VAAPI device, e.g. /dev/dri/renderD128; "
            "auto discovers render nodes when omitted"
        ),
    )
    project_export.add_argument(
        "--render-pipeline",
        choices=("panorama", "direct"),
        default="panorama",
        help=(
            "Final image pipeline: accepted panorama baseline or experimental "
            "direct dual-lens renderer (default: panorama)"
        ),
    )
    project_export.add_argument(
        "--no-projection-prefetch",
        action="store_false",
        dest="projection_prefetch",
        help=(
            "Disable one-frame-ahead projection-map generation "
            "for A/B benchmarking"
        ),
    )
    project_export.set_defaults(
        projection_prefetch=True,
    )
    project_export.add_argument(
        "--report",
        default=None,
        help="Optional JSON path for the complete export/performance report",
    )
    project_export.set_defaults(
        func=_cmd_project_export
    )

    project_preview = sub.add_parser(
        "project-preview",
        help="Preview the complete sequential Project Timeline",
    )
    project_preview.add_argument(
        "project",
        help="PanoPilot project JSON path",
    )
    project_preview.add_argument(
        "--view-long-edge",
        type=int,
        default=960,
        help="Conventional preview long edge (default: 960)",
    )
    project_preview.add_argument(
        "--preview-fps",
        type=float,
        default=20.0,
        help="Panoramic editing preview frame rate (default: 20)",
    )
    project_preview.add_argument(
        "--cache-dir",
        default=None,
    )
    project_preview.add_argument(
        "--rebuild-preview",
        action="store_true",
    )
    project_preview.add_argument(
        "--no-playback-audio",
        action="store_true",
    )
    project_preview.set_defaults(
        func=_cmd_project_preview
    )

    timeline_info = sub.add_parser(
        "timeline-info",
        help="Show sequential Clip spans after applying each Clip trim",
    )
    timeline_info.add_argument("project")
    timeline_info.set_defaults(func=_cmd_timeline_info)

    camera_at = sub.add_parser(
        "camera-at",
        help="Evaluate the persisted View Path at one Source Time",
    )
    camera_at.add_argument("project")
    camera_at.add_argument(
        "source",
        help="Clip id or source path",
    )
    camera_at.add_argument(
        "--time",
        type=float,
        required=True,
    )
    camera_at.set_defaults(func=_cmd_camera_at)

    reframe_path = sub.add_parser(
        "reframe-path",
        help="Render one conventional frame using the persisted View Path",
    )
    reframe_path.add_argument("project")
    reframe_path.add_argument(
        "source",
        help="Clip id or source path",
    )
    reframe_path.add_argument(
        "--time",
        type=float,
        required=True,
    )
    reframe_path.add_argument(
        "--width",
        type=int,
        default=None,
    )
    reframe_path.add_argument(
        "--height",
        type=int,
        default=None,
    )
    reframe_path.add_argument(
        "--no-level-horizon",
        action="store_true",
    )
    reframe_path.add_argument(
        "--level-strength",
        type=float,
        default=1.0,
    )
    reframe_path.add_argument(
        "--imu-source",
        choices=("highrate", "perframe"),
        default="highrate",
    )
    reframe_path.add_argument(
        "--imu-offset-ms",
        type=float,
        default=0.0,
    )
    reframe_path.add_argument(
        "--panorama-width",
        type=int,
        default=1920,
    )
    reframe_path.add_argument(
        "--panorama-height",
        type=int,
        default=960,
    )
    reframe_path.add_argument(
        "-o",
        "--output",
        default="results/reframed_path.jpg",
    )
    reframe_path.set_defaults(func=_cmd_reframe_path)

    prepare_preview = sub.add_parser(
        "prepare-preview",
        help="Prepare the disposable panoramic editing representation",
    )
    prepare_preview.add_argument("source")
    prepare_preview.add_argument("--width", type=int, default=1280)
    prepare_preview.add_argument("--height", type=int, default=640)
    prepare_preview.add_argument("--fps", type=float, default=20.0)
    prepare_preview.add_argument("--no-level-horizon", action="store_true")
    prepare_preview.add_argument("--level-strength", type=float, default=1.0)
    prepare_preview.add_argument("--level-smoothing-ms", type=float, default=100.0)
    prepare_preview.add_argument(
        "--imu-source",
        choices=("highrate", "perframe"),
        default="highrate",
    )
    prepare_preview.add_argument("--imu-offset-ms", type=float, default=0.0)
    prepare_preview.add_argument("--no-audio", action="store_true")
    prepare_preview.add_argument("--crf", type=int, default=23)
    prepare_preview.add_argument("--preset", default="veryfast")
    prepare_preview.add_argument("--cache-dir", default=None)
    prepare_preview.add_argument("--rebuild", action="store_true")
    prepare_preview.set_defaults(func=_cmd_prepare_preview)

    inspect_cmd = sub.add_parser(
        "inspect",
        help="Inspect an OSV and its DJI calibration metadata",
    )
    inspect_cmd.add_argument("source")
    inspect_cmd.set_defaults(func=_cmd_inspect)

    imu = sub.add_parser(
        "imu",
        help="Inspect DJI orientation telemetry in an OSV",
    )
    imu.add_argument("source")
    imu.set_defaults(func=_cmd_imu)

    stitch = sub.add_parser(
        "stitch",
        help="Create a factory-calibrated equirectangular frame directly from an OSV",
    )
    stitch.add_argument("source")
    stitch.add_argument(
        "--time",
        type=float,
        default=0.0,
        help="Source Time in seconds (default: 0)",
    )
    stitch.add_argument("-o", "--output", default="results/panorama.jpg")
    stitch.add_argument("--width", type=int, default=1920)
    stitch.add_argument("--height", type=int, default=960)
    stitch.add_argument(
        "--level-horizon",
        action="store_true",
        help="Use DJI IMU orientation to level the spherical horizon",
    )
    stitch.add_argument(
        "--level-strength",
        type=float,
        default=1.0,
        help="Horizon correction strength in [0,1] (default: 1.0)",
    )
    stitch.add_argument(
        "--imu-source",
        choices=("highrate", "perframe"),
        default="highrate",
        help="DJI orientation stream used by --level-horizon",
    )
    stitch.add_argument(
        "--imu-offset-ms",
        type=float,
        default=0.0,
        help="Timing offset applied to IMU lookup (default: 0)",
    )
    stitch.set_defaults(func=_cmd_stitch)

    reframe = sub.add_parser(
        "reframe",
        help="Render a conventional rectilinear Virtual Camera frame from an OSV",
    )
    reframe.add_argument("source")
    reframe.add_argument("--time", type=float, default=0.0)
    reframe.add_argument(
        "--yaw",
        type=float,
        default=0.0,
        help="Horizontal orientation in degrees; positive = right",
    )
    reframe.add_argument(
        "--pitch",
        type=float,
        default=0.0,
        help="Vertical orientation in degrees; positive = up",
    )
    reframe.add_argument(
        "--fov",
        type=float,
        default=90.0,
        help="Horizontal rectilinear field of view in degrees",
    )
    reframe.add_argument(
        "--aspect",
        choices=("16:9", "9:16"),
        default="16:9",
    )
    reframe.add_argument("--width", type=int, default=None)
    reframe.add_argument("--height", type=int, default=None)
    reframe.add_argument(
        "--no-level-horizon",
        action="store_true",
    )
    reframe.add_argument(
        "--level-strength",
        type=float,
        default=1.0,
    )
    reframe.add_argument(
        "--imu-source",
        choices=("highrate", "perframe"),
        default="highrate",
    )
    reframe.add_argument(
        "--imu-offset-ms",
        type=float,
        default=0.0,
    )
    reframe.add_argument(
        "--panorama-width",
        type=int,
        default=1920,
    )
    reframe.add_argument(
        "--panorama-height",
        type=int,
        default=960,
    )
    reframe.add_argument(
        "-o",
        "--output",
        default="results/reframed.jpg",
    )
    reframe.set_defaults(func=_cmd_reframe)

    explore = sub.add_parser(
        "explore",
        help="Open a local interactive Virtual Camera explorer for one OSV frame",
    )
    explore.add_argument("source")
    explore.add_argument(
        "--time",
        type=float,
        default=None,
        help="Initial Source Time; default starts at the Clip In point",
    )
    explore.add_argument(
        "--yaw",
        type=float,
        default=None,
        help="Initial horizontal camera orientation in degrees",
    )
    explore.add_argument(
        "--pitch",
        type=float,
        default=None,
        help="Initial vertical camera orientation in degrees",
    )
    explore.add_argument(
        "--fov",
        type=float,
        default=None,
        help=(
            "Initial FOV; default uses the persisted View Path when "
            "available"
        ),
    )
    explore.add_argument(
        "--aspect",
        choices=("16:9", "9:16"),
        default="16:9",
    )
    explore.add_argument(
        "--no-level-horizon",
        action="store_true",
    )
    explore.add_argument(
        "--level-strength",
        type=float,
        default=1.0,
    )
    explore.add_argument(
        "--imu-source",
        choices=("highrate", "perframe"),
        default="highrate",
    )
    explore.add_argument(
        "--imu-offset-ms",
        type=float,
        default=0.0,
    )
    explore.add_argument(
        "--panorama-width",
        type=int,
        default=1280,
    )
    explore.add_argument(
        "--panorama-height",
        type=int,
        default=640,
    )
    explore.add_argument(
        "--view-long-edge",
        type=int,
        default=800,
        help="Interactive preview long edge in pixels (default: 800)",
    )
    explore.add_argument(
        "--no-hud",
        action="store_true",
        help="Start with the on-screen controls/status overlay hidden",
    )
    explore.add_argument(
        "--project",
        default="results/panopilot_project.json",
        help=(
            "Project JSON path written only after 'Use this view' "
            "(default: results/panopilot_project.json)"
        ),
    )
    explore.add_argument(
        "--seek-step-ms",
        type=float,
        default=100.0,
        help="Left/right arrow seek increment in milliseconds (default: 100)",
    )
    explore.add_argument(
        "--preview-fps",
        type=float,
        default=20.0,
        help="Prepared panoramic preview frame rate (default: 20)",
    )
    explore.add_argument(
        "--level-smoothing-ms",
        type=float,
        default=100.0,
        help="Horizon smoothing used while preparing the preview cache",
    )
    explore.add_argument(
        "--cache-dir",
        default=None,
        help="Optional preview-cache directory (default: XDG user cache)",
    )
    explore.add_argument(
        "--rebuild-preview",
        action="store_true",
        help="Rebuild the panoramic editing preview even if a valid cache exists",
    )
    explore.add_argument(
        "--no-preview-cache",
        action="store_true",
        help="Debug only: use original-source synchronous seeks instead of the cache",
    )
    explore.add_argument(
        "--no-playback-audio",
        action="store_true",
        help="Disable audio during cached playback",
    )
    explore.set_defaults(func=_cmd_explore)

    preview = sub.add_parser(
        "preview",
        help="Render a short stitched panoramic preview video from an OSV",
    )
    preview.add_argument("source")
    preview.add_argument(
        "--start",
        type=float,
        default=0.0,
        help="Source Time at which preview starts (default: 0)",
    )
    preview.add_argument(
        "--duration",
        type=float,
        default=3.0,
        help="Preview duration in seconds (default: 3)",
    )
    preview.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Preview frame rate (default: 30)",
    )
    preview.add_argument(
        "--width",
        type=int,
        default=1920,
    )
    preview.add_argument(
        "--height",
        type=int,
        default=960,
    )
    preview.add_argument(
        "-o",
        "--output",
        default="results/panorama_preview.mp4",
    )
    preview.add_argument(
        "--no-level-horizon",
        action="store_true",
        help="Disable DJI IMU horizon leveling",
    )
    preview.add_argument(
        "--level-strength",
        type=float,
        default=1.0,
        help="Horizon correction strength in [0,1] (default: 1)",
    )
    preview.add_argument(
        "--level-smoothing-ms",
        type=float,
        default=100.0,
        help=(
            "Centered zero-phase horizon smoothing sigma in milliseconds "
            "(default: 100; use 0 to disable)"
        ),
    )
    preview.add_argument(
        "--imu-source",
        choices=("highrate", "perframe"),
        default="highrate",
        help="DJI orientation stream (default: highrate)",
    )
    preview.add_argument(
        "--imu-offset-ms",
        type=float,
        default=0.0,
        help=(
            "Timing offset added to video exposure time before IMU lookup "
            "(default: 0)"
        ),
    )
    preview.add_argument(
        "--no-actual-video-pts",
        action="store_true",
        help="Use synthetic preview times instead of actual source-frame PTS",
    )
    preview.add_argument(
        "--no-audio",
        action="store_true",
        help="Do not include source audio",
    )
    preview.add_argument(
        "--crf",
        type=int,
        default=20,
        help="H.264 CRF for the prototype preview (default: 20)",
    )
    preview.add_argument(
        "--preset",
        default="veryfast",
        help="libx264 preset (default: veryfast)",
    )
    preview.set_defaults(func=_cmd_preview)

    imu_sweep = sub.add_parser(
        "imu-sweep",
        help="Render a diagnostic sweep of IMU/video timing offsets",
    )
    imu_sweep.add_argument("source")
    imu_sweep.add_argument(
        "--offsets",
        default="-40,-20,0,20,40",
        help="Comma-separated offsets in milliseconds",
    )
    imu_sweep.add_argument("--start", type=float, default=0.0)
    imu_sweep.add_argument("--duration", type=float, default=3.0)
    imu_sweep.add_argument("--fps", type=float, default=15.0)
    imu_sweep.add_argument("--width", type=int, default=1280)
    imu_sweep.add_argument("--height", type=int, default=640)
    imu_sweep.add_argument(
        "--level-smoothing-ms",
        type=float,
        default=100.0,
    )
    imu_sweep.add_argument(
        "--imu-source",
        choices=("highrate", "perframe"),
        default="highrate",
    )
    imu_sweep.add_argument(
        "--with-audio",
        action="store_true",
    )
    imu_sweep.add_argument(
        "-o",
        "--output-dir",
        default="results/imu_sweep",
    )
    imu_sweep.set_defaults(func=_cmd_imu_sweep)

    calibration = sub.add_parser(
        "extract-calibration",
        help="Debug operation: extract DJI factory calibration from an OSV",
    )
    calibration.add_argument("source")
    calibration.add_argument("-o", "--output")
    calibration.set_defaults(func=_cmd_calibration)

    stitch_lenses = sub.add_parser(
        "stitch-lenses",
        help="Debug operation: stitch two extracted lens images",
    )
    stitch_lenses.add_argument("lens0")
    stitch_lenses.add_argument("lens1")
    stitch_lenses.add_argument("--calibration", required=True)
    stitch_lenses.add_argument("-o", "--output", default="results/panorama.jpg")
    stitch_lenses.add_argument("--width", type=int, default=1920)
    stitch_lenses.add_argument("--height", type=int, default=960)
    stitch_lenses.set_defaults(func=_cmd_stitch_lenses)

    return parser


def main():
    args = build_parser().parse_args()

    try:
        if hasattr(args, "level_strength"):
            if not 0.0 <= args.level_strength <= 1.0:
                raise ValueError("--level-strength must be between 0 and 1")

        if hasattr(args, "level_smoothing_ms"):
            if args.level_smoothing_ms < 0.0:
                raise ValueError("--level-smoothing-ms must be >= 0")

        args.func(args)

    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"Error: {exc}") from exc


if __name__ == "__main__":
    main()
