import { useEffect, useRef, useState } from "react"
import { DEPARTMENT_USAGE_LABELS, hasDepartmentUsage } from "../departmentUsage"
import { BrandMark } from "../pages/DashboardPage"

function DepartmentDeleteDialog({ departments, error, onClose, onConfirm, saving, state, onTargetChange }) {
  const targetRef = useRef(null)
  const targetOptions = departments.filter((name) => name !== state.name)

  useEffect(() => {
    targetRef.current?.focus()

    const handleKeyDown = (event) => {
      if (event.key === "Escape" && !saving) {
        onClose()
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [onClose, saving])

  return (
    <div className="modal-backdrop" onClick={saving ? undefined : onClose}>
      <section
        className="modal-card side-modal modal-card-enter department-delete-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="department-delete-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <h3 id="department-delete-title">迁移并删除部门</h3>
            <span className="panel-muted">{state.name}</span>
          </div>
          <button type="button" className="modal-close" onClick={onClose} disabled={saving}>
            关闭
          </button>
        </div>

        <div className="department-usage-grid" aria-label="关联数据数量">
          {DEPARTMENT_USAGE_LABELS.map(([key, label]) => (
            <div key={key}>
              <span>{label}</span>
              <strong>{Number(state.usage[key] ?? 0)}</strong>
            </div>
          ))}
        </div>

        <form className="stack-form" onSubmit={onConfirm}>
          <label className="field" htmlFor="department-delete-target">
            <span>迁移到</span>
            <select
              ref={targetRef}
              id="department-delete-target"
              value={state.target}
              onChange={(event) => onTargetChange(event.target.value)}
              disabled={saving}
              required
            >
              <option value="">请选择目标部门</option>
              {targetOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>

          {!targetOptions.length ? <div className="form-error">没有可接收数据的其他部门。</div> : null}
          {error ? <div className="form-error">{error}</div> : null}

          <button
            type="submit"
            className="primary-button danger-button department-delete-submit"
            disabled={saving || !state.target}
          >
            {saving ? "迁移中..." : "迁移并删除"}
          </button>
        </form>
      </section>
    </div>
  )
}

export default function DepartmentManagerPage({
  departments,
  onBack,
  onCreate,
  onDelete,
  onGetUsage,
  onMerge,
  onRename,
}) {
  const [newName, setNewName] = useState("")
  const [editingName, setEditingName] = useState("")
  const [editingValue, setEditingValue] = useState("")
  const [error, setError] = useState("")
  const [saving, setSaving] = useState(false)
  const [deleteState, setDeleteState] = useState(null)

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
    setSaving(true)
    setError("")
    try {
      const usage = await onGetUsage(name)
      if (hasDepartmentUsage(usage)) {
        setDeleteState({ name, usage, target: "" })
        return
      }
      if (!window.confirm(`确认删除部门 ${name} 吗？`)) {
        return
      }
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

  const closeDeleteDialog = () => {
    if (!saving) {
      setDeleteState(null)
      setError("")
    }
  }

  const handleDeleteTargetChange = (target) => {
    setDeleteState((current) => (current ? { ...current, target } : current))
  }

  const handleMergeDelete = async (event) => {
    event.preventDefault()
    if (!deleteState?.target) {
      return
    }
    setSaving(true)
    setError("")
    try {
      await onMerge(deleteState.name, deleteState.target)
      if (editingName === deleteState.name) {
        setEditingName("")
        setEditingValue("")
      }
      setDeleteState(null)
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

          {error && !deleteState ? <div className="form-error">{error}</div> : null}
        </section>
      </div>

      {deleteState ? (
        <DepartmentDeleteDialog
          departments={departments}
          error={error}
          onClose={closeDeleteDialog}
          onConfirm={handleMergeDelete}
          onTargetChange={handleDeleteTargetChange}
          saving={saving}
          state={deleteState}
        />
      ) : null}
    </section>
  )
}
