import { useEffect } from "react"
import { getAssetUrl } from "../api"

function formatPhotoTime(photo) {
  if (photo.actual_time_text) {
    return photo.actual_time_text
  }
  const value = photo.actual_time ?? photo.time
  return value ? new Date(value * 1000).toLocaleString() : ""
}

export default function PhotoModal({ photo, onClose }) {
  useEffect(() => {
    if (!photo) {
      return undefined
    }

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        onClose()
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [photo, onClose])

  if (!photo) return null

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div
        className="modal-card modal-card-enter"
        role="dialog"
        aria-modal="true"
        aria-label="照片预览"
        onClick={(event) => event.stopPropagation()}
      >
        <button type="button" className="modal-close" onClick={onClose}>
          关闭
        </button>

        <img src={getAssetUrl(photo.url)} alt={photo.name} className="modal-image" />

        <div className="modal-caption">
          <div>{photo.name}</div>
          <div>{formatPhotoTime(photo)}</div>
        </div>
      </div>
    </div>
  )
}
