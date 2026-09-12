"""Shared SDR delivery encoding for rendered BGR frames."""

SDR_VIDEO_PROPERTIES = {
    "pix_fmt": "yuv420p",
    "color_range": "tv",
    "color_space": "bt709",
    "color_transfer": "bt709",
    "color_primaries": "bt709",
}


def video_encoder_command(output, *, width, height, fps, crf, preset):
    # BGR frames are full-range, gamma-encoded SDR. Color tags alone do not
    # select swscale's RGB -> YCbCr matrix. Set the conversion and the filtered
    # frame properties explicitly, including after optional stabilization.
    # This is not a tone mapper or a D-Log/HDR-to-SDR transform.
    return [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s:v", f"{int(width)}x{int(height)}",
        "-r", f"{float(fps):.9f}", "-i", "pipe:0",
        "-map", "0:v:0",
        "-vf", (
            "scale=in_range=pc:out_range=tv:out_color_matrix=bt709,"
            "format=yuv420p,"
            "setparams=range=limited:color_primaries=bt709:"
            "color_trc=bt709:colorspace=bt709"
        ),
        "-c:v", "libx264", "-preset", str(preset), "-crf", str(int(crf)),
        "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-color_range", "tv", "-color_primaries", "bt709",
        "-color_trc", "bt709", "-colorspace", "bt709",
        "-an", "-movflags", "+faststart", str(output),
    ]
