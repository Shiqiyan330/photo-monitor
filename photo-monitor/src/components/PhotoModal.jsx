import { getAssetUrl } from "../api"

export default function PhotoModal({ photo, onClose }) {
  if (!photo) return null

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(event) => event.stopPropagation()}>
        <button type="button" className="modal-close" onClick={onClose}>
          关闭
        </button>

        <img
          src={getAssetUrl(photo.url.replace("http://127.0.0.1:8000", ""))}
          alt={photo.name}
          className="modal-image"
        />

        <div className="modal-caption">
          <div>{photo.name}</div>
          <div>{new Date(photo.time * 1000).toLocaleString()}</div>
        </div>
      </div>
    </div>
  )
}
