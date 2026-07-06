import { create } from "zustand";
import type {
  MeshData,
  MeshStats,
  Printer,
  PartInfo,
  Bed,
  PackResponse,
} from "../api/client";

export type Axis = "x" | "y" | "z";
export type ViewMode = "assembled" | "bed";

export interface CutPlane {
  id: string;
  axis: Axis;
  offset: number;
  source: "auto" | "manual";
}

export const CUSTOM_PRINTER_ID = "custom";

let planeCounter = 0;
export function newPlane(axis: Axis, offset: number, source: "auto" | "manual"): CutPlane {
  planeCounter += 1;
  return { id: `p${planeCounter}`, axis, offset, source };
}

interface AppState {
  sessionId: string | null;
  filename: string | null;
  mesh: MeshData | null;
  stats: MeshStats | null;
  scale: number;

  printers: Printer[];
  selectedPrinterId: string;
  customBed: Bed;

  // Editable cut plan
  cutPlan: CutPlane[];
  selectedPlaneId: string | null;
  past: CutPlane[][];
  future: CutPlane[][];
  connectorsEnabled: boolean;
  connectorRadius: number;
  connectorCount: number;

  // Cut results
  parts: PartInfo[] | null;
  partMeshes: MeshData[] | null;
  cutting: boolean;
  explode: number; // 0 = assembled, 1 = fully separated
  viewMode: ViewMode;
  pack: PackResponse | null;

  loading: boolean;
  busy: boolean;
  error: string | null;

  setPrinters: (printers: Printer[]) => void;
  selectPrinter: (id: string) => void;
  setCustomBed: (bed: Partial<Bed>) => void;
  setLoading: (loading: boolean) => void;
  setBusy: (busy: boolean) => void;
  setError: (error: string | null) => void;
  loadUpload: (r: {
    sessionId: string;
    filename: string;
    mesh: MeshData;
    stats: MeshStats;
  }) => void;
  applyScaleResult: (scale: number, mesh: MeshData, stats: MeshStats) => void;

  addPlane: (axis: Axis) => void;
  updatePlane: (id: string, offset: number) => void;
  removePlane: (id: string) => void;
  selectPlane: (id: string | null) => void;
  setCutPlan: (planes: CutPlane[]) => void;
  clearPlan: () => void;
  snapshotPlan: () => void;
  undo: () => void;
  redo: () => void;

  setConnectorsEnabled: (on: boolean) => void;
  setConnectorRadius: (r: number) => void;
  setCutting: (cutting: boolean) => void;
  setCutResult: (parts: PartInfo[], meshes: MeshData[], connectorCount: number) => void;
  setExplode: (explode: number) => void;
  setViewMode: (mode: ViewMode) => void;
  setPack: (pack: PackResponse | null) => void;
  clearCut: () => void;

  selectedPrinter: () => Printer | null;
  bedDims: () => Bed;
}

const DEFAULT_CUSTOM_BED: Bed = { x: 220, y: 220, z: 250 };

export const useStore = create<AppState>((set, get) => ({
  sessionId: null,
  filename: null,
  mesh: null,
  stats: null,
  scale: 1,

  printers: [],
  selectedPrinterId: "ender3",
  customBed: { ...DEFAULT_CUSTOM_BED },

  cutPlan: [],
  selectedPlaneId: null,
  past: [],
  future: [],
  connectorsEnabled: false,
  connectorRadius: 3,
  connectorCount: 0,

  parts: null,
  partMeshes: null,
  cutting: false,
  explode: 0,
  viewMode: "assembled",
  pack: null,

  loading: false,
  busy: false,
  error: null,

  setPrinters: (printers) => set({ printers }),
  selectPrinter: (id) => set({ selectedPrinterId: id }),
  setCustomBed: (bed) => set((s) => ({ customBed: { ...s.customBed, ...bed } })),
  setLoading: (loading) => set({ loading }),
  setBusy: (busy) => set({ busy }),
  setError: (error) => set({ error }),
  loadUpload: (r) =>
    set({
      sessionId: r.sessionId,
      filename: r.filename,
      mesh: r.mesh,
      stats: r.stats,
      scale: 1,
      error: null,
      parts: null,
      partMeshes: null,
      cutPlan: [],
      selectedPlaneId: null,
      past: [],
      future: [],
    }),
  applyScaleResult: (scale, mesh, stats) =>
    set({ scale, mesh, stats, parts: null, partMeshes: null }),

  snapshotPlan: () =>
    set((s) => ({ past: [...s.past, s.cutPlan], future: [] })),
  addPlane: (axis) => {
    const stats = get().stats;
    if (!stats) return;
    // X/Y models are centered on 0; Z sits on the bed, so default to mid-height.
    const offset = axis === "z" ? stats.sizeMm[2] / 2 : 0;
    const p = newPlane(axis, offset, "manual");
    set((s) => ({
      past: [...s.past, s.cutPlan],
      future: [],
      cutPlan: [...s.cutPlan, p],
      selectedPlaneId: p.id,
    }));
  },
  updatePlane: (id, offset) =>
    set((s) => ({
      cutPlan: s.cutPlan.map((p) => (p.id === id ? { ...p, offset } : p)),
    })),
  removePlane: (id) =>
    set((s) => ({
      past: [...s.past, s.cutPlan],
      future: [],
      cutPlan: s.cutPlan.filter((p) => p.id !== id),
      selectedPlaneId: s.selectedPlaneId === id ? null : s.selectedPlaneId,
    })),
  selectPlane: (selectedPlaneId) => set({ selectedPlaneId }),
  setCutPlan: (cutPlan) =>
    set((s) => ({
      past: [...s.past, s.cutPlan],
      future: [],
      cutPlan,
      selectedPlaneId: cutPlan.length ? cutPlan[0].id : null,
    })),
  clearPlan: () =>
    set((s) => ({
      past: [...s.past, s.cutPlan],
      future: [],
      cutPlan: [],
      selectedPlaneId: null,
    })),
  undo: () =>
    set((s) => {
      if (s.past.length === 0) return {};
      const prev = s.past[s.past.length - 1];
      return {
        past: s.past.slice(0, -1),
        future: [s.cutPlan, ...s.future],
        cutPlan: prev,
        selectedPlaneId: prev.length ? prev[0].id : null,
      };
    }),
  redo: () =>
    set((s) => {
      if (s.future.length === 0) return {};
      const next = s.future[0];
      return {
        past: [...s.past, s.cutPlan],
        future: s.future.slice(1),
        cutPlan: next,
        selectedPlaneId: next.length ? next[0].id : null,
      };
    }),

  setConnectorsEnabled: (connectorsEnabled) => set({ connectorsEnabled }),
  setConnectorRadius: (connectorRadius) => set({ connectorRadius }),
  setCutting: (cutting) => set({ cutting }),
  setCutResult: (parts, partMeshes, connectorCount) =>
    set({
      parts,
      partMeshes,
      connectorCount,
      cutting: false,
      explode: 0,
      viewMode: "assembled",
      pack: null,
    }),
  setExplode: (explode) => set({ explode }),
  setViewMode: (viewMode) => set({ viewMode }),
  setPack: (pack) => set({ pack }),
  clearCut: () =>
    set({ parts: null, partMeshes: null, explode: 0, viewMode: "assembled", pack: null }),

  selectedPrinter: () =>
    get().printers.find((p) => p.id === get().selectedPrinterId) ?? null,
  bedDims: () => {
    const s = get();
    if (s.selectedPrinterId === CUSTOM_PRINTER_ID) return s.customBed;
    const p = s.printers.find((pr) => pr.id === s.selectedPrinterId);
    return p ? { x: p.x, y: p.y, z: p.z } : s.customBed;
  },
}));
