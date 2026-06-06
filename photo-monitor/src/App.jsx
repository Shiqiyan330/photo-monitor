import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  createEmployee,
  deleteCompanyFile,
  deleteEmployee,
  deleteLedger,
  deleteStudyArticle,
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
import useAuth from "./hooks/useAuth"
import usePhotoFeed, { DEFAULT_STATION, keepDigitsOnly } from "./hooks/usePhotoFeed"
import DashboardPage from "./pages/DashboardPage"
import MonitorPage from "./pages/MonitorPage"
import OfficeUploadPage from "./pages/OfficeUploadPage"
import StructurePage from "./pages/StructurePage"
import {
  getDepartmentViewOptions,
  hasCameraPermission,
  hasMatrixReadPermission,
  hasModuleAccess,
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

const OFFICE_PAGE_CONFIGS = {
  [PAGE_DOCUMENTS]: {
    pageTitle: "公司文件",
    toolbarTitle: "公司文件",
    toolbarDescription: "部门资料、通知附件和通用文档统一保存到公司文件目录。",
    uploadTitle: "上传公司文件",
    uploadDescription: "支持图片、PDF、Office 表格、文本、压缩包等常用资料。",
    listTitle: "公司文件列表",
    emptyText: "还没有上传公司文件。",
    deleteLabel: "文件",
    system: "company_files",
    fetchItems: fetchUploadedFiles,
    uploadItem: uploadCompanyFile,
    deleteItem: deleteCompanyFile,
    viewUrl: viewUploadedFile,
    messages: {
      uploaded: "文件上传成功",
      deleted: "文件已删除",
    },
  },
  [PAGE_LEARNING]: {
    pageTitle: "学习交流",
    toolbarTitle: "学习文章",
    toolbarDescription: "上传培训资料、制度学习文档和内部交流文章，列表按账号可访问部门过滤。",
    uploadTitle: "上传学习文章",
    uploadDescription: "支持 PDF、Word、PPT、文本、Markdown、HTML 和压缩包。",
    listTitle: "学习文章列表",
    emptyText: "还没有上传学习文章。",
    deleteLabel: "学习文章",
    system: "study_articles",
    fetchItems: fetchStudyArticles,
    uploadItem: uploadStudyArticle,
    deleteItem: deleteStudyArticle,
    viewUrl: viewStudyArticle,
    messages: {
      uploaded: "学习文章上传成功",
      deleted: "学习文章已删除",
    },
  },
  [PAGE_LEDGER]: {
    pageTitle: "台账管理",
    toolbarTitle: "台账上传",
    toolbarDescription: "工作台账、日报、月报和 Excel 表格统一保存到台账目录。",
    uploadTitle: "上传台账",
    uploadDescription: "用于工作台账、日报、月报、Excel 表格等。",
    listTitle: "台账列表",
    emptyText: "还没有上传台账。",
    deleteLabel: "台账",
    system: "ledgers",
    fetchItems: fetchLedgers,
    uploadItem: uploadLedger,
    deleteItem: deleteLedger,
    viewUrl: viewLedger,
    messages: {
      uploaded: "台账上传成功",
      deleted: "台账已删除",
    },
  },
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
    setPhotoLimit,
    setDedupeWindowSeconds,
    loadingPhotos,
    loadingMorePhotos,
    photoError,
    loadPhotos,
    loadMorePhotos,
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
        <OfficeUploadPage
          config={OFFICE_PAGE_CONFIGS[PAGE_DOCUMENTS]}
          user={user}
          departments={departments}
          showBanner={showBanner}
          onBack={openDashboardPage}
        />
      </div>
    )
  }

  if (currentPage === PAGE_LEARNING && hasModuleAccess(user, MODULES.find((item) => item.key === PAGE_LEARNING))) {
    return (
      <div className="app-shell office-page-shell">
        <OfficeUploadPage
          config={OFFICE_PAGE_CONFIGS[PAGE_LEARNING]}
          user={user}
          departments={departments}
          showBanner={showBanner}
          onBack={openDashboardPage}
        />
      </div>
    )
  }

  if (currentPage === PAGE_LEDGER && hasModuleAccess(user, MODULES.find((item) => item.key === PAGE_LEDGER))) {
    return (
      <div className="app-shell office-page-shell">
        <OfficeUploadPage
          config={OFFICE_PAGE_CONFIGS[PAGE_LEDGER]}
          user={user}
          departments={departments}
          showBanner={showBanner}
          onBack={openDashboardPage}
        />
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
    <>
      {bannerMessage ? <div className="status-card success-card">{bannerMessage}</div> : null}

      <MonitorPage
        hasPhotoAccess={hasPhotoAccess}
        loadingMorePhotos={loadingMorePhotos}
        loadingPhotos={loadingPhotos}
        onBack={openDashboardPage}
        onLoadMore={loadMorePhotos}
        onRefresh={() => loadPhotos(station)}
        photoDepartmentOptions={photoDepartmentOptions}
        photoError={photoError}
        photoFeed={{
          ...photoFeed,
          setPhotoLimit: (value) => setPhotoLimit(keepDigitsOnly(value)),
          setDedupeWindowSeconds: (value) => setDedupeWindowSeconds(keepDigitsOnly(value)),
        }}
        user={user}
      />

      {passwordModalOpen ? (
        <ChangePasswordModal
          onClose={() => setPasswordModalOpen(false)}
          onSubmit={handleChangePassword}
        />
      ) : null}
    </>
  )
}

export default App
