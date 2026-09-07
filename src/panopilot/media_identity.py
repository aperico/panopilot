"""Persistent Source Recording identity for PanoPilot Projects.

Preview-cache identity deliberately includes filesystem mutation metadata so a
cache can be invalidated cheaply. Project identity has a different purpose: it
must detect when a Project path resolves to *different media* without requiring
a full hash of a multi-gigabyte OSV on every open.

``sampled-sha256-v1`` hashes the file size plus deterministic 1 MiB windows at
the beginning, middle and end of the file. The resolved path and mtime are
stored as diagnostics but are not authoritative identity fields. Touching or
renaming the same media therefore does not create a false mismatch, while
ordinary source replacement is detected with cryptographic strength over the
sampled regions.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path


SOURCE_IDENTITY_ALGORITHM = "sampled-sha256-v1"
SOURCE_IDENTITY_SAMPLE_BYTES = 1024 * 1024


def _sample_offsets(size, sample_bytes=SOURCE_IDENTITY_SAMPLE_BYTES):
    size = max(0, int(size))
    width = max(1, int(sample_bytes))
    if size <= width:
        return (0,)

    last = max(0, size - width)
    middle = max(0, min(last, (size - width) // 2))
    return tuple(sorted(set((0, middle, last))))


def source_identity(source, *, sample_bytes=SOURCE_IDENTITY_SAMPLE_BYTES):
    source = Path(source).expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"Source does not exist: {source}")

    stat = source.stat()
    size = int(stat.st_size)
    digest = sha256()
    digest.update(b"PanoPilot Source Identity sampled-sha256-v1\0")
    digest.update(str(size).encode("ascii"))
    digest.update(b"\0")

    offsets = _sample_offsets(size, sample_bytes)
    with source.open("rb", buffering=0) as handle:
        for offset in offsets:
            handle.seek(int(offset))
            block = handle.read(min(int(sample_bytes), max(0, size - int(offset))))
            digest.update(str(int(offset)).encode("ascii"))
            digest.update(b":")
            digest.update(str(len(block)).encode("ascii"))
            digest.update(b":")
            digest.update(block)

    return {
        "algorithm": SOURCE_IDENTITY_ALGORITHM,
        "size": size,
        "fingerprint": digest.hexdigest(),
        "sample_bytes": int(sample_bytes),
        "sample_offsets": [int(v) for v in offsets],
        "resolved_path": str(source.resolve(strict=False)),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def identity_matches(expected, actual):
    if not expected or not actual:
        return False
    if str(expected.get("algorithm")) != SOURCE_IDENTITY_ALGORITHM:
        return False
    if str(actual.get("algorithm")) != SOURCE_IDENTITY_ALGORITHM:
        return False
    return (
        int(expected.get("size", -1)) == int(actual.get("size", -2))
        and str(expected.get("fingerprint", ""))
        == str(actual.get("fingerprint", "!"))
    )


def source_reference_status(source, expected_identity):
    """Return a non-throwing Project-reference status dictionary."""
    source = Path(source).expanduser()
    if not source.is_file():
        return {
            "status": "missing",
            "source": str(source),
            "expected_identity": expected_identity,
            "actual_identity": None,
            "message": f"Source Recording cannot be located: {source}",
        }

    try:
        actual = source_identity(source)
    except Exception as exc:
        return {
            "status": "unreadable",
            "source": str(source),
            "expected_identity": expected_identity,
            "actual_identity": None,
            "message": f"Source Recording identity could not be read: {exc}",
        }

    if expected_identity is None:
        return {
            "status": "unverified",
            "source": str(source),
            "expected_identity": None,
            "actual_identity": actual,
            "message": "Project has no expected Source Identity for this legacy reference.",
        }

    if identity_matches(expected_identity, actual):
        return {
            "status": "ok",
            "source": str(source),
            "expected_identity": expected_identity,
            "actual_identity": actual,
            "message": "Source Recording matches the Project identity.",
        }

    return {
        "status": "mismatch",
        "source": str(source),
        "expected_identity": expected_identity,
        "actual_identity": actual,
        "message": (
            "Source Recording at the saved path does not match the media "
            "expected by this Project. PanoPilot will not use it silently."
        ),
    }


def assert_source_reference(source, expected_identity):
    status = source_reference_status(source, expected_identity)
    if status["status"] == "ok":
        return status
    if status["status"] == "unverified":
        # Legacy projects are upgraded on load/save where possible. Keep this
        # branch explicit so callers cannot accidentally treat a mismatch as a
        # missing baseline.
        raise RuntimeError(status["message"])
    raise RuntimeError(status["message"])
