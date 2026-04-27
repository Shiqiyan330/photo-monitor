import { getAssetUrl } from "../api"

export default function PhotoGrid({
  photos,
  loading,
  station,
  displayCount,
  totalCount,
  originalCount,
  onClickPhoto,
}) {
  if (loading && photos.length === 0) {
    return <div className="status-card">正在加载 {station} 的照片...</div>
  }

  if (!loading && photos.length === 0) {
    return <div className="status-card">当前站点还没有可展示的照片。</div>
  }

  return (
    <>
      <div className="photo-summary">
        当前展示 {displayCount} / {totalCount} 张
        {originalCount > totalCount ? `（原始共 ${originalCount} 张）` : ""}
      </div>

      <div className="photo-grid">
        {photos.map((photo, index) => (
          <article key={`${photo.url}-${index}`} className="photo-card">
            <img
              src={getAssetUrl(photo.url)}
              alt={photo.name}
              className="photo-thumb"
              onClick={() => onClickPhoto(photo)}
            />

            <div className="photo-meta">
              <span>{new Date(photo.time * 1000).toLocaleString()}</span>
              <span>{(photo.size / 1024).toFixed(1)} KB</span>
            </div>

            <div className="photo-name" title={photo.name}>
              {photo.name}
            </div>

            <div className="photo-folder" title={photo.folder}>
              {photo.folder}
            </div>
          </article>
        ))}
      </div>
    </>
  )
}
