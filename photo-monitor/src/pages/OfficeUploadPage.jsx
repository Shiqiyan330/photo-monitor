import { useEffect, useState } from "react"
import { downloadFile, getAssetUrl } from "../api"
import useOfficeUploads from "../hooks/useOfficeUploads"
import { getDepartmentViewOptions, hasAnyMatrixAction, hasMatrixPermission } from "../permissions"
import { BrandMark } from "./DashboardPage"

export function OfficeModulePage({ title, children, onBack }) {
  return (
    <div className="office-page">
      <section className="office-page-header">
        <div>
          <BrandMark compact />
          <p className="eyebrow">Workspace</p>
          <h2>{title}</h2>
        </div>
        <button type="button" className="ghost-button" onClick={onBack}>
          返回主界面
        </button>
      </section>
      {children}
    </div>
  )
}

function UploadPanel({ title, description, departmentOptions, onSubmit, submitting }) {
  const [department, setDepartment] = useState(departmentOptions[0] ?? "")
  const [file, setFile] = useState(null)
  const [dragging, setDragging] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!department && departmentOptions.length) {
      const timer = window.setTimeout(() => setDepartment(departmentOptions[0]), 0)
      return () => window.clearTimeout(timer)
    }
    return undefined
  }, [department, departmentOptions])

  const selectFile = (files) => {
    const nextFile = files?.[0]
    if (nextFile) {
      setFile(nextFile)
      setError("")
      setProgress(0)
    }
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    if (!file) {
      setError("请选择要上传的文件")
      return
    }

    setError("")
    setProgress(0)
    try {
      await onSubmit({ department, file }, { onProgress: setProgress })
      setFile(null)
      setProgress(0)
    } catch (submitError) {
      setError(submitError.message)
    }
  }

  return (
    <form className="stack-form" onSubmit={handleSubmit}>
      <div>
        <h3>{title}</h3>
        {description ? <p className="panel-muted">{description}</p> : null}
      </div>

      {departmentOptions.length ? (
        <label className="field">
          <span>部门</span>
          <select value={department} onChange={(event) => setDepartment(event.target.value)}>
            {departmentOptions.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <label
        className={dragging ? "file-drop-zone active" : "file-drop-zone"}
        onDragEnter={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          selectFile(event.dataTransfer.files)
        }}
      >
        <input type="file" disabled={submitting} onChange={(event) => selectFile(event.target.files)} />
        <span className="material-symbols-outlined file-drop-icon" aria-hidden="true">
          upload_file
        </span>
        <span className="file-drop-title">{file ? file.name : "拖拽文件到这里，或点击选择文件"}</span>
        <span className="file-drop-meta">{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : "支持常用文档、图片和压缩包"}</span>
      </label>

      {progress > 0 ? (
        <div className="upload-progress">
          <div className="upload-progress-track">
            <span style={{ width: `${progress}%` }} />
          </div>
          <span>{progress}%</span>
        </div>
      ) : null}

      {error ? <div className="form-error">{error}</div> : null}

      <button type="submit" className="primary-button" disabled={submitting}>
        {submitting ? "上传中..." : "上传"}
      </button>
    </form>
  )
}

function UploadList({ title, items, emptyText, onDelete, onDownload, onView, canDeleteItem }) {
  return (
    <section className="office-panel">
      <div className="panel-header">
        <div>
          <h3>{title}</h3>
          <p className="panel-muted">按部门归档，支持在线查看、下载和删除。</p>
        </div>
        <span className="file-count-badge">共 {items.length} 个文件</span>
      </div>

      {items.length ? (
        <div className="file-card-grid">
          {items.map((item) => (
            <article key={item.id ?? item.url ?? item.name} className="file-card">
              <div className="file-card-icon" aria-hidden="true">
                <span className="material-symbols-outlined">description</span>
              </div>
              <div className="file-card-body">
                <div className="file-card-title" title={item.name}>{item.name}</div>
                <div className="file-card-meta">
                  <span>{item.department || "未分配部门"}</span>
                  <span>{item.size ? `${(item.size / 1024 / 1024).toFixed(2)} MB` : "未知大小"}</span>
                </div>
                <div className="file-card-sub">
                  {(item.uploaded_at || item.created_at || "未知时间") + (item.uploader ? ` / ${item.uploader}` : "")}
                </div>
              </div>
              <div className="file-card-actions">
                <button type="button" className="ghost-button" onClick={() => onView(item)}>
                  查看
                </button>
                <button type="button" className="ghost-button" onClick={() => onDownload(item)}>
                  下载
                </button>
                {canDeleteItem?.(item) ? (
                  <button type="button" className="ghost-button danger-button" onClick={() => onDelete(item)}>
                    删除
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state compact-empty-state">{emptyText}</div>
      )}
    </section>
  )
}

export default function OfficeUploadPage({ config, departments, onBack, showBanner, user }) {
  const departmentOptions = getDepartmentViewOptions(user, departments, config.system, "create").filter(Boolean)
  const canUpload = hasAnyMatrixAction(user, config.system, ["create"])
  const { items, loading, uploading, error, loadItems, upload, remove } = useOfficeUploads({
    fetchItems: config.fetchItems,
    uploadItem: config.uploadItem,
    deleteItem: config.deleteItem,
    successMessages: config.messages,
    showBanner,
  })

  const handleView = async (item) => {
    if (!item.id) {
      return
    }
    window.open(config.viewUrl(item.id), "_blank", "noopener,noreferrer")
  }

  const handleDownload = async (item) => {
    if (!item.url) {
      return
    }
    await downloadFile(getAssetUrl(item.url), item.name)
  }

  const handleDelete = async (item) => {
    if (!item.id || !window.confirm(`确认删除${config.deleteLabel}：${item.name}？`)) {
      return
    }
    await remove(item)
  }

  return (
    <OfficeModulePage title={config.pageTitle} onBack={onBack}>
      <section className="office-toolbar">
        <div>
          <h3>{config.toolbarTitle}</h3>
          <p className="panel-muted">{config.toolbarDescription}</p>
        </div>
        <button type="button" className="ghost-button icon-button-text" onClick={loadItems} disabled={loading}>
          <span className="material-symbols-outlined button-icon" aria-hidden="true">
            refresh
          </span>
          {loading ? "刷新中..." : "刷新列表"}
        </button>
      </section>

      {error ? <div className="status-card error-card">{error}</div> : null}

      {canUpload ? (
        <section className="ledger-upload-grid single-column">
          <div className="office-panel">
            <UploadPanel
              title={config.uploadTitle}
              description={config.uploadDescription}
              departmentOptions={departmentOptions}
              onSubmit={upload}
              submitting={uploading}
            />
          </div>
        </section>
      ) : null}

      <UploadList
        title={config.listTitle}
        items={items}
        emptyText={config.emptyText}
        onDelete={handleDelete}
        onDownload={handleDownload}
        onView={handleView}
        canDeleteItem={(item) => hasMatrixPermission(user, config.system, "delete", item.department)}
      />
    </OfficeModulePage>
  )
}

