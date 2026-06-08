from __future__ import annotations

import json
from pathlib import Path


def normalize_department_name(value: str | None) -> str:
    return (value or "").strip()


class DepartmentStore:
    def __init__(self, data_file: Path | None = None):
        backend_root = Path(__file__).resolve().parents[1]
        self.data_file = data_file or backend_root / "departments.json"

    def list_departments(self) -> list[str]:
        if not self.data_file.exists():
            return []
        with self.data_file.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, list):
            return []
        return sorted(dict.fromkeys(normalize_department_name(item) for item in data if normalize_department_name(item)))

    def create_department(self, name: str) -> str:
        normalized = self._validate_name(name)
        departments = self.list_departments()
        if normalized in departments:
            raise ValueError("部门已存在")
        self._save_departments([*departments, normalized])
        return normalized

    def rename_department(self, old_name: str, new_name: str) -> str:
        old_normalized = self._validate_name(old_name)
        new_normalized = self._validate_name(new_name)
        departments = self.list_departments()
        if old_normalized not in departments:
            raise ValueError("部门不存在")
        if new_normalized != old_normalized and new_normalized in departments:
            raise ValueError("部门已存在")
        self._save_departments([new_normalized if item == old_normalized else item for item in departments])
        return new_normalized

    def delete_department(self, name: str) -> None:
        normalized = self._validate_name(name)
        departments = self.list_departments()
        if normalized not in departments:
            raise ValueError("部门不存在")
        self._save_departments([item for item in departments if item != normalized])

    def _save_departments(self, departments: list[str]) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with self.data_file.open("w", encoding="utf-8") as file:
            json.dump(sorted(dict.fromkeys(departments)), file, ensure_ascii=False, indent=2)

    def _validate_name(self, name: str | None) -> str:
        normalized = normalize_department_name(name)
        if not normalized:
            raise ValueError("部门名称不能为空")
        return normalized
