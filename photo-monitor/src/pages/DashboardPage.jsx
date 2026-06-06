export function BrandMark({ compact = false }) {
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

export default function DashboardPage({
  user,
  modules,
  onOpenModule,
  onOpenEmployees,
  onOpenPassword,
  onOpenProfile,
  onLogout,
}) {
  return (
    <div className="dashboard-shell">
      <section className="dashboard-hero">
        <div>
          <BrandMark />
          <p className="eyebrow">Main Dashboard</p>
          <h1>监控照片管理系统</h1>
          <p className="hero-copy">
            根据账号权限展示可用功能，进入对应模块处理监控、文档、学习、台账和组织信息。
          </p>
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
            <button type="button" className="ghost-button" onClick={onOpenProfile}>
              个人信息
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
