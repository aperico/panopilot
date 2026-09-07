from pathlib import Path
import time
from threading import Event

from panopilot.jobs import (
    BackgroundJobManager,
    JobCancelled,
)


def _wait_terminal(manager, key, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = manager.snapshot(key)
        if snapshot is not None and snapshot.terminal:
            return snapshot
        time.sleep(0.005)
    raise AssertionError(f"job {key} did not finish")


def test_failure_of_one_job_does_not_block_another_job():
    manager = BackgroundJobManager(max_workers=2)
    gate = Event()

    def failing(context):
        gate.wait(0.2)
        raise RuntimeError("broken clip")

    def ready(context):
        context.progress({"message": "ready clip"})
        return "usable"

    try:
        manager.submit("preview:bad", "Bad", failing)
        manager.submit("preview:good", "Good", ready)

        good = _wait_terminal(manager, "preview:good")
        assert good.state == "succeeded"
        assert good.result == "usable"

        gate.set()
        bad = _wait_terminal(manager, "preview:bad")
        assert bad.state == "failed"
        assert "broken clip" in bad.message

        # The successful job remains usable after another Clip failed.
        assert manager.snapshot("preview:good").state == "succeeded"
    finally:
        gate.set()
        manager.shutdown(cancel=True, wait=True)


def test_long_running_job_does_not_block_unrelated_job():
    manager = BackgroundJobManager(max_workers=2)
    release = Event()

    def long_job(context):
        while not release.wait(0.005):
            context.check_cancelled()
        return "long-done"

    def quick_edit_side_job(context):
        return "quick-done"

    try:
        manager.submit("preview:long", "Long preview", long_job)
        manager.submit("ui:quick", "Independent work", quick_edit_side_job)

        quick = _wait_terminal(manager, "ui:quick")
        assert quick.state == "succeeded"
        assert quick.result == "quick-done"
        assert manager.snapshot("preview:long").active
    finally:
        release.set()
        manager.shutdown(cancel=True, wait=True)


def test_cooperative_cancellation_reaches_cancelled_terminal_state():
    manager = BackgroundJobManager(max_workers=1)
    started = Event()

    def cancellable(context):
        started.set()
        while True:
            context.check_cancelled()
            time.sleep(0.002)

    try:
        manager.submit("export:1", "Export", cancellable)
        assert started.wait(0.5)
        assert manager.cancel("export:1") is True
        snapshot = _wait_terminal(manager, "export:1")
        assert snapshot.state == "cancelled"
        assert isinstance(snapshot.error, JobCancelled)
    finally:
        manager.shutdown(cancel=True, wait=True)


def test_preview_cache_cancellation_removes_preparing_files(tmp_path, monkeypatch):
    from panopilot import cache as cache_module
    from panopilot.cache import PreviewProfile

    source = tmp_path / "clip.OSV"
    source.write_bytes(b"x" * 64)
    cache_root = tmp_path / "cache"

    monkeypatch.setattr(
        cache_module,
        "probe_source",
        lambda _source: {
            "format": {
                "duration": "1.0",
            }
        },
    )

    def fake_render_preview(_source, output, **kwargs):
        Path(output).write_bytes(b"partial")
        raise JobCancelled("cancelled in renderer")

    monkeypatch.setattr(
        cache_module,
        "render_preview",
        fake_render_preview,
    )

    try:
        cache_module.ensure_preview_cache(
            source,
            profile=PreviewProfile(),
            cache_dir=cache_root,
        )
    except JobCancelled:
        pass
    else:
        raise AssertionError("expected cancellation")

    assert not list(
        cache_root.rglob("panorama.preparing.mp4")
    )
    assert not list(
        cache_root.rglob("*.json.tmp")
    )
