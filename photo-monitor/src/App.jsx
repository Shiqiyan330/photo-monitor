import { useEffect, useRef, useState } from "react"
import {
  changePassword,
  createEmployee,
  deleteCompanyFile,
  deleteEmployee,
  deleteLedger,
  deleteStudyArticle,
  downloadFile,
  getAuthorizedUrl,
  getAssetUrl,
  fetchLedgers,
  fetchCurrentUser,
  fetchEmployees,
  fetchPhotos,
  fetchStudyArticles,
  fetchUploadedFiles,
  getStoredToken,
  getWebSocketUrl,
  login,
  logout,
  setStoredToken,
  updateEmployee,
  uploadCompanyFile,
  uploadLedger,
  uploadStudyArticle,
} from "./api"
import ChangePasswordModal from "./components/ChangePasswordModal"
import EmployeeManagerPage from "./components/EmployeeManagerPage"
import LoginForm from "./components/LoginForm"
import PhotoGrid from "./components/PhotoGrid"
import PhotoModal from "./components/PhotoModal"
import Toolbar from "./components/Toolbar"

const DEFAULT_STATION = "xiazhan"
const DEFAULT_PHOTO_LIMIT = ""
const DEFAULT_DEDUPE_ENABLED = true
const DEFAULT_DEDUPE_WINDOW_SECONDS = "20"
const PHOTO_FEED_BATCH_SIZE = 24
const MOBILE_PHOTO_FEED_BATCH_SIZE = 4
const PHOTO_LIMIT_STORAGE_KEY = "photo_monitor_photo_limit"
const PHOTO_DEDUPE_ENABLED_STORAGE_KEY = "photo_monitor_dedupe_enabled"
const PHOTO_DEDUPE_WINDOW_STORAGE_KEY = "photo_monitor_dedupe_window"
const PAGE_DASHBOARD = "dashboard"
const PAGE_EMPLOYEES = "employees"
const PAGE_MONITOR = "monitor"
const PAGE_DOCUMENTS = "documents"
const PAGE_LEARNING = "learning"
const PAGE_LEDGER = "ledger"
const PAGE_STRUCTURE = "structure"

const MODULES = [
  {
    key: PAGE_MONITOR,
    permission: "camera",
    title: "监控拍照",
    description: "实时监控与拍照记录",
    accent: "blue",
    icon: "photo_camera",
  },
  {
    key: PAGE_DOCUMENTS,
    permission: "photo_all_departments",
    title: "公司文件",
    description: "公司文档资料库",
    accent: "green",
    icon: "folder_open",
  },
  {
    key: PAGE_LEARNING,
    permission: "study_view",
    title: "学习交流",
    description: "在线学习与文档交流",
    accent: "orange",
    icon: "menu_book",
  },
  {
    key: PAGE_LEDGER,
    permission: "ledger_view",
    title: "台账管理",
    description: "工作台账上传与管理",
    accent: "teal",
    icon: "upload_file",
  },
  {
    key: PAGE_STRUCTURE,
    permission: "structure",
    title: "公司架构",
    description: "组织架构与人员联系",
    accent: "purple",
    icon: "account_tree",
  },
]

function keepDigitsOnly(value) {
  return value.replace(/\D/g, "")
}

function parsePositiveInteger(value) {
  if (!value) {
    return null
  }

  const parsed = Number.parseInt(value, 10)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null
  }

  return parsed
}

function readStoredDigits(key, fallback) {
  const saved = window.localStorage.getItem(key)
  if (!saved) {
    return fallback
  }

  const normalized = keepDigitsOnly(saved)
  return normalized || fallback
}

function readInitialPhotoLimit() {
  return readStoredDigits(PHOTO_LIMIT_STORAGE_KEY, DEFAULT_PHOTO_LIMIT)
}

function readInitialDedupeEnabled() {
  const saved = window.localStorage.getItem(PHOTO_DEDUPE_ENABLED_STORAGE_KEY)
  if (saved == null) {
    return DEFAULT_DEDUPE_ENABLED
  }
  return saved === "true"
}

function readInitialDedupeWindow() {
  return readStoredDigits(PHOTO_DEDUPE_WINDOW_STORAGE_KEY, DEFAULT_DEDUPE_WINDOW_SECONDS)
}

function getPhotoFeedBatchSize() {
  return window.matchMedia("(max-width: 640px)").matches
    ? MOBILE_PHOTO_FEED_BATCH_SIZE
    : PHOTO_FEED_BATCH_SIZE
}

function dedupePhotosByWindow(photos, windowSeconds) {
  if (!windowSeconds || photos.length <= 1) {
    return photos
  }

  const deduped = []
  let lastPhotoTime = null

  for (const photo of photos) {
    if (lastPhotoTime == null || Math.abs(lastPhotoTime - photo.time) > windowSeconds) {
      deduped.push(photo)
    }

    lastPhotoTime = photo.time
  }

  return deduped
}

function uniqueStrings(values) {
  return Array.from(new Set(values.map((item) => (item || "").trim()).filter(Boolean)))
}

function getDepartmentPermissions(user) {
  if (!user) {
    return []
  }

  if (Array.isArray(user.department_permissions)) {
    return uniqueStrings(user.department_permissions)
  }

  return uniqueStrings(
    (user.permissions ?? [])
      .filter((item) => item.startsWith("dept_"))
      .map((item) => item.slice(5)),
  )
}

function getDepartmentViewOptions(user, departments) {
  if (!user) {
    return []
  }

  const departmentOptions =
    user.role === "admin"
      ? uniqueStrings(departments)
      : uniqueStrings([...getDepartmentPermissions(user), user.department ?? ""])

  return departmentOptions.length > 1 ? ["", ...departmentOptions] : departmentOptions
}

function hasCameraPermission(user) {
  return Boolean(user && (user.role === "admin" || user.permissions?.includes("camera")))
}

function hasPermission(user, permission) {
  return Boolean(user && (user.role === "admin" || user.permissions?.includes(permission)))
}

function readCurrentPage() {
  const route = window.location.hash.replace(/^#\/?/, "")
  if (route === PAGE_EMPLOYEES) {
    return PAGE_EMPLOYEES
  }

  if (MODULES.some((module) => module.key === route)) {
    return route
  }

  return PAGE_DASHBOARD
}

function setRoute(page) {
  window.location.hash = page === PAGE_DASHBOARD ? "#/" : `#/${page}`
}

function BrandMark({ compact = false }) {
  return (
    <div className={compact ? "brand-mark compact" : "brand-mark"}>
      <div className="brand-logo-slot" aria-hidden="true">
        <span>Logo</span>
      </div>
      <div>
        <div className="brand-name">越岚索道</div>
        {!compact ? <div className="brand-subtitle">办公管理系统</div> : null}
      </div>
    </div>
  )
}

function DashboardPage({ user, modules, onOpenModule, onOpenEmployees, onOpenPassword, onLogout }) {
  return (
    <div className="dashboard-shell">
      <section className="dashboard-hero">
        <div>
          <BrandMark />
          <p className="eyebrow">Main Dashboard</p>
          <h1>办公管理主界面</h1>
          <p className="hero-copy">根据账号权限展示可用功能，进入对应模块处理监控、文档、学习、台账和组织信息。</p>
        </div>

        <div className="user-panel">
          <div className="user-avatar">{user.avatar}</div>
          <div className="user-name">{user.name}</div>
          <div className="user-meta">
            {(user.role === "admin" ? "管理员" : user.department || "员工") + " / " + user.username}
          </div>
          <div className="user-actions">
            <button type="button" className="ghost-button" onClick={onOpenPassword}>
              修改密码
            </button>
            {user.role === "admin" ? (
              <button type="button" className="ghost-button" onClick={onOpenEmployees}>
                员工管理
              </button>
            ) : null}
            <button type="button" className="ghost-button" onClick={onLogout}>
              退出登录
            </button>
          </div>
        </div>
      </section>

      {modules.length ? (
        <section className="module-grid">
          {modules.map((module) => (
            <button
              key={module.key}
              type="button"
              className={`module-card module-card-${module.accent}`}
              onClick={() => onOpenModule(module.key)}
            >
              <span className="material-symbols-outlined module-icon" aria-hidden="true">
                {module.icon}
              </span>
              <span>
                <span className="module-title">{module.title}</span>
                <span className="module-description">{module.description}</span>
              </span>
              <span className="module-arrow" aria-hidden="true" />
            </button>
          ))}
        </section>
      ) : (
        <div className="status-card">当前账号还没有可用功能，请联系管理员分配权限。</div>
      )}
    </div>
  )
}

function OfficeModulePage({ title, children, onBack }) {
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
      setDepartment(departmentOptions[0])
    }
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

function UploadList({ title, items, emptyText, onDelete, onDownload, onView }) {
  return (
    <section className="office-panel">
      <div className="panel-header">
        <h3>{title}</h3>
        <span className="panel-muted">共 {items.length} 个文件</span>
      </div>

      {items.length ? (
        <div className="upload-list">
          {items.map((item) => (
            <article key={item.id ?? item.url ?? item.name} className="upload-list-row">
              <div>
                <div className="employee-main">{item.name}</div>
                <div className="employee-sub">
                  {(item.department || "未分配部门") + " / " + (item.size ? `${(item.size / 1024 / 1024).toFixed(2)} MB` : "未知大小")}
                </div>
                <div className="employee-sub">
                  {(item.uploaded_at || item.created_at || "未知时间") + (item.uploader ? ` / ${item.uploader}` : "")}
                </div>
              </div>
              <div className="employee-actions">
                <button type="button" className="ghost-button" onClick={() => onView(item)}>
                  查看
                </button>
                <button type="button" className="ghost-button" onClick={() => onDownload(item)}>
                  下载
                </button>
                <button type="button" className="ghost-button danger-button" onClick={() => onDelete(item)}>
                  删除
                </button>
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

function DocumentsPage({ onBack, user, departments, showBanner }) {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState("")
  const departmentOptions = getDepartmentViewOptions(user, departments).filter(Boolean)

  const loadFiles = async () => {
    setLoading(true)
    setError("")
    try {
      const data = await fetchUploadedFiles()
      setFiles(data.items ?? [])
    } catch (loadError) {
      setError(loadError.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadFiles()
  }, [])

  const handleUpload = async (payload, options) => {
    setUploading(true)
    try {
      await uploadCompanyFile(payload, options)
      showBanner("文件上传成功")
      await loadFiles()
    } finally {
      setUploading(false)
    }
  }

  const handleView = async (item) => {
    window.open(getAuthorizedUrl(item.url), "_blank", "noopener,noreferrer")
  }

  const handleDownload = async (item) => {
    await downloadFile(getAssetUrl(item.url), item.name)
  }

  const handleDelete = async (item) => {
    if (!item.id || !window.confirm(`确认删除文件：${item.name}？`)) {
      return
    }
    await deleteCompanyFile(item.id)
    showBanner("文件已删除")
    await loadFiles()
  }

  return (
    <OfficeModulePage title="公司文件" onBack={onBack}>
      <section className="office-toolbar">
        <div>
          <h3>公司文件</h3>
          <p className="panel-muted">部门资料、通知附件和通用文档统一保存到公司文件目录。</p>
        </div>
        <button type="button" className="ghost-button icon-button-text" onClick={loadFiles} disabled={loading}>
          <span className="material-symbols-outlined button-icon" aria-hidden="true">
            refresh
          </span>
          {loading ? "刷新中..." : "刷新列表"}
        </button>
      </section>

      {error ? <div className="status-card error-card">{error}</div> : null}

      <section className="ledger-upload-grid single-column">
        <div className="office-panel">
          <UploadPanel
            title="上传公司文件"
            description="支持图片、PDF、Office 表格、文本、压缩包等常用资料。"
            departmentOptions={departmentOptions}
            onSubmit={handleUpload}
            submitting={uploading}
          />
        </div>
      </section>

      <UploadList
        title="公司文件列表"
        items={files}
        emptyText="还没有上传公司文件。"
        onDelete={handleDelete}
        onDownload={handleDownload}
        onView={handleView}
      />
    </OfficeModulePage>
  )
}

function LearningPage({ onBack, user, departments, showBanner }) {
  const [articles, setArticles] = useState([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState("")
  const departmentOptions = getDepartmentViewOptions(user, departments).filter(Boolean)

  const loadArticles = async () => {
    setLoading(true)
    setError("")
    try {
      const data = await fetchStudyArticles()
      setArticles(data.items ?? [])
    } catch (loadError) {
      setError(loadError.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadArticles()
  }, [])

  const handleUpload = async (payload, options) => {
    setUploading(true)
    try {
      await uploadStudyArticle(payload, options)
      showBanner("学习文章上传成功")
      await loadArticles()
    } finally {
      setUploading(false)
    }
  }

  const handleView = async (item) => {
    window.open(getAuthorizedUrl(item.url), "_blank", "noopener,noreferrer")
  }

  const handleDownload = async (item) => {
    await downloadFile(getAssetUrl(item.url), item.name)
  }

  const handleDelete = async (item) => {
    if (!item.id || !window.confirm(`确认删除学习文章：${item.name}？`)) {
      return
    }
    await deleteStudyArticle(item.id)
    showBanner("学习文章已删除")
    await loadArticles()
  }

  return (
    <OfficeModulePage title="学习交流" onBack={onBack}>
      <section className="office-toolbar">
        <div>
          <h3>学习文章</h3>
          <p className="panel-muted">上传培训资料、制度学习文档和内部交流文章，列表按账号可访问部门过滤。</p>
        </div>
        <button type="button" className="ghost-button icon-button-text" onClick={loadArticles} disabled={loading}>
          <span className="material-symbols-outlined button-icon" aria-hidden="true">
            refresh
          </span>
          {loading ? "刷新中..." : "刷新列表"}
        </button>
      </section>

      {error ? <div className="status-card error-card">{error}</div> : null}

      <section className="ledger-upload-grid single-column">
        <div className="office-panel">
          <UploadPanel
            title="上传学习文章"
            description="支持 PDF、Word、PPT、文本、Markdown、HTML 和压缩包。"
            departmentOptions={departmentOptions}
            onSubmit={handleUpload}
            submitting={uploading}
          />
        </div>
      </section>

      <UploadList
        title="学习文章列表"
        items={articles}
        emptyText="还没有上传学习文章。"
        onDelete={handleDelete}
        onDownload={handleDownload}
        onView={handleView}
      />
    </OfficeModulePage>
  )
}

function LedgerWorkspacePage({ onBack, user, departments, showBanner }) {
  const [ledgers, setLedgers] = useState([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState("")
  const departmentOptions = getDepartmentViewOptions(user, departments).filter(Boolean)

  const loadLists = async () => {
    setLoading(true)
    setError("")
    try {
      const ledgerData = await fetchLedgers()
      setLedgers(ledgerData.items ?? [])
    } catch (loadError) {
      setError(loadError.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadLists()
  }, [])

  const handleLedgerUpload = async (payload, options) => {
    setUploading(true)
    try {
      await uploadLedger(payload, options)
      showBanner("台账上传成功")
      await loadLists()
    } finally {
      setUploading(false)
    }
  }

  const handleDeleteLedger = async (item) => {
    if (!item.id || !window.confirm(`确认删除台账：${item.name}？`)) {
      return
    }
    await deleteLedger(item.id)
    showBanner("台账已删除")
    await loadLists()
  }

  const handleView = async (item) => {
    if (!item.url) {
      return
    }
    window.open(getAuthorizedUrl(item.url), "_blank", "noopener,noreferrer")
  }

  const handleDownload = async (item) => {
    if (!item.url) {
      return
    }
    await downloadFile(getAssetUrl(item.url), item.name)
  }

  return (
    <OfficeModulePage title="台账管理" onBack={onBack}>
      <section className="office-toolbar">
        <div>
          <h3>台账上传</h3>
          <p className="panel-muted">工作台账、日报、月报和 Excel 表格统一保存到台账目录。</p>
        </div>
        <button type="button" className="ghost-button icon-button-text" onClick={loadLists} disabled={loading}>
          <span className="material-symbols-outlined button-icon" aria-hidden="true">
            refresh
          </span>
          {loading ? "刷新中..." : "刷新列表"}
        </button>
      </section>

      {error ? <div className="status-card error-card">{error}</div> : null}

      <section className="ledger-upload-grid single-column">
        <div className="office-panel">
          <UploadPanel
            title="上传台账"
            description="用于工作台账、日报、月报、Excel 表格等。"
            departmentOptions={departmentOptions}
            onSubmit={handleLedgerUpload}
            submitting={uploading}
          />
        </div>
      </section>

      <UploadList
        title="台账列表"
        items={ledgers}
        emptyText="还没有上传台账。"
        onDelete={handleDeleteLedger}
        onDownload={handleDownload}
        onView={handleView}
      />
    </OfficeModulePage>
  )
}
function StructurePage({ onBack, user, employees }) {
  const [collapsedDepartments, setCollapsedDepartments] = useState(new Set())
  const visibleEmployees = user.role === "admin" ? employees : [user]
  const groups = new Map()

  for (const employee of visibleEmployees) {
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
function App() {
  const [user, setUser] = useState(null)
  const [booting, setBooting] = useState(true)
  const [authError, setAuthError] = useState("")
  const [photos, setPhotos] = useState([])
  const [photoCursor, setPhotoCursor] = useState(null)
  const [photoTotal, setPhotoTotal] = useState(0)
  const [station, setStation] = useState(DEFAULT_STATION)
  const [photoLimit, setPhotoLimit] = useState(readInitialPhotoLimit)
  const [dedupeEnabled, setDedupeEnabled] = useState(readInitialDedupeEnabled)
  const [dedupeWindowSeconds, setDedupeWindowSeconds] = useState(readInitialDedupeWindow)
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")
  const [selectedPhoto, setSelectedPhoto] = useState(null)
  const [loadingPhotos, setLoadingPhotos] = useState(false)
  const [loadingMorePhotos, setLoadingMorePhotos] = useState(false)
  const [photoError, setPhotoError] = useState("")
  const [employees, setEmployees] = useState([])
  const [departments, setDepartments] = useState([])
  const [currentPage, setCurrentPage] = useState(readCurrentPage)
  const [passwordModalOpen, setPasswordModalOpen] = useState(false)
  const [bannerMessage, setBannerMessage] = useState("")
  const wsRef = useRef(null)
  const bannerTimerRef = useRef(0)

  const hasPhotoAccess = hasCameraPermission(user)
  const parsedPhotoLimit = parsePositiveInteger(photoLimit)
  const parsedDedupeWindow =
    parsePositiveInteger(dedupeWindowSeconds) ??
    parsePositiveInteger(DEFAULT_DEDUPE_WINDOW_SECONDS)
  const filteredPhotos = dedupeEnabled ? dedupePhotosByWindow(photos, parsedDedupeWindow) : photos
  const limitedPhotos = parsedPhotoLimit ? filteredPhotos.slice(0, parsedPhotoLimit) : filteredPhotos
  const displayedPhotos = limitedPhotos
  const hasMorePhotos = photoCursor != null && (!parsedPhotoLimit || photos.length < parsedPhotoLimit)
  const accessibleModules = MODULES.filter((module) => hasPermission(user, module.permission))

  const getNextPhotoPageSize = () => {
    const batchSize = getPhotoFeedBatchSize()
    if (!parsedPhotoLimit) {
      return batchSize
    }

    return Math.max(Math.min(batchSize, parsedPhotoLimit - photos.length), 0)
  }

  const showBanner = (message) => {
    setBannerMessage(message)
    window.clearTimeout(bannerTimerRef.current)
    bannerTimerRef.current = window.setTimeout(() => setBannerMessage(""), 2400)
  }

  const loadCurrentUser = async () => {
    if (!getStoredToken()) {
      setBooting(false)
      setUser(null)
      return
    }

    try {
      const data = await fetchCurrentUser()
      setUser(data.user)
      setAuthError("")
    } catch (error) {
      if (error.status !== 401) {
        setAuthError(error.message)
      }
      setStoredToken("")
      setUser(null)
    } finally {
      setBooting(false)
    }
  }

  const loadPhotos = async (nextStation = station) => {
    if (!hasPhotoAccess) {
      setPhotos([])
      setPhotoCursor(null)
      setPhotoTotal(0)
      setPhotoError("")
      setLoadingPhotos(false)
      return
    }

    setLoadingPhotos(true)
    setLoadingMorePhotos(false)
    setPhotoError("")

    try {
      const initialLimit = parsedPhotoLimit
        ? Math.min(getPhotoFeedBatchSize(), parsedPhotoLimit)
        : getPhotoFeedBatchSize()
      const data = await fetchPhotos(nextStation, "", {
        limit: initialLimit,
        cursor: 0,
        startDate,
        endDate,
      })
      setPhotos(data.items ?? data)
      setPhotoCursor(data.next_cursor ?? null)
      setPhotoTotal(data.total ?? data.length ?? 0)
    } catch (error) {
      setPhotos([])
      setPhotoCursor(null)
      setPhotoTotal(0)
      setPhotoError(error.message)
      if (error.status === 401) {
        setStoredToken("")
        setUser(null)
      }
    } finally {
      setLoadingPhotos(false)
    }
  }

  const loadMorePhotos = async () => {
    if (!hasMorePhotos || loadingPhotos || loadingMorePhotos) {
      return
    }

    const pageSize = getNextPhotoPageSize()
    if (!pageSize) {
      return
    }

    setLoadingMorePhotos(true)
    setPhotoError("")

    try {
      const data = await fetchPhotos(station, "", {
        limit: pageSize,
        cursor: photoCursor,
        startDate,
        endDate,
      })
      setPhotos((current) => [...current, ...(data.items ?? data)])
      setPhotoCursor(data.next_cursor ?? null)
      setPhotoTotal(data.total ?? photoTotal)
    } catch (error) {
      setPhotoError(error.message)
      if (error.status === 401) {
        setStoredToken("")
        setUser(null)
      }
    } finally {
      setLoadingMorePhotos(false)
    }
  }

  const loadEmployees = async () => {
    const data = await fetchEmployees()
    setEmployees(data.employees)
    setDepartments(data.departments)
  }

  useEffect(() => {
    loadCurrentUser()
  }, [])

  useEffect(() => {
    const handleHashChange = () => setCurrentPage(readCurrentPage())
    window.addEventListener("hashchange", handleHashChange)
    return () => window.removeEventListener("hashchange", handleHashChange)
  }, [])

  useEffect(() => {
    window.localStorage.setItem(PHOTO_LIMIT_STORAGE_KEY, photoLimit)
  }, [photoLimit])

  useEffect(() => {
    window.localStorage.setItem(PHOTO_DEDUPE_ENABLED_STORAGE_KEY, String(dedupeEnabled))
  }, [dedupeEnabled])

  useEffect(() => {
    window.localStorage.setItem(PHOTO_DEDUPE_WINDOW_STORAGE_KEY, dedupeWindowSeconds)
  }, [dedupeWindowSeconds])

  useEffect(() => {
    if (!user) {
      setPhotos([])
      setPhotoCursor(null)
      setPhotoTotal(0)
      setEmployees([])
      setDepartments([])
      setStartDate("")
      setEndDate("")
      setSelectedPhoto(null)
      return
    }

    if (currentPage !== PAGE_MONITOR) {
      return
    }

    if (!hasPhotoAccess) {
      setPhotos([])
      setPhotoCursor(null)
      setPhotoTotal(0)
      setPhotoError("")
      setSelectedPhoto(null)
      return
    }

    loadPhotos()
  }, [station, startDate, endDate, user, hasPhotoAccess, currentPage])

  useEffect(() => {
    if (!user || user.role !== "admin") {
      setEmployees([])
      setDepartments([])
      if (currentPage === PAGE_EMPLOYEES) {
        setRoute(PAGE_DASHBOARD)
      }
      return
    }

    loadEmployees()
  }, [user, currentPage])

  useEffect(() => {
    if (!user || currentPage === PAGE_DASHBOARD || currentPage === PAGE_EMPLOYEES) {
      return
    }

    const module = MODULES.find((item) => item.key === currentPage)
    if (module && !hasPermission(user, module.permission)) {
      setRoute(PAGE_DASHBOARD)
    }
  }, [user, currentPage])

  useEffect(() => {
    if (!user) {
      wsRef.current?.close()
      wsRef.current = null
      return
    }

    if (!hasPhotoAccess || currentPage !== PAGE_MONITOR) {
      wsRef.current?.close()
      wsRef.current = null
      return
    }

    const ws = new WebSocket(getWebSocketUrl())
    wsRef.current = ws

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === "new_photo") {
        loadPhotos()
      }
    }

    ws.onclose = () => {
      if (wsRef.current === ws) {
        wsRef.current = null
      }
    }

    return () => {
      ws.close()
      if (wsRef.current === ws) {
        wsRef.current = null
      }
    }
  }, [user, station, hasPhotoAccess, currentPage])

  useEffect(() => {
    return () => window.clearTimeout(bannerTimerRef.current)
  }, [])

  const handleLogin = async ({ username, password }) => {
    const result = await login(username, password)
    setUser(result.user)
    setStation(DEFAULT_STATION)
    setStartDate("")
    setEndDate("")
    setPhotos([])
    setPhotoCursor(null)
    setPhotoTotal(0)
    setSelectedPhoto(null)
    setAuthError("")
  }

  const handleLogout = async () => {
    await logout()
    wsRef.current?.close()
    wsRef.current = null
    setUser(null)
    setPhotos([])
    setPhotoCursor(null)
    setPhotoTotal(0)
    setStartDate("")
    setEndDate("")
    setSelectedPhoto(null)
    setPasswordModalOpen(false)
    setCurrentPage(PAGE_DASHBOARD)
    setRoute(PAGE_DASHBOARD)
  }

  const handleChangePassword = async ({ oldPassword, newPassword }) => {
    const result = await changePassword(oldPassword, newPassword)
    setUser(result.user)
    showBanner("密码修改成功")
  }

  const handleCreateEmployee = async (payload) => {
    await createEmployee(payload)
    await loadEmployees()
    showBanner("员工已新增")
  }

  const handleUpdateEmployee = async (username, payload) => {
    await updateEmployee(username, payload)
    await loadEmployees()
    showBanner("员工信息已更新")
  }

  const handleDeleteEmployee = async (username) => {
    await deleteEmployee(username)
    await loadEmployees()
    showBanner("员工已删除")
  }

  const openEmployeePage = () => {
    setCurrentPage(PAGE_EMPLOYEES)
    setRoute(PAGE_EMPLOYEES)
  }

  const openMonitorPage = () => {
    setCurrentPage(PAGE_MONITOR)
    setRoute(PAGE_MONITOR)
  }

  const openDashboardPage = () => {
    setCurrentPage(PAGE_DASHBOARD)
    setRoute(PAGE_DASHBOARD)
  }

  const openModulePage = (page) => {
    setCurrentPage(page)
    setRoute(page)
  }

  if (booting) {
    return (
      <div className="app-shell">
        <div className="status-card">正在恢复登录状态...</div>
      </div>
    )
  }

  if (!user) {
    return (
      <div className="app-shell auth-shell">
        <LoginForm onSubmit={handleLogin} serverMessage={authError} />
      </div>
    )
  }

  if (currentPage === PAGE_DASHBOARD) {
    return (
      <div className="app-shell dashboard-app-shell">
        {bannerMessage ? <div className="status-card success-card">{bannerMessage}</div> : null}

        <DashboardPage
          user={user}
          modules={accessibleModules}
          onOpenModule={openModulePage}
          onOpenEmployees={openEmployeePage}
          onOpenPassword={() => setPasswordModalOpen(true)}
          onLogout={handleLogout}
        />

        {passwordModalOpen ? (
          <ChangePasswordModal
            onClose={() => setPasswordModalOpen(false)}
            onSubmit={handleChangePassword}
          />
        ) : null}
      </div>
    )
  }

  if (currentPage === PAGE_EMPLOYEES && user.role === "admin") {
    return (
      <div className="app-shell admin-page-shell">
        {bannerMessage ? <div className="status-card success-card">{bannerMessage}</div> : null}

        <EmployeeManagerPage
          employees={employees}
          departments={departments}
          onBack={openDashboardPage}
          onCreate={handleCreateEmployee}
          onUpdate={handleUpdateEmployee}
          onDelete={handleDeleteEmployee}
        />

        {passwordModalOpen ? (
          <ChangePasswordModal
            onClose={() => setPasswordModalOpen(false)}
            onSubmit={handleChangePassword}
          />
        ) : null}
      </div>
    )
  }

  if (currentPage === PAGE_DOCUMENTS && hasPermission(user, "photo_all_departments")) {
    return (
      <div className="app-shell office-page-shell">
        <DocumentsPage user={user} departments={departments} showBanner={showBanner} onBack={openDashboardPage} />
      </div>
    )
  }

  if (currentPage === PAGE_LEARNING && hasPermission(user, "study_view")) {
    return (
      <div className="app-shell office-page-shell">
        <LearningPage user={user} departments={departments} showBanner={showBanner} onBack={openDashboardPage} />
      </div>
    )
  }

  if (currentPage === PAGE_LEDGER && hasPermission(user, "ledger_view")) {
    return (
      <div className="app-shell office-page-shell">
        <LedgerWorkspacePage user={user} departments={departments} showBanner={showBanner} onBack={openDashboardPage} />
      </div>
    )
  }

  if (currentPage === PAGE_STRUCTURE && hasPermission(user, "structure")) {
    return (
      <div className="app-shell office-page-shell">
        <StructurePage user={user} employees={employees} onBack={openDashboardPage} />
      </div>
    )
  }

  return (
    <div className="app-shell">
      <section className="hero-card">
        <div>
          <BrandMark compact />
          <p className="eyebrow">Photo Monitor</p>
          <h1>员工监控照片工作台</h1>
          <p className="hero-copy">支持按站点和时间段查看照片，控制展示数量，并按秒级时间窗去重展示。</p>

        </div>

        <div className="user-panel">
          <div className="user-avatar">{user.avatar}</div>
          <div className="user-name">{user.name}</div>
          <div className="user-meta">
            {(user.role === "admin" ? "管理员" : user.department || "员工") + " / " + user.username}
          </div>
          <div className="user-actions">
            <button type="button" className="ghost-button" onClick={openDashboardPage}>
              返回主界面
            </button>
            <button type="button" className="ghost-button" onClick={() => setPasswordModalOpen(true)}>
              修改密码
            </button>
            {user.role === "admin" ? (
              <button type="button" className="ghost-button" onClick={openEmployeePage}>
                员工管理
              </button>
            ) : null}
            <button type="button" className="ghost-button" onClick={handleLogout}>
              退出登录
            </button>
          </div>
        </div>
      </section>

      {bannerMessage ? <div className="status-card success-card">{bannerMessage}</div> : null}

      {hasPhotoAccess ? (
        <>
          <Toolbar
            station={station}
            setStation={setStation}
            photoLimit={photoLimit}
            setPhotoLimit={(value) => setPhotoLimit(keepDigitsOnly(value))}
            dedupeEnabled={dedupeEnabled}
            setDedupeEnabled={setDedupeEnabled}
            dedupeWindowSeconds={dedupeWindowSeconds}
            setDedupeWindowSeconds={(value) => setDedupeWindowSeconds(keepDigitsOnly(value))}
            startDate={startDate}
            setStartDate={setStartDate}
            endDate={endDate}
            setEndDate={setEndDate}
            onRefresh={() => loadPhotos(station)}
            loading={loadingPhotos}
          />

          {photoError ? <div className="status-card error-card">{photoError}</div> : null}

          {!photoError ? (
            <PhotoGrid
              photos={displayedPhotos}
              loading={loadingPhotos || loadingMorePhotos}
              station={station}
              displayCount={displayedPhotos.length}
              totalCount={parsedPhotoLimit ? Math.min(photoTotal, parsedPhotoLimit) : photoTotal}
              originalCount={photoTotal}
              hasMore={hasMorePhotos}
              onLoadMore={loadMorePhotos}
              onClickPhoto={(photo) => setSelectedPhoto(photo)}
            />
          ) : null}
        </>
      ) : (
        <div className="status-card">
          当前账号没有监控查看权限，监控站点、展示去重和部门切换区域已自动隐藏。
        </div>
      )}

      <PhotoModal photo={selectedPhoto} onClose={() => setSelectedPhoto(null)} />

      {passwordModalOpen ? (
        <ChangePasswordModal
          onClose={() => setPasswordModalOpen(false)}
          onSubmit={handleChangePassword}
        />
      ) : null}
    </div>
  )
}

export default App
