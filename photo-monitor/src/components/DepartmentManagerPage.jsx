import { useState } from "react"
import { BrandMark } from "../pages/DashboardPage"

export default function DepartmentManagerPage({
  departments,
  onBack,
  onCreate,
  onRename,
  onDelete,
}) {
  const [newName, setNewName] = useState("")
  const [editingName, setEditingName] = useState("")
  const [editingValue, setEditingValue] = useState("")
  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)

  const startRename = (name) => {
    setEditingName(name)
    setEditingValue(name)
    setError("")
  }

  const handleCreate = async (event) => {
    event.preventDefault()
    setSaving(true)
    setError("")
    try {
      await onCreate({ name: newName.trim() })
      setNewName("")
    } catch (submitError) {
      setError(submitError.message)
    } finally {
      setSaving(false)
    }
  }

  const handleRename = async (event) => {
    event.preventDefault()
    if (!editingName) {
      return
    }
    setSaving(true)
    setError("")
    try {
      await onRename(editingName, { name: editingValue.trim() })
      setEditingName("")
      setEditingValue("")
    } catch (submitError) {
      setError(submitError.message)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (name) => {
    if (!window.confirm(`确认删除部门 ${name} 吗？`)) {
      return
    }
    setSaving(true)
    setError("")
    try {
      await onDelete(name)
      if (editingName === name) {
        setEditingName("")
        setEditingValue("")
      }
    } catch (submitError) {
      setError(submitError.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="admin-page">
      <div className="admin-page-header">
        <div>
          <BrandMark compact />
          <h2>部门管理</h2>
        </div>
        <button type="button" className="ghost-button" onClick={onBack}>
          返回工作台
        </button>
      </div>

      <div className="admin-layout">
        <section className="admin-panel admin-list-panel">
          <div className="panel-header">
            <div>
              <h3>部门列表</h3>
              <span className="panel-muted">共 {departments.length} 个部门</span>
            </div>
          </div>

          {departments.length ? (
            <div className="department-list">
              {departments.map((name) => (
                <div key={name} className="department-row">
                  <span>{name}</span>
                  <div className="employee-actions">
                    <button type="button" className="ghost-button" onClick={() => startRename(name)} disabled={saving}>
                      改名
                    </button>
                    <button
                      type="button"
                      className="ghost-button danger-button"
                      onClick={() => handleDelete(name)}
                      disabled={saving}
                    >
                      删除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">还没有部门。</div>
          )}
        </section>

        <section className="admin-panel admin-form-panel">
          <form className="stack-form" onSubmit={handleCreate}>
            <section className="admin-form-section">
              <h4>新增部门</h4>
              <label className="field">
                <span>部门名称</span>
                <input value={newName} onChange={(event) => setNewName(event.target.value)} required />
              </label>
              <button type="submit" className="primary-button" disabled={saving}>
                {saving ? "保存中..." : "新增部门"}
              </button>
            </section>
          </form>

          <form className="stack-form" onSubmit={handleRename}>
            <section className="admin-form-section">
              <h4>部门改名</h4>
              <label className="field">
                <span>当前部门</span>
                <input value={editingName} readOnly placeholder="请选择左侧部门" />
              </label>
              <label className="field">
                <span>新名称</span>
                <input
                  value={editingValue}
                  onChange={(event) => setEditingValue(event.target.value)}
                  disabled={!editingName}
                  required
                />
              </label>
              <button type="submit" className="primary-button" disabled={saving || !editingName}>
                {saving ? "保存中..." : "保存改名"}
              </button>
            </section>
          </form>

          {error ? <div className="form-error">{error}</div> : null}
        </section>
      </div>
    </section>
  )
}
