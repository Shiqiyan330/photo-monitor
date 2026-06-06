import { useCallback, useEffect, useState } from "react"

export default function useOfficeUploads({ fetchItems, uploadItem, deleteItem, successMessages, showBanner }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState("")

  const loadItems = useCallback(async () => {
    setLoading(true)
    setError("")
    try {
      const data = await fetchItems()
      setItems(data.items ?? [])
    } catch (loadError) {
      setError(loadError.message)
    } finally {
      setLoading(false)
    }
  }, [fetchItems])

  useEffect(() => {
    const timer = window.setTimeout(loadItems, 0)
    return () => window.clearTimeout(timer)
  }, [loadItems])

  const upload = useCallback(async (payload, options) => {
    setUploading(true)
    try {
      await uploadItem(payload, options)
      showBanner(successMessages.uploaded)
      await loadItems()
    } finally {
      setUploading(false)
    }
  }, [loadItems, showBanner, successMessages.uploaded, uploadItem])

  const remove = useCallback(async (item) => {
    await deleteItem(item.id)
    showBanner(successMessages.deleted)
    await loadItems()
  }, [deleteItem, loadItems, showBanner, successMessages.deleted])

  return { items, loading, uploading, error, loadItems, upload, remove }
}

