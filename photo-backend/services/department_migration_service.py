from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

from services.auth_service import parse_matrix_permission
from services.department_service import normalize_department_name
from services.upload_service import (
    DATA_MUTATION_LOCK,
    UPLOAD_CATEGORY_CONFIG,
    read_upload_metadata,
    write_upload_metadata,
)


logger = logging.getLogger(__name__)


class DepartmentMigrationConflict(ValueError):
    pass


class DepartmentMigrationFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class FileMove:
    source: Path
    target: Path


@dataclass(frozen=True)
class FileSnapshot:
    path: Path
    existed: bool
    content: bytes


class DepartmentMigrationService:
    def __init__(self, store, employee_system, photo_root, thumbnail_root, office_root):
        self.store = store
        self.employee_system = employee_system
        self.photo_root = Path(photo_root)
        self.thumbnail_root = Path(thumbnail_root)
        self.office_root = Path(office_root)

    def list_departments(self) -> list[str]:
        departments = {
            *self.store.list_departments(),
            *self.employee_system.list_departments(),
        }
        for root in (self.photo_root, self.thumbnail_root):
            if root.exists():
                departments.update(path.name for path in root.iterdir() if path.is_dir())
        for category in UPLOAD_CATEGORY_CONFIG:
            root = self.office_root / category
            if root.exists():
                departments.update(path.name for path in root.iterdir() if path.is_dir())
        departments.update(
            normalize_department_name(item.get("department"))
            for item in read_upload_metadata(self.office_root).values()
            if isinstance(item, dict)
        )
        return sorted(name for name in departments if normalize_department_name(name))

    def get_usage(self, department: str) -> dict[str, int]:
        name = normalize_department_name(department)
        employees = 0
        permissions = 0
        for user in self.employee_system.get_all_employees():
            employees += int(user.department == name)
            permissions += sum(
                1
                for permission in user.permissions
                if (parsed := parse_matrix_permission(permission)) and parsed[1] == name
            )

        usage = {
            "employees": employees,
            "permissions": permissions,
            "photos": self._count_files(self.photo_root / name),
            "thumbnails": self._count_files(self.thumbnail_root / name),
            **{
                category: self._count_files(self.office_root / category / name)
                for category in UPLOAD_CATEGORY_CONFIG
            },
        }
        usage["metadata"] = sum(
            1
            for item in read_upload_metadata(self.office_root).values()
            if isinstance(item, dict) and normalize_department_name(item.get("department")) == name
        )
        return usage

    @staticmethod
    def has_usage(usage: dict[str, int]) -> bool:
        return any(value > 0 for value in usage.values())

    @staticmethod
    def _count_files(root: Path) -> int:
        if not root.exists():
            return 0
        return sum(1 for path in root.rglob("*") if path.is_file())

    def rename(self, source: str, target: str) -> dict[str, int]:
        source_name, target_name = self._validate_names(source, target)
        departments = self.list_departments()
        if source_name not in departments:
            raise ValueError("部门不存在")
        if target_name in departments:
            raise DepartmentMigrationConflict("目标部门已存在")
        return self._transfer(
            source_name,
            target_name,
            lambda: self._rename_store_department(source_name, target_name),
        )

    def merge_and_delete(self, source: str, target: str) -> dict[str, int]:
        source_name, target_name = self._validate_names(source, target)
        departments = self.list_departments()
        if source_name not in departments or target_name not in departments:
            raise ValueError("源部门或目标部门不存在")
        return self._transfer(
            source_name,
            target_name,
            lambda: self._merge_store_departments(source_name, target_name),
        )

    def _rename_store_department(self, source: str, target: str) -> None:
        stored = self.store.list_departments()
        if source in stored:
            self.store.rename_department(source, target)
        else:
            self.store.create_department(target)

    def _merge_store_departments(self, source: str, target: str) -> None:
        stored = self.store.list_departments()
        if target not in stored:
            self.store.create_department(target)
        if source in self.store.list_departments():
            self.store.delete_department(source)

    @staticmethod
    def _validate_names(source: str, target: str) -> tuple[str, str]:
        source_name = normalize_department_name(source)
        target_name = normalize_department_name(target)
        if not source_name or not target_name:
            raise ValueError("部门名称不能为空")
        if source_name == target_name:
            raise ValueError("目标部门不能与原部门相同")
        return source_name, target_name

    def _build_moves(self, source: str, target: str) -> list[FileMove]:
        root_pairs = [
            (self.photo_root / source, self.photo_root / target),
            (self.thumbnail_root / source, self.thumbnail_root / target),
            *[
                (self.office_root / category / source, self.office_root / category / target)
                for category in UPLOAD_CATEGORY_CONFIG
            ],
        ]
        moves = []
        for source_root, target_root in root_pairs:
            if not source_root.exists():
                continue
            for file in source_root.rglob("*"):
                if file.is_file():
                    moves.append(FileMove(file, target_root / file.relative_to(source_root)))

        conflicts = [move.target for move in moves if move.target.exists()]
        if conflicts:
            raise DepartmentMigrationConflict(f"目标位置已存在文件: {conflicts[0]}")
        return moves

    def _rewrite_metadata(self, source: str, target: str) -> dict:
        rewritten = {}
        for upload_id, original in read_upload_metadata(self.office_root).items():
            item = dict(original) if isinstance(original, dict) else original
            if isinstance(item, dict) and normalize_department_name(item.get("department")) == source:
                item["department"] = target
                path = PurePosixPath(item.get("path", ""))
                parts = list(path.parts)
                if len(parts) >= 2 and parts[1] == source:
                    parts[1] = target
                    item["path"] = PurePosixPath(*parts).as_posix()
            rewritten[upload_id] = item
        return rewritten

    @staticmethod
    def _snapshot(path: Path) -> FileSnapshot:
        return FileSnapshot(path, path.exists(), path.read_bytes() if path.exists() else b"")

    @staticmethod
    def _restore(snapshot: FileSnapshot) -> None:
        if snapshot.existed:
            snapshot.path.parent.mkdir(parents=True, exist_ok=True)
            snapshot.path.write_bytes(snapshot.content)
        else:
            snapshot.path.unlink(missing_ok=True)

    def _transfer(
        self,
        source: str,
        target: str,
        finalize_store: Callable[[], None],
    ) -> dict[str, int]:
        with DATA_MUTATION_LOCK:
            usage = self.get_usage(source)
            moves = self._build_moves(source, target)
            metadata = self._rewrite_metadata(source, target)
            metadata_path = self.office_root / ".metadata.json"
            snapshots = [
                self._snapshot(self.store.data_file),
                self._snapshot(self.employee_system.data_file),
                self._snapshot(metadata_path),
            ]
            completed = []
            try:
                for move in moves:
                    move.target.parent.mkdir(parents=True, exist_ok=True)
                    move.source.replace(move.target)
                    completed.append(move)
                if snapshots[2].existed or metadata:
                    write_upload_metadata(self.office_root, metadata)
                self.employee_system.rename_department(source, target)
                finalize_store()
                self._remove_empty_source_directories(source)
                return usage
            except Exception as error:
                rollback_errors = self._rollback(completed, snapshots)
                if rollback_errors:
                    logger.error(
                        "Department migration rollback failed for %s -> %s: %s",
                        source,
                        target,
                        rollback_errors,
                    )
                    raise DepartmentMigrationFailure("部门迁移失败且回滚不完整，需要人工检查") from error
                raise DepartmentMigrationFailure("部门迁移失败，已恢复原数据") from error

    def _rollback(self, completed: list[FileMove], snapshots: list[FileSnapshot]) -> list[Exception]:
        errors = []
        for move in reversed(completed):
            try:
                move.source.parent.mkdir(parents=True, exist_ok=True)
                move.target.replace(move.source)
            except Exception as error:
                errors.append(error)
        for snapshot in snapshots:
            try:
                self._restore(snapshot)
            except Exception as error:
                errors.append(error)
        try:
            self.employee_system.load_data()
        except Exception as error:
            errors.append(error)
        (self.office_root / ".metadata.json.tmp").unlink(missing_ok=True)
        return errors

    def _source_roots(self, source: str) -> list[Path]:
        return [
            self.photo_root / source,
            self.thumbnail_root / source,
            *[self.office_root / category / source for category in UPLOAD_CATEGORY_CONFIG],
        ]

    def _remove_empty_source_directories(self, source: str) -> None:
        for root in self._source_roots(source):
            if not root.exists():
                continue
            directories = sorted(
                (path for path in root.rglob("*") if path.is_dir()),
                key=lambda path: len(path.parts),
                reverse=True,
            )
            for directory in directories:
                try:
                    directory.rmdir()
                except OSError:
                    pass
            try:
                root.rmdir()
            except OSError:
                pass
