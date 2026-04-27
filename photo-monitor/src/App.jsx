import { useEffect, useRef, useState } from "react"
import {
  changePassword,
  createEmployee,
  deleteEmployee,
  fetchCurrentUser,
  fetchEmployees,
  fetchPhotos,
  getStoredToken,
  getWebSocketUrl,
  login,
  logout,
  setStoredToken,
  updateEmployee,
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
    permission: "files",
    title: "公司文件",
    description: "公司文档资料库",
    accent: "green",
    icon: "folder_open",
  },
  {
    key: PAGE_LEARNING,
    permission: "study",
    title: "学习交流",
    description: "在线学习与文字讨论",
    accent: "orange",
    icon: "menu_book",
  },
  {
    key: PAGE_LEDGER,
    permission: "upload",
    title: "台账上传",
    description: "工作台账上传与管理",
    accent: "teal",
    icon: "upload_file",
  },
  {
    key: PAGE_STRUCTURE,
    permission: "structure",
    title: "公司架构",
    description: "组织架构与人员联系方式",
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
          <p className="hero-copy">根据账号权限展示可用功能，进入对应模块处理监控、文件、学习、台账和组织信息。</p>
        </div>

        <div className="user-panel">
          <div className="user-avatar">{user.avatar}</div>
          <div className="user-name">{user.name}</div>
          <div className="user-meta">
            {user.role === "admin" ? "管理员" : user.department || "员工"} · {user.username}
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

function DocumentsPage({ onBack }) {
  return (
    <OfficeModulePage title="公司文件" onBack={onBack}>
      <section className="office-toolbar">
        <button type="button" className="ghost-button icon-button-text">
          <span className="material-symbols-outlined button-icon" aria-hidden="true">
            arrow_back
          </span>
          返回
        </button>
        <label className="toolbar-select">
          <span>部门筛选</span>
          <select defaultValue="">
            <option value="">所有部门</option>
          </select>
        </label>
        <button type="button" className="primary-action-button icon-button-text">
          <span className="material-symbols-outlined button-icon" aria-hidden="true">
            upload_file
          </span>
          上传文件
        </button>
        <button type="button" className="ghost-button icon-button-text">
          <span className="material-symbols-outlined button-icon" aria-hidden="true">
            refresh
          </span>
          刷新
        </button>
      </section>

      <section className="office-table">
        <div className="office-table-row office-table-head">
          <span>文件名称</span>
          <span>文件形式</span>
          <span>上传时间</span>
          <span>上传人</span>
          <span>下载</span>
          <span>删除</span>
        </div>
        <div className="empty-state">公司文件接口待接入，删除操作将使用密码保护。</div>
      </section>
    </OfficeModulePage>
  )
}

function LearningPage({ onBack }) {
  const [activeTab, setActiveTab] = useState("articles")

  return (
    <OfficeModulePage title="学习交流" onBack={onBack}>
      <section className="office-toolbar">
        <div className="tab-group">
          <button
            type="button"
            className={activeTab === "articles" ? "station-button active" : "station-button"}
            onClick={() => setActiveTab("articles")}
          >
            学习文章
          </button>
          <button
            type="button"
            className={activeTab === "discussion" ? "station-button active" : "station-button"}
            onClick={() => setActiveTab("discussion")}
          >
            讨论区
          </button>
        </div>
        <button type="button" className="primary-action-button icon-button-text">
          <span className="material-symbols-outlined button-icon" aria-hidden="true">
            upload_file
          </span>
          上传文章
        </button>
      </section>

      {activeTab === "articles" ? (
        <section className="office-table">
          <div className="office-table-row office-table-head">
            <span>文件名称</span>
            <span>上传时间</span>
            <span>上传人</span>
            <span>上传人删除</span>
            <span>密码删除</span>
          </div>
          <div className="empty-state">学习文章接口待接入，后续点击文件名称可直接查看文章。</div>
        </section>
      ) : (
        <section className="discussion-panel">
          <div className="empty-state">讨论区接口待接入，目标是仅支持内部文字交流。</div>
        </section>
      )}
    </OfficeModulePage>
  )
}

function LedgerPage({ onBack }) {
  return (
    <OfficeModulePage title="台账上传" onBack={onBack}>
      <section className="office-panel">
        <h3>台账上传</h3>
        <p className="panel-muted">这里将承载工作台账上传、列表查看和管理流程。</p>
        <button type="button" className="primary-action-button icon-button-text">
          <span className="material-symbols-outlined button-icon" aria-hidden="true">
            upload_file
          </span>
          上传台账
        </button>
      </section>
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
  const [selectedDepartment, setSelectedDepartment] = useState("")
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
  const departmentViewOptions = getDepartmentViewOptions(user, departments)
  const departmentViewKey = departmentViewOptions.join("|")
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

  const loadPhotos = async (nextStation = station, nextDepartment = selectedDepartment) => {
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
      const data = await fetchPhotos(nextStation, nextDepartment, {
        limit: initialLimit,
        cursor: 0,
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
      const data = await fetchPhotos(station, selectedDepartment, {
        limit: pageSize,
        cursor: photoCursor,
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
      setSelectedDepartment("")
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
  }, [station, selectedDepartment, user, hasPhotoAccess, currentPage])

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

  useEffect(() => {
    if (!departmentViewOptions.length) {
      if (selectedDepartment) {
        setSelectedDepartment("")
      }
      return
    }

    if (!departmentViewOptions.includes(selectedDepartment)) {
      setSelectedDepartment(departmentViewOptions[0])
    }
  }, [departmentViewKey, selectedDepartment])

  const handleLogin = async ({ username, password }) => {
    const result = await login(username, password)
    setUser(result.user)
    setStation(DEFAULT_STATION)
    setSelectedDepartment("")
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
    setSelectedDepartment("")
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

  if (currentPage === PAGE_DOCUMENTS && hasPermission(user, "files")) {
    return (
      <div className="app-shell office-page-shell">
        <DocumentsPage onBack={openDashboardPage} />
      </div>
    )
  }

  if (currentPage === PAGE_LEARNING && hasPermission(user, "study")) {
    return (
      <div className="app-shell office-page-shell">
        <LearningPage onBack={openDashboardPage} />
      </div>
    )
  }

  if (currentPage === PAGE_LEDGER && hasPermission(user, "upload")) {
    return (
      <div className="app-shell office-page-shell">
        <LedgerPage onBack={openDashboardPage} />
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
          <p className="hero-copy">
            现在支持按站点查看照片、控制展示数量，并在前端按秒级时间窗进行去重展示。
          </p>
        </div>

        <div className="user-panel">
          <div className="user-avatar">{user.avatar}</div>
          <div className="user-name">{user.name}</div>
          <div className="user-meta">
            {user.role === "admin" ? "管理员" : user.department || "员工"} · {user.username}
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
          departmentOptions={departmentViewOptions}
          selectedDepartment={selectedDepartment}
          setSelectedDepartment={setSelectedDepartment}
            showDepartmentSwitch={departmentViewOptions.length > 1}
            onRefresh={() => loadPhotos(station, selectedDepartment)}
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
