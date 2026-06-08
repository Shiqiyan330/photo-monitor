import { useEffect, useRef, useState } from "react"

const EMPTY_CERTIFICATE = { name: "", number: "", expires_at: "", note: "" }

function normalizeCertificates(certificates) {
  return (certificates ?? [])
    .map((item) => ({
      name: (item.name ?? "").trim(),
      number: (item.number ?? "").trim(),
      expires_at: (item.expires_at ?? "").trim(),
      note: (item.note ?? "").trim(),
    }))
    .filter((item) => item.name || item.number || item.expires_at || item.note)
}

function createInitialForm(user) {
  return {
    phone: user?.phone ?? "",
    name: user?.name ?? "",
    id_number: user?.id_number ?? "",
    birthday: user?.birthday ?? "",
    home_address: user?.home_address ?? "",
    emergency_contact: user?.emergency_contact ?? "",
    certificates: user?.certificates?.length ? user.certificates : [],
  }
}

export default function ProfileModal({ user, onClose, onSubmit }) {
  const [form, setForm] = useState(() => createInitialForm(user))
  const [error, setError] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const nameRef = useRef(null)

  useEffect(() => {
    nameRef.current?.focus()

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        onClose()
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [onClose])

  const handleChange = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }))
  }

  const addCertificate = () => {
    setForm((current) => ({
      ...current,
      certificates: [...current.certificates, { ...EMPTY_CERTIFICATE }],
    }))
  }

  const updateCertificate = (index, field, value) => {
    setForm((current) => ({
      ...current,
      certificates: current.certificates.map((item, itemIndex) =>
        itemIndex === index ? { ...item, [field]: value } : item,
      ),
    }))
  }

  const removeCertificate = (index) => {
    setForm((current) => ({
      ...current,
      certificates: current.certificates.filter((_, itemIndex) => itemIndex !== index),
    }))
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setError("")
    setSubmitting(true)

    try {
      await onSubmit({
        phone: form.phone.trim(),
        name: form.name.trim(),
        id_number: form.id_number.trim(),
        birthday: form.birthday.trim(),
        home_address: form.home_address.trim(),
        emergency_contact: form.emergency_contact.trim(),
        certificates: normalizeCertificates(form.certificates),
      })
      onClose()
    } catch (submitError) {
      setError(submitError.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-card side-modal modal-card-enter profile-modal"
        role="dialog"
        aria-modal="true"
        aria-label="个人信息维护"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="modal-header">
          <h2>个人信息维护</h2>
          <button type="button" className="modal-close" onClick={onClose}>
            关闭
          </button>
        </div>

        <form className="stack-form" onSubmit={handleSubmit}>
          <section className="admin-form-section">
            <h4>基础信息</h4>
            <div className="form-grid">
              <label className="field">
                <span>姓名</span>
                <input
                  ref={nameRef}
                  value={form.name}
                  onChange={(event) => handleChange("name", event.target.value)}
                />
              </label>
              <label className="field">
                <span>手机号</span>
                <input value={form.phone} onChange={(event) => handleChange("phone", event.target.value)} />
              </label>
              <label className="field">
                <span>证件号码</span>
                <input value={form.id_number} onChange={(event) => handleChange("id_number", event.target.value)} />
              </label>
              <label className="field">
                <span>生日</span>
                <input
                  type="date"
                  value={form.birthday}
                  onChange={(event) => handleChange("birthday", event.target.value)}
                />
              </label>
              <label className="field wide-field">
                <span>家庭住址</span>
                <input
                  value={form.home_address}
                  onChange={(event) => handleChange("home_address", event.target.value)}
                />
              </label>
              <label className="field wide-field">
                <span>紧急联系人</span>
                <input
                  value={form.emergency_contact}
                  onChange={(event) => handleChange("emergency_contact", event.target.value)}
                  placeholder="姓名、关系、联系电话"
                />
              </label>
            </div>
          </section>

          <section className="admin-form-section">
            <div className="panel-header">
              <h4>证书信息</h4>
              <button type="button" className="ghost-button" onClick={addCertificate}>
                新增证书
              </button>
            </div>

            <div className="certificate-list">
              {form.certificates.length ? (
                form.certificates.map((certificate, index) => (
                  <div key={`${index}-${certificate.name || "certificate"}`} className="certificate-row">
                    <label className="field">
                      <span>证书名称</span>
                      <input
                        value={certificate.name}
                        onChange={(event) => updateCertificate(index, "name", event.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span>证书编号</span>
                      <input
                        value={certificate.number}
                        onChange={(event) => updateCertificate(index, "number", event.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span>有效期</span>
                      <input
                        type="date"
                        value={certificate.expires_at}
                        onChange={(event) => updateCertificate(index, "expires_at", event.target.value)}
                      />
                    </label>
                    <label className="field">
                      <span>备注</span>
                      <input
                        value={certificate.note}
                        onChange={(event) => updateCertificate(index, "note", event.target.value)}
                      />
                    </label>
                    <button
                      type="button"
                      className="ghost-button danger-button"
                      onClick={() => removeCertificate(index)}
                    >
                      删除
                    </button>
                  </div>
                ))
              ) : (
                <div className="compact-empty-state">暂无证书记录。</div>
              )}
            </div>
          </section>

          {error ? <div className="form-error">{error}</div> : null}

          <button type="submit" className="primary-button" disabled={submitting}>
            {submitting ? "保存中..." : "保存个人信息"}
          </button>
        </form>
      </div>
    </div>
  )
}
