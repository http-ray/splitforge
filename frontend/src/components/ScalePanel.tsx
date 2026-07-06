import { useState, useEffect } from "react";
import { useStore } from "../store/useStore";
import { scaleMesh } from "../api/client";

export default function ScalePanel() {
  const { sessionId, scale, stats, busy, setBusy, setError, applyScaleResult } =
    useStore();
  const [factor, setFactor] = useState(scale);

  useEffect(() => setFactor(scale), [scale]);

  if (!stats) return null;

  async function apply(f: number) {
    if (!sessionId) return;
    const clamped = Math.min(Math.max(f, 0.05), 50);
    setBusy(true);
    setError(null);
    try {
      const res = await scaleMesh(sessionId, clamped);
      applyScaleResult(res.scale, res.mesh, res.stats);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Scale failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="section-title">Scale</div>
      <div className="card">
        <div className="stat-row">
          <span className="k">Factor</span>
          <span>{factor.toFixed(2)}×</span>
        </div>
        <input
          type="range"
          min={0.1}
          max={5}
          step={0.05}
          value={factor}
          onChange={(e) => setFactor(parseFloat(e.target.value))}
          onMouseUp={() => apply(factor)}
          onTouchEnd={() => apply(factor)}
          disabled={busy}
          style={{ width: "100%" }}
        />
        <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
          <input
            type="number"
            min={0.05}
            step={0.1}
            value={factor}
            onChange={(e) => setFactor(parseFloat(e.target.value) || 0)}
            style={{
              flex: 1,
              background: "var(--panel-2)",
              color: "var(--text)",
              border: "1px solid var(--border)",
              borderRadius: 6,
              padding: "6px",
            }}
          />
          <button onClick={() => apply(factor)} disabled={busy}>
            Apply
          </button>
        </div>
      </div>
    </div>
  );
}
