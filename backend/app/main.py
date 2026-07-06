"""SplitForge backend API.

M0: upload an STL, store it in a session, return mesh stats + geometry for the
frontend to render. Later milestones add /cut, /partition, /pack, /export.
"""

from __future__ import annotations

import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .geometry.connectors import ConnectorParams, add_connectors
from .geometry.mesh import Mesh
from .geometry.pack import pack_parts
from .geometry.partition import auto_partition
from .geometry.slice import cut_mesh_multi
from .models.schemas import (
    AssistantPlane,
    AssistantRequest,
    AssistantResponse,
    CutRequest,
    CutResponse,
    MeshStats,
    PackRequest,
    PackResponse,
    PartInfo,
    PartitionRequest,
    PartitionResponse,
    PlacementInfo,
    ProposedPlane,
    ScaleRequest,
    ScaleResponse,
)
from .printers import PRINTERS, get_printer
from .session import create_session, get_session

app = FastAPI(title="SplitForge API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/printers")
def list_printers() -> dict:
    return {"printers": [p.as_dict() for p in PRINTERS.values()]}


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    name = (file.filename or "").lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else "stl"
    if ext not in ("stl", "obj", "ply", "glb", "off"):
        raise HTTPException(400, f"Unsupported file type: .{ext}")

    data = await file.read()
    try:
        mesh = Mesh.from_bytes(data, file_type=ext)
    except Exception as exc:  # noqa: BLE001 - surface parse errors to the client
        raise HTTPException(400, f"Failed to parse mesh: {exc}") from exc

    if mesh.is_empty:
        raise HTTPException(400, "Mesh has no faces")

    mesh = mesh.recentered_on_bed()
    session = create_session(mesh)
    return {
        "sessionId": session.id,
        "filename": file.filename,
        "stats": _stats(mesh).model_dump(),
        "mesh": mesh.to_dict(),
    }


def _stats(mesh: Mesh) -> MeshStats:
    size = mesh.size
    return MeshStats(
        vertexCount=int(len(mesh.vertices)),
        triangleCount=int(len(mesh.faces)),
        sizeMm=[float(size[0]), float(size[1]), float(size[2])],
        watertight=mesh.is_watertight(),
    )


@app.post("/api/scale", response_model=ScaleResponse)
def scale(req: ScaleRequest) -> ScaleResponse:
    session = get_session(req.sessionId)
    if session is None:
        raise HTTPException(404, "Session not found")
    session.apply_scale(req.factor)
    return ScaleResponse(
        scale=session.scale,
        stats=_stats(session.source),
        mesh=session.source.to_dict(),
    )


@app.post("/api/partition", response_model=PartitionResponse)
def partition(req: PartitionRequest) -> PartitionResponse:
    session = get_session(req.sessionId)
    if session is None:
        raise HTTPException(404, "Session not found")
    proposed = auto_partition(session.source, req.bed.as_tuple())
    return PartitionResponse(
        planes=[ProposedPlane(axis=p["axis"], offset=p["offset"]) for p in proposed]
    )


@app.get("/api/session/{sid}/mesh")
def session_mesh(sid: str) -> dict:
    session = get_session(sid)
    if session is None:
        raise HTTPException(404, "Session not found")
    return {"mesh": session.source.to_dict()}


@app.post("/api/cut", response_model=CutResponse)
def cut(req: CutRequest, printer: str = "ender3") -> CutResponse:
    session = get_session(req.sessionId)
    if session is None:
        raise HTTPException(404, "Session not found")
    if not req.planes:
        raise HTTPException(400, "No cut planes provided")

    planes = [
        (np.array(p.point, dtype=float), np.array(p.normal, dtype=float))
        for p in req.planes
    ]
    parts = cut_mesh_multi(session.source, planes)

    connector_count = 0
    if req.connectors and len(parts) > 1:
        parts, connector_count = add_connectors(
            parts, ConnectorParams(radius=req.connectorRadius)
        )
    session.parts = parts

    # Prefer explicit bed dimensions (supports custom printers); fall back to preset.
    if req.bed is not None:
        bed = req.bed.as_tuple()
    else:
        prof = get_printer(printer)
        bed = (prof.x, prof.y, prof.z)
    infos: list[PartInfo] = []
    meshes: list[dict] = []
    for i, part in enumerate(parts):
        size = part.size
        fits = size[0] <= bed[0] and size[1] <= bed[1] and size[2] <= bed[2]
        infos.append(
            PartInfo(
                index=i,
                triangleCount=int(len(part.faces)),
                sizeMm=[float(size[0]), float(size[1]), float(size[2])],
                volumeMm3=float(part.volume()),
                watertight=part.is_watertight(),
                fits=bool(fits),
            )
        )
        meshes.append(part.to_dict())

    return CutResponse(
        partCount=len(parts), parts=infos, meshes=meshes, connectorCount=connector_count
    )


@app.post("/api/pack", response_model=PackResponse)
def pack(req: PackRequest) -> PackResponse:
    session = get_session(req.sessionId)
    if session is None:
        raise HTTPException(404, "Session not found")
    if not session.parts:
        raise HTTPException(400, "No parts to pack — cut the model first")
    count, placements, unplaceable = pack_parts(session.parts, req.bed.as_tuple())
    return PackResponse(
        plateCount=count,
        placements=[PlacementInfo(**p.__dict__) for p in placements],
        unplaceable=unplaceable,
    )


@app.post("/api/assistant", response_model=AssistantResponse)
def assistant(req: AssistantRequest) -> AssistantResponse:
    session = get_session(req.sessionId)
    if session is None:
        raise HTTPException(404, "Session not found")
    try:
        from .assistant import run_assistant
    except ImportError as exc:  # anthropic SDK not installed
        raise HTTPException(503, f"AI assistant unavailable: {exc}") from exc

    try:
        result = run_assistant(session, req.message, req.bed.as_tuple())
    except Exception as exc:  # noqa: BLE001 - surface auth/API errors to the client
        # Most commonly a missing/invalid ANTHROPIC_API_KEY.
        raise HTTPException(
            503, f"AI assistant error (is ANTHROPIC_API_KEY set?): {exc}"
        ) from exc

    return AssistantResponse(
        reply=result["reply"],
        scale=result["scale"],
        planes=[AssistantPlane(**p) for p in result["planes"]],
    )


@app.get("/api/session/{sid}/part/{index}.stl")
def part_stl(sid: str, index: int) -> Response:
    session = get_session(sid)
    if session is None:
        raise HTTPException(404, "Session not found")
    if index < 0 or index >= len(session.parts):
        raise HTTPException(404, "Part not found")
    data = session.parts[index].to_stl_bytes()
    return Response(
        content=data,
        media_type="model/stl",
        headers={"Content-Disposition": f'attachment; filename="part_{index + 1}.stl"'},
    )
