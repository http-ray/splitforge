"""Core mesh representation.

A `Mesh` is a plain indexed triangle mesh: an (N, 3) float array of vertices and
an (M, 3) int array of triangle indices. We keep our own lightweight type so the
slicing/capping code operates on raw numpy arrays (the CS core is ours). `trimesh`
is used *only* for file I/O and watertight validation, never for the cut itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

import numpy as np
import trimesh


@dataclass
class Mesh:
    vertices: np.ndarray  # (N, 3) float64
    faces: np.ndarray     # (M, 3) int64

    def __post_init__(self) -> None:
        self.vertices = np.asarray(self.vertices, dtype=np.float64).reshape(-1, 3)
        self.faces = np.asarray(self.faces, dtype=np.int64).reshape(-1, 3)

    # --- construction / IO -------------------------------------------------
    @classmethod
    def from_bytes(cls, data: bytes, file_type: str = "stl") -> "Mesh":
        loaded = trimesh.load(BytesIO(data), file_type=file_type, process=False)
        if isinstance(loaded, trimesh.Scene):
            loaded = loaded.to_geometry()
        return cls(np.asarray(loaded.vertices), np.asarray(loaded.faces))

    def to_trimesh(self) -> trimesh.Trimesh:
        return trimesh.Trimesh(
            vertices=self.vertices.copy(), faces=self.faces.copy(), process=False
        )

    def to_stl_bytes(self) -> bytes:
        return self.to_trimesh().export(file_type="stl")

    # --- properties --------------------------------------------------------
    @property
    def bounds(self) -> np.ndarray:
        """(2, 3) array: [min_xyz, max_xyz]. Empty mesh -> zeros."""
        if len(self.vertices) == 0:
            return np.zeros((2, 3))
        return np.array([self.vertices.min(axis=0), self.vertices.max(axis=0)])

    @property
    def size(self) -> np.ndarray:
        b = self.bounds
        return b[1] - b[0]

    @property
    def is_empty(self) -> bool:
        return len(self.faces) == 0

    def volume(self) -> float:
        """Signed volume via the divergence theorem (sum of tetra volumes)."""
        if self.is_empty:
            return 0.0
        v = self.vertices
        tris = v[self.faces]  # (M, 3, 3)
        a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
        return float(np.abs(np.sum(np.einsum("ij,ij->i", np.cross(a, b), c)) / 6.0))

    def is_watertight(self) -> bool:
        """Watertight test with vertex merging.

        STL and our own slice output store triangles with unshared vertices, so
        edges aren't detected as adjacent until coincident vertices are merged.
        We merge on a throwaway copy purely for the topology check.
        """
        if self.is_empty:
            return False
        tm = self.to_trimesh()
        tm.merge_vertices()
        return bool(tm.is_watertight)

    def translated(self, offset: np.ndarray) -> "Mesh":
        return Mesh(self.vertices + np.asarray(offset, dtype=np.float64), self.faces)

    def scaled(self, factor: float) -> "Mesh":
        """Uniform scale about the origin (keeps a bed-centered mesh on the bed)."""
        return Mesh(self.vertices * float(factor), self.faces)

    def recentered_on_bed(self) -> "Mesh":
        """Translate so the model is centered in X/Y with its base at Z=0.

        Gives frontend and backend a single shared coordinate space (the model
        sits on the print bed), so a cut plane placed in the viewer maps directly
        to model coordinates. Uniform translation preserves all relative
        geometry, so reassembly is unaffected.
        """
        if self.is_empty:
            return self
        b = self.bounds
        center = (b[0] + b[1]) / 2.0
        offset = np.array([-center[0], -center[1], -b[0][2]])
        return self.translated(offset)

    def to_dict(self) -> dict:
        return {
            "vertices": self.vertices.astype(np.float32).ravel().tolist(),
            "faces": self.faces.astype(np.int32).ravel().tolist(),
        }
