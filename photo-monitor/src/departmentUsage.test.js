import assert from "node:assert/strict"
import test from "node:test"

import { DEPARTMENT_USAGE_LABELS, hasDepartmentUsage } from "./departmentUsage.js"

test("hasDepartmentUsage detects any department-owned record", () => {
  assert.equal(hasDepartmentUsage({ employees: 0, study_articles: 0 }), false)
  assert.equal(hasDepartmentUsage({ employees: 0, study_articles: 1 }), true)
})

test("department usage labels cover every user-facing resource", () => {
  assert.deepEqual(
    DEPARTMENT_USAGE_LABELS.map(([key]) => key),
    ["employees", "permissions", "photos", "company_files", "study_articles", "ledgers"],
  )
})
