export const DEPARTMENT_USAGE_LABELS = [
  ["employees", "员工"],
  ["permissions", "权限配置"],
  ["photos", "监控照片"],
  ["company_files", "公司文件"],
  ["study_articles", "学习交流"],
  ["ledgers", "台账"],
]

export function hasDepartmentUsage(usage) {
  return Object.values(usage ?? {}).some((value) => Number(value) > 0)
}
