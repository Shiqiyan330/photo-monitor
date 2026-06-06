import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { fetchPhotos, getWebSocketUrl, setStoredToken } from "../api"

export const DEFAULT_STATION = "xiazhan"
export const DEFAULT_PHOTO_LIMIT = ""
export const DEFAULT_DEDUPE_ENABLED = true
export const DEFAULT_DEDUPE_WINDOW_SECONDS = "10"
const PHOTO_FEED_BATCH_SIZE = 24
const MOBILE_PHOTO_FEED_BATCH_SIZE = 4
const PHOTO_LIMIT_STORAGE_KEY = "photo_monitor_photo_limit"
const PHOTO_DEDUPE_ENABLED_STORAGE_KEY = "photo_monitor_dedupe_enabled"
const PHOTO_DEDUPE_WINDOW_STORAGE_KEY = "photo_monitor_dedupe_window"

export function keepDigitsOnly(value) {
  return value.replace(/\D/g, "")
}

export function parsePositiveInteger(value) {
  if (!value) {
    return null
  }

  const parsed = Number.parseInt(value, 10)
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null
  }

  return parsed
}

function readStoredDigits(key, fallback) {
  const saved = window.localStorage.getItem(key)
  if (!saved) {
    return fallback
  }

  const normalized = keepDigitsOnly(saved)
  return normalized || fallback
}

function readInitialPhotoLimit() {
  return readStoredDigits(PHOTO_LIMIT_STORAGE_KEY, DEFAULT_PHOTO_LIMIT)
}

function readInitialDedupeEnabled() {
  const saved = window.localStorage.getItem(PHOTO_DEDUPE_ENABLED_STORAGE_KEY)
  if (saved == null) {
    return DEFAULT_DEDUPE_ENABLED
  }
  return saved === "true"
}

function readInitialDedupeWindow() {
  return readStoredDigits(PHOTO_DEDUPE_WINDOW_STORAGE_KEY, DEFAULT_DEDUPE_WINDOW_SECONDS)
}

function getPhotoFeedBatchSize() {
  return window.matchMedia("(max-width: 640px)").matches
    ? MOBILE_PHOTO_FEED_BATCH_SIZE
    : PHOTO_FEED_BATCH_SIZE
}

function dedupePhotosByWindow(photos, windowSeconds) {
  if (!windowSeconds || photos.length <= 1) {
    return photos
  }

  const deduped = []
  let lastPhotoTime = null

  for (const photo of photos) {
    const photoTime = photo.actual_time ?? photo.time
    if (lastPhotoTime == null || Math.abs(lastPhotoTime - photoTime) > windowSeconds) {
      deduped.push(photo)
    }

    lastPhotoTime = photoTime
  }

  return deduped
}

export default function usePhotoFeed({ user, hasPhotoAccess, currentPage, monitorPageKey, setUser }) {
  const [photos, setPhotos] = useState([])
  const [photoCursor, setPhotoCursor] = useState(null)
  const [photoTotal, setPhotoTotal] = useState(0)
  const [station, setStation] = useState(DEFAULT_STATION)
  const [photoLimit, setPhotoLimit] = useState(readInitialPhotoLimit)
  const [dedupeEnabled, setDedupeEnabled] = useState(readInitialDedupeEnabled)
  const [dedupeWindowSeconds, setDedupeWindowSeconds] = useState(readInitialDedupeWindow)
  const [startTime, setStartTime] = useState("")
  const [endTime, setEndTime] = useState("")
  const [selectedDepartment, setSelectedDepartment] = useState("")
  const [selectedPhoto, setSelectedPhoto] = useState(null)
  const [loadingPhotos, setLoadingPhotos] = useState(false)
  const [loadingMorePhotos, setLoadingMorePhotos] = useState(false)
  const [photoError, setPhotoError] = useState("")
  const wsRef = useRef(null)

  const parsedPhotoLimit = parsePositiveInteger(photoLimit)
  const parsedDedupeWindow =
    parsePositiveInteger(dedupeWindowSeconds) ??
    parsePositiveInteger(DEFAULT_DEDUPE_WINDOW_SECONDS)
  const filteredPhotos = useMemo(
    () => (dedupeEnabled ? dedupePhotosByWindow(photos, parsedDedupeWindow) : photos),
    [dedupeEnabled, parsedDedupeWindow, photos],
  )
  const displayedPhotos = useMemo(
    () => (parsedPhotoLimit ? filteredPhotos.slice(0, parsedPhotoLimit) : filteredPhotos),
    [filteredPhotos, parsedPhotoLimit],
  )
  const hasMorePhotos = photoCursor != null && (!parsedPhotoLimit || photos.length < parsedPhotoLimit)

  const resetPhotoState = useCallback(() => {
    setPhotos([])
    setPhotoCursor(null)
    setPhotoTotal(0)
    setStartTime("")
    setEndTime("")
    setSelectedDepartment("")
    setSelectedPhoto(null)
    setPhotoError("")
  }, [])

  const getNextPhotoPageSize = useCallback(() => {
    const batchSize = getPhotoFeedBatchSize()
    if (!parsedPhotoLimit) {
      return batchSize
    }

    return Math.max(Math.min(batchSize, parsedPhotoLimit - photos.length), 0)
  }, [parsedPhotoLimit, photos.length])

  const loadPhotos = useCallback(async (nextStation = station) => {
    if (!hasPhotoAccess) {
      setPhotos([])
      setPhotoCursor(null)
      setPhotoTotal(0)
      setPhotoError("")
      setLoadingPhotos(false)
      return
    }

    setLoadingPhotos(true)
    setLoadingMorePhotos(false)
    setPhotoError("")

    try {
      const initialLimit = parsedPhotoLimit
        ? Math.min(getPhotoFeedBatchSize(), parsedPhotoLimit)
        : getPhotoFeedBatchSize()
      const data = await fetchPhotos(nextStation, selectedDepartment, {
        limit: initialLimit,
        cursor: 0,
        startTime,
        endTime,
      })
      setPhotos(data.items ?? data)
      setPhotoCursor(data.next_cursor ?? null)
      setPhotoTotal(data.total ?? data.length ?? 0)
    } catch (error) {
      setPhotos([])
      setPhotoCursor(null)
      setPhotoTotal(0)
      setPhotoError(error.message)
      if (error.status === 401) {
        setStoredToken("")
        setUser(null)
      }
    } finally {
      setLoadingPhotos(false)
    }
  }, [endTime, hasPhotoAccess, parsedPhotoLimit, selectedDepartment, setUser, startTime, station])

  const loadMorePhotos = useCallback(async () => {
    if (!hasMorePhotos || loadingPhotos || loadingMorePhotos) {
      return
    }

    const pageSize = getNextPhotoPageSize()
    if (!pageSize) {
      return
    }

    setLoadingMorePhotos(true)
    setPhotoError("")

    try {
      const data = await fetchPhotos(station, selectedDepartment, {
        limit: pageSize,
        cursor: photoCursor,
        startTime,
        endTime,
      })
      setPhotos((current) => [...current, ...(data.items ?? data)])
      setPhotoCursor(data.next_cursor ?? null)
      setPhotoTotal(data.total ?? photoTotal)
    } catch (error) {
      setPhotoError(error.message)
      if (error.status === 401) {
        setStoredToken("")
        setUser(null)
      }
    } finally {
      setLoadingMorePhotos(false)
    }
  }, [
    endTime,
    getNextPhotoPageSize,
    hasMorePhotos,
    loadingMorePhotos,
    loadingPhotos,
    photoCursor,
    photoTotal,
    selectedDepartment,
    setUser,
    startTime,
    station,
  ])

  useEffect(() => {
    window.localStorage.setItem(PHOTO_LIMIT_STORAGE_KEY, photoLimit)
  }, [photoLimit])

  useEffect(() => {
    window.localStorage.setItem(PHOTO_DEDUPE_ENABLED_STORAGE_KEY, String(dedupeEnabled))
  }, [dedupeEnabled])

  useEffect(() => {
    window.localStorage.setItem(PHOTO_DEDUPE_WINDOW_STORAGE_KEY, dedupeWindowSeconds)
  }, [dedupeWindowSeconds])

  useEffect(() => {
    if (!user) {
      const timer = window.setTimeout(resetPhotoState, 0)
      return () => window.clearTimeout(timer)
    }

    if (currentPage !== monitorPageKey) {
      return undefined
    }

    if (!hasPhotoAccess) {
      const timer = window.setTimeout(() => {
        setPhotos([])
        setPhotoCursor(null)
        setPhotoTotal(0)
        setPhotoError("")
        setSelectedPhoto(null)
      }, 0)
      return () => window.clearTimeout(timer)
    }

    const timer = window.setTimeout(loadPhotos, 0)
    return () => window.clearTimeout(timer)
  }, [currentPage, hasPhotoAccess, loadPhotos, monitorPageKey, resetPhotoState, user])

  useEffect(() => {
    if (!user) {
      wsRef.current?.close()
      wsRef.current = null
      return undefined
    }

    if (!hasPhotoAccess || currentPage !== monitorPageKey) {
      wsRef.current?.close()
      wsRef.current = null
      return undefined
    }

    const ws = new WebSocket(getWebSocketUrl())
    wsRef.current = ws

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === "new_photo") {
        loadPhotos()
      }
    }

    ws.onclose = () => {
      if (wsRef.current === ws) {
        wsRef.current = null
      }
    }

    return () => {
      ws.close()
      if (wsRef.current === ws) {
        wsRef.current = null
      }
    }
  }, [currentPage, hasPhotoAccess, loadPhotos, monitorPageKey, user])

  return {
    station,
    setStation,
    photoLimit,
    setPhotoLimit,
    dedupeEnabled,
    setDedupeEnabled,
    dedupeWindowSeconds,
    setDedupeWindowSeconds,
    startTime,
    setStartTime,
    endTime,
    setEndTime,
    selectedDepartment,
    setSelectedDepartment,
    selectedPhoto,
    setSelectedPhoto,
    loadingPhotos,
    loadingMorePhotos,
    photoError,
    displayedPhotos,
    hasMorePhotos,
    parsedPhotoLimit,
    loadPhotos,
    loadMorePhotos,
    photoTotal,
    resetPhotoState,
  }
}
