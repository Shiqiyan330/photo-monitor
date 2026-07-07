from pathlib import Path
from tempfile import SpooledTemporaryFile

from fastapi import UploadFile

from services.upload_service import save_photo_upload_file


def make_upload(filename: str, content: bytes) -> UploadFile:
    file_obj = SpooledTemporaryFile()
    file_obj.write(content)
    file_obj.seek(0)
    return UploadFile(filename=filename, file=file_obj)


def test_photo_upload_removes_older_file_in_default_dedupe_window(tmp_path: Path):
    user = {"role": "admin", "username": "admin"}
    first = save_photo_upload_file(
        tmp_path,
        make_upload("camera_20260707120000_001.jpg", b"first"),
        "ops",
        "xiazhan",
        user,
    )
    second = save_photo_upload_file(
        tmp_path,
        make_upload("camera_20260707120005_002.jpg", b"second"),
        "ops",
        "xiazhan",
        user,
    )

    assert not (tmp_path / first["path"]).exists()
    assert (tmp_path / second["path"]).exists()
    assert sorted(path.name for path in tmp_path.rglob("*.jpg")) == [second["name"]]


def test_photo_upload_keeps_files_outside_default_dedupe_window(tmp_path: Path):
    user = {"role": "admin", "username": "admin"}
    first = save_photo_upload_file(
        tmp_path,
        make_upload("camera_20260707120000_001.jpg", b"first"),
        "ops",
        "xiazhan",
        user,
    )
    second = save_photo_upload_file(
        tmp_path,
        make_upload("camera_20260707120011_002.jpg", b"second"),
        "ops",
        "xiazhan",
        user,
    )

    assert (tmp_path / first["path"]).exists()
    assert (tmp_path / second["path"]).exists()
    assert sorted(path.name for path in tmp_path.rglob("*.jpg")) == [first["name"], second["name"]]
