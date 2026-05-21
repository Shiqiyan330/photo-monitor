import { useCallback, useEffect, useState } from "react"
import { fetchPhotos } from "../api"
import useWebSocket from "./useWebsockets"

export default function usePhotos(station) {
  const [photos, setPhotos] = useState([])

  const load = useCallback(async () => {
    const data = await fetchPhotos(station)
    setPhotos(data)
  }, [station])

  useEffect(() => {
    const timer = window.setTimeout(load, 0)
    return () => window.clearTimeout(timer)
  }, [load])

  useWebSocket(
    useCallback(
      (msg) => {
        if (msg.type === "new_photo") {
          load()
        }
      },
      [load],
    ),
  )

  return { photos, reload: load }
}
