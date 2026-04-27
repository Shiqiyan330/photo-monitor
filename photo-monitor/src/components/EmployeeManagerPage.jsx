import { useMemo, useState } from "react"

const FEATURE_PERMISSION_OPTIONS = [
  { value: "camera", label: "监控查看" },
  { value: "files", label: "公司文件" },
  { value: "study", label: "学习交流" },
  { value: "upload", label: "台账上传" },
  { value: "structure", label: "公司架构" },
  { value: "cross_dept_files", label: "跨部门文件" },
]

const EMPTY_FORM = {
  username: "",
  password: "",
  phone: "",
  name: "",
  department: "",
  position: "",
  rank: "",
  permissions: ["camera", "files", "study", "upload"],
}

function buildDepartmentPermission(department) {
  return `dept_${department}`
}

function getDepartmentPermissions(employee) {
  if (Array.isArray(employee.department_permissions)) {
    return employee.department_permissions
  }

  return (employee.permissions ?? [])
    .filter((item) => item.startsWith("dept_"))
    .map((item) => item.slice(5))
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
      ...(departments ?? []),
      ...(form.department ? [form.department] : []),
      ...employees.map((item) => item.department).filter(Boolean),
      ...employees.flatMap((item) => getDepartmentPermissions(item)),
    ]

    return Array.from(new Set(values.map((item) => item.trim()).filter(Boolean))).sort((left, right) =>
      left.localeCompare(right, "zh-CN"),
    )
  }, [departments, employees, form.department])

  const departmentPermissionOptions = departmentOptions.map((item) => ({
    value: buildDepartmentPermission(item),
    label: item,
  }))

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
      password: "",
      phone: employee.phone ?? "",
      name: employee.name ?? "",
      department: employee.department ?? "",
      position: employee.position ?? "",
      rank: employee.rank ?? "",
      permissions: employee.permissions ?? [],
    })
    setError("")
  }

  const handleChange = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }))
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
                  placeholder="默认可直接填手机号"
                  required
                />
              </label>

              <label className="field">
                <span>密码</span>
                <input
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
                <span>权限</span>

                <div className="permission-sections">
                  <section className="permission-section">
                    <div className="permission-section-head">
                      <div>
                        <div className="permission-title">功能权限</div>
                        <p className="field-hint">监控、文件、学习交流、上传和公司架构权限会在这里统一配置。</p>
                      </div>
                    </div>

                    <div className="permission-grid">
                      {FEATURE_PERMISSION_OPTIONS.map((item) => {
                        const checked = form.permissions.includes(item.value)
                        return (
                          <label
                            key={item.value}
                            className={checked ? "permission-chip active" : "permission-chip"}
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => togglePermission(item.value)}
                            />
                            <span>{item.label}</span>
                          </label>
                        )
                      })}
                    </div>
                  </section>

                  <section className="permission-section">
                    <div className="permission-section-head">
                      <div>
                        <div className="permission-title">部门查看权限</div>
                        <p className="field-hint">如果一个员工要看多个部门，直接在这里勾选，后续会联动部门切换入口。</p>
                      </div>
                    </div>

                    {departmentPermissionOptions.length ? (
                      <div className="permission-grid">
                        {departmentPermissionOptions.map((item) => {
                          const checked = form.permissions.includes(item.value)
                          return (
                            <label
                              key={item.value}
                              className={checked ? "permission-chip active" : "permission-chip"}
                            >
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => togglePermission(item.value)}
                              />
                              <span>{item.label}</span>
                            </label>
                          )
                        })}
                      </div>
                    ) : (
                      <div className="empty-state compact-empty-state">先录入员工部门，这里就会自动生成可勾选的部门权限。</div>
                    )}
                  </section>
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
                      const departmentPermissions = getDepartmentPermissions(employee)
                      return (
                        <div key={employee.username} className="employee-row">
                          <div>
                            <div className="employee-main">{employee.name || employee.username}</div>
                            <div className="employee-sub">
                              {employee.username}
                              {employee.position ? ` · ${employee.position}` : ""}
                              {employee.rank ? ` · ${employee.rank}` : ""}
                            </div>
                            <div className="employee-tags">
                              <span className="employee-tag">{(employee.permissions ?? []).length} 项权限</span>
                              {departmentPermissions.length ? (
                                <span className="employee-tag accent">{departmentPermissions.length} 个部门权限</span>
                              ) : null}
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
