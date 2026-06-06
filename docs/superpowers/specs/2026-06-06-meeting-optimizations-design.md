# Meeting Optimizations Design

## Goal

Implement the confirmed meeting follow-up items that are small enough to ship together: monitor defaults and page cleanup, title consistency, employee password visibility for admin, department-scoped permissions without "all departments" in employee management, and organization structure visibility by department scope.

## Scope

Included:

- Set the default photo dedupe window to 10 seconds and keep dedupe visible by default.
- Simplify the monitor page actions to only "返回主界面"; the toolbar refresh action remains as the list refresh.
- Use "监控照片管理系统" as the consistent visible product title.
- Remove the wildcard "全部部门" permission row from employee management so permissions are granted to concrete departments.
- Return employee passwords to admin employee APIs so the admin screen can display and edit them.
- Show company structure according to `perm:structure:<department>:read`. Admin sees all departments. Employees see their own department and departments under it, inferred from department names as a prefix hierarchy when department names are path-like.

Excluded:

- Fixed upload tool user.
- Certificate fields, expiry reminders, birthdays, and Aliyun SMS integration.
- PC-side photo auto-delete.

## Design

Backend keeps the existing matrix permission model. `User.to_public_dict()` gets an `include_sensitive` flag; admin list/detail endpoints use it to include plaintext passwords because the current project stores plaintext passwords already. Structure access uses the existing `structure` matrix read permission and a new helper that returns allowed departments. A department is visible when it exactly matches an allowed department, or when it is below an allowed department in a path-like hierarchy such as `总公司/运营部`.

Frontend keeps the existing page layout. The monitor page removes account/admin/logout actions. Login/dashboard/office headers use the agreed title. Employee management no longer renders the wildcard permission row. Structure page filters employee groups with the same front-end permission interpretation so the visible page matches the backend permission intent.

## Testing

Backend tests cover sensitive admin output and structure department scope. Frontend verification uses lint/build because the project does not currently have a JS unit test runner.
