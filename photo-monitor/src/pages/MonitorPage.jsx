import PhotoGrid from "../components/PhotoGrid"
import PhotoModal from "../components/PhotoModal"
import Toolbar from "../components/Toolbar"
import { BrandMark } from "./DashboardPage"

export default function MonitorPage({
  hasPhotoAccess,
  loadingMorePhotos,
  loadingPhotos,
  onBack,
  onLoadMore,
  onRefresh,
  photoDepartmentOptions,
  photoError,
  photoFeed,
  user,
}) {
  const {
    dedupeEnabled,
    dedupeWindowSeconds,
    displayedPhotos,
    endTime,
    hasMorePhotos,
    parsedPhotoLimit,
    photoLimit,
    photoTotal,
    selectedDepartment,
    selectedPhoto,
    setDedupeEnabled,
    setDedupeWindowSeconds,
    setEndTime,
    setPhotoLimit,
    setSelectedDepartment,
    setSelectedPhoto,
    setStartTime,
    setStation,
    startTime,
    station,
  } = photoFeed

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
            <button type="button" className="ghost-button" onClick={onBack}>
              返回主界面
            </button>
          </div>
        </div>
      </section>

      {hasPhotoAccess ? (
        <>
          <Toolbar
            station={station}
            setStation={setStation}
            photoLimit={photoLimit}
            setPhotoLimit={setPhotoLimit}
            dedupeEnabled={dedupeEnabled}
            setDedupeEnabled={setDedupeEnabled}
            dedupeWindowSeconds={dedupeWindowSeconds}
            setDedupeWindowSeconds={setDedupeWindowSeconds}
            department={selectedDepartment}
            setDepartment={setSelectedDepartment}
            departmentOptions={photoDepartmentOptions}
            startTime={startTime}
            setStartTime={setStartTime}
            endTime={endTime}
            setEndTime={setEndTime}
            onRefresh={onRefresh}
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
              onLoadMore={onLoadMore}
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
    </div>
  )
}

