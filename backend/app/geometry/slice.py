"""Plane <-> mesh slicing (the computational-geometry core).

`cut_mesh` splits a triangle mesh by a plane into a positive-side and a
negative-side part, each capped so it is watertight. The algorithm:

  1. Signed distance of every vertex to the plane; snap near-zero to exactly 0.
  2. Clip each triangle against the plane into a positive polygon and a negative
     polygon (Sutherland-Hodgman), fan-triangulating each. Record the segment
     each straddling triangle contributes to the cut cross-section.
  3. Cap both parts from the recorded segments (see `cap.py`), with opposite
     winding so each part's cut face points outward.

`cut_mesh_multi` applies a whole cut plan by slicing every current part with
each successive plane.
"""

from __future__ import annotations

import numpy as np

from . import cap as capmod
from .mesh import Mesh

Segment = tuple[np.ndarray, np.ndarray]


def _dedup_consecutive(poly: list[np.ndarray], tol: float = 1e-9) -> list[np.ndarray]:
    out: list[np.ndarray] = []
    for pt in poly:
        if not out or np.linalg.norm(pt - out[-1]) > tol:
            out.append(pt)
    if len(out) > 1 and np.linalg.norm(out[0] - out[-1]) <= tol:
        out.pop()
    return out


def _clip_triangle(
    V: np.ndarray, d: np.ndarray, keep_positive: bool
) -> list[np.ndarray]:
    """Clip one triangle to a half-space (Sutherland-Hodgman), return the polygon.

    Vertices with signed distance on the kept side stay; each edge that strictly
    crosses the plane contributes an interpolated intersection point.
    """
    poly: list[np.ndarray] = []
    for i in range(3):
        cp, cd = V[i], d[i]
        np_, nd = V[(i + 1) % 3], d[(i + 1) % 3]
        cur_in = cd >= 0 if keep_positive else cd <= 0
        if cur_in:
            poly.append(cp)
        # Insert an intersection only on a strict sign change.
        if (cd > 0 and nd < 0) or (cd < 0 and nd > 0):
            t = cd / (cd - nd)
            poly.append(cp + t * (np_ - cp))
    return poly


def _add_polygon(poly: list[np.ndarray], verts: list[np.ndarray], faces: list) -> None:
    poly = _dedup_consecutive(poly)
    if len(poly) < 3:
        return
    base = len(verts)
    verts.extend(poly)
    for i in range(1, len(poly) - 1):  # fan; preserves original winding
        faces.append((base, base + i, base + i + 1))


def cut_mesh(
    mesh: Mesh,
    plane_point: np.ndarray,
    plane_normal: np.ndarray,
    eps: float = 1e-6,
    cap: bool = True,
) -> tuple[Mesh, Mesh]:
    """Split `mesh` by a plane into (positive_side, negative_side) parts.

    Positive side is where dot(v - plane_point, plane_normal) >= 0.
    Either part may come back empty (Mesh with no faces) if the plane misses it.
    """
    p = np.asarray(plane_point, dtype=np.float64)
    n = np.asarray(plane_normal, dtype=np.float64)
    n = n / np.linalg.norm(n)

    verts = mesh.vertices
    d = (verts - p) @ n
    scale = max(float(np.abs(d).max()), 1.0)
    d = np.where(np.abs(d) < eps * scale, 0.0, d)

    pos_v: list[np.ndarray] = []
    pos_f: list = []
    neg_v: list[np.ndarray] = []
    neg_f: list = []

    for tri in mesh.faces:
        V = verts[tri]
        dd = d[tri]
        if np.all(dd >= 0):
            _add_polygon([V[0], V[1], V[2]], pos_v, pos_f)
            continue
        if np.all(dd <= 0):
            _add_polygon([V[0], V[1], V[2]], neg_v, neg_f)
            continue
        pos_poly = _clip_triangle(V, dd, keep_positive=True)
        neg_poly = _clip_triangle(V, dd, keep_positive=False)
        _add_polygon(pos_poly, pos_v, pos_f)
        _add_polygon(neg_poly, neg_v, neg_f)

    pos = _to_mesh(pos_v, pos_f)
    neg = _to_mesh(neg_v, neg_f)
    if cap:
        # Positive part's cut face points to -n (reverse cap winding); negative
        # part's points to +n. The cut outline is derived from each body's open
        # edges, which robustly handles vertices/edges lying on the plane.
        pos = _cap_body(pos, p, n, flip=True)
        neg = _cap_body(neg, p, n, flip=False)
    return pos, neg


def _cap_body(body: Mesh, p: np.ndarray, n: np.ndarray, flip: bool) -> Mesh:
    """Close the hole left on the cut plane by triangulating the open boundary.

    The boundary is the set of edges used by exactly one triangle *and* lying on
    the cut plane (so pre-existing holes elsewhere in a non-watertight input are
    left untouched). We reuse loop assembly + ear clipping from `cap.py`.
    """
    if body.is_empty:
        return body
    from trimesh.grouping import group_rows

    tm = body.to_trimesh()
    tm.merge_vertices()
    groups = group_rows(tm.edges_sorted, require_count=1)
    if len(groups) == 0:
        return body

    pts = np.asarray(tm.vertices)
    scale = max(float(np.abs((pts - p) @ n).max()), 1.0)
    on_plane_tol = 1e-5 * scale
    segments: list[Segment] = []
    for a, b in tm.edges_sorted[groups]:
        pa, pb = pts[a], pts[b]
        if abs((pa - p) @ n) < on_plane_tol and abs((pb - p) @ n) < on_plane_tol:
            segments.append((pa, pb))
    if not segments:
        return body

    cap_v, cap_f = capmod.build_cap(segments, p, n)
    if len(cap_f) == 0:
        return body

    verts: list[np.ndarray] = list(tm.vertices)
    faces: list = [tuple(int(i) for i in f) for f in tm.faces]
    _append_faces(verts, faces, cap_v, cap_f, flip=flip)
    return Mesh(np.array(verts), np.array(faces, dtype=np.int64))


def _append_faces(
    verts: list[np.ndarray], faces: list, cap_v: np.ndarray, cap_f: np.ndarray, flip: bool
) -> None:
    base = len(verts)
    verts.extend(cap_v)
    for f in cap_f:
        tri = (base + f[0], base + f[2], base + f[1]) if flip else (
            base + f[0],
            base + f[1],
            base + f[2],
        )
        faces.append(tri)


def _to_mesh(verts: list[np.ndarray], faces: list) -> Mesh:
    if not faces:
        return Mesh(np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64))
    return Mesh(np.array(verts), np.array(faces, dtype=np.int64))


def cut_mesh_multi(
    mesh: Mesh, planes: list[tuple[np.ndarray, np.ndarray]], eps: float = 1e-6
) -> list[Mesh]:
    """Apply a cut plan: slice every current part by each successive plane."""
    parts = [mesh]
    for point, normal in planes:
        nxt: list[Mesh] = []
        for part in parts:
            pos, neg = cut_mesh(part, point, normal, eps=eps)
            if not pos.is_empty:
                nxt.append(pos)
            if not neg.is_empty:
                nxt.append(neg)
        parts = nxt if nxt else parts
    return parts
