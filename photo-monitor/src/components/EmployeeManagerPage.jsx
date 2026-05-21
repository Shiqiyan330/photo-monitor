import { useMemo, useState } from "react"

const FEATURE_PERMISSION_OPTIONS = [
  { value: "camera", label: "照片查看", description: "查看本人有权限部门的监控照片" },
  { value: "camera_all_departments", label: "全部门照片", description: "查看所有部门的监控照片" },
  { value: "photo_upload", label: "照片上传", description: "允许本地脚本或接口上传监控照片" },
  { value: "company_files_view", label: "公司文件", description: "访问公司文件页面和文件列表" },
  { value: "company_files_edit", label: "公司文件上传/删除", description: "上传或删除公司文件" },
  { value: "study_view", label: "学习交流查看", description: "访问学习文章列表和在线查看" },
  { value: "study_edit", label: "学习交流上传/删除", description: "上传或删除学习文章" },
  { value: "ledger_view", label: "台账查看", description: "访问台账列表和在线查看" },
  { value: "ledger_upload", label: "台账上传", description: "上传台账文件" },
  { value: "structure", label: "公司架构", description: "查看组织架构和员工联系方式" },
]

const EMPTY_FORM = {
  username: "",
  password: "",
  phone: "",
  name: "",
  department: "",
  position: "",
  rank: "",
  permissions: ["camera", "study_view", "ledger_view", "structure"],
}

const PERMISSION_SYSTEMS = [
  { value: "photos", label: "照片" },
  { value: "company_files", label: "公司文件" },
  { value: "study_articles", label: "学习交流" },
  { value: "ledgers", label: "台账" },
]

const PERMISSION_ACTIONS = [
  { value: "read", label: "查" },
  { value: "create", label: "增" },
  { value: "update", label: "改" },
  { value: "delete", label: "删" },
]

function buildDepartmentPermission(department) {
  return `dept_${department}`
}

function buildMatrixPermission(system, department, action) {
  return `perm:${system}:${department || "*"}:${action}`
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

  const departmentPermissionOptions = useMemo(
    () =>
      departmentOptions.map((item) => ({
        value: buildDepartmentPermission(item),
        label: item,
      })),
    [departmentOptions],
  )
  const matrixDepartmentOptions = useMemo(() => ["*", ...departmentOptions], [departmentOptions])

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
              <span>权限</span>

              <div className="permission-sections">
                <section className="permission-section">
                  <div className="permission-section-head">
                    <div>
                      <div className="permission-title">系统-部门-增删改查权限</div>
                      <p className="field-hint">
                        按“某人、某系统、某部门、增删改查”授权，* 表示全部部门。
                      </p>
                    </div>
                  </div>

                  <div className="permission-matrix">
                    <div className="permission-matrix-head">
                      <span>系统</span>
                      <span>部门</span>
                      {PERMISSION_ACTIONS.map((action) => (
                        <span key={action.value}>{action.label}</span>
                      ))}
                    </div>
                    {PERMISSION_SYSTEMS.flatMap((system) =>
                      matrixDepartmentOptions.map((department) => (
                        <div key={`${system.value}-${department}`} className="permission-matrix-row">
                          <span>{system.label}</span>
                          <span>{department === "*" ? "全部部门" : department}</span>
                          {PERMISSION_ACTIONS.map((action) => {
                            const permission = buildMatrixPermission(system.value, department, action.value)
                            return (
                              <label key={permission} className="matrix-check">
                                <input
                                  type="checkbox"
                                  checked={form.permissions.includes(permission)}
                                  onChange={() => togglePermission(permission)}
                                />
                              </label>
                            )
                          })}
                        </div>
                      )),
                    )}
                  </div>
                </section>

                <section className="permission-section">
                  <div className="permission-section-head">
                    <div>
                      <div className="permission-title">兼容功能权限</div>
                      <p className="field-hint">
                        用于兼容旧账号和页面入口控制。新权限请优先在上方矩阵配置。
                      </p>
                    </div>
                  </div>

                  <div className="permission-grid">
                    {[...FEATURE_PERMISSION_OPTIONS, ...departmentPermissionOptions].map((item) => {
                      const checked = form.permissions.includes(item.value)
                      return (
                        <label key={item.value} className={checked ? "permission-chip active" : "permission-chip"}>
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => togglePermission(item.value)}
                          />
                          <span>
                            <strong>{item.label}</strong>
                            {item.description ? <small>{item.description}</small> : null}
                          </span>
                        </label>
                      )
                    })}
                  </div>
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
                              {employee.position ? ` / ${employee.position}` : ""}
                              {employee.rank ? ` / ${employee.rank}` : ""}
                            </div>
                            <div className="employee-tags">
                              <span className="employee-tag">{(employee.permissions ?? []).length} 项权限</span>
                              {departmentPermissions.length ? (
                                <span className="employee-tag accent">
                                  {departmentPermissions.length} 个部门权限
                                </span>
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
