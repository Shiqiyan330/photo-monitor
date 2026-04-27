// src/hooks/usePhotos.js
import { useEffect, useState } from "react"
import { fetchPhotos } from "../api"
import useWebSocket from "./useWebSocket"

export default function usePhotos(station) {
  const [photos, setPhotos] = useState([])

  const load = async () => {
    const data = await fetchPhotos(station)
    setPhotos(data)
  }

  useEffect(() => {
    load()
  }, [station])

  useWebSocket((msg) => {
    if (msg.type === "new_photo") {
      load()
    }
  })

  return { photos, reload: load }
}