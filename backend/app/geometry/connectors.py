"""Reassembly connectors: alignment pins (peg + socket) at cut interfaces.

After cutting, adjacent parts meet on a flat interface. To help them reassemble
and stay aligned, we add a cylindrical **peg** protruding from one part and a
matching **socket** (slightly oversized cavity) in the mating part.

Unlike the slicer, this legitimately needs CSG (union to add the peg, difference
to carve the socket), so it uses trimesh's `manifold3d` boolean backend. The peg
is centered on the interface plane and extends into both parts; when the parts
are pulled apart in the exploded view you can see the peg and socket line up.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import trimesh

from .mesh import Mesh


@dataclass
class ConnectorParams:
    radius: float = 3.0
    length: float = 12.0      # total peg length (extends length/2 each side)
    clearance: float = 0.2    # socket radius margin for a friction fit
    max_pins_per_edge: int = 2


@dataclass
class Interface:
    lo: int          # part index on the negative side of the plane
    hi: int          # part index on the positive side
    axis: int        # 0/1/2
    offset: float    # plane position along axis
    rect: list[tuple[int, float, float]]  # overlap on the other two axes


def find_interfaces(parts: list[Mesh], tol: float = 1e-3) -> list[Interface]:
    """Find pairs of parts that meet on an axis-aligned interface."""
    interfaces: list[Interface] = []
    bounds = [p.bounds for p in parts]
    for a in range(3):
        for i in range(len(parts)):
            for j in range(len(parts)):
                if i == j:
                    continue
                # i on the negative side, j on the positive side: i.max == j.min.
                if abs(bounds[i][1][a] - bounds[j][0][a]) > tol:
                    continue
                others = [o for o in range(3) if o != a]
                rect: list[tuple[int, float, float]] = []
                ok = True
                for o in others:
                    omin = max(bounds[i][0][o], bounds[j][0][o])
                    omax = min(bounds[i][1][o], bounds[j][1][o])
                    if omax - omin <= 4 * tol:
                        ok = False
                        break
                    rect.append((o, omin, omax))
                if ok:
                    interfaces.append(
                        Interface(lo=i, hi=j, axis=a, offset=float(bounds[i][1][a]), rect=rect)
                    )
    return interfaces


def _pin_positions(iface: Interface, params: ConnectorParams) -> list[np.ndarray]:
    """Pin centers on the interface plane, spread along the longer overlap side."""
    (o1, min1, max1), (o2, min2, max2) = iface.rect
    c1, c2 = (min1 + max1) / 2, (min2 + max2) / 2
    span1, span2 = max1 - min1, max2 - min2
    # Spread pins along whichever overlap side is longer.
    spread_axis, spread_c, spread_span = (o1, c1, span1) if span1 >= span2 else (o2, c2, span2)
    fixed_axis, fixed_c = (o2, c2) if span1 >= span2 else (o1, c1)

    n = params.max_pins_per_edge if spread_span > 6 * params.radius else 1
    positions: list[np.ndarray] = []
    for k in range(n):
        frac = (k + 1) / (n + 1)
        pos = np.zeros(3)
        pos[iface.axis] = iface.offset
        pos[spread_axis] = min(max1 if spread_axis == o1 else max2, max(min1 if spread_axis == o1 else min2, spread_c + (frac - 0.5) * spread_span * 0.6))
        pos[fixed_axis] = fixed_c
        positions.append(pos)
    return positions


def _as_volume(tm: trimesh.Trimesh) -> trimesh.Trimesh:
    """Weld + fix winding/normals so trimesh recognizes the mesh as a solid volume.

    Our slicer emits watertight parts, but with per-triangle (unshared) vertices
    and locally-fanned caps, so winding isn't globally consistent until repaired.
    The boolean backend requires `is_volume`.
    """
    tm.merge_vertices()
    tm.fix_normals()
    return tm


def _make_pin(center: np.ndarray, axis: int, radius: float, length: float) -> trimesh.Trimesh:
    pin = trimesh.creation.cylinder(radius=radius, height=length, sections=24)
    # Default cylinder is along +Z; rotate its axis to the interface normal.
    if axis == 0:
        pin.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    elif axis == 1:
        pin.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    pin.apply_translation(center)
    return pin


def add_connectors(
    parts: list[Mesh], params: ConnectorParams | None = None
) -> tuple[list[Mesh], int]:
    """Return (parts_with_connectors, connector_count).

    Pegs are added to the positive-side part; sockets are carved from the
    negative-side part. Pins whose center isn't inside solid material on both
    sides are skipped, so pegs always anchor.
    """
    params = params or ConnectorParams()
    result = [_as_volume(p.to_trimesh()) for p in parts]
    count = 0

    for iface in find_interfaces(parts):
        for center in _pin_positions(iface, params):
            # Only add a pin if there's material just inside each part at this spot.
            inside = center.copy()
            inside[iface.axis] = iface.offset + params.length * 0.2
            outside = center.copy()
            outside[iface.axis] = iface.offset - params.length * 0.2
            if not result[iface.hi].contains([inside])[0]:
                continue
            if not result[iface.lo].contains([outside])[0]:
                continue

            peg = _make_pin(center, iface.axis, params.radius, params.length)
            socket = _make_pin(
                center, iface.axis, params.radius + params.clearance, params.length
            )
            hi = trimesh.boolean.union([result[iface.hi], peg])
            lo = trimesh.boolean.difference([result[iface.lo], socket])
            if hi.is_watertight and lo.is_watertight:
                result[iface.hi] = hi
                result[iface.lo] = lo
                count += 1

    meshes = [Mesh(np.asarray(t.vertices), np.asarray(t.faces)) for t in result]
    return meshes, count
