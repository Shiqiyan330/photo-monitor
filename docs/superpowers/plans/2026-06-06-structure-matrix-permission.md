# Structure Matrix Permission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the backend the only permission authority for the company structure page and make the frontend a pure renderer of backend-filtered structure data.

**Architecture:** `/structure/employees` remains the single matrix-permission-filtered source for structure data. `StructurePage.jsx` groups and displays the employees it receives, without reading user permissions or applying visibility rules.

**Tech Stack:** FastAPI, pytest, React, Vite, ESLint.

---

### Task 1: Backend Matrix Permission Coverage

**Files:**
- Modify: `photo-backend/tests/test_permission_matrix.py`

- [ ] Add tests that prove `/structure/employees` rejects users without `perm:structure:*:read` or scoped `read`, allows wildcard `perm:structure:*:read`, and returns all employees for admin.
- [ ] Run `pytest tests/test_permission_matrix.py -q` from `photo-backend`.

### Task 2: Frontend Pure Structure Renderer

**Files:**
- Modify: `photo-monitor/src/pages/StructurePage.jsx`
- Modify: `photo-monitor/src/App.jsx`

- [ ] Remove frontend permission filtering from `StructurePage.jsx`; it should only group the `employees` prop.
- [ ] Remove `user` prop from `StructurePage` usage.
- [ ] Load `/structure/employees` whenever the current page is `structure` and the user has matrix read permission, including admin.
- [ ] Keep admin employee-management loading only for the employee management page.
- [ ] Run `npm run lint` and `npm run build` from `photo-monitor`.

### Task 3: Final Verification

- [ ] Run `pytest -q` from `photo-backend`.
- [ ] Run `npm run lint` and `npm run build` from `photo-monitor`.
- [ ] Commit the focused change.
