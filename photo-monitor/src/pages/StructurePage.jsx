import { useState } from "react"
import { OfficeModulePage } from "./OfficeUploadPage"

export default function StructurePage({ onBack, employees }) {
  const [collapsedDepartments, setCollapsedDepartments] = useState(new Set())
  const groups = new Map()

  for (const employee of employees) {
    const department = employee.department || "未分配部门"
    if (!groups.has(department)) {
      groups.set(department, [])
    }
    groups.get(department).push(employee)
  }

  const departmentGroups = Array.from(groups.entries()).sort(([left], [right]) =>
    left.localeCompare(right, "zh-CN"),
  )

  const toggleDepartment = (department) => {
    setCollapsedDepartments((current) => {
      const next = new Set(current)
      if (next.has(department)) {
        next.delete(department)
      } else {
        next.add(department)
      }
      return next
    })
  }

  return (
    <OfficeModulePage title="公司架构" onBack={onBack}>
      <section className="structure-groups">
        {departmentGroups.map(([department, members]) => {
          const collapsed = collapsedDepartments.has(department)
          return (
            <section key={department} className="structure-group">
              <button type="button" className="structure-group-header" onClick={() => toggleDepartment(department)}>
                <span>{department}</span>
                <span>{collapsed ? "展开" : "收起"}</span>
              </button>

              {!collapsed ? (
                <div className="structure-members">
                  {members.map((member) => (
                    <article key={member.username} className="structure-card">
                      <div className="employee-main">{member.name || member.username}</div>
                      <div className="employee-sub">{member.position || "未填写职位"}</div>
                      <div className="employee-sub">{member.rank || "未填写职级"}</div>
                      <a className="phone-link" href={member.phone ? `tel:${member.phone}` : undefined}>
                        {member.phone || "未填写电话"}
                      </a>
                    </article>
                  ))}
                </div>
              ) : null}
            </section>
          )
        })}
      </section>
    </OfficeModulePage>
  )
}
