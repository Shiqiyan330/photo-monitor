import { uniqueStrings } from "./permissions.js"

export function filterOfficeItems(items, filters) {
  const selectedDepartment = (filters.department || "").trim()
  const titleQuery = (filters.title || "").trim().toLowerCase()

  return (items ?? []).filter((item) => {
    const itemDepartment = (item.department || "").trim()
    if (selectedDepartment && itemDepartment !== selectedDepartment) {
      return false
    }
    if (!titleQuery) {
      return true
    }
    return (item.name || "").toLowerCase().includes(titleQuery)
  })
}

export function buildOfficeDepartmentOptions(departments, items) {
  return uniqueStrings([...(departments ?? []), ...(items ?? []).map((item) => item.department)])
}
