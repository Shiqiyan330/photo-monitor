# Admin Department Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add admin-only CRUD for departments and use the managed department list across employee editing, uploads, and filters.

**Architecture:** Introduce a small `DepartmentStore` backed by `departments.json` and compose it with existing employee-derived departments for backward compatibility. Admin APIs mutate the store; renames update employee home departments and matrix permission department segments, while delete is blocked when employees, permissions, uploaded data, or stored files still reference the department.

**Tech Stack:** FastAPI, Pydantic, pytest, React/Vite, browser fetch API.

---

### Task 1: Backend Department Store and Rename/Delete Rules

**Files:**
- Create: `photo-backend/services/department_service.py`
- Modify: `photo-backend/services/auth_service.py`
- Test: `photo-backend/tests/test_department_management.py`

- [ ] **Step 1: Write failing tests**

Add pytest tests for:
- `DepartmentStore` normalizes, deduplicates, creates, renames, and deletes departments.
- `EmployeeSystem.rename_department(old, new)` updates `user.department` and matrix permissions.
- `EmployeeSystem.department_is_used(name)` reports employee department and permission usage.

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_department_management.py -v`
Expected: FAIL because `services.department_service` does not exist.

- [ ] **Step 3: Implement minimal backend services**

Create `DepartmentStore` with `list_departments`, `create_department`, `rename_department`, `delete_department`.
Add `EmployeeSystem.rename_department` and `EmployeeSystem.department_is_used`.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_department_management.py -v`
Expected: PASS.

### Task 2: Admin Department API

**Files:**
- Modify: `photo-backend/routers/admin.py`
- Modify: `photo-backend/services/upload_service.py`
- Test: `photo-backend/tests/test_department_management.py`

- [ ] **Step 1: Write failing API tests**

Add FastAPI tests for:
- Non-admin cannot access `/admin/departments`.
- Admin can list, create, rename, and delete unused departments.
- Delete used department returns 400.

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_department_management.py -v`
Expected: FAIL with 404 for `/admin/departments`.

- [ ] **Step 3: Implement API**

Add Pydantic payloads and endpoints under existing admin router.
Use `DepartmentStore` and existing `employee_system`; check upload metadata and category directories before delete.

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_department_management.py -v`
Expected: PASS.

### Task 3: Frontend API and Admin UI

**Files:**
- Modify: `photo-monitor/src/api.js`
- Modify: `photo-monitor/src/App.jsx`
- Modify: `photo-monitor/src/pages/DashboardPage.jsx`
- Create: `photo-monitor/src/components/DepartmentManagerPage.jsx`
- Modify: `photo-monitor/src/index.css`

- [ ] **Step 1: Add API helpers**

Add `fetchDepartments`, `createDepartment`, `renameDepartment`, `deleteDepartment`.

- [ ] **Step 2: Add admin route and dashboard entry**

Add a department management page constant and show a “部门管理” button only when `user.role === "admin"`.

- [ ] **Step 3: Build DepartmentManagerPage**

Implement list, create form, inline rename, delete with confirmation, loading and error states.

- [ ] **Step 4: Refresh shared departments**

After create/rename/delete, reload departments and employees so employee forms, uploads, and search filters see fresh values.

### Task 4: Verification

**Files:**
- No new files.

- [ ] **Step 1: Run backend tests**

Run: `pytest`
Expected: all tests pass.

- [ ] **Step 2: Run frontend tests and checks**

Run:
- `node --test src/officeFilters.test.js`
- `npm run lint`
- `npm run build`

Expected: all commands pass.
