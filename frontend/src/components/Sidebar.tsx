import { useRef } from "react";
import { useStore } from "../store/useStore";
import { uploadMesh } from "../api/client";
import PrinterPanel from "./PrinterPanel";
import ScalePanel from "./ScalePanel";
import CutPanel from "./CutPanel";
import AssistantPanel from "./AssistantPanel";

function fmt(n: number): string {
  return n.toFixed(1);
}

export default function Sidebar() {
  const fileRef = useRef<HTMLInputElement>(null);
  const { filename, stats, loading, error, setLoading, setError, loadUpload } =
    useStore();
  const bed = useStore((s) => s.bedDims());
  const parts = useStore((s) => s.parts);

  async function onFile(file: File) {
    setLoading(true);
    setError(null);
    try {
      const res = await uploadMesh(file);
      loadUpload(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  const overflowAxes =
    stats
      ? (["x", "y", "z"] as const).filter((ax, i) => stats.sizeMm[i] > bed[ax])
      : [];

  return (
    <div className="sidebar">
      <div className="brand">
        Split<span>Forge</span>
      </div>

      <div>
        <div className="section-title">Model</div>
        <input
          ref={fileRef}
          type="file"
          accept=".stl,.obj,.ply,.off,.glb"
          style={{ display: "none" }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onFile(f);
          }}
        />
        <div
          className="file-drop"
          onClick={() => fileRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files?.[0];
            if (f) onFile(f);
          }}
        >
          {loading ? "Loading…" : filename ? filename : "Drop an STL here or click to browse"}
        </div>
        {error && (
          <div style={{ color: "var(--danger)", fontSize: 13, marginTop: 8 }}>{error}</div>
        )}
      </div>

      <PrinterPanel />

      {stats && <ScalePanel />}

      {stats && (
        <div>
          <div className="section-title">Details</div>
          <div className="card">
            <div className="stat-row">
              <span className="k">Triangles</span>
              <span>{stats.triangleCount.toLocaleString()}</span>
            </div>
            <div className="stat-row">
              <span className="k">Size (mm)</span>
              <span>
                {fmt(stats.sizeMm[0])} × {fmt(stats.sizeMm[1])} × {fmt(stats.sizeMm[2])}
              </span>
            </div>
            <div className="stat-row">
              <span className="k">Fits printer</span>
              {overflowAxes.length === 0 ? (
                <span className="badge ok">fits</span>
              ) : (
                <span className="badge warn">
                  over on {overflowAxes.join(", ").toUpperCase()}
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {stats && !parts && <AssistantPanel />}

      {stats && <CutPanel />}
    </div>
  );
}
