import { memo, useEffect, useRef } from "react"
import { getAssetUrl, getAuthorizedUrl } from "../api"

function formatPhotoTime(photo) {
  if (photo.actual_time_text) {
    return photo.actual_time_text
  }
  const value = photo.actual_time ?? photo.time
  return value ? new Date(value * 1000).toLocaleString() : ""
}

function PhotoGrid({
  photos,
  loading,
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
    return (
      <div className="photo-grid" aria-label="照片加载中">
        {Array.from({ length: 8 }).map((_, index) => (
          <div key={index} className="photo-card photo-card-skeleton">
            <div className="photo-thumb-skeleton" />
            <div className="skeleton-line wide" />
            <div className="skeleton-line" />
          </div>
        ))}
      </div>
    )
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
          <article key={photo.id ?? `${photo.url}-${index}`} className="photo-card">
            <button
              type="button"
              className="photo-thumb-button"
              onClick={() => onClickPhoto(photo)}
              aria-label={`查看照片：${photo.name}`}
            >
              <img
                src={getAuthorizedUrl(getAssetUrl(photo.thumbnail_url ?? photo.url))}
                alt={photo.name}
                className="photo-thumb"
                loading="lazy"
                decoding="async"
              />
            </button>

            <div className="photo-meta">
              <span>{formatPhotoTime(photo)}</span>
              <span>{photo.size ? `${(photo.size / 1024).toFixed(1)} KB` : "未知大小"}</span>
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

export default memo(PhotoGrid)
