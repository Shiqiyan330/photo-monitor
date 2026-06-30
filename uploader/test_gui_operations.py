import os
import shutil
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
WORKSPACE_TEMP = Path(__file__).resolve().parents[1] / ".photo-monitor-uploader-test"
WORKSPACE_TEMP.mkdir(exist_ok=True)


def make_case_dir(name: str) -> Path:
    path = WORKSPACE_TEMP / name
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path

try:
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication

    from uploader import gui
    from uploader.config import UploaderError
    from uploader.worker import ScanResult
except ImportError as error:
    QApplication = None
    QCloseEvent = None
    gui = None
    UploaderError = None
    ScanResult = None
    GUI_IMPORT_ERROR = error
else:
    GUI_IMPORT_ERROR = None


@unittest.skipIf(GUI_IMPORT_ERROR is not None, f"PySide6 GUI unavailable: {GUI_IMPORT_ERROR}")
class GuiOperationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = gui.MainWindow()
        self.window.server_input.setText("http://example.com")
        self.window.username_input.setText("alice")
        self.window.password_input.setText("secret")
        self.window.department_input.setText("HQ")
        self.window.station_input.setText("uploads")
        self.window.watch_dir_input.setText(str(WORKSPACE_TEMP))
        self.window.stable_input.setValue(0)
        self.window.retry_delay_input.setValue(1)

    def tearDown(self):
        self.window.allow_quit = True
        self.window.stop_watching()
        self.window.close()
        self.app.processEvents()

    def _wait_for_tasks(self):
        for thread in list(self.window.task_threads):
            self.assertTrue(thread.wait(3000), "GUI background task did not finish")
        self.app.processEvents()

    def test_login_and_save_persists_token_and_password_when_requested(self):
        self.window.remember_password_input.setChecked(True)

        with (
            mock.patch.object(
                gui.api_client,
                "login",
                return_value={"token": "token-123", "user": {"username": "alice", "department": "HQ"}},
            ) as login,
            mock.patch.object(gui, "save_config") as save_config,
            mock.patch.object(gui, "save_password") as save_password,
        ):
            self.window.login_and_save()
            self._wait_for_tasks()

        login.assert_called_once_with("http://example.com", "alice", "secret", 120)
        saved_config = save_config.call_args.args[0]
        self.assertEqual(saved_config.token, "token-123")
        self.assertEqual(saved_config.username, "alice")
        save_password.assert_called_once_with("alice", "secret")
        self.assertIn("登录", self.window.activity_log.toPlainText())

    def test_save_settings_uses_form_values_without_plaintext_password_config(self):
        self.window.remember_password_input.setChecked(True)

        with (
            mock.patch.object(gui, "load_saved_config", side_effect=UploaderError("missing config")),
            mock.patch.object(gui, "save_config") as save_config,
            mock.patch.object(gui, "save_password") as save_password,
        ):
            self.window.save_settings()

        saved_config = save_config.call_args.args[0]
        self.assertEqual(saved_config.username, "alice")
        self.assertEqual(saved_config.department, "HQ")
        self.assertEqual(saved_config.token, "")
        self.assertFalse(hasattr(saved_config, "password"))
        save_password.assert_called_once_with("alice", "secret")

    def test_upload_files_uses_selected_photos_and_saved_token(self):
        temp_dir = make_case_dir("gui_upload_files")
        photo = temp_dir / "photo.jpg"
        photo.write_bytes(b"photo")

        with (
            mock.patch.object(
                gui,
                "load_saved_config",
                return_value=gui.UploaderConfig(
                    server="http://example.com",
                    token="token-123",
                    username="alice",
                    department="HQ",
                    station="uploads",
                    watch_dir=str(temp_dir),
                ),
            ),
            mock.patch.object(gui.QFileDialog, "getOpenFileNames", return_value=([str(photo)], "")),
            mock.patch.object(gui.api_client, "upload_with_retry", return_value={"item": {"name": "photo.jpg"}}) as upload,
        ):
            self.window.upload_files()
            self._wait_for_tasks()

        upload.assert_called_once()
        config, uploaded_path = upload.call_args.args[:2]
        self.assertEqual(config.token, "token-123")
        self.assertEqual(uploaded_path.name, "photo.jpg")
        self.assertIn("已上传", self.window.activity_log.toPlainText())

    def test_scan_once_runs_worker_and_reports_counts(self):
        with (
            mock.patch.object(
                gui,
                "load_saved_config",
                return_value=gui.UploaderConfig(
                    server="http://example.com",
                    token="token-123",
                    username="alice",
                    department="HQ",
                    station="uploads",
                    watch_dir=str(WORKSPACE_TEMP),
                ),
            ),
            mock.patch.object(gui, "read_json", return_value={}),
            mock.patch.object(gui, "save_json") as save_json,
            mock.patch.object(gui.worker, "scan_once", return_value=ScanResult(matched=2, uploaded=1, skipped=1, failed=0)) as scan,
        ):
            self.window.scan_once()
            self._wait_for_tasks()

        scan.assert_called_once()
        self.assertIsNotNone(scan.call_args.kwargs["save_state"])
        self.assertIn("扫描完成", self.window.activity_log.toPlainText())
        self.assertFalse(save_json.called)

    def test_start_and_stop_watching_wires_controller_and_buttons(self):
        class FakeController:
            def __init__(self):
                self.started = False
                self.stopped = False
                self.joined = False

            def start(self):
                self.started = True

            def stop(self):
                self.stopped = True

            def join(self, _timeout):
                self.joined = True

        controller = FakeController()

        with (
            mock.patch.object(gui, "load_saved_config", side_effect=UploaderError("missing config")),
            mock.patch.object(gui, "read_json", return_value={}),
            mock.patch.object(gui.worker, "make_watch_controller", return_value=controller) as factory,
        ):
            self.window.start_watching()
            self.assertTrue(controller.started)
            self.assertFalse(self.window.start_button.isEnabled())
            self.assertTrue(self.window.stop_button.isEnabled())

            self.window.stop_watching()

        factory.assert_called_once()
        self.assertTrue(controller.stopped)
        self.assertTrue(controller.joined)
        self.assertIsNone(self.window.watch_controller)
        self.assertTrue(self.window.start_button.isEnabled())

    def test_close_button_hides_window_instead_of_quitting(self):
        self.window.show()
        self.app.processEvents()
        event = QCloseEvent()

        self.window.closeEvent(event)

        self.assertFalse(event.isAccepted())
        self.assertFalse(self.window.isVisible())


if __name__ == "__main__":
    unittest.main()
