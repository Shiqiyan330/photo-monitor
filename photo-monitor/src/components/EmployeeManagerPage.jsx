import { useMemo, useState } from "react"

const DEFAULT_DEPARTMENTS = ["大茅山", "湄江", "雪峰山", "浙江之心", "总公司"]

const EMPTY_FORM = {
  username: "",
  password: "",
  phone: "",
  name: "",
  department: "",
  position: "",
  rank: "",
  permissions: [],
}

const PERMISSION_SYSTEMS = [
  { value: "photos", label: "照片", actions: ["read", "create", "update", "delete"] },
  { value: "company_files", label: "公司文件", actions: ["read", "create", "update", "delete"] },
  { value: "study_articles", label: "学习交流", actions: ["read", "create", "update", "delete"] },
  { value: "ledgers", label: "台账", actions: ["read", "create", "update", "delete"] },
  { value: "structure", label: "公司架构", actions: ["read"] },
]

const PERMISSION_ACTIONS = [
  { value: "read", label: "查" },
  { value: "create", label: "增" },
  { value: "update", label: "改" },
  { value: "delete", label: "删" },
]

function buildMatrixPermission(system, department, action) {
  return `perm:${system}:${department || "*"}:${action}`
}

function parseMatrixPermission(permission) {
  if (typeof permission !== "string" || !permission.startsWith("perm:")) {
    return null
  }
  const parts = permission.slice(5).split(":")
  if (parts.length !== 3 || parts.some((item) => !item)) {
    return null
  }
  return { system: parts[0], department: parts[1], action: parts[2] }
}

function getMatrixDepartments(employee) {
  return (employee.permissions ?? [])
    .map(parseMatrixPermission)
    .filter(Boolean)
    .map((item) => item.department)
    .filter((item) => item && item !== "*")
}

function isActionAvailable(system, action) {
  return system.actions.includes(action.value)
}

function isConcreteMatrixPermission(permission) {
  const parsed = parseMatrixPermission(permission)
  return Boolean(parsed && parsed.department !== "*")
}

function syncDefaultStructurePermission(permissions, department) {
  const normalizedDepartment = (department || "").trim()
  const nonStructurePermissions = permissions.filter((permission) => {
    const parsed = parseMatrixPermission(permission)
    return !parsed || parsed.system !== "structure"
  })

  if (!normalizedDepartment) {
    return nonStructurePermissions
  }

  return [
    ...nonStructurePermissions,
    buildMatrixPermission("structure", normalizedDepartment, "read"),
  ]
}

function summarizePermissions(employee) {
  const grouped = new Map()

  for (const permission of employee.permissions ?? []) {
    const parsed = parseMatrixPermission(permission)
    if (!parsed) {
      continue
    }
    if (parsed.department === "*") {
      continue
    }
    const system = PERMISSION_SYSTEMS.find((item) => item.value === parsed.system)
    const action = PERMISSION_ACTIONS.find((item) => item.value === parsed.action)
    if (!system || !action) {
      continue
    }

    const key = `${system.value}:${parsed.department}`
    if (!grouped.has(key)) {
      grouped.set(key, {
        system: system.label,
        department: parsed.department,
        actions: [],
      })
    }
    grouped.get(key).actions.push(action.label)
  }

  return Array.from(grouped.values())
    .slice(0, 3)
    .map((item) => `${item.system}/${item.department}: ${item.actions.join("")}`)
}

export default function EmployeeManagerPage({
  employees,
  departments,
  onBack,
  onCreate,
  onUpdate,
  onDelete,
}) {
  const [editingUsername, setEditingUsername] = useState("")
  const [form, setForm] = useState(EMPTY_FORM)
  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)

  const departmentOptions = useMemo(() => {
    const values = [
      ...DEFAULT_DEPARTMENTS,
      ...(departments ?? []),
      ...(form.department ? [form.department] : []),
      ...employees.map((item) => item.department).filter(Boolean),
      ...employees.flatMap((item) => getMatrixDepartments(item)),
    ]

    return Array.from(new Set(values.map((item) => item.trim()).filter(Boolean))).sort((left, right) =>
      left.localeCompare(right, "zh-CN"),
    )
  }, [departments, employees, form.department])

  const matrixDepartmentOptions = departmentOptions

  const groupedEmployees = useMemo(() => {
    const groups = new Map()

    for (const employee of employees) {
      const departmentName = employee.department || "未分配部门"
      if (!groups.has(departmentName)) {
        groups.set(departmentName, [])
      }
      groups.get(departmentName).push(employee)
    }

    return Array.from(groups.entries())
      .sort(([leftName], [rightName]) => {
        if (leftName === "未分配部门") {
          return 1
        }
        if (rightName === "未分配部门") {
          return -1
        }
        return leftName.localeCompare(rightName, "zh-CN")
      })
      .map(([departmentName, members]) => ({
        departmentName,
        members: [...members].sort((left, right) =>
          (left.name || left.username).localeCompare(right.name || right.username, "zh-CN"),
        ),
      }))
  }, [employees])

  const startCreate = () => {
    setEditingUsername("")
    setForm(EMPTY_FORM)
    setError("")
  }

  const startEdit = (employee) => {
    setEditingUsername(employee.username)
    setForm({
      username: employee.username,
      password: employee.password ?? "",
      phone: employee.phone ?? "",
      name: employee.name ?? "",
      department: employee.department ?? "",
      position: employee.position ?? "",
      rank: employee.rank ?? "",
      permissions: (employee.permissions ?? []).filter(isConcreteMatrixPermission),
    })
    setError("")
  }

  const handleChange = (field, value) => {
    setForm((current) => {
      if (!editingUsername && field === "department") {
        return {
          ...current,
          department: value,
          permissions: syncDefaultStructurePermission(current.permissions, value),
        }
      }
      return { ...current, [field]: value }
    })
  }

  const togglePermission = (value) => {
    setForm((current) => {
      const exists = current.permissions.includes(value)
      return {
        ...current,
        permissions: exists
          ? current.permissions.filter((item) => item !== value)
          : [...current.permissions, value],
      }
    })
  }

  const toggleDepartmentSystem = (system, department) => {
    const rowPermissions = system.actions.map((action) => buildMatrixPermission(system.value, department, action))
    const allSelected = rowPermissions.every((permission) => form.permissions.includes(permission))

    setForm((current) => ({
      ...current,
      permissions: allSelected
        ? current.permissions.filter((item) => !rowPermissions.includes(item))
        : Array.from(new Set([...current.permissions, ...rowPermissions])),
    }))
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError("")

    try {
      const payload = {
        ...form,
        username: form.username.trim(),
        phone: form.phone.trim(),
        name: form.name.trim(),
        department: form.department.trim(),
        position: form.position.trim(),
        rank: form.rank.trim(),
        permissions: form.permissions.filter(isConcreteMatrixPermission),
      }

      if (editingUsername) {
        await onUpdate(editingUsername, payload)
      } else {
        await onCreate(payload)
      }

      startCreate()
    } catch (submitError) {
      setError(submitError.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (username) => {
    if (!window.confirm(`确认删除员工 ${username} 吗？`)) {
      return
    }

    try {
      await onDelete(username)
      if (editingUsername === username) {
        startCreate()
      }
    } catch (submitError) {
      setError(submitError.message)
    }
  }

  return (
    <section className="admin-page">
      <div className="admin-page-header">
        <div>
          <div className="brand-mark compact">
            <div className="brand-logo-slot" aria-hidden="true">
              <span>Logo</span>
            </div>
            <div>
              <div className="brand-name">越岚索道</div>
            </div>
          </div>
          <p className="eyebrow">Admin</p>
          <h2>员工管理</h2>
        </div>
        <button type="button" className="ghost-button" onClick={onBack}>
          返回工作台
        </button>
      </div>

      <div className="admin-layout">
        <section className="admin-panel admin-form-panel">
          <div className="panel-header">
            <h3>{editingUsername ? "编辑员工" : "新增员工"}</h3>
            {editingUsername ? (
              <button type="button" className="ghost-button" onClick={startCreate}>
                切换为新增
              </button>
            ) : null}
          </div>

          <form className="stack-form" onSubmit={handleSubmit}>
            <label className="field">
              <span>用户名</span>
              <input
                value={form.username}
                onChange={(event) => handleChange("username", event.target.value)}
                placeholder="默认可直接填写手机号"
                required
              />
            </label>

            <label className="field">
              <span>密码</span>
              <input
                type="text"
                value={form.password}
                onChange={(event) => handleChange("password", event.target.value)}
                placeholder={editingUsername ? "留空表示不修改密码" : "不填写则默认与手机号相同"}
              />
            </label>

            <label className="field">
              <span>手机号</span>
              <input value={form.phone} onChange={(event) => handleChange("phone", event.target.value)} />
            </label>

            <label className="field">
              <span>姓名</span>
              <input value={form.name} onChange={(event) => handleChange("name", event.target.value)} />
            </label>

            <label className="field">
              <span>部门</span>
              <input
                list="department-options"
                value={form.department}
                onChange={(event) => handleChange("department", event.target.value)}
              />
            </label>

            <label className="field">
              <span>职位</span>
              <input value={form.position} onChange={(event) => handleChange("position", event.target.value)} />
            </label>

            <label className="field">
              <span>职级</span>
              <input value={form.rank} onChange={(event) => handleChange("rank", event.target.value)} />
            </label>

            <div className="field">
              <span>系统-部门-增删改查权限</span>
              <p className="field-hint">
                按“某人、某系统、某部门、增删改查”授权，照片和架构权限需关联到单个部门。
              </p>

              <div className="permission-matrix">
                <div className="permission-matrix-head">
                  <span>系统</span>
                  <span>部门</span>
                  {PERMISSION_ACTIONS.map((action) => (
                    <span key={action.value}>{action.label}</span>
                  ))}
                  <span>整行</span>
                </div>
                {PERMISSION_SYSTEMS.flatMap((system) =>
                  matrixDepartmentOptions.map((department) => {
                    const rowPermissions = system.actions.map((action) =>
                      buildMatrixPermission(system.value, department, action),
                    )
                    const allSelected = rowPermissions.every((permission) => form.permissions.includes(permission))

                    return (
                      <div key={`${system.value}-${department}`} className="permission-matrix-row">
                        <span>{system.label}</span>
                        <span>{department}</span>
                        {PERMISSION_ACTIONS.map((action) => {
                          const available = isActionAvailable(system, action)
                          const permission = buildMatrixPermission(system.value, department, action.value)
                          return (
                            <label key={permission} className={available ? "matrix-check" : "matrix-check disabled"}>
                              <input
                                type="checkbox"
                                disabled={!available}
                                checked={available && form.permissions.includes(permission)}
                                onChange={() => togglePermission(permission)}
                              />
                            </label>
                          )
                        })}
                        <button
                          type="button"
                          className={allSelected ? "matrix-row-toggle active" : "matrix-row-toggle"}
                          onClick={() => toggleDepartmentSystem(system, department)}
                        >
                          {allSelected ? "清除" : "全选"}
                        </button>
                      </div>
                    )
                  }),
                )}
              </div>
            </div>

            {error ? <div className="form-error">{error}</div> : null}

            <button type="submit" className="primary-button" disabled={saving}>
              {saving ? "保存中..." : editingUsername ? "保存修改" : "新增员工"}
            </button>
          </form>

          <datalist id="department-options">
            {departmentOptions.map((item) => (
              <option key={item} value={item} />
            ))}
          </datalist>
        </section>

        <section className="admin-panel admin-list-panel">
          <div className="panel-header">
            <h3>员工列表</h3>
            <span className="panel-muted">共 {employees.length} 人</span>
          </div>

          {groupedEmployees.length ? (
            <div className="employee-groups">
              {groupedEmployees.map((group) => (
                <section key={group.departmentName} className="employee-group">
                  <div className="employee-group-header">
                    <h4>{group.departmentName}</h4>
                    <span className="panel-muted">{group.members.length} 人</span>
                  </div>

                  <div className="employee-table">
                    {group.members.map((employee) => {
                      const summaries = summarizePermissions(employee)
                      return (
                        <div key={employee.username} className="employee-row">
                          <div>
                            <div className="employee-main">{employee.name || employee.username}</div>
                            <div className="employee-sub">
                              {employee.username}
                              {employee.password ? ` / 密码：${employee.password}` : ""}
                              {employee.position ? ` / ${employee.position}` : ""}
                              {employee.rank ? ` / ${employee.rank}` : ""}
                            </div>
                            <div className="employee-tags">
                              <span className="employee-tag">{(employee.permissions ?? []).length} 项矩阵权限</span>
                              {summaries.map((summary) => (
                                <span key={summary} className="employee-tag accent">
                                  {summary}
                                </span>
                              ))}
                            </div>
                          </div>

                          <div className="employee-actions">
                            <button type="button" className="ghost-button" onClick={() => startEdit(employee)}>
                              编辑
                            </button>
                            <button
                              type="button"
                              className="ghost-button danger-button"
                              onClick={() => handleDelete(employee.username)}
                            >
                              删除
                            </button>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </section>
              ))}
            </div>
          ) : (
            <div className="empty-state">还没有员工，先在左侧创建账号。</div>
          )}
        </section>
      </div>
    </section>
  )
}
