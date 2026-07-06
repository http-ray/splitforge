"""Auto-partition: propose axis-aligned cut planes so every part fits the bed.

For each axis whose model extent exceeds the build volume, we split that axis
into the fewest equal slabs that fit (ceil(extent / bed)) and place evenly
spaced cut planes between them. The result is a starting cut plan the user can
then edit. Evenly spaced slabs minimize the number of pieces along each axis.
"""

from __future__ import annotations

import math

import numpy as np

from .mesh import Mesh

AXES = ("x", "y", "z")


def auto_partition(mesh: Mesh, bed: tuple[float, float, float]) -> list[dict]:
    """Return proposed cut planes as [{"axis": "x", "offset": <mm>}, ...]."""
    if mesh.is_empty:
        return []
    bounds = mesh.bounds
    size = mesh.size
    planes: list[dict] = []
    for i, axis in enumerate(AXES):
        extent = float(size[i])
        bed_len = float(bed[i])
        if bed_len <= 0 or extent <= bed_len:
            continue
        pieces = math.ceil(extent / bed_len)
        lo, hi = float(bounds[0][i]), float(bounds[1][i])
        for k in range(1, pieces):
            offset = lo + (hi - lo) * k / pieces
            planes.append({"axis": axis, "offset": offset})
    return planes


def plane_to_point_normal(axis: str, offset: float) -> tuple[np.ndarray, np.ndarray]:
    i = AXES.index(axis)
    point = np.zeros(3)
    point[i] = offset
    normal = np.zeros(3)
    normal[i] = 1.0
    return point, normal
