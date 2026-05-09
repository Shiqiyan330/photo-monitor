const BASE_URL = ""
const TOKEN_KEY = "photo_monitor_token"

export function getStoredToken() {
  return window.localStorage.getItem(TOKEN_KEY) ?? ""
}

export function setStoredToken(token) {
  if (token) {
    window.localStorage.setItem(TOKEN_KEY, token)
    return
  }
  window.localStorage.removeItem(TOKEN_KEY)
}

async function request(path, options = {}) {
  const token = getStoredToken()
  const isFormData = options.body instanceof FormData
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
    ...options,
  })

  const isJson = response.headers.get("content-type")?.includes("application/json")
  const payload = isJson ? await response.json() : null

  if (!response.ok) {
    const error = new Error(payload?.detail ?? "Request failed")
    error.status = response.status
    throw error
  }

  return payload
}

export async function downloadFile(path, filename) {
  const token = getStoredToken()
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })

  if (!response.ok) {
    const isJson = response.headers.get("content-type")?.includes("application/json")
    const payload = isJson ? await response.json() : null
    throw new Error(payload?.detail ?? "Download failed")
  }

  const blob = await response.blob()
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename || "download"
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.URL.revokeObjectURL(url)
}

export function getAssetUrl(path) {
  if (!path) {
    return ""
  }

  if (path.startsWith("http://") || path.startsWith("https://")) {
    const url = new URL(path)
    return `${url.pathname}${url.search}`
  }

  return path
}

export function getWebSocketUrl() {
  const token = encodeURIComponent(getStoredToken())
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:"
  return `${protocol}//${window.location.host}/ws?token=${token}`
}

export async function login(username, password) {
  const payload = await request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  })
  setStoredToken(payload.token)
  return payload
}

export async function logout() {
  try {
    return await request("/auth/logout", { method: "POST" })
  } finally {
    setStoredToken("")
  }
}

export function fetchCurrentUser() {
  return request("/auth/me")
}

export function changePassword(oldPassword, newPassword) {
  return request("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({
      old_password: oldPassword,
      new_password: newPassword,
    }),
  })
}

export function fetchPhotos(station, department = "", options = {}) {
  const params = new URLSearchParams({ station })
  if (department) {
    params.set("department", department)
  }
  if (options.limit) {
    params.set("limit", String(options.limit))
  }
  if (options.cursor != null) {
    params.set("cursor", String(options.cursor))
  }
  return request(`/photos?${params.toString()}`)
}

function uploadMultipart(path, { department, file }) {
  const body = new FormData()
  body.append("department", department)
  body.append("file", file)
  return request(path, {
    method: "POST",
    body,
  })
}

export function uploadCompanyFile(payload) {
  return uploadMultipart("/uploads/files", payload)
}

export function uploadLedger(payload) {
  return uploadMultipart("/uploads/ledgers", payload)
}

export function uploadStudyArticle(payload) {
  return uploadMultipart("/uploads/study-articles", payload)
}

export function fetchUploadedFiles() {
  return request("/uploads/files")
}

export function fetchLedgers() {
  return request("/uploads/ledgers")
}

export function fetchStudyArticles() {
  return request("/uploads/study-articles")
}

export function deleteCompanyFile(id) {
  return request(`/uploads/files/${encodeURIComponent(id)}`, {
    method: "DELETE",
  })
}

export function deleteLedger(id) {
  return request(`/uploads/ledgers/${encodeURIComponent(id)}`, {
    method: "DELETE",
  })
}

export function deleteStudyArticle(id) {
  return request(`/uploads/study-articles/${encodeURIComponent(id)}`, {
    method: "DELETE",
  })
}

export function fetchEmployees() {
  return request("/admin/employees")
}

export function createEmployee(payload) {
  return request("/admin/employees", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export function updateEmployee(username, payload) {
  return request(`/admin/employees/${encodeURIComponent(username)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  })
}

export function deleteEmployee(username) {
  return request(`/admin/employees/${encodeURIComponent(username)}`, {
    method: "DELETE",
  })
}
