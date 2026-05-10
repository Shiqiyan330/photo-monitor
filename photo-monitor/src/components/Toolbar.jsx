const STATIONS = [
  { value: "xiazhan", label: "下站" },
  { value: "shangzhan", label: "上站" },
]

export default function Toolbar({
  station,
  setStation,
  photoLimit,
  setPhotoLimit,
  dedupeEnabled,
  setDedupeEnabled,
  dedupeWindowSeconds,
  setDedupeWindowSeconds,
  department,
  setDepartment,
  departmentOptions,
  startTime,
  setStartTime,
  endTime,
  setEndTime,
  onRefresh,
  loading,
}) {
  return (
    <section className="toolbar">
      <div className="toolbar-group">
        <div className="station-group">
          {STATIONS.map((item) => (
            <button
              key={item.value}
              type="button"
              className={station === item.value ? "station-button active" : "station-button"}
              onClick={() => setStation(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>

        {departmentOptions.length ? (
          <label className="toolbar-select">
            <span>部门</span>
            <select value={department} onChange={(event) => setDepartment(event.target.value)}>
              {departmentOptions.map((item) => (
                <option key={item || "all"} value={item}>
                  {item || "全部部门"}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <label className="toolbar-select">
          <span>展示数量</span>
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9]*"
            value={photoLimit}
            onChange={(event) => setPhotoLimit(event.target.value)}
            placeholder="全部"
          />
        </label>

        <label className="toolbar-select">
          <span>开始时段</span>
          <input type="time" value={startTime} onChange={(event) => setStartTime(event.target.value)} />
        </label>

        <label className="toolbar-select">
          <span>结束时段</span>
          <input type="time" value={endTime} onChange={(event) => setEndTime(event.target.value)} />
        </label>

        <label className="toolbar-check">
          <input
            type="checkbox"
            checked={dedupeEnabled}
            onChange={(event) => setDedupeEnabled(event.target.checked)}
          />
          <span>展示去重</span>
        </label>

        {dedupeEnabled ? (
          <label className="toolbar-select">
            <span>去重时间窗</span>
            <div className="toolbar-input-suffix">
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                value={dedupeWindowSeconds}
                onChange={(event) => setDedupeWindowSeconds(event.target.value)}
                placeholder="20"
              />
              <span>秒</span>
            </div>
          </label>
        ) : null}
      </div>

      <div className="toolbar-actions">
        <a className="ghost-button icon-button-text" href="/downloads/photo-monitor-uploader.ps1" download>
          <span className="material-symbols-outlined button-icon" aria-hidden="true">
            download
          </span>
          下载上传程序
        </a>
        <button type="button" className="ghost-button" onClick={onRefresh} disabled={loading}>
          {loading ? "刷新中..." : "手动刷新"}
        </button>
      </div>
    </section>
  )
}
