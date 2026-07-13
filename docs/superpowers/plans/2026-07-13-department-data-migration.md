# Department Data Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make department rename and deletion preserve all historical department-owned data, including photos and all office-upload categories.

**Architecture:** Add a backend `DepartmentMigrationService` that plans, validates, executes, and rolls back file and JSON changes as one serialized operation. Admin endpoints call the service for rename, usage inspection, direct delete, and merge-and-delete; the React department manager uses the usage endpoint to choose between direct deletion and transfer-before-delete.

**Tech Stack:** Python 3, FastAPI, pytest, pathlib/JSON filesystem storage, React 19, Vite, ESLint

---

## File Structure

- Create `photo-backend/services/department_migration_service.py`: usage reporting, move planning, conflict detection, JSON snapshots, execution, rollback, and source-directory cleanup.
- Modify `photo-backend/services/upload_service.py`: expose metadata read/write helpers and serialize upload/delete mutations with the lock shared by migrations.
- Modify `photo-backend/routers/admin.py`: construct the migration service and expose usage, rename, delete, and merge operations.
- Modify `photo-backend/tests/test_department_management.py`: service and endpoint regression coverage.
- Modify `photo-monitor/src/api.js`: usage and merge API calls.
- Modify `photo-monitor/src/App.jsx`: wire usage/merge handlers and refresh employees/departments.
- Modify `photo-monitor/src/components/DepartmentManagerPage.jsx`: direct-delete and transfer-delete dialog states.
- Modify `photo-monitor/src/index.css`: compact usage summary and delete dialog styling.
- Modify `docs/数据库设计说明书.md`, `docs/接口文档说明书.md`, and `docs/系统详细设计说明书.md`: document consistency and API behavior without overwriting unrelated user edits.

### Task 1: Migration Usage and File Planning

**Files:**
- Create: `photo-backend/services/department_migration_service.py`
- Modify: `photo-backend/services/upload_service.py`
- Test: `photo-backend/tests/test_department_management.py`

- [ ] **Step 1: Write failing usage and plan tests**

Add these helpers, then add the tests below:

```python
def write_file(path: Path, content: bytes = b"data") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def metadata_item(upload_id: str, category: str, department: str) -> dict:
    return {
        "id": upload_id,
        "name": f"{category}.txt",
        "category": category,
        "department": department,
        "path": f"{category}/{department}/2026_07_13/{category}.txt",
        "time": 1.0,
    }


def write_metadata(base: Path, metadata: dict) -> None:
    write_upload_metadata(base, metadata)


def make_migration_service(tmp_path: Path):
    store = DepartmentStore(tmp_path / "departments.json")
    system = EmployeeSystem(tmp_path / "users.json")
    photos = tmp_path / "photos"
    thumbnails = tmp_path / ".thumbnails"
    office = tmp_path / "office_data"
    service = DepartmentMigrationService(store, system, photos, thumbnails, office)
    return service, store, system, photos, thumbnails, office


def test_department_usage_counts_every_owned_resource(tmp_path: Path):
    service, _, system, photos, thumbnails, office = make_migration_service(tmp_path)
    system.create_employee({
        "username": "worker",
        "password": "worker",
        "department": "总公司",
        "permissions": ["perm:study_articles:总公司:read"],
    })
    write_file(photos / "总公司" / "上站" / "2026_07_13-2026_07_13" / "photo.jpg")
    write_file(thumbnails / "总公司" / "上站" / "2026_07_13-2026_07_13" / "photo.jpg")
    for category in UPLOAD_CATEGORY_CONFIG:
        write_file(office / category / "总公司" / "2026_07_13" / f"{category}.txt")
    write_metadata(office, {
        "study-id": metadata_item("study-id", "study_articles", "总公司")
    })

    usage = service.get_usage("总公司")

    assert usage == {
        "employees": 1,
        "permissions": 1,
        "photos": 1,
        "thumbnails": 1,
        "company_files": 1,
        "study_articles": 1,
        "ledgers": 1,
        "metadata": 1,
    }
    assert service.has_usage(usage) is True


def test_department_plan_rejects_destination_collision_without_mutation(tmp_path: Path):
    service, store, _, photos, _, _ = make_migration_service(tmp_path)
    store.create_department("总公司")
    source = photos / "总公司" / "上站" / "day" / "photo.jpg"
    target = photos / "总部" / "上站" / "day" / "photo.jpg"
    write_file(source, b"source")
    write_file(target, b"target")

    with pytest.raises(DepartmentMigrationConflict, match="目标位置已存在文件"):
        service.rename("总公司", "总部")

    assert source.read_bytes() == b"source"
    assert target.read_bytes() == b"target"
    assert store.list_departments() == ["总公司"]
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `cd photo-backend && pytest tests/test_department_management.py -k "usage_counts or destination_collision" -v`

Expected: FAIL because `services.department_migration_service` does not exist.

- [ ] **Step 3: Expose metadata helpers and shared mutation lock**

In `upload_service.py`, add:

```python
from threading import RLock

DATA_MUTATION_LOCK = RLock()


def read_upload_metadata(base: Path) -> dict:
    import json

    path = _metadata_path(base)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def write_upload_metadata(base: Path, metadata: dict) -> None:
    import json

    base.mkdir(parents=True, exist_ok=True)
    path = _metadata_path(base)
    temp_path = path.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
    temp_path.replace(path)
```

Replace internal `_read_metadata` and `_write_metadata` calls with these public names. Wrap `save_photo_upload_file`, `save_data_upload_file`, and `delete_data_upload` mutation sections in `with DATA_MUTATION_LOCK:` without changing validation or response shapes.

- [ ] **Step 4: Implement usage reporting and preflight planning**

Create the service module with these concrete types and methods:

```python
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable

from services.auth_service import EmployeeSystem, parse_matrix_permission
from services.department_service import DepartmentStore, normalize_department_name
from services.upload_service import (
    DATA_MUTATION_LOCK,
    UPLOAD_CATEGORY_CONFIG,
    read_upload_metadata,
    write_upload_metadata,
)


class DepartmentMigrationConflict(ValueError):
    pass


class DepartmentMigrationFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class FileMove:
    source: Path
    target: Path


class DepartmentMigrationService:
    def __init__(self, store, employee_system, photo_root, thumbnail_root, office_root):
        self.store = store
        self.employee_system = employee_system
        self.photo_root = Path(photo_root)
        self.thumbnail_root = Path(thumbnail_root)
        self.office_root = Path(office_root)

    def get_usage(self, department: str) -> dict[str, int]:
        name = normalize_department_name(department)
        employees = 0
        permissions = 0
        for user in self.employee_system.get_all_employees():
            employees += int(user.department == name)
            permissions += sum(
                1 for permission in user.permissions
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
            1 for item in read_upload_metadata(self.office_root).values()
            if isinstance(item, dict) and normalize_department_name(item.get("department")) == name
        )
        return usage

    @staticmethod
    def has_usage(usage: dict[str, int]) -> bool:
        return any(value > 0 for value in usage.values())

    @staticmethod
    def _count_files(root: Path) -> int:
        return sum(1 for path in root.rglob("*") if path.is_file()) if root.exists() else 0

    def _build_moves(self, source: str, target: str) -> list[FileMove]:
        pairs = [
            (self.photo_root / source, self.photo_root / target),
            (self.thumbnail_root / source, self.thumbnail_root / target),
            *[
                (self.office_root / category / source, self.office_root / category / target)
                for category in UPLOAD_CATEGORY_CONFIG
            ],
        ]
        moves = []
        for source_root, target_root in pairs:
            if not source_root.exists():
                continue
            for file in source_root.rglob("*"):
                if file.is_file():
                    moves.append(FileMove(file, target_root / file.relative_to(source_root)))
        conflicts = [move.target for move in moves if move.target.exists()]
        if conflicts:
            raise DepartmentMigrationConflict(f"目标位置已存在文件: {conflicts[0]}")
        return moves
```

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `cd photo-backend && pytest tests/test_department_management.py -k "usage_counts or destination_collision" -v`

Expected: both tests PASS.

- [ ] **Step 6: Commit usage and planning foundation**

```bash
git add photo-backend/services/department_migration_service.py photo-backend/services/upload_service.py photo-backend/tests/test_department_management.py docs/superpowers/plans/2026-07-13-department-data-migration.md
git commit -m "feat: plan department data migrations"
```

### Task 2: Transactional Rename and Merge

**Files:**
- Modify: `photo-backend/services/department_migration_service.py`
- Test: `photo-backend/tests/test_department_management.py`

- [ ] **Step 1: Write failing rename, merge, legacy, and rollback tests**

Add tests that create one file in every root, including an office file not present in metadata. Assert:

```python
service.rename("总公司", "总部")
assert store.list_departments() == ["总部"]
assert system.get_user("worker").department == "总部"
assert "perm:study_articles:总部:read" in system.get_user("worker").permissions
assert not (photos / "总公司").exists()
assert (photos / "总部" / "上站" / "day" / "photo.jpg").is_file()
assert (thumbnails / "总部" / "上站" / "day" / "photo.jpg").is_file()
for category in UPLOAD_CATEGORY_CONFIG:
    assert (office / category / "总部" / "2026_07_13" / f"{category}.txt").is_file()
metadata = read_upload_metadata(office)
assert metadata["study-id"]["department"] == "总部"
assert metadata["study-id"]["path"] == "study_articles/总部/2026_07_13/study_articles.txt"
assert metadata["study-id"]["id"] == "study-id"
```

Add a merge test where both departments exist and their relative file paths do not collide; assert the target remains and source is removed. Add a rollback test by monkeypatching `store.rename_department` to raise after moves and assert all files and JSON bytes exactly match their pre-operation snapshots.

- [ ] **Step 2: Run transactional tests and verify RED**

Run: `cd photo-backend && pytest tests/test_department_management.py -k "migration_rename or migration_merge or migration_rollback" -v`

Expected: FAIL because transaction execution is not implemented.

- [ ] **Step 3: Implement metadata rewriting, snapshots, execution, and rollback**

Add to the migration service:

```python
@dataclass(frozen=True)
class FileSnapshot:
    path: Path
    existed: bool
    content: bytes


def _snapshot(self, path: Path) -> FileSnapshot:
    return FileSnapshot(path, path.exists(), path.read_bytes() if path.exists() else b"")


def _restore(self, snapshot: FileSnapshot) -> None:
    if snapshot.existed:
        snapshot.path.parent.mkdir(parents=True, exist_ok=True)
        snapshot.path.write_bytes(snapshot.content)
    else:
        snapshot.path.unlink(missing_ok=True)


def _rewrite_metadata(self, source: str, target: str) -> dict:
    metadata = read_upload_metadata(self.office_root)
    rewritten = {}
    for upload_id, original in metadata.items():
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


def rename(self, source: str, target: str) -> dict[str, int]:
    source, target = self._validate_names(source, target)
    departments = self.store.list_departments()
    if source not in departments:
        raise ValueError("部门不存在")
    if target in departments:
        raise DepartmentMigrationConflict("目标部门已存在")
    return self._transfer(source, target, lambda: self.store.rename_department(source, target))


def merge_and_delete(self, source: str, target: str) -> dict[str, int]:
    source, target = self._validate_names(source, target)
    departments = self.store.list_departments()
    if source not in departments or target not in departments:
        raise ValueError("源部门或目标部门不存在")
    return self._transfer(source, target, lambda: self.store.delete_department(source))


def _transfer(self, source: str, target: str, finalize_store: Callable[[], None]) -> dict[str, int]:
    with DATA_MUTATION_LOCK:
        moves = self._build_moves(source, target)
        metadata = self._rewrite_metadata(source, target)
        snapshots = [
            self._snapshot(self.store.data_file),
            self._snapshot(self.employee_system.data_file),
            self._snapshot(self.office_root / ".metadata.json"),
        ]
        completed = []
        usage = self.get_usage(source)
        try:
            for move in moves:
                move.target.parent.mkdir(parents=True, exist_ok=True)
                move.source.replace(move.target)
                completed.append(move)
            write_upload_metadata(self.office_root, metadata)
            self.employee_system.rename_department(source, target)
            finalize_store()
            self._remove_empty_source_directories(source)
            return usage
        except Exception as error:
            rollback_errors = []
            for move in reversed(completed):
                try:
                    move.source.parent.mkdir(parents=True, exist_ok=True)
                    move.target.replace(move.source)
                except Exception as rollback_error:
                    rollback_errors.append(rollback_error)
            for snapshot in snapshots:
                try:
                    self._restore(snapshot)
                except Exception as rollback_error:
                    rollback_errors.append(rollback_error)
            if rollback_errors:
                raise DepartmentMigrationFailure("部门迁移失败且回滚不完整，需要人工检查") from error
            raise DepartmentMigrationFailure("部门迁移失败，已恢复原数据") from error
```

Add the validation and cleanup methods:

```python
def _validate_names(self, source: str, target: str) -> tuple[str, str]:
    source_name = normalize_department_name(source)
    target_name = normalize_department_name(target)
    if not source_name or not target_name:
        raise ValueError("部门名称不能为空")
    if source_name == target_name:
        raise ValueError("目标部门不能与原部门相同")
    return source_name, target_name


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
```

- [ ] **Step 4: Run transactional tests and verify GREEN**

Run: `cd photo-backend && pytest tests/test_department_management.py -k "migration_rename or migration_merge or migration_rollback" -v`

Expected: all transactional tests PASS.

- [ ] **Step 5: Run all department tests**

Run: `cd photo-backend && pytest tests/test_department_management.py -v`

Expected: all tests PASS.

- [ ] **Step 6: Commit transaction implementation**

```bash
git add photo-backend/services/department_migration_service.py photo-backend/tests/test_department_management.py
git commit -m "feat: migrate department files transactionally"
```

### Task 3: Admin Migration API

**Files:**
- Modify: `photo-backend/routers/admin.py`
- Test: `photo-backend/tests/test_department_management.py`

- [ ] **Step 1: Write failing endpoint tests**

Extend the admin endpoint fixture to monkeypatch `OFFICE_DATA_DIR`, `PHOTO_DATA_DIR`, and `THUMBNAIL_DATA_DIR`. Add tests:

```python
usage_response = client.get("/admin/departments/总公司/usage", headers=headers)
assert usage_response.status_code == 200
assert usage_response.json()["usage"]["study_articles"] == 1

blocked = client.delete("/admin/departments/总公司", headers=headers)
assert blocked.status_code == 409
assert blocked.json()["detail"]["usage"]["study_articles"] == 1

merged = client.post(
    "/admin/departments/总公司/merge",
    json={"target": "总部"},
    headers=headers,
)
assert merged.status_code == 200
assert merged.json()["departments"] == ["总部"]
```

Keep and update the existing direct-delete assertion so an unused department still returns 200.

- [ ] **Step 2: Run endpoint tests and verify RED**

Run: `cd photo-backend && pytest tests/test_department_management.py -k "admin_department" -v`

Expected: FAIL with 404 for usage/merge and the old 400 delete response shape.

- [ ] **Step 3: Route all mutations through the migration service**

Add roots, payload, and factory:

```python
PHOTO_DATA_DIR = Path(__file__).resolve().parents[1] / "photos"
THUMBNAIL_DATA_DIR = Path(__file__).resolve().parents[1] / ".thumbnails"


class DepartmentMergePayload(BaseModel):
    target: str


def _migration_service() -> DepartmentMigrationService:
    return DepartmentMigrationService(
        department_store,
        employee_system,
        PHOTO_DATA_DIR,
        THUMBNAIL_DATA_DIR,
        OFFICE_DATA_DIR,
    )
```

Change rename to `service.rename(name, payload.name)`. Add usage and merge endpoints. Change direct delete to:

```python
usage = service.get_usage(name)
if service.has_usage(usage):
    raise HTTPException(
        status_code=409,
        detail={"message": "部门仍有关联数据，请选择目标部门迁移后删除", "usage": usage},
    )
department_store.delete_department(name)
```

Map `DepartmentMigrationConflict` to 409, validation errors to 400, and `DepartmentMigrationFailure` to 500.

- [ ] **Step 4: Run endpoint and full backend tests**

Run: `cd photo-backend && pytest tests/test_department_management.py -v`

Expected: PASS.

Run: `cd photo-backend && pytest -q`

Expected: full suite PASS with no errors.

- [ ] **Step 5: Commit API behavior**

```bash
git add photo-backend/routers/admin.py photo-backend/tests/test_department_management.py
git commit -m "feat: add safe department merge deletion"
```

### Task 4: Department Delete and Transfer UI

**Files:**
- Modify: `photo-monitor/src/api.js`
- Modify: `photo-monitor/src/App.jsx`
- Modify: `photo-monitor/src/components/DepartmentManagerPage.jsx`
- Modify: `photo-monitor/src/index.css`

- [ ] **Step 1: Add API and App handlers**

In `api.js` add:

```javascript
export function getDepartmentUsage(name) {
  return request(`/admin/departments/${encodeURIComponent(name)}/usage`)
}

export function mergeDepartment(name, payload) {
  return request(`/admin/departments/${encodeURIComponent(name)}/merge`, {
    method: "POST",
    body: JSON.stringify(payload),
  })
}
```

Import both in `App.jsx` and add:

```javascript
const handleGetDepartmentUsage = async (name) => {
  const result = await getDepartmentUsage(name)
  return result.usage
}

const handleMergeDepartment = async (name, target) => {
  const result = await mergeDepartment(name, { target })
  setDepartments(result.departments)
  await loadEmployees()
  showBanner("部门数据已迁移，原部门已删除")
}
```

Pass them to `DepartmentManagerPage` as `onGetUsage={handleGetDepartmentUsage}` and `onMerge={handleMergeDepartment}`.

- [ ] **Step 2: Implement accessible transfer dialog**

In `DepartmentManagerPage.jsx`, add `deleteState` with `{ name, usage, target }`. On delete click, load usage. If no value is positive, use the existing confirmation and direct delete. Otherwise display a modal with:

```jsx
<div className="modal-backdrop" onClick={closeDeleteDialog}>
  <section
    className="modal-card side-modal modal-card-enter department-delete-modal"
    role="dialog"
    aria-modal="true"
    aria-labelledby="department-delete-title"
    onClick={(event) => event.stopPropagation()}
  >
    <div className="modal-header">
      <h3 id="department-delete-title">迁移并删除部门</h3>
      <button type="button" className="modal-close" aria-label="关闭" onClick={closeDeleteDialog}>×</button>
    </div>
    <div className="department-usage-grid">
      {USAGE_LABELS.map(([key, label]) => (
        <div key={key}><span>{label}</span><strong>{deleteState.usage[key] || 0}</strong></div>
      ))}
    </div>
    <label className="field">
      <span>迁移到</span>
      <select value={deleteState.target} onChange={handleTargetChange}>
        <option value="">请选择目标部门</option>
        {departments.filter((item) => item !== deleteState.name).map((item) => (
          <option key={item} value={item}>{item}</option>
        ))}
      </select>
    </label>
    <button
      type="button"
      className="primary-button danger-button"
      disabled={saving || !deleteState.target}
      onClick={handleMergeDelete}
    >
      {saving ? "迁移中..." : "迁移并删除"}
    </button>
  </section>
</div>
```

Use labels for employees, permissions, photos, company files, study articles, and ledgers. Do not show thumbnails and metadata as separate user concepts; include them in the backend operation while displaying primary-data counts.

- [ ] **Step 3: Add stable responsive styling**

Add these rules without changing unrelated palette or layout declarations:

```css
.department-delete-modal {
  width: min(460px, calc(100vw - 32px));
}

.department-usage-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 16px 0;
}

.department-usage-grid > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 40px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 6px;
}

@media (max-width: 520px) {
  .department-usage-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 4: Run frontend static verification**

Run: `cd photo-monitor && npm run lint`

Expected: exit 0, no ESLint errors.

Run: `cd photo-monitor && npm run build`

Expected: exit 0 and Vite emits the production bundle.

- [ ] **Step 5: Commit frontend workflow**

```bash
git add photo-monitor/src/api.js photo-monitor/src/App.jsx photo-monitor/src/components/DepartmentManagerPage.jsx photo-monitor/src/index.css
git commit -m "feat: transfer data before department deletion"
```

### Task 5: Documentation, Verification, and Delivery

**Files:**
- Modify: `docs/数据库设计说明书.md`
- Modify: `docs/接口文档说明书.md`
- Modify: `docs/系统详细设计说明书.md`

- [ ] **Step 1: Update existing documentation in place**

Document the expanded rename consistency list, usage endpoint, merge endpoint, 409 response, collision rule, and rollback behavior. Preserve all unrelated working-tree edits by applying narrow patches only around department consistency/API sections.

- [ ] **Step 2: Run the complete verification suite**

Run: `cd photo-backend && pytest -q`

Expected: all backend tests PASS.

Run: `cd photo-monitor && npm run lint`

Expected: exit 0.

Run: `cd photo-monitor && npm run build`

Expected: exit 0.

Run: `git diff --check`

Expected: no whitespace errors in implementation files. If unrelated user-edited files have pre-existing findings, scope the command to files changed by this implementation and report that distinction.

- [ ] **Step 3: Audit scope before the final commit**

Run `git status --short`, `git diff --name-only`, and `git diff --cached --name-only`. Confirm user-owned photo deletions and unrelated documentation changes are not accidentally staged. Inspect the complete implementation diff.

- [ ] **Step 4: Commit remaining docs and verified changes**

```bash
git add docs/数据库设计说明书.md docs/接口文档说明书.md docs/系统详细设计说明书.md
git commit -m "docs: document department migration behavior"
```

- [ ] **Step 5: Push and verify remote synchronization**

Run: `git push origin main`

Expected: push succeeds.

Run: `git rev-parse HEAD` and `git ls-remote origin refs/heads/main`

Expected: local `HEAD` equals the remote `main` hash.
