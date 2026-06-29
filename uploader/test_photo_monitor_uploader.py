import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

WORKSPACE_TEMP = Path(__file__).resolve().parents[1] / ".photo-monitor-uploader-test"
WORKSPACE_TEMP.mkdir(exist_ok=True)
tempfile.tempdir = str(WORKSPACE_TEMP)

from uploader import config as uploader_config


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


if __name__ == "__main__":
    unittest.main()
