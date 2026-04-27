const BASE_URL = "http://127.0.0.1:8000"
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
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
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

export function getAssetUrl(path) {
  return `${BASE_URL}${path}`
}

export function getWebSocketUrl() {
  const token = encodeURIComponent(getStoredToken())
  return `${BASE_URL.replace("http://", "ws://").replace("https://", "wss://")}/ws?token=${token}`
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

export function fetchPhotos(station, department = "") {
  const params = new URLSearchParams({ station })
  if (department) {
    params.set("department", department)
  }
  return request(`/photos?${params.toString()}`)
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
