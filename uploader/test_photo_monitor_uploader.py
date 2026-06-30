import shutil
import tempfile
import unittest
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

WORKSPACE_TEMP = Path(__file__).resolve().parents[1] / ".photo-monitor-uploader-test"
WORKSPACE_TEMP.mkdir(exist_ok=True)
tempfile.tempdir = str(WORKSPACE_TEMP)

from uploader import config as uploader_config


def make_case_dir(name: str) -> Path:
    path = WORKSPACE_TEMP / name
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


class ConfigTests(unittest.TestCase):
    def tearDown(self):
        for child in WORKSPACE_TEMP.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)

    def test_normalize_server_rejects_invalid_url(self):
        self.assertEqual(uploader_config.normalize_server(" http://example.com/ "), "http://example.com")
        with self.assertRaisesRegex(uploader_config.UploaderError, "Server must start"):
            uploader_config.normalize_server("ftp://example.com")

    def test_safe_path_part_rejects_windows_invalid_characters(self):
        self.assertEqual(uploader_config.safe_path_part("Department", " HQ "), "HQ")
        with self.assertRaisesRegex(uploader_config.UploaderError, "invalid path characters"):
            uploader_config.safe_path_part("Department", "bad/name")

    def test_save_and_read_json_round_trips_utf8(self):
        path = WORKSPACE_TEMP / "config.json"
        uploader_config.save_json(path, {"department": "General"})
        self.assertEqual(uploader_config.read_json(path, {}), {"department": "General"})

    def test_read_json_returns_default_for_invalid_json(self):
        path = WORKSPACE_TEMP / "broken.json"
        path.write_text("{", encoding="utf-8")
        self.assertEqual(uploader_config.read_json(path, {"ok": True}), {"ok": True})

    def test_config_defaults_include_gui_fields(self):
        data = {
            "server": "http://example.com",
            "token": "token",
            "username": "user",
            "department": "General",
            "station": "uploads",
            "watch_dir": str(WORKSPACE_TEMP),
        }
        config = uploader_config.config_from_dict(data)
        self.assertFalse(config.launch_minimized)
        self.assertFalse(config.start_watching_on_launch)
        self.assertTrue(config.include_subdirectories)

    def test_password_helpers_use_keyring_when_enabled(self):
        with mock.patch.object(uploader_config, "keyring", create=True) as fake_keyring:
            uploader_config.save_password("alice", "secret")
            fake_keyring.set_password.assert_called_once_with("PhotoMonitorUploader", "alice", "secret")
            fake_keyring.get_password.return_value = "secret"
            self.assertEqual(uploader_config.load_password("alice"), "secret")


from uploader import api_client, scanner


class ScannerTests(unittest.TestCase):
    def tearDown(self):
        for child in WORKSPACE_TEMP.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)

    def test_resolve_photo_station_uses_known_folder_name(self):
        path = Path("C:/photos/HQ/xiazhan/image.jpg")
        self.assertEqual(scanner.resolve_photo_station("uploads", path), "xiazhan")

    def test_iter_watched_files_filters_extensions_and_subdirectories(self):
        root = make_case_dir("iter_watched_files")
        (root / "a.jpg").write_bytes(b"a")
        (root / "b.txt").write_bytes(b"b")
        (root / "nested").mkdir()
        (root / "nested" / "c.png").write_bytes(b"c")

        recursive = [item.name for item in scanner.iter_watched_files(root, include_subdirectories=True)]
        flat = [item.name for item in scanner.iter_watched_files(root, include_subdirectories=False)]

        self.assertEqual(recursive, ["a.jpg", "c.png"])
        self.assertEqual(flat, ["a.jpg"])

    def test_state_recorder_adds_uploaded_file_key(self):
        root = make_case_dir("state_recorder")
        photo = root / "photo.jpg"
        photo.write_bytes(b"photo")
        state = {}
        scanner.record_uploaded_file(
            state,
            photo,
            station="uploads",
            result={"item": {"name": "photo.jpg"}},
            uploaded_at=datetime(2026, 6, 30, tzinfo=timezone.utc),
        )
        key = scanner.file_key(photo)
        self.assertEqual(state[key]["station"], "uploads")
        self.assertEqual(state[key]["server_item"], {"name": "photo.jpg"})


class ApiClientTests(unittest.TestCase):
    def test_request_json_reports_server_detail(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps({"detail": "No permission"}).encode("utf-8")

            def close(self):
                return None

        error = api_client.urllib.error.HTTPError(
            url="http://example.com/uploads",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=FakeResponse(),
        )
        with mock.patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(uploader_config.UploaderError, "No permission"):
                api_client.request_json("http://example.com/uploads")

    def test_upload_file_reports_server_detail(self):
        class FakeResponse:
            status = 400

            def read(self):
                return json.dumps({"detail": "No permission"}).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        root = make_case_dir("upload_file")
        path = root / "photo.jpg"
        path.write_bytes(b"photo")
        config = uploader_config.UploaderConfig(
            server="http://example.com",
            token="token",
            username="admin",
            department="HQ",
            station="uploads",
            watch_dir=str(path.parent),
        )
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse()):
            with self.assertRaisesRegex(uploader_config.UploaderError, "No permission"):
                api_client.upload_file(config, path)


from uploader import cli, worker


class WorkerTests(unittest.TestCase):
    def tearDown(self):
        for child in WORKSPACE_TEMP.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)

    def test_scan_once_uploads_matching_stable_file(self):
        root = make_case_dir("scan_once")
        photo = root / "photo.jpg"
        photo.write_bytes(b"photo")
        config = uploader_config.UploaderConfig(
            server="http://example.com",
            token="token",
            username="admin",
            department="HQ",
            station="uploads",
            watch_dir=str(root),
            stable_seconds=0,
        )
        events = []
        state = {}

        result = worker.scan_once(
            config,
            state,
            upload=lambda _config, path: {"item": {"name": path.name}},
            save_state=lambda value: events.append(("save", len(value))),
            log=lambda message: events.append(("log", message)),
        )

        self.assertEqual(result.uploaded, 1)
        self.assertEqual(result.failed, 0)
        self.assertTrue(any(item[0] == "save" for item in events))

    def test_watch_controller_stop_sets_cancel_event(self):
        controller = worker.WatchController(lambda cancelled: None)
        controller.stop()
        self.assertTrue(controller.cancelled.is_set())


class WatchdogSelectionTests(unittest.TestCase):
    def test_make_watch_controller_returns_controller(self):
        config = uploader_config.UploaderConfig(
            server="http://example.com",
            token="token",
            username="admin",
            department="HQ",
            station="uploads",
            watch_dir=str(WORKSPACE_TEMP),
            interval_seconds=5,
        )
        controller = worker.make_watch_controller(
            config,
            {},
            save_state=lambda _state: None,
            log=lambda _message: None,
        )
        self.assertIsInstance(controller, worker.WatchController)
        controller.stop()


class BuildScriptTests(unittest.TestCase):
    def test_windows_build_script_runs_tests_builds_and_copies_download(self):
        script = Path(__file__).with_name("build_windows.ps1")
        self.assertTrue(script.exists())
        content = script.read_text(encoding="utf-8")
        self.assertIn('$Python = if ($env:PYTHON)', content)
        self.assertIn("& $Python -m unittest uploader.test_photo_monitor_uploader", content)
        self.assertIn("& $Python -m pip install --timeout 120", content)
        self.assertIn("if ($LASTEXITCODE -ne 0)", content)
        self.assertIn("& $Python -m PyInstaller", content)
        self.assertIn("photo-monitor\\public\\downloads\\photo-monitor-uploader.exe", content)


class CliTests(unittest.TestCase):
    def test_parser_accepts_gui_and_legacy_powershell_option_names(self):
        args = cli.build_parser().parse_args(
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

        gui_args = cli.build_parser().parse_args(["gui"])
        self.assertEqual(gui_args.command, "gui")


class GuiTests(unittest.TestCase):
    def test_gui_module_imports_or_reports_missing_pyside6(self):
        try:
            from uploader import gui
        except ImportError as error:
            self.assertTrue("PySide6" in str(error) or "DLL load failed" in str(error))
            return
        self.assertTrue(hasattr(gui, "main"))

    def test_gui_defines_readable_chinese_labels(self):
        try:
            from uploader import gui
        except ImportError as error:
            self.assertTrue("PySide6" in str(error) or "DLL load failed" in str(error))
            return
        labels = gui.UI_TEXT
        self.assertEqual(labels["window_title"], "网站照片上传器")
        self.assertEqual(labels["start_watch"], "开始监听")
        self.assertEqual(labels["upload_files"], "上传照片")


if __name__ == "__main__":
    unittest.main()
