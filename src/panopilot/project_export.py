"""
Final sequential conventional-video export for PanoPilot.

Authoritative path:

    original OSV lens streams
        ↓
    DJI factory-calibrated panoramic reconstruction
        ↓
    DJI IMU horizon correction
        ↓
    Clip View Path + Project Camera Motion
        ↓
    conventional Output Profile frame
        ↓
    one continuous H.264 project video stream

Project audio is assembled separately from each original source trim, with
silence inserted only for Clips that have no audio when at least one Project
Clip does have audio. Video and audio are then muxed atomically into MP4.

The disposable panoramic preview cache is never an export image source.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import glob
import shutil
import subprocess
import tempfile
import time

import cv2
import numpy as np

from .attitude import (
    gravity_equirectangular,
    horizon_correction_from_gravity,
    smooth_unit_vectors_centered,
)
from .dji import (
    extract_calibration,
    extract_orientation_data,
    orientation_from_samples,
)
from .factory import FactoryCalibratedMapper
from .direct_render import DirectLensRenderer, DirectMapPrefetcher
from .output_profile import output_profile_for_project
from .performance import (
    StageProfiler,
    dominant_stage,
)
from .projection_prefetch import (
    ProjectionMapPrefetcher,
)
from .project import load_project
from .source import (
    audio_streams,
    lens_streams,
    preview_exposure_times,
    probe_source,
    source_frame_times,
)
from .timeline import (
    build_project_timeline,
    timeline_time_to_source,
)
from .virtual_camera import RectilinearProjector
from .view_path import evaluate_clip_view_path


EXPORT_AV_SYNC_TOLERANCE_S = 0.050
DEFAULT_FINAL_PANORAMA_WIDTH = 3840
DEFAULT_FINAL_PANORAMA_HEIGHT = 1920


@dataclass(frozen=True)
class ExportFrameGroup:
    clip_id: str
    clip_index: int
    source: str
    first_frame_index: int
    frame_count: int
    project_time_start: float
    source_time_start: float

    @property
    def frame_end_exclusive(self):
        return self.first_frame_index + self.frame_count

    def to_dict(self):
        return {
            "clip_id": self.clip_id,
            "clip_index": int(self.clip_index),
            "source": self.source,
            "first_frame_index": int(self.first_frame_index),
            "frame_count": int(self.frame_count),
            "frame_end_exclusive": int(
                self.frame_end_exclusive
            ),
            "project_time_start": float(
                self.project_time_start
            ),
            "source_time_start": float(
                self.source_time_start
            ),
        }



@dataclass(frozen=True)
class DecoderSelection:
    requested: str
    backend: str
    vaapi_device: str | None
    smoke_tested: bool
    fallback: bool
    reason: str

    def to_dict(self):
        return {
            "requested": self.requested,
            "backend": self.backend,
            "vaapi_device": self.vaapi_device,
            "smoke_tested": bool(
                self.smoke_tested
            ),
            "fallback": bool(
                self.fallback
            ),
            "reason": self.reason,
        }


def _candidate_vaapi_devices(
    preferred=None,
):
    if preferred:
        return [
            str(
                Path(
                    preferred
                )
            )
        ]

    return sorted(
        str(
            Path(path)
        )
        for path in glob.glob(
            "/dev/dri/renderD*"
        )
    )


def _decoder_hwaccel_args(
    backend,
    vaapi_device=None,
):
    backend = str(
        backend
    )

    if backend == "software":
        return []

    if backend == "vaapi":
        if not vaapi_device:
            raise ValueError(
                "VAAPI decoder requires a device path"
            )

        return [
            "-hwaccel",
            "vaapi",
            "-hwaccel_device",
            str(
                vaapi_device
            ),
        ]

    raise ValueError(
        "decoder backend must be 'software' or 'vaapi'"
    )


def _emit(progress_callback, stage, message, **extra):
    if progress_callback is None:
        return

    progress_callback(
        {
            "stage": str(stage),
            "message": str(message),
            **extra,
        }
    )


def _read_exact(pipe, byte_count):
    chunks = []
    remaining = int(byte_count)

    while remaining > 0:
        chunk = pipe.read(remaining)

        if not chunk:
            return None

        chunks.append(chunk)
        remaining -= len(chunk)

    return b"".join(chunks)


def _lens_decoder_command(
    source,
    stream0,
    stream1,
    source_width,
    source_height,
    *,
    fps,
    start,
    frame_count,
    decoder_backend="software",
    vaapi_device=None,
):
    # Final CFR allocation can legitimately request the nearest output frame
    # at a source EOF boundary. FFmpeg's fps filter may otherwise stop one
    # frame short depending on source duration/time-base rounding. Clone only
    # a very small tail (two output frames) so CFR quantization is robust while
    # still exposing larger/truncated decode failures.
    tail_pad_seconds = (
        2.0
        / max(
            1.0,
            float(fps),
        )
    )

    filter_graph = (
        f"[0:{int(stream0)}]"
        f"fps={float(fps):.9f},"
        f"tpad=stop_mode=clone:stop_duration={tail_pad_seconds:.9f},"
        "format=bgr24[l0];"
        f"[0:{int(stream1)}]"
        f"fps={float(fps):.9f},"
        f"tpad=stop_mode=clone:stop_duration={tail_pad_seconds:.9f},"
        "format=bgr24[l1];"
        "[l0][l1]hstack=inputs=2[out]"
    )

    return [
        "ffmpeg",
        "-v", "error",
        *_decoder_hwaccel_args(
            decoder_backend,
            vaapi_device,
        ),
        "-ss", f"{float(start):.9f}",
        "-i", str(source),
        "-filter_complex", filter_graph,
        "-map", "[out]",
        "-frames:v", str(int(frame_count)),
        "-pix_fmt", "bgr24",
        "-f", "rawvideo",
        "pipe:1",
    ]



def _smoke_test_lens_decoder(
    source,
    stream0,
    stream1,
    source_width,
    source_height,
    *,
    fps,
    start,
    backend,
    vaapi_device=None,
    timeout_s=20.0,
):
    """
    Execute the exact dual-lens-to-BGR path for one frame.

    Hardware acceleration is accepted only if the real source, device,
    dual-stream decode, software-frame transfer/filtering, BGR conversion,
    and hstack all execute successfully.
    """
    cmd = _lens_decoder_command(
        source,
        stream0,
        stream1,
        source_width,
        source_height,
        fps=fps,
        start=start,
        frame_count=1,
        decoder_backend=backend,
        vaapi_device=vaapi_device,
    )

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=float(
                timeout_s
            ),
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "ffmpeg was not found. Install a full FFmpeg build first."
        ) from exc
    except subprocess.TimeoutExpired:
        return (
            False,
            "smoke test timed out",
        )

    if result.returncode == 0:
        return (
            True,
            "exact lens decode smoke test passed",
        )

    stderr = (
        result.stderr.decode(
            "utf-8",
            "replace",
        )
        if result.stderr
        else ""
    ).strip()

    if len(stderr) > 500:
        stderr = (
            stderr[:500]
            + "…"
        )

    return (
        False,
        stderr
        or (
            "ffmpeg lens decode smoke test failed "
            f"with exit code {result.returncode}"
        ),
    )


def _select_decoder_backend(
    source,
    stream0,
    stream1,
    source_width,
    source_height,
    *,
    fps,
    start,
    requested="auto",
    preferred_vaapi_device=None,
):
    requested = str(
        requested
    ).lower()

    if requested not in (
        "auto",
        "software",
        "vaapi",
    ):
        raise ValueError(
            "decoder must be 'auto', 'software', or 'vaapi'"
        )

    if requested == "software":
        return DecoderSelection(
            requested="software",
            backend="software",
            vaapi_device=None,
            smoke_tested=False,
            fallback=False,
            reason="software decoder explicitly requested",
        )

    candidates = _candidate_vaapi_devices(
        preferred_vaapi_device
    )

    if not candidates:
        if requested == "vaapi":
            raise RuntimeError(
                "VAAPI decoding was requested but no render device is "
                "available. Use --vaapi-device to specify one."
            )

        return DecoderSelection(
            requested="auto",
            backend="software",
            vaapi_device=None,
            smoke_tested=False,
            fallback=True,
            reason="no VAAPI render device available",
        )

    failures = []

    for device in candidates:
        ok, reason = _smoke_test_lens_decoder(
            source,
            stream0,
            stream1,
            source_width,
            source_height,
            fps=fps,
            start=start,
            backend="vaapi",
            vaapi_device=device,
        )

        if ok:
            return DecoderSelection(
                requested=requested,
                backend="vaapi",
                vaapi_device=device,
                smoke_tested=True,
                fallback=False,
                reason=reason,
            )

        failures.append(
            f"{device}: {reason}"
        )

    failure_text = "; ".join(
        failures
    )

    if requested == "vaapi":
        raise RuntimeError(
            "VAAPI decoding was requested but the exact runtime "
            "lens-decode smoke test failed. "
            + failure_text
        )

    return DecoderSelection(
        requested="auto",
        backend="software",
        vaapi_device=None,
        smoke_tested=True,
        fallback=True,
        reason=(
            "VAAPI runtime smoke test failed; using software decode. "
            + failure_text
        ),
    )


def _video_encoder_command(
    output,
    *,
    width,
    height,
    fps,
    crf,
    preset,
):
    return [
        "ffmpeg",
        "-y",
        "-v", "error",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s:v", f"{int(width)}x{int(height)}",
        "-r", f"{float(fps):.9f}",
        "-i", "pipe:0",
        "-map", "0:v:0",
        "-c:v", "libx264",
        "-preset", str(preset),
        "-crf", str(int(crf)),
        "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart",
        str(output),
    ]


def build_export_frame_groups(
    project,
    spans,
    *,
    fps,
):
    """
    Allocate one Project-wide CFR sequence using rounded cumulative Clip
    boundaries.

    A Clip boundary at time ``T`` maps to ``round(T * fps)``. Using cumulative
    boundary rounding rather than classifying every frame-start timestamp
    avoids an asymmetric ``ceil`` effect where a 6.016 s Clip at 30 fps would
    incorrectly receive 181 frames even though the nearest CFR boundary is
    frame 180.

    This preserves the one-global-clock invariant and minimizes every Clip
    boundary error to approximately half an output frame.
    """
    spans = list(spans)

    if not spans:
        return [], 0

    fps = float(fps)

    if fps <= 0.0:
        raise ValueError(
            "fps must be greater than zero"
        )

    project_duration = float(
        spans[-1].timeline_end
    )
    total_frames = max(
        1,
        int(
            round(
                project_duration * fps
            )
        ),
    )

    groups = []
    previous_end_frame = 0

    for span_index, span in enumerate(
        spans
    ):
        is_last = (
            span_index
            == len(spans) - 1
        )

        end_frame = (
            total_frames
            if is_last
            else int(
                round(
                    float(
                        span.timeline_end
                    )
                    * fps
                )
            )
        )
        end_frame = max(
            previous_end_frame,
            min(
                total_frames,
                end_frame,
            ),
        )
        frame_count = (
            end_frame
            - previous_end_frame
        )

        if frame_count <= 0:
            # A positive Clip shorter than half an output-frame interval can be
            # unrepresentable at the fixed Output Profile frame rate. Do not
            # manufacture duration by stealing frames from neighboring Clips.
            previous_end_frame = (
                end_frame
            )
            continue

        clip_index = project.clip_index(
            span.clip_id
        )

        if clip_index is None:
            raise RuntimeError(
                f"Timeline references missing Clip {span.clip_id}"
            )

        project_time_start = (
            float(
                previous_end_frame
            )
            / fps
        )

        # CFR boundary rounding can place the first Project frame a fraction of
        # one frame before or after the exact mathematical Clip boundary. Map
        # that quantized frame into the Clip, clamped to the active source
        # range.
        source_offset = max(
            0.0,
            project_time_start
            - float(
                span.timeline_start
            ),
        )
        source_time_start = min(
            float(
                span.source_out
            ),
            float(
                span.source_in
            )
            + source_offset,
        )

        groups.append(
            ExportFrameGroup(
                clip_id=span.clip_id,
                clip_index=int(
                    clip_index
                ),
                source=span.source,
                first_frame_index=int(
                    previous_end_frame
                ),
                frame_count=int(
                    frame_count
                ),
                project_time_start=float(
                    project_time_start
                ),
                source_time_start=float(
                    source_time_start
                ),
            )
        )

        previous_end_frame = (
            end_frame
        )

    if sum(
        group.frame_count
        for group in groups
    ) != total_frames:
        raise RuntimeError(
            "Internal CFR frame allocation does not cover the complete Project"
        )

    return groups, total_frames


def _orientation_gravity_for_times(
    source,
    exposure_times,
    *,
    fps,
    level_smoothing_ms,
    imu_source,
    imu_offset_ms,
):
    data = extract_orientation_data(
        source
    )

    if (
        imu_source == "highrate"
        and data["highrate"]
    ):
        samples = data["highrate"]
    elif imu_source in (
        "highrate",
        "perframe",
    ):
        samples = data["perframe"]
    else:
        raise ValueError(
            "imu_source must be 'highrate' or 'perframe'"
        )

    raw = []

    for source_time in exposure_times:
        orientation = orientation_from_samples(
            samples,
            float(source_time)
            + float(imu_offset_ms)
            / 1000.0,
        )
        raw.append(
            gravity_equirectangular(
                orientation["quat"]
            )
        )

    raw = np.asarray(
        raw,
        dtype=np.float64,
    )

    sigma_frames = (
        max(
            0.0,
            float(level_smoothing_ms),
        )
        / 1000.0
        * float(fps)
    )

    return smooth_unit_vectors_centered(
        raw,
        sigma_frames,
    )


def _source_duration_from_probe(probe, source):
    value = probe.get(
        "format",
        {},
    ).get("duration")

    if value is None:
        raise RuntimeError(
            f"Could not determine source duration: {source}"
        )

    duration = float(value)

    if duration <= 0.0:
        raise RuntimeError(
            f"Source duration must be positive: {source}"
        )

    return duration


def _render_video_stream(
    project,
    spans,
    groups,
    probes,
    output,
    *,
    profile,
    panorama_width,
    panorama_height,
    level_horizon,
    level_strength,
    level_smoothing_ms,
    imu_source,
    imu_offset_ms,
    crf,
    preset,
    decoder_mode,
    vaapi_device,
    projection_prefetch,
    render_pipeline,
    progress_callback,
):
    encoder = subprocess.Popen(
        _video_encoder_command(
            output,
            width=profile.width,
            height=profile.height,
            fps=profile.fps,
            crf=crf,
            preset=preset,
        ),
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=16 * 1024 * 1024,
    )

    projector = RectilinearProjector(
        int(panorama_width),
        int(panorama_height),
        int(profile.width),
        int(profile.height),
    )
    render_pipeline = str(render_pipeline).lower()
    if render_pipeline not in ("panorama", "direct"):
        raise ValueError("render_pipeline must be 'panorama' or 'direct'")

    video_profiler = StageProfiler()
    projection_profiler = StageProfiler()
    direct_profiler = StageProfiler()

    rendered_frames = 0
    total_frames = sum(
        group.frame_count
        for group in groups
    )
    started = time.perf_counter()
    clip_summaries = []

    def projection_state(
        clip,
        local_index,
        exposure_times,
        leveled_gravity,
    ):
        content_rotation = None

        if level_horizon:
            with video_profiler.measure(
                "horizon_rotation_math"
            ):
                (
                    content_rotation,
                    _diagnostics,
                ) = (
                    horizon_correction_from_gravity(
                        leveled_gravity[
                            local_index
                        ],
                        strength=(
                            level_strength
                        ),
                    )
                )

        source_time = float(
            exposure_times[
                local_index
            ]
        )

        with video_profiler.measure(
            "view_path_evaluation"
        ):
            sample = (
                evaluate_clip_view_path(
                    clip,
                    source_time,
                    interpolation=(
                        project.camera_motion_easing
                    ),
                    strength=(
                        project.camera_motion_strength
                    ),
                )
            )

        return (
            content_rotation,
            sample.camera,
        )

    try:
        for group_number, group in enumerate(
            groups,
            start=1,
        ):
            clip = project.clip_for_id(
                group.clip_id
            )

            if clip is None:
                raise RuntimeError(
                    f"Missing Clip {group.clip_id} during export"
                )

            source = Path(
                clip.source
            )

            if not source.is_file():
                raise FileNotFoundError(
                    f"Source does not exist: {source}"
                )

            probe = probes[
                clip.id
            ]
            lenses = lens_streams(
                probe
            )
            stream0 = int(
                lenses[0]["index"]
            )
            stream1 = int(
                lenses[1]["index"]
            )
            source_width = int(
                lenses[0]["width"]
            )
            source_height = int(
                lenses[0]["height"]
            )

            if (
                int(lenses[1]["width"])
                != source_width
                or int(lenses[1]["height"])
                != source_height
            ):
                raise RuntimeError(
                    "The two lens streams have different dimensions"
                )

            with video_profiler.measure(
                "decoder_backend_probe"
            ):
                decoder_selection = (
                    _select_decoder_backend(
                        source,
                        stream0,
                        stream1,
                        source_width,
                        source_height,
                        fps=profile.fps,
                        start=(
                            group.source_time_start
                        ),
                        requested=(
                            decoder_mode
                        ),
                        preferred_vaapi_device=(
                            vaapi_device
                        ),
                    )
                )

            decoder_label = (
                (
                    "VAAPI "
                    + str(
                        decoder_selection.vaapi_device
                    )
                )
                if (
                    decoder_selection.backend
                    == "vaapi"
                )
                else "software"
            )

            _emit(
                progress_callback,
                "decoder",
                (
                    f"Decoder Clip {group_number}/{len(groups)} — "
                    f"{decoder_label}"
                ),
                clip_id=clip.id,
                decoder=(
                    decoder_selection.to_dict()
                ),
            )

            _emit(
                progress_callback,
                "render-clip",
                (
                    f"Rendering Clip {group_number}/{len(groups)} — "
                    f"{source.name}"
                ),
                clip_id=clip.id,
                clip_index=group.clip_index,
                frame_count=group.frame_count,
            )

            with video_profiler.measure(
                "clip_setup_calibration_maps"
            ):
                calibration = extract_calibration(
                    source
                )
                mapper = FactoryCalibratedMapper(
                    calibration,
                    source_width,
                    source_height,
                    out_w=int(
                        panorama_width
                    ),
                    out_h=int(
                        panorama_height
                    ),
                )
                direct_renderer = (
                    DirectLensRenderer(mapper)
                    if render_pipeline == "direct"
                    else None
                )

            decode_duration = (
                float(group.frame_count)
                / float(profile.fps)
            )
            with video_profiler.measure(
                "clip_setup_source_pts"
            ):
                (
                    source_pts,
                    source_pts_diagnostics,
                ) = source_frame_times(
                    source,
                    stream0,
                    group.source_time_start,
                    decode_duration,
                    probe=probe,
                    return_diagnostics=True,
                )
                exposure_times, pts_diagnostics = (
                    preview_exposure_times(
                        source_pts,
                        start=(
                            group.source_time_start
                        ),
                        duration=decode_duration,
                        output_fps=profile.fps,
                    )
                )
                pts_diagnostics = {
                    **source_pts_diagnostics,
                    **pts_diagnostics,
                }

            if (
                len(exposure_times)
                != group.frame_count
            ):
                raise RuntimeError(
                    "Internal export exposure-time count mismatch"
                )

            leveled_gravity = None

            if level_horizon:
                with video_profiler.measure(
                    "clip_setup_imu"
                ):
                    leveled_gravity = (
                        _orientation_gravity_for_times(
                            source,
                            exposure_times,
                            fps=profile.fps,
                            level_smoothing_ms=(
                                level_smoothing_ms
                            ),
                            imu_source=imu_source,
                            imu_offset_ms=(
                                imu_offset_ms
                            ),
                        )
                    )

            with video_profiler.measure(
                "decoder_startup"
            ):
                decoder_process = subprocess.Popen(
                    _lens_decoder_command(
                        source,
                        stream0,
                        stream1,
                        source_width,
                        source_height,
                        fps=profile.fps,
                        start=(
                            group.source_time_start
                        ),
                        frame_count=(
                            group.frame_count
                        ),
                        decoder_backend=(
                            decoder_selection.backend
                        ),
                        vaapi_device=(
                            decoder_selection.vaapi_device
                        ),
                    ),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=(
                        16 * 1024 * 1024
                    ),
                )

            stacked_width = (
                source_width * 2
            )
            frame_bytes = (
                stacked_width
                * source_height
                * 3
            )
            clip_frames = 0

            if render_pipeline == "panorama":
                with ProjectionMapPrefetcher(
                    projector,
                    enabled=(projection_prefetch),
                ) as map_prefetcher:
                    first_rotation, first_camera = projection_state(
                        clip, 0, exposure_times, leveled_gravity
                    )
                    map_prefetcher.submit(first_camera, first_rotation)
                    try:
                        for local_index in range(group.frame_count):
                            with video_profiler.measure("decoder_read_wait"):
                                raw = _read_exact(decoder_process.stdout, frame_bytes)
                            if raw is None:
                                raise RuntimeError(
                                    "FFmpeg lens decoder ended before the expected frame count "
                                    f"for {clip.id}: {local_index}/{group.frame_count}"
                                )
                            stacked=np.frombuffer(raw,dtype=np.uint8).reshape(
                                source_height, stacked_width, 3
                            )
                            lens0=stacked[:,:source_width]
                            lens1=stacked[:,source_width:]

                            with video_profiler.measure("factory_stitch"):
                                panorama=mapper.stitch(lens0,lens1)

                            with video_profiler.measure("projection_map_wait"):
                                map_result=map_prefetcher.result()
                            projection_profiler.add(
                                "map_generation_worker", map_result.worker_seconds, calls=1
                            )

                            next_index=local_index+1
                            if next_index < group.frame_count:
                                next_rotation,next_camera=projection_state(
                                    clip,next_index,exposure_times,leveled_gravity
                                )
                                map_prefetcher.submit(next_camera,next_rotation)

                            with video_profiler.measure("composed_projection"):
                                with projection_profiler.measure("panorama_remap"):
                                    frame=cv2.remap(
                                        panorama,map_result.map_x,map_result.map_y,
                                        interpolation=cv2.INTER_LINEAR,
                                        borderMode=cv2.BORDER_REPLICATE,
                                    )
                            try:
                                with video_profiler.measure("encoder_write_wait"):
                                    encoder.stdin.write(frame.tobytes())
                            except BrokenPipeError as exc:
                                raise RuntimeError(
                                    "Final H.264 encoder stopped unexpectedly"
                                ) from exc

                            clip_frames += 1
                            rendered_frames += 1
                            source_time=float(exposure_times[local_index])
                            if (rendered_frames == 1 or rendered_frames == total_frames
                                    or rendered_frames % 15 == 0):
                                percent=100.0*rendered_frames/max(1,total_frames)
                                _emit(
                                    progress_callback,"render-frame",
                                    f"Rendering final video — {rendered_frames}/{total_frames} "
                                    f"frames ({percent:.1f}%)",
                                    frame=rendered_frames,total_frames=total_frames,
                                    percent=percent,clip_id=clip.id,source_time=source_time,
                                )
                    finally:
                        if decoder_process.stdout:
                            decoder_process.stdout.close()
                        with video_profiler.measure("decoder_finalize"):
                            decoder_stderr=(
                                decoder_process.stderr.read().decode("utf-8","replace")
                                if decoder_process.stderr else ""
                            )
                            decoder_process.wait()
            else:
                with DirectMapPrefetcher(
                    projector,
                    direct_renderer,
                    enabled=(projection_prefetch),
                ) as direct_prefetcher:
                    first_rotation, first_camera = projection_state(
                        clip, 0, exposure_times, leveled_gravity
                    )
                    direct_prefetcher.submit(first_camera, first_rotation)
                    try:
                        for local_index in range(group.frame_count):
                            with video_profiler.measure("decoder_read_wait"):
                                raw=_read_exact(decoder_process.stdout,frame_bytes)
                            if raw is None:
                                raise RuntimeError(
                                    "FFmpeg lens decoder ended before the expected frame count "
                                    f"for {clip.id}: {local_index}/{group.frame_count}"
                                )
                            stacked=np.frombuffer(raw,dtype=np.uint8).reshape(
                                source_height,stacked_width,3
                            )
                            lens0=stacked[:,:source_width]
                            lens1=stacked[:,source_width:]

                            with video_profiler.measure("direct_map_wait"):
                                direct_result=direct_prefetcher.result()
                            direct_profiler.add(
                                "projection_map_worker",direct_result.projection_seconds,calls=1
                            )
                            direct_profiler.add(
                                "factory_map_compose_worker",direct_result.composition_seconds,calls=1
                            )

                            next_index=local_index+1
                            if next_index < group.frame_count:
                                next_rotation,next_camera=projection_state(
                                    clip,next_index,exposure_times,leveled_gravity
                                )
                                direct_prefetcher.submit(next_camera,next_rotation)

                            with video_profiler.measure("direct_lens_render"):
                                with direct_profiler.measure("lens_remap_blend"):
                                    frame=direct_renderer.render(
                                        lens0,lens1,direct_result.maps
                                    )
                            try:
                                with video_profiler.measure("encoder_write_wait"):
                                    encoder.stdin.write(frame.tobytes())
                            except BrokenPipeError as exc:
                                raise RuntimeError(
                                    "Final H.264 encoder stopped unexpectedly"
                                ) from exc

                            clip_frames += 1
                            rendered_frames += 1
                            source_time=float(exposure_times[local_index])
                            if (rendered_frames == 1 or rendered_frames == total_frames
                                    or rendered_frames % 15 == 0):
                                percent=100.0*rendered_frames/max(1,total_frames)
                                _emit(
                                    progress_callback,"render-frame",
                                    f"Rendering final video — {rendered_frames}/{total_frames} "
                                    f"frames ({percent:.1f}%)",
                                    frame=rendered_frames,total_frames=total_frames,
                                    percent=percent,clip_id=clip.id,source_time=source_time,
                                )
                    finally:
                        if decoder_process.stdout:
                            decoder_process.stdout.close()
                        with video_profiler.measure("decoder_finalize"):
                            decoder_stderr=(
                                decoder_process.stderr.read().decode("utf-8","replace")
                                if decoder_process.stderr else ""
                            )
                            decoder_process.wait()

            if decoder_process.returncode != 0:
                raise RuntimeError(
                    "FFmpeg lens decode failed:\n"
                    + decoder_stderr
                )

            if clip_frames != group.frame_count:
                raise RuntimeError(
                    f"Rendered {clip_frames} frames for {clip.id}; "
                    f"expected {group.frame_count}"
                )

            clip_summaries.append(
                {
                    **group.to_dict(),
                    "frames_rendered": int(
                        clip_frames
                    ),
                    "decoder": (
                        decoder_selection.to_dict()
                    ),
                    "source_pts": (
                        pts_diagnostics
                    ),
                    "factory_mapping": (
                        mapper.diagnostics.__dict__
                    ),
                }
            )

    finally:
        if encoder.stdin:
            try:
                encoder.stdin.close()
            except BrokenPipeError:
                pass

        with video_profiler.measure(
            "encoder_finalize"
        ):
            encoder_stderr = (
                encoder.stderr.read().decode(
                    "utf-8",
                    "replace",
                )
                if encoder.stderr
                else ""
            )
            encoder.wait()

    if encoder.returncode != 0:
        raise RuntimeError(
            "FFmpeg final video encode failed:\n"
            + encoder_stderr
        )

    if rendered_frames != total_frames:
        raise RuntimeError(
            f"Final video rendered {rendered_frames} frames; "
            f"expected {total_frames}"
        )

    elapsed = (
        time.perf_counter()
        - started
    )

    stage_timings = video_profiler.summary(
        total_seconds=elapsed,
    )
    dominant = dominant_stage(
        stage_timings
    )

    decoder_counts = {}

    for clip_summary in clip_summaries:
        backend = (
            clip_summary.get(
                "decoder",
                {},
            ).get(
                "backend",
                "unknown",
            )
        )
        decoder_counts[backend] = (
            decoder_counts.get(
                backend,
                0,
            )
            + 1
        )

    return {
        "decoder_policy": {
            "requested": str(
                decoder_mode
            ),
            "preferred_vaapi_device": (
                str(
                    vaapi_device
                )
                if vaapi_device
                else None
            ),
            "clip_backend_counts": (
                decoder_counts
            ),
        },
        "render_pipeline": str(render_pipeline),
        "projection_pipeline": (
            "factory-panorama -> composed-horizon-camera -> rectilinear"
            if render_pipeline == "panorama"
            else (
                "dynamic-camera-map -> composed-factory-lens-maps "
                "-> direct-dual-lens-remap-blend"
            )
        ),
        "full_panorama_constructed_per_frame": (
            render_pipeline == "panorama"
        ),
        "post_stitch_resamples_per_frame": (
            1 if render_pipeline == "panorama" else 0
        ),
        "projection_kernel": (
            "float32-analytic-composed-map"
        ),
        "projection_prefetch": {
            "enabled": bool(
                projection_prefetch
            ),
            "depth_frames": (
                1
                if projection_prefetch
                else 0
            ),
            "worker_count": (
                1
                if projection_prefetch
                else 0
            ),
        },
        "projection_breakdown": (
            projection_profiler.summary(total_seconds=elapsed)
        ),
        "direct_render_breakdown": (
            direct_profiler.summary(total_seconds=elapsed)
        ),
        "stage_timings": stage_timings,
        "dominant_stage": dominant,
        "measured_stage_seconds": float(
            video_profiler.total_measured_seconds()
        ),
        "frames": int(
            rendered_frames
        ),
        "processing_seconds": float(
            elapsed
        ),
        "processing_fps": (
            float(rendered_frames / elapsed)
            if elapsed > 0.0
            else 0.0
        ),
        "clips": clip_summaries,
    }


def _build_project_audio(
    project,
    spans,
    probes,
    output,
    *,
    target_duration,
    progress_callback,
):
    has_audio_by_clip = {
        clip.id: bool(
            audio_streams(
                probes[clip.id]
            )
        )
        for clip in project.clips
    }
    any_audio = any(
        has_audio_by_clip.values()
    )

    if not any_audio:
        return {
            "included": False,
            "source_audio_clips": 0,
            "silent_clips": len(
                project.clips
            ),
        }

    _emit(
        progress_callback,
        "audio",
        "Assembling Project audio from original source trims",
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-v", "error",
    ]
    filter_parts = []
    source_audio_count = 0
    silent_count = 0

    for input_index, span in enumerate(
        spans
    ):
        duration = float(
            span.duration
        )

        if has_audio_by_clip[
            span.clip_id
        ]:
            source_audio_count += 1
            cmd += [
                "-ss",
                f"{float(span.source_in):.9f}",
                "-t",
                f"{duration:.9f}",
                "-i",
                str(span.source),
            ]
        else:
            silent_count += 1
            cmd += [
                "-f", "lavfi",
                "-t", f"{duration:.9f}",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
            ]

        filter_parts.append(
            f"[{input_index}:a:0]"
            "aresample=48000:async=1:first_pts=0,"
            "aformat=sample_fmts=fltp:sample_rates=48000:"
            "channel_layouts=stereo,"
            "asetpts=PTS-STARTPTS"
            f"[a{input_index}]"
        )

    concat_inputs = "".join(
        f"[a{index}]"
        for index in range(
            len(spans)
        )
    )
    filter_parts.append(
        concat_inputs
        + f"concat=n={len(spans)}:v=0:a=1,"
        + "apad,"
        + f"atrim=duration={float(target_duration):.9f}"
        + "[aout]"
    )

    cmd += [
        "-filter_complex",
        ";".join(filter_parts),
        "-map", "[aout]",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        str(output),
    ]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "ffmpeg was not found. Install a full FFmpeg build first."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "FFmpeg Project audio assembly failed:\n"
            + exc.stderr
        ) from exc

    return {
        "included": True,
        "source_audio_clips": int(
            source_audio_count
        ),
        "silent_clips": int(
            silent_count
        ),
        "target_duration": float(
            target_duration
        ),
        "ffmpeg_stderr": result.stderr,
    }


def _mux_final(video, audio, output):
    cmd = [
        "ffmpeg",
        "-y",
        "-v", "error",
        "-i", str(video),
    ]

    if audio is not None:
        cmd += [
            "-i", str(audio),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c", "copy",
            "-shortest",
        ]
    else:
        cmd += [
            "-map", "0:v:0",
            "-c", "copy",
            "-an",
        ]

    cmd += [
        "-movflags", "+faststart",
        str(output),
    ]

    try:
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "FFmpeg final MP4 mux failed:\n"
            + exc.stderr
        ) from exc


def _stream_duration(stream):
    value = stream.get("duration")

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def verify_project_export(
    output,
    *,
    profile,
    expected_frames,
    expected_duration,
    expect_audio,
):
    probe = probe_source(
        output
    )
    video = [
        stream
        for stream in probe.get(
            "streams",
            [],
        )
        if stream.get("codec_type")
        == "video"
        and not stream.get(
            "disposition",
            {},
        ).get("attached_pic")
    ]
    audio = audio_streams(
        probe
    )

    if len(video) != 1:
        raise RuntimeError(
            "Export verification expected exactly one video stream"
        )

    stream = video[0]

    if stream.get("codec_name") != "h264":
        raise RuntimeError(
            "Export verification expected H.264 video"
        )

    if (
        int(stream.get("width") or 0)
        != int(profile.width)
        or int(stream.get("height") or 0)
        != int(profile.height)
    ):
        raise RuntimeError(
            "Export verification output resolution mismatch"
        )

    if expect_audio and not audio:
        raise RuntimeError(
            "Export verification expected Project audio"
        )

    if not expect_audio and audio:
        raise RuntimeError(
            "Export verification found unexpected audio"
        )

    nb_frames = stream.get(
        "nb_frames"
    )

    if nb_frames not in (
        None,
        "N/A",
    ):
        try:
            if int(nb_frames) != int(
                expected_frames
            ):
                raise RuntimeError(
                    "Export verification frame-count mismatch: "
                    f"{nb_frames} != {expected_frames}"
                )
        except ValueError:
            pass

    format_duration = probe.get(
        "format",
        {},
    ).get("duration")
    actual_duration = (
        float(format_duration)
        if format_duration is not None
        else None
    )

    if actual_duration is not None:
        error = abs(
            actual_duration
            - float(expected_duration)
        )

        if error > max(
            EXPORT_AV_SYNC_TOLERANCE_S,
            1.5 / float(profile.fps),
        ):
            raise RuntimeError(
                "Export verification duration mismatch: "
                f"{actual_duration:.6f}s vs "
                f"{expected_duration:.6f}s"
            )

    av_delta = None

    if expect_audio and audio:
        video_duration = _stream_duration(
            stream
        )
        audio_duration = _stream_duration(
            audio[0]
        )

        if (
            video_duration is not None
            and audio_duration is not None
        ):
            av_delta = abs(
                video_duration
                - audio_duration
            )

            if av_delta > (
                EXPORT_AV_SYNC_TOLERANCE_S
            ):
                raise RuntimeError(
                    "Export A/V synchronization verification failed: "
                    f"stream duration delta {av_delta:.6f}s exceeds "
                    f"{EXPORT_AV_SYNC_TOLERANCE_S:.3f}s"
                )

    return {
        "codec": stream.get(
            "codec_name"
        ),
        "width": int(
            stream.get("width")
            or 0
        ),
        "height": int(
            stream.get("height")
            or 0
        ),
        "audio_stream_count": len(
            audio
        ),
        "format_duration": (
            actual_duration
        ),
        "av_stream_duration_delta_s": (
            av_delta
        ),
        "av_sync_tolerance_s": (
            EXPORT_AV_SYNC_TOLERANCE_S
        ),
    }


def export_project_video(
    project_path,
    output,
    *,
    panorama_width=DEFAULT_FINAL_PANORAMA_WIDTH,
    panorama_height=DEFAULT_FINAL_PANORAMA_HEIGHT,
    level_horizon=True,
    level_strength=1.0,
    level_smoothing_ms=100.0,
    imu_source="highrate",
    imu_offset_ms=0.0,
    crf=18,
    preset="medium",
    decoder="auto",
    vaapi_device=None,
    projection_prefetch=True,
    render_pipeline="panorama",
    progress_callback=None,
):
    project_path = Path(
        project_path
    )
    output = Path(
        output
    )

    if not project_path.is_file():
        raise FileNotFoundError(
            f"Project does not exist: {project_path}"
        )

    if output.suffix.lower() != ".mp4":
        raise ValueError(
            "Final Project export must use an .mp4 output path"
        )

    panorama_width = int(
        panorama_width
    )
    panorama_height = int(
        panorama_height
    )
    decoder = str(decoder).lower()
    render_pipeline = str(render_pipeline).lower()
    if render_pipeline not in ("panorama", "direct"):
        raise ValueError("render_pipeline must be 'panorama' or 'direct'")

    if decoder not in (
        "auto",
        "software",
        "vaapi",
    ):
        raise ValueError(
            "decoder must be 'auto', 'software', or 'vaapi'"
        )

    if (
        panorama_width <= 0
        or panorama_height <= 0
        or abs(
            panorama_width
            / panorama_height
            - 2.0
        ) > 0.01
    ):
        raise ValueError(
            "Final panoramic render dimensions must be positive and 2:1"
        )

    project = load_project(
        project_path
    )

    if not project.clips:
        raise ValueError(
            "Project has no Clips to export"
        )

    profile = output_profile_for_project(
        project
    )
    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    _emit(
        progress_callback,
        "inspect",
        "Inspecting original source recordings",
    )

    probes = {}
    source_durations = {}

    for index, clip in enumerate(
        project.clips,
        start=1,
    ):
        source = Path(
            clip.source
        )

        if not source.is_file():
            raise FileNotFoundError(
                f"Source does not exist: {source}"
            )

        probe = probe_source(
            source
        )
        probes[
            clip.id
        ] = probe
        source_durations[
            clip.id
        ] = (
            _source_duration_from_probe(
                probe,
                source,
            )
        )
        lens_streams(
            probe
        )

        _emit(
            progress_callback,
            "inspect",
            (
                f"Source {index}/{len(project.clips)} ready — "
                f"{source.name}"
            ),
            clip_id=clip.id,
        )

    spans = build_project_timeline(
        project,
        source_durations,
    )
    groups, total_frames = (
        build_export_frame_groups(
            project,
            spans,
            fps=profile.fps,
        )
    )
    video_duration = (
        float(total_frames)
        / float(profile.fps)
    )

    output_preparing = output.with_name(
        output.stem
        + ".preparing"
        + output.suffix
    )
    output_preparing.unlink(
        missing_ok=True
    )

    started = time.perf_counter()
    overall_profiler = StageProfiler()

    try:
        with tempfile.TemporaryDirectory(
            prefix="panopilot-export-",
            dir=str(
                output.parent
            ),
        ) as temp_dir_value:
            temp_dir = Path(
                temp_dir_value
            )
            video_only = (
                temp_dir
                / "project_video.mp4"
            )
            audio_only = (
                temp_dir
                / "project_audio.m4a"
            )

            with overall_profiler.measure(
                "video_render"
            ):
                video_summary = (
                    _render_video_stream(
                        project,
                        spans,
                        groups,
                        probes,
                        video_only,
                        profile=profile,
                        panorama_width=(
                            panorama_width
                        ),
                        panorama_height=(
                            panorama_height
                        ),
                        level_horizon=(
                            level_horizon
                        ),
                        level_strength=(
                            level_strength
                        ),
                        level_smoothing_ms=(
                            level_smoothing_ms
                        ),
                        imu_source=(
                            imu_source
                        ),
                        imu_offset_ms=(
                            imu_offset_ms
                        ),
                        crf=crf,
                        preset=preset,
                        decoder_mode=(
                            decoder
                        ),
                        vaapi_device=(
                            vaapi_device
                        ),
                        projection_prefetch=(
                            projection_prefetch
                        ),
                        render_pipeline=(
                            render_pipeline
                        ),
                        progress_callback=(
                            progress_callback
                        ),
                    )
                )

            with overall_profiler.measure(
                "audio_assembly"
            ):
                audio_summary = (
                    _build_project_audio(
                        project,
                        spans,
                        probes,
                        audio_only,
                        target_duration=(
                            video_duration
                        ),
                        progress_callback=(
                            progress_callback
                        ),
                    )
                )

            _emit(
                progress_callback,
                "mux",
                "Muxing final H.264 MP4",
            )

            with overall_profiler.measure(
                "final_mux"
            ):
                _mux_final(
                    video_only,
                    (
                        audio_only
                        if audio_summary[
                            "included"
                        ]
                        else None
                    ),
                    output_preparing,
                )

            _emit(
                progress_callback,
                "verify",
                "Verifying completed export",
            )

            with overall_profiler.measure(
                "final_verification"
            ):
                verification = (
                    verify_project_export(
                        output_preparing,
                        profile=profile,
                        expected_frames=(
                            total_frames
                        ),
                        expected_duration=(
                            video_duration
                        ),
                        expect_audio=(
                            audio_summary[
                                "included"
                            ]
                        ),
                    )
                )

        output_preparing.replace(
            output
        )

    except Exception:
        output_preparing.unlink(
            missing_ok=True
        )
        raise

    elapsed = (
        time.perf_counter()
        - started
    )

    overall_stage_timings = (
        overall_profiler.summary(
            total_seconds=elapsed,
        )
    )
    video_stage_timings = (
        video_summary.get(
            "stage_timings",
            {}
        )
    )
    dominant_video = (
        video_summary.get(
            "dominant_stage"
        )
    )

    performance = {
        "processing_seconds": float(
            elapsed
        ),
        "frames": int(
            total_frames
        ),
        "processing_fps": (
            float(
                total_frames
                / elapsed
            )
            if elapsed > 0.0
            else 0.0
        ),
        "real_time_factor": (
            float(
                elapsed
                / video_duration
            )
            if video_duration > 0.0
            else None
        ),
        "overall_stage_timings": (
            overall_stage_timings
        ),
        "video_stage_timings": (
            video_stage_timings
        ),
        "dominant_video_stage": (
            dominant_video
        ),
    }

    _emit(
        progress_callback,
        "completed",
        f"Project export complete — {output.name}",
        output=str(output),
    )

    return {
        "project": str(
            project_path
        ),
        "output": str(
            output
        ),
        "clip_count": len(
            project.clips
        ),
        "project_timeline_duration": float(
            spans[-1].timeline_end
        ),
        "encoded_duration": float(
            video_duration
        ),
        "output_profile": (
            profile.to_dict()
        ),
        "panorama_render": {
            "width": int(
                panorama_width
            ),
            "height": int(
                panorama_height
            ),
            "level_horizon": bool(
                level_horizon
            ),
            "level_strength": float(
                level_strength
            ),
            "level_smoothing_ms": float(
                level_smoothing_ms
            ),
            "imu_source": str(
                imu_source
            ),
            "imu_offset_ms": float(
                imu_offset_ms
            ),
        },
        "camera_motion": {
            "easing": (
                project.camera_motion_easing
            ),
            "strength": float(
                project.camera_motion_strength
            ),
        },
        "projection_prefetch": bool(projection_prefetch),
        "render_pipeline": str(render_pipeline),
        "decoder": {
            "requested": str(
                decoder
            ),
            "preferred_vaapi_device": (
                str(
                    vaapi_device
                )
                if vaapi_device
                else None
            ),
        },
        "encoder": {
            "codec": "libx264",
            "crf": int(
                crf
            ),
            "preset": str(
                preset
            ),
        },
        "frame_groups": [
            group.to_dict()
            for group in groups
        ],
        "video": video_summary,
        "audio": audio_summary,
        "verification": verification,
        "performance": performance,
        "processing_seconds": float(
            elapsed
        ),
    }
