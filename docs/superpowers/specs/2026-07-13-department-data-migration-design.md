# Department Data Migration Design

## Goal

Keep every department-owned record and file consistent when an administrator renames or removes a department. A department name change must also change the ownership and storage paths of historical monitor photos, generated thumbnails, company files, study articles, ledgers, employees, and matrix permissions.

## Current Problem

The current rename endpoint updates `departments.json`, employee departments, and matrix permissions only. Historical office uploads remain under `office_data/<category>/<old-department>` and keep the old `department` and `path` values in `office_data/.metadata.json`. Historical photos and thumbnails also remain under their old department directories.

Consequently, the managed department list no longer contains the old name while stored data still references it. Users whose permissions were changed to the new name can no longer find or access those historical items.

## Chosen Behavior

### Rename

Renaming a department transfers all of its data to a new department name that does not already exist. The operation updates:

- `departments.json`;
- employee `department` values;
- every matrix permission whose department segment equals the old name;
- `photos/<old-department>` and `.thumbnails/<old-department>`;
- `office_data/company_files/<old-department>`;
- `office_data/study_articles/<old-department>`;
- `office_data/ledgers/<old-department>`;
- every matching `department` and `path` value in `office_data/.metadata.json`.

### Delete

An unused department can still be deleted directly.

A department with associated employees, permissions, photos, thumbnails, office files, or metadata cannot be deleted without a replacement. The administrator must select another existing department. The system transfers all associations and stored data to that target and then removes the source department. This is a merge, not a cascading delete: historical data is never silently discarded.

The target department must differ from the source and must already exist for a merge-and-delete operation.

Historical data can outlive its source entry when a rename happened before this fix. Department listing therefore includes names discovered from photo directories, office-data directories, and upload metadata. An administrator can merge such an orphaned historical department into an existing managed department even when the source is no longer present in `departments.json`.

## Backend Design

### Migration Service

Add a focused department migration service. It receives the department store, employee system, photo root, thumbnail root, and office-data root. It exposes three operations:

- `get_usage(department)` returns counts for employees, permissions, photos, thumbnails, each office category, and metadata records;
- `list_departments()` combines managed, employee/permission-derived, and storage-discovered department names;
- `rename(source, target)` transfers data and changes the managed department name;
- `merge_and_delete(source, target)` transfers data into an existing department and removes the source.

The service builds and validates a complete migration plan before changing persistent state. The plan contains every source and destination file path plus the rewritten JSON documents.

### File Movement

Files are moved individually so a source department can be merged into an existing target directory. Empty source directories are removed after a successful migration.

The preflight rejects the whole operation if any destination file already exists. Existing files are never overwritten or automatically renamed because doing so could hide duplicates or break metadata-to-file identity.

Legacy office files that are present on disk but absent from `.metadata.json` are included in the file plan. Metadata-backed items have both `department` and `path` rewritten. Metadata IDs, upload timestamps, hashes, and uploader information remain unchanged.

### Consistency and Rollback

Department migrations run under one process-level mutation lock shared with photo and office-data upload writes. This prevents a new upload from entering a department while its paths are being moved.

Before execution, the service snapshots `departments.json`, `users.json`, and `.metadata.json`, including whether each file originally existed. Every successful file move is recorded. If any move or JSON write fails, the service reverses recorded moves and restores the snapshots before returning an error.

JSON updates use the existing temporary-file replacement pattern where available. Rollback failure is logged and returned as an explicit server error because manual recovery may then be required.

### API

Keep the existing routes and add two admin operations:

- `GET /admin/departments/{name}/usage` returns the dependency counts used by the delete UI;
- `POST /admin/departments/{name}/merge` with `{ "target": "总部" }` transfers all data and deletes the source department.

`PUT /admin/departments/{name}` uses the migration service for rename. `DELETE /admin/departments/{name}` succeeds only when the usage report is empty; otherwise it returns HTTP 409 with the usage report and a message requiring a target department.

Validation and path conflicts return HTTP 400 or 409 with a concrete message. Unexpected execution or rollback failures return HTTP 500.

## Frontend Design

The department manager keeps the existing create and rename workflows. Successful rename messaging states that associated historical data was migrated.

Deleting a department first loads its usage report:

- when all counts are zero, show the existing destructive confirmation and call the direct delete endpoint;
- when associations exist, open a confirmation dialog that summarizes the affected data, provides a select containing all other departments, and offers a `迁移并删除` command;
- the destructive command remains disabled until a target is selected;
- backend conflict and rollback errors remain visible in the department manager without removing the source row.

The dialog does not offer cascading data deletion.

## Testing

Backend tests must prove:

- a rename moves historical photos and thumbnails;
- a rename moves company files, study articles, and ledgers;
- metadata `department` and `path` values change while IDs and other fields remain stable;
- employee departments and all matching matrix permissions change;
- legacy files without metadata move;
- merge-and-delete transfers into an existing target and removes only the source department;
- an orphaned source found only in historical storage can be merged into an existing target;
- direct deletion succeeds for an unused department and returns 409 with usage for a used department;
- a destination collision is detected before mutation and leaves all source data unchanged;
- an injected execution failure restores files and JSON snapshots.

Frontend verification covers the unused-delete and transfer-delete paths through component tests if the project test setup supports them. Existing frontend lint and production build checks remain required.

The full backend test suite and frontend lint/build commands must pass before commit and push.

## Delivery

Implementation is committed on `main` without including unrelated working-tree changes. After verification, `main` is pushed to its configured remote and the local and remote commit IDs are compared.
