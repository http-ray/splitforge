import { useStore, CUSTOM_PRINTER_ID } from "../store/useStore";

export default function PrinterPanel() {
  const {
    printers,
    selectedPrinterId,
    customBed,
    selectPrinter,
    setCustomBed,
  } = useStore();
  const isCustom = selectedPrinterId === CUSTOM_PRINTER_ID;

  return (
    <div>
      <div className="section-title">Printer</div>
      <select
        value={selectedPrinterId}
        onChange={(e) => selectPrinter(e.target.value)}
      >
        {printers.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name} — {p.x}×{p.y}×{p.z}
          </option>
        ))}
        <option value={CUSTOM_PRINTER_ID}>Custom…</option>
      </select>

      {isCustom && (
        <div className="card" style={{ marginTop: 8 }}>
          <div style={{ display: "flex", gap: 8 }}>
            {(["x", "y", "z"] as const).map((ax) => (
              <label key={ax} style={{ flex: 1, fontSize: 12, color: "var(--muted)" }}>
                {ax.toUpperCase()} (mm)
                <input
                  type="number"
                  min={1}
                  value={customBed[ax]}
                  onChange={(e) =>
                    setCustomBed({ [ax]: Math.max(1, parseFloat(e.target.value) || 0) })
                  }
                  style={{
                    width: "100%",
                    marginTop: 4,
                    background: "var(--panel-2)",
                    color: "var(--text)",
                    border: "1px solid var(--border)",
                    borderRadius: 6,
                    padding: "6px",
                  }}
                />
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
