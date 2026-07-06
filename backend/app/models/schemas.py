"""Request/response schemas for the cut API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Plane(BaseModel):
    point: list[float] = Field(..., min_length=3, max_length=3)
    normal: list[float] = Field(..., min_length=3, max_length=3)


class Bed(BaseModel):
    x: float = Field(..., gt=0)
    y: float = Field(..., gt=0)
    z: float = Field(..., gt=0)

    def as_tuple(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)


class ScaleRequest(BaseModel):
    sessionId: str
    factor: float = Field(..., gt=0)


class MeshStats(BaseModel):
    vertexCount: int
    triangleCount: int
    sizeMm: list[float]
    watertight: bool


class ScaleResponse(BaseModel):
    scale: float
    stats: MeshStats
    mesh: dict


class PartitionRequest(BaseModel):
    sessionId: str
    bed: Bed


class ProposedPlane(BaseModel):
    axis: str
    offset: float


class PartitionResponse(BaseModel):
    planes: list[ProposedPlane]


class CutRequest(BaseModel):
    sessionId: str
    planes: list[Plane]
    bed: Bed | None = None
    connectors: bool = False
    connectorRadius: float = Field(default=3.0, gt=0)


class PartInfo(BaseModel):
    index: int
    triangleCount: int
    sizeMm: list[float]
    volumeMm3: float
    watertight: bool
    fits: bool


class CutResponse(BaseModel):
    partCount: int
    parts: list[PartInfo]
    meshes: list[dict]  # {vertices, faces} per part, for rendering
    connectorCount: int = 0


class PackRequest(BaseModel):
    sessionId: str
    bed: Bed


class PlacementInfo(BaseModel):
    index: int
    plate: int
    x: float
    y: float
    w: float
    h: float
    rotated: bool


class PackResponse(BaseModel):
    plateCount: int
    placements: list[PlacementInfo]
    unplaceable: list[int]


class AssistantRequest(BaseModel):
    sessionId: str
    message: str
    bed: Bed


class AssistantPlane(BaseModel):
    axis: str
    offset: float


class AssistantResponse(BaseModel):
    reply: str
    scale: float
    planes: list[AssistantPlane]
