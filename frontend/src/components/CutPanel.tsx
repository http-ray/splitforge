import { useStore, type Axis, type CutPlane, newPlane } from "../store/useStore";
import {
  cutMesh,
  autoPartition,
  packParts,
  partStlUrl,
  type Plane,
} from "../api/client";

const AXES: Axis[] = ["x", "y", "z"];

function planeRange(axis: Axis, size: [number, number, number]): [number, number] {
  if (axis === "x") return [-size[0] / 2, size[0] / 2];
  if (axis === "y") return [-size[1] / 2, size[1] / 2];
  return [0, size[2]];
}

function toApiPlane(p: CutPlane): Plane {
  const normal: [number, number, number] =
    p.axis === "x" ? [1, 0, 0] : p.axis === "y" ? [0, 1, 0] : [0, 0, 1];
  const point: [number, number, number] =
    p.axis === "x" ? [p.offset, 0, 0] : p.axis === "y" ? [0, p.offset, 0] : [0, 0, p.offset];
  return { point, normal };
}

// Rough estimates from solid volume. PLA ~1.24 g/cm^3; a typical print is far from
// solid, so we assume ~30% effective fill (walls + infill). FDM lays down roughly
// 8 cm^3/hr. Both are ballpark figures for planning, not slicer-accurate.
const PLA_DENSITY = 1.24;
const EFFECTIVE_FILL = 0.3;
const THROUGHPUT_CM3_PER_HR = 8;

function estimate(totalVolumeMm3: number): { grams: number; hours: number } {
  const cm3 = (totalVolumeMm3 / 1000) * EFFECTIVE_FILL;
  return { grams: cm3 * PLA_DENSITY, hours: cm3 / THROUGHPUT_CM3_PER_HR };
}

function fmtTime(hours: number): string {
  const h = Math.floor(hours);
  const m = Math.round((hours - h) * 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export default function CutPanel() {
  const s = useStore();
  const bed = useStore((st) => st.bedDims());
  if (!s.mesh || !s.stats) return null;

  async function showBed() {
    if (!s.sessionId) return;
    s.setViewMode("bed");
    if (!s.pack) {
      try {
        const res = await packParts(s.sessionId, bed);
        s.setPack(res);
      } catch (e) {
        s.setError(e instanceof Error ? e.message : "Pack failed");
      }
    }
  }

  // ---- Results view (after a cut) --------------------------------------
  if (s.parts) {
    return (
      <div>
        <div className="section-title">Parts ({s.parts.length})</div>
        {s.connectorCount > 0 && (
          <div style={{ fontSize: 12, color: "var(--accent-2)", marginBottom: 8 }}>
            🔩 {s.connectorCount} alignment pin{s.connectorCount > 1 ? "s" : ""} added —
            drag “Separate parts” to see them mate.
          </div>
        )}

        <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
          <button
            className={s.viewMode === "assembled" ? "primary" : ""}
            style={{ flex: 1 }}
            onClick={() => s.setViewMode("assembled")}
          >
            Assembled
          </button>
          <button
            className={s.viewMode === "bed" ? "primary" : ""}
            style={{ flex: 1 }}
            onClick={showBed}
          >
            Bed layout
          </button>
        </div>

        {s.viewMode === "assembled" ? (
          <div className="card" style={{ marginBottom: 10 }}>
            <div className="stat-row">
              <span className="k">Separate parts</span>
              <span>{Math.round(s.explode * 100)}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={s.explode}
              onChange={(e) => s.setExplode(parseFloat(e.target.value))}
              style={{ width: "100%" }}
            />
          </div>
        ) : (
          <div className="card" style={{ marginBottom: 10 }}>
            <div className="stat-row">
              <span className="k">Plates needed</span>
              <span className="badge ok">{s.pack ? s.pack.plateCount : "…"}</span>
            </div>
            {s.pack && s.pack.unplaceable.length > 0 && (
              <div style={{ fontSize: 12, color: "var(--danger)", marginTop: 6 }}>
                {s.pack.unplaceable.length} part(s) don't fit the bed — cut them smaller.
              </div>
            )}
          </div>
        )}
        {(() => {
          const total = s.parts.reduce((a, p) => a + p.volumeMm3, 0);
          const est = estimate(total);
          return (
            <div className="card" style={{ marginBottom: 10 }}>
              <div className="stat-row">
                <span className="k">Est. filament</span>
                <span>~{est.grams.toFixed(0)} g</span>
              </div>
              <div className="stat-row">
                <span className="k">Est. print time</span>
                <span>~{fmtTime(est.hours)}</span>
              </div>
              <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>
                Rough estimate at ~30% fill — use your slicer for exact numbers.
              </div>
            </div>
          );
        })()}

        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {s.parts.map((p) => (
            <div className="card" key={p.index}>
              <div className="stat-row">
                <span style={{ fontWeight: 600 }}>Part {p.index + 1}</span>
                <span className={`badge ${p.fits ? "ok" : "warn"}`}>
                  {p.fits ? "fits" : "too big"}
                </span>
              </div>
              <div className="stat-row">
                <span className="k">Size</span>
                <span>{p.sizeMm.map((n) => n.toFixed(0)).join(" × ")} mm</span>
              </div>
              <div className="stat-row">
                <span className="k">Watertight</span>
                <span className={`badge ${p.watertight ? "ok" : "warn"}`}>
                  {p.watertight ? "yes" : "no"}
                </span>
              </div>
              {s.sessionId && (
                <a href={partStlUrl(s.sessionId, p.index)} download style={{ display: "block", marginTop: 6 }}>
                  <button style={{ width: "100%" }}>Download STL</button>
                </a>
              )}
            </div>
          ))}
        </div>
        <button style={{ marginTop: 12, width: "100%" }} onClick={s.clearCut}>
          ← Edit cut plan
        </button>
      </div>
    );
  }

  // ---- Cut-plan editor -------------------------------------------------
  async function suggest() {
    if (!s.sessionId) return;
    s.setBusy(true);
    s.setError(null);
    try {
      const proposed = await autoPartition(s.sessionId, bed);
      s.setCutPlan(proposed.map((p) => newPlane(p.axis, p.offset, "auto")));
      if (proposed.length === 0) s.setError("Model already fits — no cuts needed.");
    } catch (e) {
      s.setError(e instanceof Error ? e.message : "Auto-partition failed");
    } finally {
      s.setBusy(false);
    }
  }

  async function doCut() {
    if (!s.sessionId || s.cutPlan.length === 0) return;
    s.setCutting(true);
    s.setError(null);
    try {
      const res = await cutMesh(s.sessionId, s.cutPlan.map(toApiPlane), bed, {
        connectors: s.connectorsEnabled,
        connectorRadius: s.connectorRadius,
      });
      s.setCutResult(res.parts, res.meshes, res.connectorCount);
    } catch (e) {
      s.setError(e instanceof Error ? e.message : "Cut failed");
      s.setCutting(false);
    }
  }

  const size = s.stats.sizeMm;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div className="section-title" style={{ marginBottom: 0 }}>Cut plan</div>
        <div style={{ display: "flex", gap: 4 }}>
          <button
            onClick={s.undo}
            disabled={s.past.length === 0}
            title="Undo"
            style={{ padding: "2px 8px" }}
          >
            ↶
          </button>
          <button
            onClick={s.redo}
            disabled={s.future.length === 0}
            title="Redo"
            style={{ padding: "2px 8px" }}
          >
            ↷
          </button>
        </div>
      </div>

      <button
        className="primary"
        style={{ width: "100%", marginTop: 8 }}
        onClick={suggest}
        disabled={s.busy}
      >
        {s.busy ? "Thinking…" : "⚡ Auto-partition to fit"}
      </button>

      <div style={{ display: "flex", gap: 6, margin: "10px 0" }}>
        {AXES.map((a) => (
          <button key={a} style={{ flex: 1 }} onClick={() => s.addPlane(a)}>
            + {a.toUpperCase()} cut
          </button>
        ))}
      </div>

      {s.cutPlan.length === 0 && (
        <div style={{ fontSize: 12, color: "var(--muted)" }}>
          Auto-partition for a suggested plan, or add cut planes manually. Drag a slider to reposition.
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {s.cutPlan.map((p, i) => {
          const [min, max] = planeRange(p.axis, size);
          const selected = p.id === s.selectedPlaneId;
          return (
            <div
              className="card"
              key={p.id}
              onClick={() => s.selectPlane(p.id)}
              style={{ borderColor: selected ? "var(--accent)" : "var(--border)", cursor: "pointer" }}
            >
              <div className="stat-row">
                <span style={{ fontWeight: 600 }}>
                  {p.axis.toUpperCase()} cut {i + 1}
                  {p.source === "auto" && (
                    <span className="badge ok" style={{ marginLeft: 6 }}>auto</span>
                  )}
                </span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    s.removePlane(p.id);
                  }}
                  style={{ padding: "2px 8px" }}
                >
                  ✕
                </button>
              </div>
              <div className="stat-row">
                <span className="k">Position</span>
                <span>{p.offset.toFixed(1)} mm</span>
              </div>
              <input
                type="range"
                min={min}
                max={max}
                step={(max - min) / 200 || 1}
                value={p.offset}
                onPointerDown={() => s.snapshotPlan()}
                onChange={(e) => s.updatePlane(p.id, parseFloat(e.target.value))}
                onClick={(e) => e.stopPropagation()}
                style={{ width: "100%" }}
              />
            </div>
          );
        })}
      </div>

      <div className="card" style={{ marginTop: 12 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={s.connectorsEnabled}
            onChange={(e) => s.setConnectorsEnabled(e.target.checked)}
          />
          <span style={{ fontWeight: 600 }}>Add alignment pins</span>
        </label>
        {s.connectorsEnabled && (
          <>
            <div className="stat-row" style={{ marginTop: 8 }}>
              <span className="k">Pin radius</span>
              <span>{s.connectorRadius.toFixed(1)} mm</span>
            </div>
            <input
              type="range"
              min={1.5}
              max={8}
              step={0.5}
              value={s.connectorRadius}
              onChange={(e) => s.setConnectorRadius(parseFloat(e.target.value))}
              style={{ width: "100%" }}
            />
            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
              Adds a peg to one part and a matching socket to its neighbor so parts snap
              back together.
            </div>
          </>
        )}
      </div>

      <button
        className="primary"
        style={{ width: "100%", marginTop: 12 }}
        onClick={doCut}
        disabled={s.cutting || s.cutPlan.length === 0}
      >
        {s.cutting ? "Cutting…" : `Cut into ${s.cutPlan.length + 1}+ parts`}
      </button>
    </div>
  );
}
