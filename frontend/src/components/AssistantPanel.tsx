import { useState } from "react";
import { useStore, newPlane } from "../store/useStore";
import { askAssistant, scaleMesh } from "../api/client";

export default function AssistantPanel() {
  const s = useStore();
  const bed = useStore((st) => st.bedDims());
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (!s.stats || !s.sessionId) return null;

  async function send() {
    if (!s.sessionId || !message.trim()) return;
    setBusy(true);
    setErr(null);
    setReply(null);
    try {
      const res = await askAssistant(s.sessionId, message, bed);
      // The assistant may have scaled the model server-side — re-sync the mesh.
      if (Math.abs(res.scale - s.scale) > 1e-6) {
        const sc = await scaleMesh(s.sessionId, res.scale);
        s.applyScaleResult(sc.scale, sc.mesh, sc.stats);
      }
      s.setCutPlan(res.planes.map((p) => newPlane(p.axis, p.offset, "auto")));
      setReply(res.reply || "Done.");
      setMessage("");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Assistant failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="section-title">✦ AI assistant</div>
      <div className="card">
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder='e.g. "make it 2x bigger and split into the fewest pieces that fit"'
          rows={2}
          style={{
            width: "100%",
            resize: "vertical",
            background: "var(--panel-2)",
            color: "var(--text)",
            border: "1px solid var(--border)",
            borderRadius: 6,
            padding: 8,
            font: "inherit",
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) send();
          }}
        />
        <button
          className="primary"
          style={{ width: "100%", marginTop: 8 }}
          onClick={send}
          disabled={busy || !message.trim()}
        >
          {busy ? "Thinking…" : "Ask"}
        </button>
        {reply && (
          <div style={{ fontSize: 13, marginTop: 8, color: "var(--text)" }}>{reply}</div>
        )}
        {err && (
          <div style={{ fontSize: 12, marginTop: 8, color: "var(--danger)" }}>{err}</div>
        )}
      </div>
    </div>
  );
}
