from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import api_client, worker
from .config import (
    CONFIG_FILE,
    DEFAULT_SERVER,
    DEFAULT_STATION,
    DEFAULT_WATCH_DIR,
    LOG_FILE,
    STATE_FILE,
    UploaderConfig,
    load_password,
    load_saved_config,
    read_json,
    safe_path_part,
    save_config,
    save_json,
    save_password,
)


UI_TEXT = {
    "window_title": "网站照片上传器",
    "status_ready": "就绪",
    "tab_upload": "上传与监听",
    "tab_diagnostics": "诊断与日志",
    "settings": "账号与监听设置",
    "server": "服务器",
    "username": "用户名",
    "password": "密码",
    "remember_password": "记住密码",
    "department": "部门",
    "station": "站点",
    "watch_folder": "监听文件夹",
    "choose_folder": "选择文件夹",
    "include_subfolders": "包含子文件夹",
    "scan_interval": "扫描间隔（秒）",
    "stable_delay": "稳定等待（秒）",
    "retry_count": "重试次数",
    "retry_delay": "重试等待（秒）",
    "start_on_launch": "启动后自动监听",
    "launch_minimized": "启动后最小化到托盘",
    "actions": "操作",
    "login_save": "登录并保存",
    "save_settings": "保存设置",
    "upload_files": "上传照片",
    "scan_once": "立即扫描",
    "start_watch": "开始监听",
    "stop_watch": "停止监听",
    "activity": "活动记录",
    "refresh_diagnostics": "刷新诊断",
    "open_log_folder": "打开日志目录",
    "show_window": "显示主窗口",
    "quit": "退出",
}


class TaskThread(QThread):
    message = Signal(str)
    failed = Signal(str)
    finished_ok = Signal(str)

    def __init__(self, target):
        super().__init__()
        self._target = target

    def run(self) -> None:
        try:
            result = self._target(self.message.emit)
            self.finished_ok.emit(result or "Done")
        except Exception as error:
            self.failed.emit(str(error))


class MainWindow(QMainWindow):
    watch_message = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(UI_TEXT["window_title"])
        self.resize(980, 680)
        self.allow_quit = False
        self.watch_controller: worker.WatchController | None = None
        self.task_threads: list[TaskThread] = []
        self.watch_message.connect(self.append_log)
        self._build_ui()
        self._build_tray()
        self._load_config_to_form()
        self._refresh_status(UI_TEXT["status_ready"])

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        self.status_label = QLabel(UI_TEXT["status_ready"])
        self.status_label.setObjectName("statusLabel")
        root.addWidget(self.status_label)

        tabs = QTabWidget()
        tabs.addTab(self._build_upload_tab(), UI_TEXT["tab_upload"])
        tabs.addTab(self._build_diagnostics_tab(), UI_TEXT["tab_diagnostics"])
        root.addWidget(tabs)

        self.setCentralWidget(central)
        self.setStyleSheet(
            """
            QMainWindow { background: #f5f7f8; }
            QLabel#statusLabel { padding: 14px; background: #1e3a3a; color: white; font-size: 15px; font-weight: 600; }
            QGroupBox { font-weight: 600; border: 1px solid #d7dce2; border-radius: 6px; margin-top: 12px; padding: 10px; background: white; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QPushButton { padding: 8px 12px; border: 1px solid #bac3cf; border-radius: 5px; background: white; }
            QPushButton:hover { background: #eef6f4; border-color: #8fb7ae; }
            QPushButton:disabled { color: #8a94a3; background: #eef0f3; }
            QLineEdit, QSpinBox { padding: 7px; border: 1px solid #bac3cf; border-radius: 5px; background: white; }
            QTextEdit { border: 1px solid #d7dce2; border-radius: 6px; background: white; }
            """
        )

    def _build_upload_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        settings = QGroupBox(UI_TEXT["settings"])
        form = QFormLayout(settings)
        self.server_input = QLineEdit(DEFAULT_SERVER)
        self.username_input = QLineEdit("admin")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.remember_password_input = QCheckBox(UI_TEXT["remember_password"])
        self.department_input = QLineEdit()
        self.station_input = QLineEdit(DEFAULT_STATION)
        self.watch_dir_input = QLineEdit(DEFAULT_WATCH_DIR)
        self.include_subdirs_input = QCheckBox(UI_TEXT["include_subfolders"])
        self.include_subdirs_input.setChecked(True)
        self.interval_input = QSpinBox()
        self.interval_input.setRange(5, 86400)
        self.interval_input.setValue(60)
        self.stable_input = QSpinBox()
        self.stable_input.setRange(0, 3600)
        self.stable_input.setValue(10)
        self.retry_count_input = QSpinBox()
        self.retry_count_input.setRange(1, 10)
        self.retry_count_input.setValue(3)
        self.retry_delay_input = QSpinBox()
        self.retry_delay_input.setRange(1, 300)
        self.retry_delay_input.setValue(5)
        self.start_on_launch_input = QCheckBox(UI_TEXT["start_on_launch"])
        self.launch_minimized_input = QCheckBox(UI_TEXT["launch_minimized"])

        form.addRow(UI_TEXT["server"], self.server_input)
        form.addRow(UI_TEXT["username"], self.username_input)
        form.addRow(UI_TEXT["password"], self.password_input)
        form.addRow("", self.remember_password_input)
        form.addRow(UI_TEXT["department"], self.department_input)
        form.addRow(UI_TEXT["station"], self.station_input)

        folder_row = QHBoxLayout()
        folder_row.addWidget(self.watch_dir_input)
        choose_button = QPushButton(UI_TEXT["choose_folder"])
        choose_button.clicked.connect(self.choose_watch_dir)
        folder_row.addWidget(choose_button)
        form.addRow(UI_TEXT["watch_folder"], folder_row)
        form.addRow("", self.include_subdirs_input)
        form.addRow(UI_TEXT["scan_interval"], self.interval_input)
        form.addRow(UI_TEXT["stable_delay"], self.stable_input)
        form.addRow(UI_TEXT["retry_count"], self.retry_count_input)
        form.addRow(UI_TEXT["retry_delay"], self.retry_delay_input)
        form.addRow("", self.start_on_launch_input)
        form.addRow("", self.launch_minimized_input)
        layout.addWidget(settings)

        actions = QGroupBox(UI_TEXT["actions"])
        action_layout = QGridLayout(actions)
        self.login_button = QPushButton(UI_TEXT["login_save"])
        self.login_button.clicked.connect(self.login_and_save)
        self.save_button = QPushButton(UI_TEXT["save_settings"])
        self.save_button.clicked.connect(self.save_settings)
        self.upload_button = QPushButton(UI_TEXT["upload_files"])
        self.upload_button.clicked.connect(self.upload_files)
        self.scan_button = QPushButton(UI_TEXT["scan_once"])
        self.scan_button.clicked.connect(self.scan_once)
        self.start_button = QPushButton(UI_TEXT["start_watch"])
        self.start_button.clicked.connect(self.start_watching)
        self.stop_button = QPushButton(UI_TEXT["stop_watch"])
        self.stop_button.clicked.connect(self.stop_watching)
        self.stop_button.setEnabled(False)

        for index, button in enumerate(
            [self.login_button, self.save_button, self.upload_button, self.scan_button, self.start_button, self.stop_button]
        ):
            action_layout.addWidget(button, index // 3, index % 3)
        layout.addWidget(actions)

        activity = QGroupBox(UI_TEXT["activity"])
        activity_layout = QVBoxLayout(activity)
        self.activity_log = QTextEdit()
        self.activity_log.setReadOnly(True)
        activity_layout.addWidget(self.activity_log)
        layout.addWidget(activity, 1)
        return page

    def _build_diagnostics_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.diagnostics = QTextEdit()
        self.diagnostics.setReadOnly(True)
        refresh = QPushButton(UI_TEXT["refresh_diagnostics"])
        refresh.clicked.connect(self.refresh_diagnostics)
        open_log = QPushButton(UI_TEXT["open_log_folder"])
        open_log.clicked.connect(self.open_log_folder)
        row = QHBoxLayout()
        row.addWidget(refresh)
        row.addWidget(open_log)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(self.diagnostics)
        return page

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ComputerIcon))
        menu = QMenu()
        show_action = QAction(UI_TEXT["show_window"], self)
        show_action.triggered.connect(self.show_window)
        start_action = QAction(UI_TEXT["start_watch"], self)
        start_action.triggered.connect(self.start_watching)
        stop_action = QAction(UI_TEXT["stop_watch"], self)
        stop_action.triggered.connect(self.stop_watching)
        scan_action = QAction(UI_TEXT["scan_once"], self)
        scan_action.triggered.connect(self.scan_once)
        upload_action = QAction(UI_TEXT["upload_files"], self)
        upload_action.triggered.connect(self.upload_files)
        open_log_action = QAction(UI_TEXT["open_log_folder"], self)
        open_log_action.triggered.connect(self.open_log_folder)
        quit_action = QAction(UI_TEXT["quit"], self)
        quit_action.triggered.connect(self.quit_app)
        for action in [show_action, start_action, stop_action, scan_action, upload_action, open_log_action, quit_action]:
            menu.addAction(action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason: self.show_window() if reason == QSystemTrayIcon.DoubleClick else None)
        self.tray.show()

    def _load_config_to_form(self) -> None:
        try:
            config = load_saved_config()
        except Exception:
            return
        self.server_input.setText(config.server)
        self.username_input.setText(config.username)
        self.password_input.setText(load_password(config.username))
        self.department_input.setText(config.department)
        self.station_input.setText(config.station)
        self.watch_dir_input.setText(config.watch_dir)
        self.include_subdirs_input.setChecked(config.include_subdirectories)
        self.interval_input.setValue(config.interval_seconds)
        self.stable_input.setValue(config.stable_seconds)
        self.retry_count_input.setValue(config.retry_count)
        self.retry_delay_input.setValue(config.retry_delay_seconds)
        self.start_on_launch_input.setChecked(config.start_watching_on_launch)
        self.launch_minimized_input.setChecked(config.launch_minimized)

    def _config_from_form(self, token: str = "") -> UploaderConfig:
        return UploaderConfig(
            server=self.server_input.text().strip().rstrip("/"),
            token=token,
            username=self.username_input.text().strip(),
            department=safe_path_part("Department", self.department_input.text()),
            station=safe_path_part("Station", self.station_input.text() or DEFAULT_STATION),
            watch_dir=self.watch_dir_input.text().strip(),
            interval_seconds=self.interval_input.value(),
            stable_seconds=self.stable_input.value(),
            retry_count=self.retry_count_input.value(),
            retry_delay_seconds=self.retry_delay_input.value(),
            include_subdirectories=self.include_subdirs_input.isChecked(),
            launch_minimized=self.launch_minimized_input.isChecked(),
            start_watching_on_launch=self.start_on_launch_input.isChecked(),
        )

    def _saved_or_form_config(self) -> UploaderConfig:
        try:
            saved = load_saved_config()
            return self._config_from_form(saved.token)
        except Exception:
            return self._config_from_form("")

    def _refresh_status(self, text: str) -> None:
        self.status_label.setText(text)
        if hasattr(self, "tray"):
            self.tray.setToolTip(f"{UI_TEXT['window_title']} - {text}")

    def append_log(self, message: str) -> None:
        self.activity_log.append(message)
        self._refresh_status(message)

    def choose_watch_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, UI_TEXT["choose_folder"], self.watch_dir_input.text())
        if folder:
            self.watch_dir_input.setText(folder)

    def _run_task(self, target) -> None:
        thread = TaskThread(target)
        self.task_threads.append(thread)
        thread.message.connect(self.append_log)
        thread.failed.connect(lambda message: QMessageBox.warning(self, "操作失败", message))
        thread.failed.connect(self.append_log)
        thread.finished_ok.connect(self.append_log)
        thread.finished.connect(lambda: self.task_threads.remove(thread) if thread in self.task_threads else None)
        thread.start()

    def save_settings(self) -> None:
        try:
            token = load_saved_config().token
        except Exception:
            token = ""
        config = self._config_from_form(token)
        save_config(config)
        if self.remember_password_input.isChecked() and self.password_input.text():
            save_password(config.username, self.password_input.text())
        self.append_log("设置已保存")

    def login_and_save(self) -> None:
        def task(log):
            config = self._config_from_form("")
            payload = api_client.login(config.server, config.username, self.password_input.text(), config.timeout_seconds)
            user = payload.get("user") or {}
            config.token = str(payload["token"])
            config.username = str(user.get("username") or config.username)
            if not config.department and user.get("department"):
                config.department = str(user["department"])
            save_config(config)
            if self.remember_password_input.isChecked() and self.password_input.text():
                save_password(config.username, self.password_input.text())
            log(f"登录成功：{config.username}")
            return "登录并保存完成"

        self._run_task(task)

    def upload_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(self, "选择照片", "", "Images (*.jpg *.jpeg *.png *.webp)")
        if not files:
            return

        def task(log):
            config = self._saved_or_form_config()
            for file_name in files:
                api_client.upload_with_retry(config, Path(file_name), log=log)
                log(f"已上传：{Path(file_name).name}")
            return f"上传完成：{len(files)} 个文件"

        self._run_task(task)

    def scan_once(self) -> None:
        def task(log):
            config = self._saved_or_form_config()
            state = read_json(STATE_FILE, {})
            if not isinstance(state, dict):
                state = {}
            result = worker.scan_once(config, state, save_state=lambda value: save_json(STATE_FILE, value), log=log)
            return f"扫描完成：上传 {result.uploaded}，跳过 {result.skipped}，失败 {result.failed}"

        self._run_task(task)

    def start_watching(self) -> None:
        if self.watch_controller is not None:
            self.append_log("监听已在运行")
            return
        try:
            config = self._saved_or_form_config()
        except Exception as error:
            QMessageBox.warning(self, "无法开始监听", str(error))
            self.append_log(f"无法开始监听：{error}")
            return
        state = read_json(STATE_FILE, {})
        if not isinstance(state, dict):
            state = {}
        self.watch_controller = worker.make_watch_controller(
            config,
            state,
            save_state=lambda value: save_json(STATE_FILE, value),
            log=self.watch_message.emit,
        )
        self.watch_controller.start()
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.append_log("监听已启动")

    def stop_watching(self) -> None:
        if self.watch_controller is None:
            return
        self.watch_controller.stop()
        self.watch_controller.join(2)
        self.watch_controller = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.append_log("监听已停止")

    def refresh_diagnostics(self) -> None:
        lines = [
            f"配置文件：{CONFIG_FILE}",
            f"日志文件：{LOG_FILE}",
            f"状态文件：{STATE_FILE}",
            f"监听文件夹：{self.watch_dir_input.text()}",
            f"日志存在：{'是' if LOG_FILE.exists() else '否'}",
        ]
        try:
            config = self._saved_or_form_config()
            api_client.auth_me(config)
            lines.append(f"登录状态：有效，用户 {config.username}")
        except Exception as error:
            lines.append(f"登录状态：需要检查，{error}")
        self.diagnostics.setPlainText("\n".join(lines))

    def open_log_folder(self) -> None:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        os.startfile(str(LOG_FILE.parent))

    def show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def quit_app(self) -> None:
        self.allow_quit = True
        self.stop_watching()
        QApplication.quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.allow_quit:
            event.accept()
            return
        event.ignore()
        self.hide()
        self.tray.showMessage(UI_TEXT["window_title"], "程序已最小化到系统托盘。", QSystemTrayIcon.Information, 2500)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    if window.launch_minimized_input.isChecked():
        window.hide()
    else:
        window.show()
    if window.start_on_launch_input.isChecked():
        window.start_watching()
    return app.exec()
