from datetime import (
    datetime,
    timezone,
)
import json

from panopilot.project import (
    CameraPosition,
    Clip,
    Project,
    latest_project_backup,
    list_project_backups,
    load_project,
    recover_project_backup,
    save_project,
)


def _project(yaw=20.0):
    return Project(
        clips=[
            Clip(
                id="clip-1",
                source="/tmp/source.OSV",
                camera_positions=[
                    CameraPosition(
                        source_time=2.0,
                        yaw_deg=yaw,
                        pitch_deg=-5.0,
                        fov_deg=75.0,
                    )
                ],
            )
        ]
    )


def test_save_creates_backup_outside_project_directory(
    tmp_path,
):
    project_path = (
        tmp_path
        / "checkout"
        / "results"
        / "project.json"
    )
    backup_root = (
        tmp_path
        / "durable"
    )

    save_project(
        _project(),
        project_path,
        backup_root=backup_root,
    )

    backup = latest_project_backup(
        project_path,
        backup_root=backup_root,
    )

    assert project_path.is_file()
    assert backup is not None
    assert backup.is_file()
    assert backup_root in backup.parents
    assert project_path.parent not in backup.parents


def test_deleted_project_can_be_recovered_from_external_backup(
    tmp_path,
):
    project_path = (
        tmp_path
        / "checkout"
        / "results"
        / "project.json"
    )
    backup_root = (
        tmp_path
        / "durable"
    )

    save_project(
        _project(
            yaw=47.0
        ),
        project_path,
        backup_root=backup_root,
    )

    project_path.unlink()

    result = recover_project_backup(
        project_path,
        backup_root=backup_root,
    )

    assert result["clip_count"] == 1
    recovered = load_project(
        project_path
    )
    assert (
        recovered.clips[0]
        .camera_positions[0]
        .yaw_deg
        == 47.0
    )


def test_multiple_saves_create_history_and_latest(
    tmp_path,
    monkeypatch,
):
    project_path = (
        tmp_path
        / "project.json"
    )
    backup_root = (
        tmp_path
        / "durable"
    )

    # Explicit snapshots exercise history independently of real wall time.
    from panopilot.project import backup_project_snapshot

    first = _project(
        yaw=10.0
    )
    second = _project(
        yaw=80.0
    )

    save_project(
        first,
        project_path,
        create_backup=False,
    )

    backup_project_snapshot(
        first,
        project_path,
        backup_root=backup_root,
        now=datetime(
            2026,
            9,
            6,
            12,
            0,
            0,
            tzinfo=timezone.utc,
        ),
    )

    save_project(
        second,
        project_path,
        create_backup=False,
    )

    backup_project_snapshot(
        second,
        project_path,
        backup_root=backup_root,
        now=datetime(
            2026,
            9,
            6,
            12,
            1,
            0,
            tzinfo=timezone.utc,
        ),
    )

    backups = list_project_backups(
        project_path,
        backup_root=backup_root,
    )

    assert len(backups) == 2

    latest = latest_project_backup(
        project_path,
        backup_root=backup_root,
    )

    data = json.loads(
        latest.read_text(
            encoding="utf-8"
        )
    )
    assert (
        data["clips"][0]
        ["camera_positions"][0]
        ["yaw_deg"]
        == 80.0
    )
