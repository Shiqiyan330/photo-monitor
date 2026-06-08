import assert from "node:assert/strict"
import test from "node:test"

import { buildOfficeDepartmentOptions, filterOfficeItems } from "./officeFilters.js"

const items = [
  { id: "1", name: "安全培训记录.pdf", department: "总公司" },
  { id: "2", name: "设备台账.xlsx", department: "湄江" },
  { id: "3", name: "Safety Guide.docx", department: "雪峰山" },
  { id: "4", name: "会议纪要.docx", department: "" },
]

test("filters all departments by title when department is empty", () => {
  const result = filterOfficeItems(items, { department: "", title: "安全" })

  assert.deepEqual(result.map((item) => item.id), ["1"])
})

test("filters selected department before matching title", () => {
  const result = filterOfficeItems(items, { department: "湄江", title: "安全" })

  assert.deepEqual(result, [])
})

test("matches title case-insensitively and trims search text", () => {
  const result = filterOfficeItems(items, { department: "", title: " safety " })

  assert.deepEqual(result.map((item) => item.id), ["3"])
})

test("builds department options from configured and loaded item departments", () => {
  const result = buildOfficeDepartmentOptions(["总公司", "大茅山"], items)

  assert.deepEqual(result, ["总公司", "大茅山", "湄江", "雪峰山"])
})
