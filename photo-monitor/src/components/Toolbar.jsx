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
  departmentOptions,
  selectedDepartment,
  setSelectedDepartment,
  showDepartmentSwitch,
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

        {showDepartmentSwitch ? (
          <label className="toolbar-select">
            <span>部门切换</span>
            <select value={selectedDepartment} onChange={(event) => setSelectedDepartment(event.target.value)}>
              {departmentOptions.map((item) => (
                <option key={item} value={item}>
                  {item || "全部部门"}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>

      <button type="button" className="ghost-button" onClick={onRefresh} disabled={loading}>
        {loading ? "刷新中..." : "手动刷新"}
      </button>
    </section>
  )
}
