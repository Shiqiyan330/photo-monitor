import { useState } from "react"

export default function ChangePasswordModal({ onClose, onSubmit }) {
  const [oldPassword, setOldPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [error, setError] = useState("")
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (event) => {
    event.preventDefault()

    if (newPassword !== confirmPassword) {
      setError("两次输入的新密码不一致")
      return
    }

    setError("")
    setSubmitting(true)

    try {
      await onSubmit({ oldPassword, newPassword })
      onClose()
    } catch (submitError) {
      setError(submitError.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card side-modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h2>修改密码</h2>
          <button type="button" className="modal-close" onClick={onClose}>
            关闭
          </button>
        </div>

        <form className="stack-form" onSubmit={handleSubmit}>
          <label className="field">
            <span>原密码</span>
            <input
              type="password"
              value={oldPassword}
              onChange={(event) => setOldPassword(event.target.value)}
              required
            />
          </label>

          <label className="field">
            <span>新密码</span>
            <input
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              required
            />
          </label>

          <label className="field">
            <span>确认新密码</span>
            <input
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              required
            />
          </label>

          {error ? <div className="form-error">{error}</div> : null}

          <button type="submit" className="primary-button" disabled={submitting}>
            {submitting ? "提交中..." : "确认修改"}
          </button>
        </form>
      </div>
    </div>
  )
}
