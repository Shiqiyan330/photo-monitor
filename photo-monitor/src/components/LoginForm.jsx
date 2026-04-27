import { useState } from "react"

export default function LoginForm({ onSubmit, serverMessage }) {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState("")

  const handleSubmit = async (event) => {
    event.preventDefault()
    setSubmitting(true)
    setError("")

    try {
      await onSubmit({ username, password })
    } catch (submitError) {
      setError(submitError.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="login-layout">
      <div className="login-intro">
        <div className="brand-mark">
          <div className="brand-logo-slot" aria-hidden="true">
            <span>Logo</span>
          </div>
          <div>
            <div className="brand-name">越岚索道</div>
            <div className="brand-subtitle">办公管理系统</div>
          </div>
        </div>
        <p className="eyebrow">Employee Login</p>
        <h1 className="login-title">员工登录系统</h1>
        <p className="hero-copy">
          账号数据现在保存在当前项目的 <code>photo-backend/users.json</code> 中，员工可以继续使用已有账号登录。
        </p>
      </div>

      <form className="login-card" onSubmit={handleSubmit}>
        <h2>登录到监控照片平台</h2>

        <label className="field">
          <span>用户名</span>
          <input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            placeholder="手机号或管理员账号"
            autoComplete="username"
            required
          />
        </label>

        <label className="field">
          <span>密码</span>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="输入密码"
            autoComplete="current-password"
            required
          />
        </label>

        {error || serverMessage ? <div className="form-error">{error || serverMessage}</div> : null}

        <button type="submit" className="primary-button" disabled={submitting}>
          {submitting ? "登录中..." : "登录"}
        </button>
      </form>
    </section>
  )
}
