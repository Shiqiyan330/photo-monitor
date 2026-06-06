import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  createEmployee,
  deleteCompanyFile,
  deleteEmployee,
  deleteLedger,
  deleteStudyArticle,
  downloadFile,
  getAssetUrl,
  fetchLedgers,
  fetchEmployees,
  fetchStructureEmployees,
  fetchStudyArticles,
  fetchUploadedFiles,
  updateEmployee,
  uploadCompanyFile,
  uploadLedger,
  uploadStudyArticle,
  viewLedger,
  viewStudyArticle,
  viewUploadedFile,
} from "./api"
import ChangePasswordModal from "./components/ChangePasswordModal"
import EmployeeManagerPage from "./components/EmployeeManagerPage"
import LoginForm from "./components/LoginForm"
import PhotoGrid from "./components/PhotoGrid"
import PhotoModal from "./components/PhotoModal"
import Toolbar from "./components/Toolbar"
import useAuth from "./hooks/useAuth"
import usePhotoFeed, { DEFAULT_STATION, keepDigitsOnly } from "./hooks/usePhotoFeed"
import {
  getDepartmentViewOptions,
  getStructureVisibleDepartments,
  hasAnyMatrixAction,
  hasCameraPermission,
  hasMatrixPermission,
  hasMatrixReadPermission,
  hasModuleAccess,
  uniqueStrings,
} from "./permissions"

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
    matrixSystem: "photos",
    title: "监控拍照",
    description: "实时监控与拍照记录",
    accent: "blue",
    icon: "photo_camera",
  },
  {
    key: PAGE_DOCUMENTS,
    matrixSystem: "company_files",
    title: "公司文件",
    description: "公司文档资料库",
    accent: "green",
    icon: "folder_open",
  },
  {
    key: PAGE_LEARNING,
    matrixSystem: "study_articles",
    title: "学习交流",
    description: "在线学习与文档交流",
    accent: "orange",
    icon: "menu_book",
  },
  {
    key: PAGE_LEDGER,
    matrixSystem: "ledgers",
    title: "台账管理",
    description: "工作台账上传与管理",
    accent: "teal",
    icon: "upload_file",
  },
  {
    key: PAGE_STRUCTURE,
    matrixSystem: "structure",
    title: "公司架构",
    description: "组织架构与人员联系",
    accent: "purple",
    icon: "account_tree",
  },
]

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
        <div className="brand-name">监控照片管理系统</div>
        {!compact ? <div className="brand-subtitle">越岚索道</div> : null}
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
          <h1>监控照片管理系统</h1>
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

function DocumentsPage({ onBack, user, departments, showBanner }) {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState("")
  const departmentOptions = getDepartmentViewOptions(user, departments, "company_files", "create").filter(Boolean)
  const canUpload = hasAnyMatrixAction(user, "company_files", ["create"])

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
    const timer = window.setTimeout(loadFiles, 0)
    return () => window.clearTimeout(timer)
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
    window.open(viewUploadedFile(item.id), "_blank", "noopener,noreferrer")
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

      {canUpload ? (
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
      ) : null}

      <UploadList
        title="公司文件列表"
        items={files}
        emptyText="还没有上传公司文件。"
        onDelete={handleDelete}
        onDownload={handleDownload}
        onView={handleView}
        canDeleteItem={(item) => hasMatrixPermission(user, "company_files", "delete", item.department)}
      />
    </OfficeModulePage>
  )
}

function LearningPage({ onBack, user, departments, showBanner }) {
  const [articles, setArticles] = useState([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState("")
  const departmentOptions = getDepartmentViewOptions(user, departments, "study_articles", "create").filter(Boolean)
  const canUpload = hasAnyMatrixAction(user, "study_articles", ["create"])

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
    const timer = window.setTimeout(loadArticles, 0)
    return () => window.clearTimeout(timer)
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
    window.open(viewStudyArticle(item.id), "_blank", "noopener,noreferrer")
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

      {canUpload ? (
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
      ) : null}

      <UploadList
        title="学习文章列表"
        items={articles}
        emptyText="还没有上传学习文章。"
        onDelete={handleDelete}
        onDownload={handleDownload}
        onView={handleView}
        canDeleteItem={(item) => hasMatrixPermission(user, "study_articles", "delete", item.department)}
      />
    </OfficeModulePage>
  )
}

function LedgerWorkspacePage({ onBack, user, departments, showBanner }) {
  const [ledgers, setLedgers] = useState([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState("")
  const departmentOptions = getDepartmentViewOptions(user, departments, "ledgers", "create").filter(Boolean)
  const canUpload = hasAnyMatrixAction(user, "ledgers", ["create"])

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
    const timer = window.setTimeout(loadLists, 0)
    return () => window.clearTimeout(timer)
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
    window.open(viewLedger(item.id), "_blank", "noopener,noreferrer")
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

      {canUpload ? (
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
      ) : null}

      <UploadList
        title="台账列表"
        items={ledgers}
        emptyText="还没有上传台账。"
        onDelete={handleDeleteLedger}
        onDownload={handleDownload}
        onView={handleView}
        canDeleteItem={(item) => hasMatrixPermission(user, "ledgers", "delete", item.department)}
      />
    </OfficeModulePage>
  )
}
function StructurePage({ onBack, user, employees }) {
  const [collapsedDepartments, setCollapsedDepartments] = useState(new Set())
  const allDepartments = uniqueStrings(employees.map((employee) => employee.department))
  const visibleDepartments = getStructureVisibleDepartments(user, allDepartments)
  const visibleEmployees =
    user.role === "admin"
      ? employees
      : employees.filter((employee) => visibleDepartments.includes(employee.department || ""))
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
  const [employees, setEmployees] = useState([])
  const [departments, setDepartments] = useState([])
  const [currentPage, setCurrentPage] = useState(readCurrentPage)
  const [passwordModalOpen, setPasswordModalOpen] = useState(false)
  const [bannerMessage, setBannerMessage] = useState("")
  const bannerTimerRef = useRef(0)

  const showBanner = useCallback((message) => {
    setBannerMessage(message)
    window.clearTimeout(bannerTimerRef.current)
    bannerTimerRef.current = window.setTimeout(() => setBannerMessage(""), 2400)
  }, [])

  const {
    user,
    setUser,
    booting,
    authError,
    handleLogin: loginUser,
    handleLogout: logoutUser,
    handleChangePassword,
  } = useAuth({
    onPasswordChanged: () => showBanner("密码修改成功"),
  })

  const hasPhotoAccess = useMemo(() => hasCameraPermission(user), [user])
  const accessibleModules = useMemo(() => MODULES.filter((module) => hasModuleAccess(user, module)), [user])
  const photoDepartmentOptions = useMemo(() => getDepartmentViewOptions(user, departments), [departments, user])

  const photoFeed = usePhotoFeed({
    user,
    hasPhotoAccess,
    currentPage,
    monitorPageKey: PAGE_MONITOR,
    setUser,
  })
  const {
    station,
    setStation,
    photoLimit,
    setPhotoLimit,
    dedupeEnabled,
    setDedupeEnabled,
    dedupeWindowSeconds,
    setDedupeWindowSeconds,
    startTime,
    setStartTime,
    endTime,
    setEndTime,
    selectedDepartment,
    setSelectedDepartment,
    selectedPhoto,
    setSelectedPhoto,
    loadingPhotos,
    loadingMorePhotos,
    photoError,
    displayedPhotos,
    hasMorePhotos,
    parsedPhotoLimit,
    loadPhotos,
    loadMorePhotos,
    photoTotal,
    resetPhotoState,
  } = photoFeed

  const loadEmployees = useCallback(async () => {
    const data = await fetchEmployees()
    setEmployees(data.employees)
    setDepartments(data.departments)
  }, [])

  const loadStructureEmployees = useCallback(async () => {
    const data = await fetchStructureEmployees()
    setEmployees(data.employees)
    setDepartments(data.departments)
  }, [])

  useEffect(() => {
    const handleHashChange = () => setCurrentPage(readCurrentPage())
    window.addEventListener("hashchange", handleHashChange)
    return () => window.removeEventListener("hashchange", handleHashChange)
  }, [])

  useEffect(() => {
    if (!user) {
      const timer = window.setTimeout(() => {
        setEmployees([])
        setDepartments([])
      }, 0)
      return () => window.clearTimeout(timer)
    }
    return undefined
  }, [user])

  useEffect(() => {
    if (!user || user.role !== "admin") {
      const timer = window.setTimeout(() => {
        setEmployees([])
        setDepartments([])
        if (currentPage === PAGE_EMPLOYEES) {
          setRoute(PAGE_DASHBOARD)
        }
      }, 0)
      return () => window.clearTimeout(timer)
    }

    const timer = window.setTimeout(loadEmployees, 0)
    return () => window.clearTimeout(timer)
  }, [currentPage, loadEmployees, user])

  useEffect(() => {
    if (!user || user.role === "admin" || currentPage !== PAGE_STRUCTURE || !hasMatrixReadPermission(user, "structure")) {
      return
    }

    const timer = window.setTimeout(loadStructureEmployees, 0)
    return () => window.clearTimeout(timer)
  }, [currentPage, loadStructureEmployees, user])

  useEffect(() => {
    if (!user || currentPage === PAGE_DASHBOARD || currentPage === PAGE_EMPLOYEES) {
      return
    }

    const module = MODULES.find((item) => item.key === currentPage)
    if (module && !hasModuleAccess(user, module)) {
      setRoute(PAGE_DASHBOARD)
    }
  }, [user, currentPage])

  useEffect(() => {
    return () => window.clearTimeout(bannerTimerRef.current)
  }, [])

  const handleLogin = async ({ username, password }) => {
    const result = await loginUser({ username, password })
    setStation(DEFAULT_STATION)
    resetPhotoState()
    return result
  }

  const handleLogout = async () => {
    await logoutUser()
    resetPhotoState()
    setPasswordModalOpen(false)
    setCurrentPage(PAGE_DASHBOARD)
    setRoute(PAGE_DASHBOARD)
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

  if (currentPage === PAGE_DOCUMENTS && hasModuleAccess(user, MODULES.find((item) => item.key === PAGE_DOCUMENTS))) {
    return (
      <div className="app-shell office-page-shell">
        <DocumentsPage user={user} departments={departments} showBanner={showBanner} onBack={openDashboardPage} />
      </div>
    )
  }

  if (currentPage === PAGE_LEARNING && hasModuleAccess(user, MODULES.find((item) => item.key === PAGE_LEARNING))) {
    return (
      <div className="app-shell office-page-shell">
        <LearningPage user={user} departments={departments} showBanner={showBanner} onBack={openDashboardPage} />
      </div>
    )
  }

  if (currentPage === PAGE_LEDGER && hasModuleAccess(user, MODULES.find((item) => item.key === PAGE_LEDGER))) {
    return (
      <div className="app-shell office-page-shell">
        <LedgerWorkspacePage user={user} departments={departments} showBanner={showBanner} onBack={openDashboardPage} />
      </div>
    )
  }

  if (currentPage === PAGE_STRUCTURE && hasMatrixReadPermission(user, "structure")) {
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
          <h1>监控照片管理系统</h1>
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
            department={selectedDepartment}
            setDepartment={setSelectedDepartment}
            departmentOptions={photoDepartmentOptions}
            startTime={startTime}
            setStartTime={setStartTime}
            endTime={endTime}
            setEndTime={setEndTime}
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
