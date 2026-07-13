import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  createEmployee,
  createDepartment,
  deleteCompanyFile,
  deleteDepartment,
  deleteEmployee,
  deleteLedger,
  deleteStudyArticle,
  fetchLedgers,
  fetchDepartments,
  fetchEmployees,
  fetchStructureEmployees,
  fetchStudyArticles,
  fetchUploadedFiles,
  getDepartmentUsage,
  mergeDepartment,
  updateEmployee,
  renameDepartment,
  uploadCompanyFile,
  uploadLedger,
  uploadStudyArticle,
  viewLedger,
  viewStudyArticle,
  viewUploadedFile,
} from "./api"
import ChangePasswordModal from "./components/ChangePasswordModal"
import DepartmentManagerPage from "./components/DepartmentManagerPage"
import EmployeeManagerPage from "./components/EmployeeManagerPage"
import LoginForm from "./components/LoginForm"
import ProfileModal from "./components/ProfileModal"
import useAuth from "./hooks/useAuth"
import usePhotoFeed, { DEFAULT_STATION, keepDigitsOnly } from "./hooks/usePhotoFeed"
import DashboardPage from "./pages/DashboardPage"
import MonitorPage from "./pages/MonitorPage"
import OfficeUploadPage from "./pages/OfficeUploadPage"
import StructurePage from "./pages/StructurePage"
import {
  canReadStructure,
  getDepartmentViewOptions,
  hasCameraPermission,
  hasModuleAccess,
} from "./permissions"

const PAGE_DASHBOARD = "dashboard"
const PAGE_EMPLOYEES = "employees"
const PAGE_DEPARTMENTS = "departments"
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
    description: "照片记录",
    accent: "blue",
    icon: "photo_camera",
  },
  {
    key: PAGE_DOCUMENTS,
    matrixSystem: "company_files",
    title: "公司文件",
    description: "文件归档",
    accent: "green",
    icon: "folder_open",
  },
  {
    key: PAGE_LEARNING,
    matrixSystem: "study_articles",
    title: "学习交流",
    description: "资料学习",
    accent: "orange",
    icon: "menu_book",
  },
  {
    key: PAGE_LEDGER,
    matrixSystem: "ledgers",
    title: "台账管理",
    description: "台账归档",
    accent: "teal",
    icon: "upload_file",
  },
  {
    key: PAGE_STRUCTURE,
    matrixSystem: "structure",
    title: "公司架构",
    description: "人员联系",
    accent: "purple",
    icon: "account_tree",
  },
]

const OFFICE_PAGE_CONFIGS = {
  [PAGE_DOCUMENTS]: {
    pageTitle: "公司文件",
    toolbarTitle: "公司文件",
    toolbarDescription: "",
    uploadTitle: "上传公司文件",
    uploadDescription: "",
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
    toolbarDescription: "",
    uploadTitle: "上传学习文章",
    uploadDescription: "",
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
    toolbarDescription: "",
    uploadTitle: "上传台账",
    uploadDescription: "",
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
  if (route === PAGE_DEPARTMENTS) {
    return PAGE_DEPARTMENTS
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
  const [profileModalOpen, setProfileModalOpen] = useState(false)
  const [bannerMessage, setBannerMessage] = useState("")
  const [structureStatus, setStructureStatus] = useState("idle")
  const [structureError, setStructureError] = useState("")
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
    handleUpdateProfile,
  } = useAuth({
    onPasswordChanged: () => showBanner("密码修改成功"),
    onProfileUpdated: () => showBanner("个人信息已更新"),
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

  const loadDepartments = useCallback(async () => {
    const data = await fetchDepartments()
    setDepartments(data.departments)
  }, [])

  const loadStructureEmployees = useCallback(async () => {
    setStructureStatus("loading")
    setStructureError("")

    try {
      const data = await fetchStructureEmployees()
      setEmployees(data.employees)
      setDepartments(data.departments)
      setStructureStatus("loaded")
    } catch (error) {
      setEmployees([])
      setDepartments([])
      setStructureError(error.message)
      setStructureStatus("error")
    }
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
        setStructureStatus("idle")
        setStructureError("")
      }, 0)
      return () => window.clearTimeout(timer)
    }
    return undefined
  }, [user])

  useEffect(() => {
    if (!user || user.role !== "admin" || (currentPage !== PAGE_EMPLOYEES && currentPage !== PAGE_DEPARTMENTS)) {
      const timer = window.setTimeout(() => {
        if (currentPage === PAGE_EMPLOYEES || currentPage === PAGE_DEPARTMENTS) {
          setEmployees([])
          setDepartments([])
          setRoute(PAGE_DASHBOARD)
        }
      }, 0)
      return () => window.clearTimeout(timer)
    }

    const timer = window.setTimeout(currentPage === PAGE_EMPLOYEES ? loadEmployees : loadDepartments, 0)
    return () => window.clearTimeout(timer)
  }, [currentPage, loadDepartments, loadEmployees, user])

  useEffect(() => {
    if (!user || currentPage !== PAGE_STRUCTURE || !canReadStructure(user)) {
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
    setProfileModalOpen(false)
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

  const handleCreateDepartment = async (payload) => {
    const result = await createDepartment(payload)
    setDepartments(result.departments)
    showBanner("部门已新增")
  }

  const handleRenameDepartment = async (name, payload) => {
    const result = await renameDepartment(name, payload)
    setDepartments(result.departments)
    await loadEmployees()
    showBanner("部门已改名，历史数据已迁移")
  }

  const handleGetDepartmentUsage = async (name) => {
    const result = await getDepartmentUsage(name)
    return result.usage
  }

  const handleDeleteDepartment = async (name) => {
    const result = await deleteDepartment(name)
    setDepartments(result.departments)
    showBanner("部门已删除")
  }

  const handleMergeDepartment = async (name, target) => {
    const result = await mergeDepartment(name, { target })
    setDepartments(result.departments)
    await loadEmployees()
    showBanner("部门数据已迁移，原部门已删除")
  }

  const openEmployeePage = () => {
    setCurrentPage(PAGE_EMPLOYEES)
    setRoute(PAGE_EMPLOYEES)
  }

  const openDepartmentPage = () => {
    setCurrentPage(PAGE_DEPARTMENTS)
    setRoute(PAGE_DEPARTMENTS)
  }

  const openDashboardPage = () => {
    setCurrentPage(PAGE_DASHBOARD)
    setRoute(PAGE_DASHBOARD)
  }

  const openModulePage = (page) => {
    setCurrentPage(page)
    setRoute(page)
  }

  const profileModal = profileModalOpen ? (
    <ProfileModal
      user={user}
      onClose={() => setProfileModalOpen(false)}
      onSubmit={handleUpdateProfile}
    />
  ) : null

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
          onOpenDepartments={openDepartmentPage}
          onOpenPassword={() => setPasswordModalOpen(true)}
          onOpenProfile={() => setProfileModalOpen(true)}
          onLogout={handleLogout}
        />

        {passwordModalOpen ? (
          <ChangePasswordModal
            onClose={() => setPasswordModalOpen(false)}
            onSubmit={handleChangePassword}
          />
        ) : null}
        {profileModal}
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
        {profileModal}
      </div>
    )
  }

  if (currentPage === PAGE_DEPARTMENTS && user.role === "admin") {
    return (
      <div className="app-shell admin-page-shell">
        {bannerMessage ? <div className="status-card success-card">{bannerMessage}</div> : null}

        <DepartmentManagerPage
          departments={departments}
          onBack={openDashboardPage}
          onCreate={handleCreateDepartment}
          onDelete={handleDeleteDepartment}
          onGetUsage={handleGetDepartmentUsage}
          onMerge={handleMergeDepartment}
          onRename={handleRenameDepartment}
        />

        {passwordModalOpen ? (
          <ChangePasswordModal
            onClose={() => setPasswordModalOpen(false)}
            onSubmit={handleChangePassword}
          />
        ) : null}
        {profileModal}
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

  if (currentPage === PAGE_STRUCTURE && canReadStructure(user)) {
    return (
      <div className="app-shell office-page-shell">
        <StructurePage
          employees={employees}
          error={structureError}
          loading={structureStatus !== "loaded" && structureStatus !== "error"}
          onBack={openDashboardPage}
        />
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
