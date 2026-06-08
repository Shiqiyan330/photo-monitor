import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import photo_monitor_uploader as uploader


class UploaderTests(unittest.TestCase):
    def test_normalize_server_rejects_invalid_url(self):
        self.assertEqual(uploader.normalize_server(" http://example.com/ "), "http://example.com")
        with self.assertRaisesRegex(uploader.UploaderError, "Server must start"):
            uploader.normalize_server("ftp://example.com")

    def test_safe_path_part_rejects_windows_invalid_characters(self):
        self.assertEqual(uploader.safe_path_part("Department", " HQ "), "HQ")
        with self.assertRaisesRegex(uploader.UploaderError, "invalid path characters"):
            uploader.safe_path_part("Department", "bad/name")

    def test_resolve_photo_station_uses_known_folder_name(self):
        path = Path("C:/photos/HQ/xiazhan/image.jpg")
        self.assertEqual(uploader.resolve_photo_station("uploads", path), "xiazhan")

    def test_iter_watched_files_filters_extensions_and_subdirectories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "a.jpg").write_bytes(b"a")
            (root / "b.txt").write_bytes(b"b")
            (root / "nested").mkdir()
            (root / "nested" / "c.png").write_bytes(b"c")

            recursive = [item.name for item in uploader.iter_watched_files(root, include_subdirectories=True)]
            flat = [item.name for item in uploader.iter_watched_files(root, include_subdirectories=False)]

        self.assertEqual(recursive, ["a.jpg", "c.png"])
        self.assertEqual(flat, ["a.jpg"])

    def test_upload_file_reports_server_detail(self):
        class FakeResponse:
            status = 400

            def read(self):
                return json.dumps({"detail": "No permission"}).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "photo.jpg"
            path.write_bytes(b"photo")
            config = uploader.UploaderConfig(
                server="http://example.com",
                token="token",
                username="admin",
                department="HQ",
                station="uploads",
                watch_dir=str(path.parent),
                interval_seconds=60,
                stable_seconds=0,
                timeout_seconds=10,
                retry_count=1,
                retry_delay_seconds=1,
                include_subdirectories=True,
            )
            with mock.patch("urllib.request.urlopen", return_value=FakeResponse()):
                with self.assertRaisesRegex(uploader.UploaderError, "No permission"):
                    uploader.upload_file(config, path)

    def test_parser_accepts_legacy_powershell_option_names(self):
        args = uploader.build_parser().parse_args(
            [
                "once",
                "-Server",
                "http://127.0.0.1:8000",
                "-WatchDir",
                "D:\\photos",
                "-DryRun",
            ]
        )

        self.assertEqual(args.command, "once")
        self.assertEqual(args.server, "http://127.0.0.1:8000")
        self.assertEqual(args.watch_dir, "D:\\photos")
        self.assertTrue(args.dry_run)


if __name__ == "__main__":
    unittest.main()
