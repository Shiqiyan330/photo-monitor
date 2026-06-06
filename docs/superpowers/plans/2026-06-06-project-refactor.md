# Project Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the project in phases so quality gates pass, backend security boundaries are explicit, frontend responsibilities are split, stale code is removed, and five server-side test scenarios are covered.

**Architecture:** Backend work starts by making tests runnable, then introduces auth/resource security behind focused service helpers. Frontend work keeps behavior stable while extracting permissions, hooks, and page modules from `src/App.jsx`.

**Tech Stack:** FastAPI, PyJWT, Python stdlib password hashing, pytest, React, Vite, ESLint.

---

## File Structure

- Modify `photo-backend/pytest.ini`: make `pytest -q` resolve local modules.
- Modify `photo-backend/services/auth_service.py`: add config-driven JWT secret, password hashing, legacy migration, safe public payloads, and admin reset support.
- Modify `photo-backend/routers/auth.py`: preserve login and password change behavior while using hashed password storage.
- Modify `photo-backend/routers/admin.py`: stop returning passwords and expose reset-password semantics.
- Modify `photo-backend/routers/deps.py`: centralize bearer token extraction and matrix permission dependency helpers.
- Modify `photo-backend/routers/photo.py`: serve authenticated photo and thumbnail resources.
- Modify `photo-backend/main.py`: remove unauthenticated `/static` photo mount.
- Modify `photo-backend/routers/upload.py`: reuse centralized auth helpers and preserve token query support for inline viewing.
- Modify `photo-backend/tests/test_permission_matrix.py`: adjust password exposure expectations.
- Create `photo-backend/tests/test_security_refactor.py`: five required server-side scenarios.
- Modify `photo-monitor/src/api.js`: update photo and thumbnail URLs and centralize authorized view URLs.
- Create `photo-monitor/src/permissions.js`: permission parsing and checks.
- Create `photo-monitor/src/pages/DashboardPage.jsx`: dashboard page.
- Create `photo-monitor/src/pages/OfficeUploadPage.jsx`: reusable office upload page.
- Create `photo-monitor/src/pages/StructurePage.jsx`: structure page.
- Create `photo-monitor/src/pages/MonitorPage.jsx`: monitor page.
- Create `photo-monitor/src/hooks/useAuth.js`: auth/session state.
- Create `photo-monitor/src/hooks/usePhotoFeed.js`: photo feed state, pagination, dedupe, WebSocket refresh.
- Create `photo-monitor/src/hooks/useOfficeUploads.js`: shared upload/list/delete state.
- Modify `photo-monitor/src/App.jsx`: top-level routing and page composition only.
- Delete `photo-monitor/pages/home.jsx`, `photo-monitor/hooks/usePhotos.js`, and `photo-monitor/hooks/useWebsockets.js` after replacements are in place.
- Modify `.gitignore`: ignore Python caches, pytest cache, frontend dist, and thumbnail cache.
- Modify `photo-monitor/README.md`: document focused local verification.

---

### Task 1: Quality Gate Stopgap

**Files:**
- Modify: `photo-monitor/src/components/EmployeeManagerPage.jsx`
- Create: `photo-backend/pytest.ini`
- Modify: `.gitignore`

- [ ] **Step 1: Verify current frontend lint failure**

Run from `photo-monitor`:

```powershell
npm run lint
```

Expected: FAIL mentioning `syncDefaultStructurePermission` is not defined.

- [ ] **Step 2: Restore the missing helper**

Add this helper after `isConcreteMatrixPermission` in `photo-monitor/src/components/EmployeeManagerPage.jsx`:

```jsx
function syncDefaultStructurePermission(permissions, department) {
  const normalizedDepartment = (department || "").trim()
  const nonStructurePermissions = permissions.filter((permission) => {
    const parsed = parseMatrixPermission(permission)
    return !parsed || parsed.system !== "structure"
  })

  if (!normalizedDepartment) {
    return nonStructurePermissions
  }

  return [
    ...nonStructurePermissions,
    buildMatrixPermission("structure", normalizedDepartment, "read"),
  ]
}
```

- [ ] **Step 3: Add pytest import path config**

Create `photo-backend/pytest.ini`:

```ini
[pytest]
pythonpath = .
```

- [ ] **Step 4: Ignore generated files**

Ensure `.gitignore` contains:

```gitignore
photo-backend/photos
photo-backend/.thumbnails
photo-backend/__pycache__/
photo-backend/**/__pycache__/
photo-backend/.pytest_cache/
photo-monitor/dist/
photo-monitor/node_modules/
```

- [ ] **Step 5: Run focused quality gates**

Run from `photo-monitor` for npm commands and from `photo-backend` for pytest:

```powershell
npm run lint
npm run build
pytest -q
```

Expected: frontend lint passes, frontend build passes, backend tests pass.

- [ ] **Step 6: Commit**

```powershell
git add .gitignore photo-backend/pytest.ini photo-monitor/src/components/EmployeeManagerPage.jsx
git commit -m "chore: restore quality gates"
```

Do not add `__pycache__` files.

---

### Task 2: Backend Auth Hardening

**Files:**
- Modify: `photo-backend/services/auth_service.py`
- Modify: `photo-backend/routers/auth.py`
- Modify: `photo-backend/routers/admin.py`
- Modify: `photo-backend/tests/test_permission_matrix.py`
- Create: `photo-backend/tests/test_security_refactor.py`

- [ ] **Step 1: Add failing password exposure test**

In `photo-backend/tests/test_security_refactor.py`, add:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from main import app
from services.auth_service import EmployeeSystem, build_matrix_permission


def make_employee_system(tmp_path: Path) -> EmployeeSystem:
    return EmployeeSystem(tmp_path / "users.json")


def test_admin_employee_payloads_do_not_expose_passwords(tmp_path, monkeypatch):
    from routers import admin, auth, deps, structure, upload, ws

    system = make_employee_system(tmp_path)
    system.create_employee(
        {
            "username": "worker",
            "password": "secret123",
            "department": "ops",
            "permissions": [build_matrix_permission("photos", "ops", "read")],
        }
    )
    monkeypatch.setattr(admin, "employee_system", system)
    monkeypatch.setattr(auth, "employee_system", system)
    monkeypatch.setattr(deps, "employee_system", system)
    monkeypatch.setattr(structure, "employee_system", system)
    monkeypatch.setattr(upload, "employee_system", system)
    monkeypatch.setattr(ws, "employee_system", system)

    token = system.create_access_token("admin")
    client = TestClient(app)
    response = client.get("/admin/employees", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    employee = response.json()["employees"][0]
    assert "password" not in employee
```

- [ ] **Step 2: Run test to verify RED**

Run from `photo-backend`:

```powershell
pytest tests/test_security_refactor.py::test_admin_employee_payloads_do_not_expose_passwords -q
```

Expected: FAIL because admin payload still includes `password`.

- [ ] **Step 3: Add password hashing helpers**

In `photo-backend/services/auth_service.py`, import `base64`, `hmac`, `os`, `hashlib`, and add constants/functions near auth constants:

```python
PASSWORD_HASH_PREFIX = "pbkdf2_sha256$"
PASSWORD_ITERATIONS = 260000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return "$".join(
        [
            PASSWORD_HASH_PREFIX.rstrip("$"),
            str(PASSWORD_ITERATIONS),
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        ]
    )


def is_hashed_password(value: str) -> bool:
    return isinstance(value, str) and value.startswith(PASSWORD_HASH_PREFIX)


def verify_password(password: str, stored_password: str) -> bool:
    if not is_hashed_password(stored_password):
        return hmac.compare_digest(stored_password, password)

    try:
        _, iterations, salt_text, digest_text = stored_password.split("$", 3)
        salt = base64.b64decode(salt_text.encode("ascii"))
        expected = base64.b64decode(digest_text.encode("ascii"))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)
```

- [ ] **Step 4: Store hashed passwords for new and changed passwords**

In `EmployeeSystem.create_employee`, set `password=hash_password(password)`.

In `EmployeeSystem.update_employee`, when a non-empty password is accepted, set `user.password = hash_password(password)`.

In `EmployeeSystem.change_password`, set `user.password = hash_password(new_password)`.

In `EmployeeSystem.admin_reset_password`, set `user.password = hash_password(new_password)`.

- [ ] **Step 5: Support legacy login migration**

Replace `User.check_password` with:

```python
def check_password(self, password: str) -> bool:
    return verify_password(password, self.password)
```

In `EmployeeSystem.authenticate`, after a successful plaintext legacy login, migrate:

```python
if user.username == username and user.check_password(password):
    if not is_hashed_password(user.password):
        user.password = hash_password(password)
        self.save_data()
    return user
```

- [ ] **Step 6: Stop exposing passwords**

Remove `include_sensitive` behavior from public API output by changing admin routes to call `to_public_dict()` without `include_sensitive=True`.

Keep `to_public_dict(include_sensitive=False)` signature for compatibility, but do not include `password` even when `include_sensitive` is true.

- [ ] **Step 7: Add failing legacy migration test**

Add to `photo-backend/tests/test_security_refactor.py`:

```python
def test_legacy_plaintext_password_is_migrated_after_login(tmp_path):
    system = make_employee_system(tmp_path)
    user = system.create_employee(
        {
            "username": "legacy",
            "password": "legacy123",
            "department": "ops",
            "permissions": [],
        }
    )
    user.password = "legacy123"
    system.save_data()

    assert system.authenticate("legacy", "legacy123")
    migrated = system.get_user("legacy")
    assert migrated.password.startswith("pbkdf2_sha256$")
    assert migrated.password != "legacy123"
```

- [ ] **Step 8: Add JWT environment secret test**

Add to `photo-backend/tests/test_security_refactor.py`:

```python
def test_jwt_uses_configured_environment_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("PHOTO_MONITOR_JWT_SECRET", "configured-secret")
    from services import auth_service

    system = make_employee_system(tmp_path)
    token = system.create_access_token("admin")

    decoded = auth_service.jwt.decode(
        token,
        "configured-secret",
        algorithms=[auth_service.JWT_ALGORITHM],
        issuer=auth_service.JWT_ISSUER,
        audience=auth_service.JWT_AUDIENCE,
    )
    assert decoded["sub"] == "admin"
```

- [ ] **Step 9: Read JWT secret from environment**

In `auth_service.py`, replace hard-coded secret with:

```python
JWT_SECRET = os.getenv("PHOTO_MONITOR_JWT_SECRET", "photo-monitor-dev-secret-change-me")
```

- [ ] **Step 10: Run backend security tests**

Run from `photo-backend`:

```powershell
pytest tests/test_security_refactor.py -q
pytest tests/test_permission_matrix.py -q
```

Expected: all selected backend tests pass.

- [ ] **Step 11: Commit**

```powershell
git add photo-backend/services/auth_service.py photo-backend/routers/auth.py photo-backend/routers/admin.py photo-backend/tests/test_permission_matrix.py photo-backend/tests/test_security_refactor.py
git commit -m "feat: harden backend authentication"
```

---

### Task 3: Backend Resource Access Hardening

**Files:**
- Modify: `photo-backend/routers/deps.py`
- Modify: `photo-backend/routers/photo.py`
- Modify: `photo-backend/main.py`
- Modify: `photo-backend/routers/upload.py`
- Modify: `photo-backend/tests/test_security_refactor.py`
- Modify: `photo-monitor/src/api.js`

- [ ] **Step 1: Add failing authenticated photo resource test**

Add to `photo-backend/tests/test_security_refactor.py`:

```python
def test_photo_resource_requires_matching_read_permission(tmp_path, monkeypatch):
    from routers import photo

    base = tmp_path / "photos"
    target = base / "ops" / "xiazhan" / "2026_06_06-2026_06_06" / "camera_20260606120000_001.jpg"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"not-a-real-image-but-downloadable")
    monkeypatch.setattr(photo, "BASE", base)

    system = make_employee_system(tmp_path)
    system.create_employee(
        {
            "username": "viewer",
            "password": "viewer123",
            "department": "ops",
            "permissions": [build_matrix_permission("photos", "ops", "read")],
        }
    )
    token = system.create_access_token("viewer")

    client = TestClient(app)
    unauthenticated = client.get("/photos/resource/ops/xiazhan/2026_06_06-2026_06_06/camera_20260606120000_001.jpg")
    allowed = client.get(
        "/photos/resource/ops/xiazhan/2026_06_06-2026_06_06/camera_20260606120000_001.jpg",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert unauthenticated.status_code == 401
    assert allowed.status_code == 200
```

- [ ] **Step 2: Run test to verify RED**

Run from `photo-backend`:

```powershell
pytest tests/test_security_refactor.py::test_photo_resource_requires_matching_read_permission -q
```

Expected: FAIL because `/photos/resource/...` does not exist yet.

- [ ] **Step 3: Add reusable auth helpers**

In `photo-backend/routers/deps.py`, expose:

```python
def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


def get_user_from_token(token: str | None) -> dict | None:
    user = employee_system.get_user_by_token(token)
    return user.to_public_dict() if user else None


def require_matrix_action(user: dict, system: str, actions: set[str], detail: str) -> dict:
    if user["role"] != "admin" and not user_has_any_matrix_permission(user, system, actions):
        raise HTTPException(status_code=403, detail=detail)
    return user
```

Update `require_login` to call `extract_bearer_token`.

- [ ] **Step 4: Add authenticated photo resource route**

In `photo-backend/routers/photo.py`, add:

```python
@router.get("/photos/resource/{file_path:path}")
def get_photo_resource(file_path: str, user=Depends(require_camera_access)):
    source = (BASE / file_path).resolve()
    base = BASE.resolve()
    if base not in source.parents or source.suffix.lower() not in IMG_EXTS or not source.is_file():
        raise HTTPException(status_code=404, detail="Photo not found")

    relative_path = source.relative_to(base)
    department = relative_path.parts[0] if len(relative_path.parts) > 2 else ""
    accessible_departments = _get_accessible_departments(user)
    if department and user["role"] != "admin" and department not in accessible_departments:
        raise HTTPException(status_code=403, detail="No permission to view this department")

    return FileResponse(source)
```

- [ ] **Step 5: Update photo URLs**

In `photo-backend/services/photo_service.py`, change photo URLs from `/static/{path}` to `/photos/resource/{path}` and keep thumbnail URLs under `/thumbnails/{path}`.

- [ ] **Step 6: Protect thumbnails**

Update `get_thumbnail` in `photo.py` to depend on `require_camera_access` and perform the same department check as `get_photo_resource`.

- [ ] **Step 7: Remove raw photo static mount**

In `photo-backend/main.py`, remove:

```python
app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")
```

Keep `/office-data` only if legacy non-sensitive office data URLs must remain available for old metadata fallback.

- [ ] **Step 8: Add upload permission scenario**

Add to `photo-backend/tests/test_security_refactor.py`:

```python
def test_upload_file_access_respects_department_and_action_permissions(tmp_path):
    from services.upload_service import delete_data_upload, save_data_upload_file
    from starlette.datastructures import Headers
    from tempfile import SpooledTemporaryFile
    from fastapi import UploadFile
    from fastapi import HTTPException
    import pytest

    base = tmp_path / "office"
    user = {
        "role": "employee",
        "username": "uploader",
        "department": "ops",
        "permissions": [
            build_matrix_permission("company_files", "ops", "create"),
            build_matrix_permission("company_files", "ops", "read"),
        ],
    }
    file_obj = SpooledTemporaryFile()
    file_obj.write(b"hello")
    file_obj.seek(0)
    upload = UploadFile(filename="note.txt", file=file_obj, headers=Headers({"content-type": "text/plain"}))

    item = save_data_upload_file(base, "company_files", upload, "ops", user)

    with pytest.raises(HTTPException):
        delete_data_upload(base, "company_files", item["id"], user)
```

- [ ] **Step 9: Update frontend resource helpers**

In `photo-monitor/src/api.js`, keep `getAuthorizedUrl(path)`.

In `photo-monitor/src/components/PhotoGrid.jsx` and `photo-monitor/src/components/PhotoModal.jsx`, wrap image `src` values with `getAuthorizedUrl(getAssetUrl(...))` so browser image requests carry token query access because `img` cannot send custom Authorization headers.

- [ ] **Step 10: Run focused checks**

Run from `photo-backend`:

```powershell
pytest tests/test_security_refactor.py -q
npm run build
```

Expected: backend security tests pass and frontend build passes.

- [ ] **Step 11: Commit**

```powershell
git add photo-backend/routers/deps.py photo-backend/routers/photo.py photo-backend/main.py photo-backend/routers/upload.py photo-backend/services/photo_service.py photo-backend/tests/test_security_refactor.py photo-monitor/src/api.js
git commit -m "feat: protect backend resource access"
```

---

### Task 4: Frontend Permission and Hook Extraction

**Files:**
- Create: `photo-monitor/src/permissions.js`
- Create: `photo-monitor/src/hooks/useAuth.js`
- Create: `photo-monitor/src/hooks/usePhotoFeed.js`
- Create: `photo-monitor/src/hooks/useOfficeUploads.js`
- Modify: `photo-monitor/src/App.jsx`

- [ ] **Step 1: Extract permission helpers**

Create `photo-monitor/src/permissions.js` with:

```js
export function uniqueStrings(values) {
  return Array.from(new Set(values.map((item) => (item || "").trim()).filter(Boolean)))
}

export function parseMatrixPermission(permission) {
  if (typeof permission !== "string" || !permission.startsWith("perm:")) {
    return null
  }
  const parts = permission.slice(5).split(":")
  if (parts.length !== 3 || parts.some((item) => !item)) {
    return null
  }
  return { system: parts[0], department: parts[1], action: parts[2] }
}

export function hasMatrixPermission(user, system, action, department = "") {
  if (!user) {
    return false
  }
  if (user.role === "admin") {
    return true
  }
  const targetDepartment = department || "*"
  return (user.permissions ?? []).some((permission) => {
    const parsed = parseMatrixPermission(permission)
    if (!parsed || parsed.system !== system || parsed.action !== action) {
      return false
    }
    return parsed.department === "*" || parsed.department === targetDepartment
  })
}

export function hasAnyMatrixAction(user, system, actions) {
  if (!user) {
    return false
  }
  if (user.role === "admin") {
    return true
  }
  return (user.permissions ?? []).some((permission) => {
    const parsed = parseMatrixPermission(permission)
    return parsed && parsed.system === system && actions.includes(parsed.action)
  })
}

export function hasMatrixReadPermission(user, system) {
  return hasAnyMatrixAction(user, system, ["read"])
}
```

Move these existing helpers from `App.jsx` into this file: `getMatrixDepartments`, `isSameOrChildDepartment`, `getStructureVisibleDepartments`, `getDepartmentViewOptions`, `hasCameraPermission`, and `hasModuleAccess`.

- [ ] **Step 2: Extract auth hook**

Create `photo-monitor/src/hooks/useAuth.js` with a hook that owns `user`, `booting`, `authError`, `loadCurrentUser`, `handleLogin`, `handleLogout`, and `handleChangePassword`. It calls `fetchCurrentUser`, `getStoredToken`, `login`, `logout`, `setStoredToken`, and `changePassword` from `api.js`, and returns `{ user, setUser, booting, authError, handleLogin, handleLogout, handleChangePassword }`.

- [ ] **Step 3: Extract photo feed hook**

Create `photo-monitor/src/hooks/usePhotoFeed.js` with a hook that owns photo state, cursor, total, filters, dedupe settings, WebSocket refresh, and `loadPhotos`/`loadMorePhotos`. Move these constants and helpers from `App.jsx` into the hook file: `DEFAULT_STATION`, `DEFAULT_PHOTO_LIMIT`, `DEFAULT_DEDUPE_ENABLED`, `DEFAULT_DEDUPE_WINDOW_SECONDS`, `PHOTO_FEED_BATCH_SIZE`, `MOBILE_PHOTO_FEED_BATCH_SIZE`, `PHOTO_LIMIT_STORAGE_KEY`, `PHOTO_DEDUPE_ENABLED_STORAGE_KEY`, `PHOTO_DEDUPE_WINDOW_STORAGE_KEY`, `keepDigitsOnly`, `parsePositiveInteger`, `readStoredDigits`, `readInitialPhotoLimit`, `readInitialDedupeEnabled`, `readInitialDedupeWindow`, `getPhotoFeedBatchSize`, and `dedupePhotosByWindow`.

- [ ] **Step 4: Extract office uploads hook**

Create `photo-monitor/src/hooks/useOfficeUploads.js`:

```js
import { useCallback, useEffect, useState } from "react"

export default function useOfficeUploads({ fetchItems, uploadItem, deleteItem, successMessages, showBanner }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState("")

  const loadItems = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const data = await fetchItems()
      setItems(data.items ?? [])
    } catch (loadError) {
      setError(loadError.message)
    } finally {
      setLoading(false)
    }
  }, [fetchItems])

  useEffect(() => {
    const timer = window.setTimeout(loadItems, 0)
    return () => window.clearTimeout(timer)
  }, [loadItems])

  const upload = useCallback(async (payload, options) => {
    setUploading(true)
    try {
      await uploadItem(payload, options)
      showBanner(successMessages.uploaded)
      await loadItems()
    } finally {
      setUploading(false)
    }
  }, [loadItems, showBanner, successMessages.uploaded, uploadItem])

  const remove = useCallback(async (item) => {
    await deleteItem(item.id)
    showBanner(successMessages.deleted)
    await loadItems()
  }, [deleteItem, loadItems, showBanner, successMessages.deleted])

  return { items, loading, uploading, error, loadItems, upload, remove }
}
```

- [ ] **Step 5: Wire App to extracted helpers**

Update `App.jsx` imports and remove duplicated helper functions only after the replacement imports are used.

- [ ] **Step 6: Run focused frontend checks**

Run from `photo-backend` for pytest and from `photo-monitor` for npm:

```powershell
npm run lint
npm run build
```

Expected: lint and build pass.

- [ ] **Step 7: Commit**

```powershell
git add photo-monitor/src/App.jsx photo-monitor/src/permissions.js photo-monitor/src/hooks/useAuth.js photo-monitor/src/hooks/usePhotoFeed.js photo-monitor/src/hooks/useOfficeUploads.js
git commit -m "refactor: extract frontend state helpers"
```

---

### Task 5: Frontend Page Decomposition

**Files:**
- Create: `photo-monitor/src/pages/DashboardPage.jsx`
- Create: `photo-monitor/src/pages/OfficeUploadPage.jsx`
- Create: `photo-monitor/src/pages/StructurePage.jsx`
- Create: `photo-monitor/src/pages/MonitorPage.jsx`
- Modify: `photo-monitor/src/App.jsx`

- [ ] **Step 1: Move dashboard components**

Move `BrandMark` and `DashboardPage` from `App.jsx` to `src/pages/DashboardPage.jsx`. Export both if other pages need `BrandMark`.

- [ ] **Step 2: Move office upload components**

Move `OfficeModulePage`, `UploadPanel`, and `UploadList` into `src/pages/OfficeUploadPage.jsx`. Implement `OfficeUploadPage` as a configurable component with props for title, system key, fetch/upload/delete/view functions, and messages.

- [ ] **Step 3: Replace document/learning/ledger pages**

In `App.jsx`, replace `DocumentsPage`, `LearningPage`, and `LedgerWorkspacePage` with three `OfficeUploadPage` usages.

- [ ] **Step 4: Move structure page**

Move `StructurePage` into `src/pages/StructurePage.jsx`.

- [ ] **Step 5: Move monitor page**

Move monitor rendering and toolbar/photo grid/modal composition into `src/pages/MonitorPage.jsx`.

- [ ] **Step 6: Keep App as router shell**

After extraction, `App.jsx` should own page selection, top-level auth state, employee management callbacks, and page composition. It should not contain office upload or monitor implementation details.

- [ ] **Step 7: Run focused frontend checks**

Run from `photo-monitor`:

```powershell
npm run lint
npm run build
```

Expected: lint and build pass.

- [ ] **Step 8: Commit**

```powershell
git add photo-monitor/src/App.jsx photo-monitor/src/pages/DashboardPage.jsx photo-monitor/src/pages/OfficeUploadPage.jsx photo-monitor/src/pages/StructurePage.jsx photo-monitor/src/pages/MonitorPage.jsx
git commit -m "refactor: split frontend pages"
```

---

### Task 6: Cleanup and Documentation

**Files:**
- Delete: `photo-monitor/pages/home.jsx`
- Delete: `photo-monitor/hooks/usePhotos.js`
- Delete: `photo-monitor/hooks/useWebsockets.js`
- Modify: `photo-monitor/README.md`

- [ ] **Step 1: Verify stale files are unused**

Run from repository root:

```powershell
rg -n "pages/home|usePhotos|useWebsockets|\\.\\./hooks|\\.\\/hooks" photo-monitor
```

Expected: only stale files themselves or no results.

- [ ] **Step 2: Delete stale files**

Delete:

```text
photo-monitor/pages/home.jsx
photo-monitor/hooks/usePhotos.js
photo-monitor/hooks/useWebsockets.js
```

- [ ] **Step 3: Document verification workflow**

Append this section to `photo-monitor/README.md`:

````markdown
## Local Verification

Frontend:

```bash
npm run lint
npm run build
```

Backend:

```bash
cd ../photo-backend
pytest -q
```

The project favors focused automated checks over manual browser testing for routine refactors.
````

- [ ] **Step 4: Run final focused checks**

Run from `photo-monitor` for npm commands and from `photo-backend` for pytest:

```powershell
npm run lint
npm run build
pytest -q
```

Expected: all focused checks pass.

- [ ] **Step 5: Commit**

```powershell
git add photo-monitor/README.md photo-monitor/pages/home.jsx photo-monitor/hooks/usePhotos.js photo-monitor/hooks/useWebsockets.js
git commit -m "chore: remove stale frontend entrypoints"
```

---

### Task 7: Final Review Commit Check

**Files:**
- Inspect all changed files.

- [ ] **Step 1: Check git status**

Run from repository root:

```powershell
git status --short
```

Expected: no uncommitted source/doc changes except ignored generated files.

- [ ] **Step 2: Confirm five server-side scenarios exist**

Run from repository root:

```powershell
rg -n "test_admin_employee_payloads_do_not_expose_passwords|test_legacy_plaintext_password_is_migrated_after_login|test_jwt_uses_configured_environment_secret|test_photo_resource_requires_matching_read_permission|test_upload_file_access_respects_department_and_action_permissions" photo-backend/tests
```

Expected: five test definitions found.

- [ ] **Step 3: Run final focused verification**

Run from `photo-monitor` for npm commands and from `photo-backend` for pytest:

```powershell
npm run lint
npm run build
pytest -q
```

Expected: all focused checks pass.

- [ ] **Step 4: Report**

Summarize commits created, tests run, and any remaining risks.
