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

export function getAuthorizedUrl(path) {
  const token = getStoredToken()
  const separator = path.includes("?") ? "&" : "?"
  return token ? `${getAssetUrl(path)}${separator}token=${encodeURIComponent(token)}` : getAssetUrl(path)
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
  if (options.startDate) {
    params.set("start_date", options.startDate)
  }
  if (options.endDate) {
    params.set("end_date", options.endDate)
  }
  if (options.startTime) {
    params.set("start_time", options.startTime)
  }
  if (options.endTime) {
    params.set("end_time", options.endTime)
  }
  return request(`/photos?${params.toString()}`)
}

function uploadMultipart(path, { department, file }, options = {}) {
  const body = new FormData()
  body.append("department", department)
  body.append("file", file)

  if (!options.onProgress) {
    return request(path, {
      method: "POST",
      body,
    })
  }

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open("POST", `${BASE_URL}${path}`)

    const token = getStoredToken()
    if (token) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`)
    }

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) {
        return
      }
      options.onProgress(Math.round((event.loaded / event.total) * 100))
    }

    xhr.onload = () => {
      const isJson = xhr.getResponseHeader("content-type")?.includes("application/json")
      const payload = isJson && xhr.responseText ? JSON.parse(xhr.responseText) : null

      if (xhr.status < 200 || xhr.status >= 300) {
        const error = new Error(payload?.detail ?? "Request failed")
        error.status = xhr.status
        reject(error)
        return
      }

      options.onProgress(100)
      resolve(payload)
    }

    xhr.onerror = () => reject(new Error("Network error"))
    xhr.onabort = () => reject(new Error("Upload cancelled"))
    xhr.send(body)
  })
}

export function uploadCompanyFile(payload, options) {
  return uploadMultipart("/uploads/files", payload, options)
}

export function uploadLedger(payload, options) {
  return uploadMultipart("/uploads/ledgers", payload, options)
}

export function uploadStudyArticle(payload, options) {
  return uploadMultipart("/uploads/study-articles", payload, options)
}

export function fetchUploadedFiles() {
  return request("/uploads/files")
}

export function viewUploadedFile(id) {
  const token = getStoredToken()
  const url = `/uploads/files/${encodeURIComponent(id)}/view`
  return token ? `${url}?token=${encodeURIComponent(token)}` : url
}

export function fetchLedgers() {
  return request("/uploads/ledgers")
}

export function viewLedger(id) {
  const token = getStoredToken()
  const url = `/uploads/ledgers/${encodeURIComponent(id)}/view`
  return token ? `${url}?token=${encodeURIComponent(token)}` : url
}

export function fetchStudyArticles() {
  return request("/uploads/study-articles")
}

export function viewStudyArticle(id) {
  const token = getStoredToken()
  const url = `/uploads/study-articles/${encodeURIComponent(id)}/view`
  return token ? `${url}?token=${encodeURIComponent(token)}` : url
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

export function fetchStructureEmployees() {
  return request("/structure/employees")
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
