"""Tests for copy_template hardlink optimization."""
import os
from pathlib import Path

from tests.support.state import copy_template


def test_copy_template_hardlinks_blobs(tmp_path: Path) -> None:
    """Blobs should be hardlinked (not copied) for I/O efficiency."""
    template = tmp_path / "template"
    template.mkdir()
    blob = template / "blobs" / "sha256" / "00" / "abc123"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"blob content")
    (template / "metadata.sqlite3").write_bytes(b"database")

    dest = tmp_path / "destination"
    copy_template(template, dest)

    assert (dest / "blobs" / "sha256" / "00" / "abc123").read_bytes() == b"blob content"
    template_inode = os.stat(blob).st_ino
    dest_inode = os.stat(dest / "blobs" / "sha256" / "00" / "abc123").st_ino
    assert template_inode == dest_inode, "blob should be hardlinked"

    template_meta = os.stat(template / "metadata.sqlite3").st_ino
    dest_meta = os.stat(dest / "metadata.sqlite3").st_ino
    assert template_meta != dest_meta, "metadata should be copied, not hardlinked"


def test_copy_template_preserves_all_files(tmp_path: Path) -> None:
    """All non-blob files should be present in the destination."""
    template = tmp_path / "template"
    template.mkdir()
    (template / "blobs").mkdir()
    blob = template / "blobs" / "sha256" / "00" / "def456"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(b"blob")
    (template / "metadata.sqlite3").write_bytes(b"database")
    (template / "metadata.sqlite3-shm").write_bytes(b"shm")
    (template / "metadata.sqlite3-wal").write_bytes(b"wal")

    dest = tmp_path / "destination"
    copy_template(template, dest)

    for name in ("metadata.sqlite3", "metadata.sqlite3-shm", "metadata.sqlite3-wal"):
        assert (dest / name).exists(), f"{name} should be copied"


def test_copy_template_raises_on_existing_destination(tmp_path: Path) -> None:
    """copy_template should refuse to overwrite an existing destination."""
    template = tmp_path / "template"
    template.mkdir()
    (template / "blobs").mkdir()
    (template / "blobs" / "sha256" / "00" / "abc").parent.mkdir(parents=True)
    (template / "blobs" / "sha256" / "00" / "abc").write_bytes(b"blob")

    dest = tmp_path / "destination"
    dest.mkdir()
    import pytest

    with pytest.raises(FileExistsError):
        copy_template(template, dest)
