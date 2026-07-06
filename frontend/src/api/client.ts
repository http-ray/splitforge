export interface MeshData {
  vertices: number[]; // flat [x,y,z, x,y,z, ...]
  faces: number[]; // flat [a,b,c, a,b,c, ...]
}

export interface MeshStats {
  vertexCount: number;
  triangleCount: number;
  sizeMm: [number, number, number];
  watertight: boolean;
}

export interface UploadResponse {
  sessionId: string;
  filename: string;
  stats: MeshStats;
  mesh: MeshData;
}

export interface Printer {
  id: string;
  name: string;
  x: number;
  y: number;
  z: number;
}

export async function uploadMesh(file: File): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/upload", { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? "Upload failed");
  }
  return res.json();
}

export async function fetchPrinters(): Promise<Printer[]> {
  const res = await fetch("/api/printers");
  if (!res.ok) throw new Error("Failed to load printers");
  const data = await res.json();
  return data.printers;
}

export interface PartInfo {
  index: number;
  triangleCount: number;
  sizeMm: [number, number, number];
  volumeMm3: number;
  watertight: boolean;
  fits: boolean;
}

export interface Plane {
  point: [number, number, number];
  normal: [number, number, number];
}

export interface CutResponse {
  partCount: number;
  parts: PartInfo[];
  meshes: MeshData[];
  connectorCount: number;
}

export interface Bed {
  x: number;
  y: number;
  z: number;
}

export interface CutOptions {
  connectors?: boolean;
  connectorRadius?: number;
}

export async function cutMesh(
  sessionId: string,
  planes: Plane[],
  bed: Bed,
  opts: CutOptions = {}
): Promise<CutResponse> {
  const res = await fetch(`/api/cut`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessionId, planes, bed, ...opts }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? "Cut failed");
  }
  return res.json();
}

export interface ScaleResponse {
  scale: number;
  stats: MeshStats;
  mesh: MeshData;
}

export async function scaleMesh(
  sessionId: string,
  factor: number
): Promise<ScaleResponse> {
  const res = await fetch(`/api/scale`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessionId, factor }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? "Scale failed");
  }
  return res.json();
}

export interface ProposedPlane {
  axis: "x" | "y" | "z";
  offset: number;
}

export async function autoPartition(
  sessionId: string,
  bed: Bed
): Promise<ProposedPlane[]> {
  const res = await fetch(`/api/partition`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessionId, bed }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? "Auto-partition failed");
  }
  const data = await res.json();
  return data.planes;
}

export function partStlUrl(sessionId: string, index: number): string {
  return `/api/session/${sessionId}/part/${index}.stl`;
}

export interface Placement {
  index: number;
  plate: number;
  x: number;
  y: number;
  w: number;
  h: number;
  rotated: boolean;
}

export interface PackResponse {
  plateCount: number;
  placements: Placement[];
  unplaceable: number[];
}

export interface AssistantResponse {
  reply: string;
  scale: number;
  planes: { axis: "x" | "y" | "z"; offset: number }[];
}

export async function askAssistant(
  sessionId: string,
  message: string,
  bed: Bed
): Promise<AssistantResponse> {
  const res = await fetch(`/api/assistant`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessionId, message, bed }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? "Assistant failed");
  }
  return res.json();
}

export async function packParts(sessionId: string, bed: Bed): Promise<PackResponse> {
  const res = await fetch(`/api/pack`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sessionId, bed }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? "Pack failed");
  }
  return res.json();
}
