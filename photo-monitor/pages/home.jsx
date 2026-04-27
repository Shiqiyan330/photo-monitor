// src/pages/Home.jsx
import { useState } from "react"
import usePhotos from "../hooks/usePhotos"
import Toolbar from "../components/Toolbar"
import PhotoGrid from "../components/PhotoGrid"
import PhotoModal from "../components/PhotoModal"

export default function Home() {
  const [station, setStation] = useState("xiazhan")
  const [selected, setSelected] = useState(null)

  const { photos, reload } = usePhotos(station)

  return (
    <div style={{ padding: 20 }}>
      <h1>📸 Photo Monitor</h1>

      <Toolbar
        station={station}
        setStation={setStation}
        onRefresh={reload}
      />

      <PhotoGrid
        photos={photos}
        onClick={setSelected}
      />

      <PhotoModal
        photo={selected}
        onClose={() => setSelected(null)}
      />
    </div>
  )
}