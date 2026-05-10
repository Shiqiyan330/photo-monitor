import { useEffect, useRef } from "react"
import { getAssetUrl } from "../api"

function formatPhotoTime(photo) {
  const value = photo.actual_time ?? photo.time
  return value ? new Date(value * 1000).toLocaleString() : ""
}

export default function PhotoGrid({
  photos,
  loading,
  station,
  displayCount,
  totalCount,
  originalCount,
  hasMore,
  onLoadMore,
  onClickPhoto,
}) {
  const loadMoreRef = useRef(null)

  useEffect(() => {
    const node = loadMoreRef.current
    if (!node || !hasMore || loading) {
      return undefined
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          onLoadMore()
        }
      },
      { rootMargin: "600px 0px" },
    )

    observer.observe(node)
    return () => observer.disconnect()
  }, [hasMore, loading, onLoadMore])

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
              src={getAssetUrl(photo.thumbnail_url ?? photo.url)}
              alt={photo.name}
              className="photo-thumb"
              loading="lazy"
              decoding="async"
              onClick={() => onClickPhoto(photo)}
            /> 

            <div className="photo-meta">
              <span>{formatPhotoTime(photo)}</span>
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

      {hasMore ? (
        <div ref={loadMoreRef} className="status-card">
          继续加载更多照片...
        </div>
      ) : null}
    </>
  )
}
