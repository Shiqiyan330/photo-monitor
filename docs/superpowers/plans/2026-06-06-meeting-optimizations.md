# Meeting Optimizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the confirmed meeting optimizations for monitor defaults, cleaner UI, admin password visibility, department-only permission assignment, and scoped company structure visibility.

**Architecture:** Keep the existing React/FastAPI structure and matrix permission model. Add focused backend helpers for sensitive admin output and structure department filtering, then mirror the same permission interpretation in the structure UI. Avoid new data stores or large model changes.

**Tech Stack:** React 19, Vite, FastAPI, pytest.

---

### Task 1: Backend Admin Password Output

**Files:**
- Modify: `photo-backend/services/auth_service.py`
- Modify: `photo-backend/routers/admin.py`
- Test: `photo-backend/tests/test_permission_matrix.py`

- [ ] Write failing tests proving admin employee output can include password while normal public output omits it.
- [ ] Run `pytest tests/test_permission_matrix.py -q` from `photo-backend` and confirm the new tests fail.
- [ ] Add `include_sensitive=False` to `User.to_public_dict()` and pass `include_sensitive=True` from admin employee endpoints.
- [ ] Run the same pytest command and confirm it passes.

### Task 2: Structure Department Scope

**Files:**
- Modify: `photo-backend/services/auth_service.py`
- Test: `photo-backend/tests/test_permission_matrix.py`

- [ ] Write failing tests for a user with `perm:structure:总公司/运营部:read` seeing `总公司/运营部` and `总公司/运营部/票务` but not sibling departments.
- [ ] Run `pytest tests/test_permission_matrix.py -q` from `photo-backend` and confirm the new tests fail.
- [ ] Add helpers that extract structure read departments and match child department paths.
- [ ] Run the same pytest command and confirm it passes.

### Task 3: Frontend UI And Permissions

**Files:**
- Modify: `photo-monitor/src/App.jsx`
- Modify: `photo-monitor/src/components/LoginForm.jsx`
- Modify: `photo-monitor/src/components/Toolbar.jsx`
- Modify: `photo-monitor/src/components/EmployeeManagerPage.jsx`

- [ ] Set the dedupe default window from `20` to `10`.
- [ ] Replace visible product/page titles with `监控照片管理系统`.
- [ ] Remove monitor page password, employee management, and logout actions, leaving only `返回主界面`.
- [ ] Rename toolbar refresh text to `刷新列表`.
- [ ] Remove wildcard `*` from employee permission department options.
- [ ] Display employee passwords in the employee list metadata.
- [ ] Filter `StructurePage` employees by `structure` read departments, including child department names.

### Task 4: Verification

**Files:**
- Existing project files only.

- [ ] Run `pytest tests/test_permission_matrix.py -q` from `photo-backend`.
- [ ] Run `npm run lint` from `photo-monitor`.
- [ ] Run `npm run build` from `photo-monitor`.
- [ ] Review `git diff --check`.
