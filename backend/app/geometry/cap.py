"""Cross-section capping.

When a plane cuts a solid, each resulting part is left with an open hole where
the plane passed through. To keep the parts watertight (and therefore printable
as solids), we must *cap* that hole: collect the intersection segments the slice
produced, stitch them into closed loops, triangulate each loop in 2D, and lift
the triangles back into 3D.

This module owns the 2D work (loop assembly + ear-clipping triangulation). All
of it is hand-written numpy — no boolean/CSG library is used.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np


def plane_basis(normal: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return orthonormal (u, w) spanning the plane so that u x w == normal.

    A CCW polygon in (u, w) coordinates therefore has an outward normal of
    +normal, which we rely on for consistent cap winding.
    """
    n = normal / np.linalg.norm(normal)
    # Pick a helper axis least aligned with n to avoid degeneracy.
    helper = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(helper, n)
    u /= np.linalg.norm(u)
    w = np.cross(n, u)  # already unit; u x w == n
    return u, w


def _weld(
    segments: list[tuple[np.ndarray, np.ndarray]], tol: float
) -> tuple[list[np.ndarray], list[tuple[int, int]]]:
    """Merge coincident segment endpoints into unique nodes within `tol`.

    Distance-based (not hash-bucketed) so points that would straddle a grid-cell
    boundary still weld. Cut boundaries are small, so O(n^2) is fine here; a
    spatial grid can replace this if very fine meshes become a bottleneck.
    """
    reps: list[np.ndarray] = []

    def node_of(pt: np.ndarray) -> int:
        for j, r in enumerate(reps):
            if np.linalg.norm(pt - r) <= tol:
                return j
        reps.append(pt)
        return len(reps) - 1

    edges: list[tuple[int, int]] = []
    for a, b in segments:
        ia, ib = node_of(a), node_of(b)
        if ia != ib:
            edges.append((ia, ib))
    return reps, edges


def assemble_loops(
    segments: list[tuple[np.ndarray, np.ndarray]], tol: float = 1e-6
) -> list[list[np.ndarray]]:
    """Stitch undirected 3D segments into closed loops of points.

    Endpoints are welded within `tol` first (relative to geometry scale), then
    we walk the resulting degree-2 graph. Robust for one or more disjoint simple
    loops (e.g. cutting a torus yields two).
    """
    if not segments:
        return []
    scale = max(
        float(np.linalg.norm(np.max([s for pair in segments for s in pair], axis=0))),
        1.0,
    )
    reps, edges = _weld(segments, tol * scale)

    adj: dict[int, list[int]] = defaultdict(list)
    for ia, ib in edges:
        adj[ia].append(ib)
        adj[ib].append(ia)

    loops: list[list[np.ndarray]] = []
    for start in list(adj.keys()):
        while adj[start]:
            loop_nodes = [start]
            prev, cur = None, start
            closed = False
            while True:
                nbrs = adj[cur]
                if not nbrs:
                    break
                nxt = next((c for c in nbrs if c != prev), nbrs[0])
                adj[cur].remove(nxt)
                adj[nxt].remove(cur)
                if nxt == start:
                    closed = True
                    break
                loop_nodes.append(nxt)
                prev, cur = cur, nxt
            if closed and len(loop_nodes) >= 3:
                loops.append([reps[i] for i in loop_nodes])
    return loops


def _signed_area(poly: np.ndarray) -> float:
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def _point_in_triangle(p, a, b, c) -> bool:
    v0, v1, v2 = c - a, b - a, p - a
    d00 = np.dot(v0, v0)
    d01 = np.dot(v0, v1)
    d02 = np.dot(v0, v2)
    d11 = np.dot(v1, v1)
    d12 = np.dot(v1, v2)
    denom = d00 * d11 - d01 * d01
    if abs(denom) < 1e-12:
        return False
    u = (d11 * d02 - d01 * d12) / denom
    v = (d00 * d12 - d01 * d02) / denom
    return u >= -1e-9 and v >= -1e-9 and (u + v) <= 1 + 1e-9


def ear_clip(poly2d: np.ndarray) -> list[tuple[int, int, int]]:
    """Triangulate a simple 2D polygon (CCW or CW) by ear clipping.

    Returns index triples into `poly2d`, wound CCW (positive area).
    """
    n = len(poly2d)
    if n < 3:
        return []
    idx = list(range(n))
    if _signed_area(poly2d) < 0:  # ensure CCW so interior is to the left
        idx.reverse()

    tris: list[tuple[int, int, int]] = []
    guard = 0
    while len(idx) > 3 and guard < 10 * n:
        guard += 1
        made_ear = False
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = poly2d[i0], poly2d[i1], poly2d[i2]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross <= 1e-12:  # reflex or collinear -> not an ear
                continue
            if any(
                _point_in_triangle(poly2d[m], a, b, c)
                for m in idx
                if m not in (i0, i1, i2)
            ):
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            made_ear = True
            break
        if not made_ear:  # fallback: fan (handles rare numerical stalls)
            for m in range(1, len(idx) - 1):
                tris.append((idx[0], idx[m], idx[m + 1]))
            return tris
    if len(idx) == 3:
        tris.append((idx[0], idx[1], idx[2]))
    return tris


def build_cap(
    segments: list[tuple[np.ndarray, np.ndarray]],
    plane_point: np.ndarray,
    plane_normal: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Triangulate the cut cross-section.

    Returns (vertices (K,3), faces (T,3)) wound so each face's normal is
    +plane_normal. The caller reverses the winding for the part that needs the
    opposite-facing cap.
    """
    loops = assemble_loops(segments)
    if not loops:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)

    u, w = plane_basis(plane_normal)
    all_v: list[np.ndarray] = []
    all_f: list[tuple[int, int, int]] = []
    for loop in loops:
        pts3d = np.array(loop)
        rel = pts3d - plane_point
        poly2d = np.column_stack([rel @ u, rel @ w])
        tris = ear_clip(poly2d)
        base = len(all_v)
        all_v.extend(pts3d)
        # ear_clip returns CCW (normal +plane_normal); keep as-is.
        for t in tris:
            all_f.append((base + t[0], base + t[1], base + t[2]))

    return np.array(all_v), np.array(all_f, dtype=np.int64)
