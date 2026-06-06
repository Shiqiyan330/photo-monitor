import { useCallback, useEffect, useState } from "react"
import {
  changePassword,
  fetchCurrentUser,
  getStoredToken,
  login,
  logout,
  setStoredToken,
} from "../api"

export default function useAuth({ onLoginSuccess, onLogoutSuccess, onPasswordChanged } = {}) {
  const [user, setUser] = useState(null)
  const [booting, setBooting] = useState(true)
  const [authError, setAuthError] = useState("")

  const loadCurrentUser = useCallback(async () => {
    if (!getStoredToken()) {
      setBooting(false)
      setUser(null)
      return
    }

    try {
      const data = await fetchCurrentUser()
      setUser(data.user)
      setAuthError("")
    } catch (error) {
      if (error.status !== 401) {
        setAuthError(error.message)
      }
      setStoredToken("")
      setUser(null)
    } finally {
      setBooting(false)
    }
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(loadCurrentUser, 0)
    return () => window.clearTimeout(timer)
  }, [loadCurrentUser])

  const handleLogin = useCallback(async ({ username, password }) => {
    const result = await login(username, password)
    setUser(result.user)
    setAuthError("")
    onLoginSuccess?.(result.user)
    return result
  }, [onLoginSuccess])

  const handleLogout = useCallback(async () => {
    await logout()
    setUser(null)
    onLogoutSuccess?.()
  }, [onLogoutSuccess])

  const handleChangePassword = useCallback(async ({ oldPassword, newPassword }) => {
    const result = await changePassword(oldPassword, newPassword)
    setUser(result.user)
    onPasswordChanged?.(result.user)
    return result
  }, [onPasswordChanged])

  return { user, setUser, booting, authError, handleLogin, handleLogout, handleChangePassword }
}

