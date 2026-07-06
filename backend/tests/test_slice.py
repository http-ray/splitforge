"""Geometry-core invariants: cuts must produce watertight parts and conserve volume."""

import numpy as np
import trimesh

from app.geometry.mesh import Mesh
from app.geometry.slice import cut_mesh, cut_mesh_multi


def _mesh_from_trimesh(tm: trimesh.Trimesh) -> Mesh:
    return Mesh(np.asarray(tm.vertices), np.asarray(tm.faces))


def test_cut_cube_axis_aligned():
    box = _mesh_from_trimesh(trimesh.creation.box(extents=[10, 10, 10]))
    pos, neg = cut_mesh(box, np.array([0, 0, 0.0]), np.array([0, 0, 1.0]))

    assert not pos.is_empty and not neg.is_empty
    assert pos.is_watertight(), "positive part must be watertight"
    assert neg.is_watertight(), "negative part must be watertight"
    # Each half of a 10^3 cube = 500.
    assert pos.volume() == np.isclose(pos.volume(), 500.0, atol=1e-3) or np.isclose(
        pos.volume(), 500.0, atol=1e-3
    )
    assert np.isclose(pos.volume(), 500.0, atol=1e-3)
    assert np.isclose(neg.volume(), 500.0, atol=1e-3)
    assert np.isclose(pos.volume() + neg.volume(), box.volume(), atol=1e-3)


def test_cut_cube_diagonal_plane():
    box = _mesh_from_trimesh(trimesh.creation.box(extents=[10, 10, 10]))
    n = np.array([1.0, 1.0, 0.3])
    pos, neg = cut_mesh(box, np.array([0.5, -0.5, 0.0]), n)
    assert pos.is_watertight()
    assert neg.is_watertight()
    assert np.isclose(pos.volume() + neg.volume(), box.volume(), atol=1e-2)


def test_cut_sphere_through_center():
    sphere = _mesh_from_trimesh(trimesh.creation.icosphere(subdivisions=3, radius=5))
    pos, neg = cut_mesh(sphere, np.array([0, 0, 0.0]), np.array([0, 0, 1.0]))
    assert pos.is_watertight()
    assert neg.is_watertight()
    assert np.isclose(pos.volume() + neg.volume(), sphere.volume(), atol=1e-1)
    # Roughly equal hemispheres.
    assert np.isclose(pos.volume(), neg.volume(), rtol=0.02)


def test_plane_misses_mesh():
    box = _mesh_from_trimesh(trimesh.creation.box(extents=[10, 10, 10]))
    pos, neg = cut_mesh(box, np.array([0, 0, 100.0]), np.array([0, 0, 1.0]))
    # Entire box is on the negative side; positive side empty.
    assert pos.is_empty
    assert not neg.is_empty
    assert np.isclose(neg.volume(), box.volume(), atol=1e-6)


def test_multi_plane_grid():
    box = _mesh_from_trimesh(trimesh.creation.box(extents=[30, 10, 10]))
    planes = [
        (np.array([-5.0, 0, 0]), np.array([1.0, 0, 0])),
        (np.array([5.0, 0, 0]), np.array([1.0, 0, 0])),
    ]
    parts = cut_mesh_multi(box, planes)
    assert len(parts) == 3
    assert all(pt.is_watertight() for pt in parts)
    assert np.isclose(sum(pt.volume() for pt in parts), box.volume(), atol=1e-2)


def test_cut_torus_two_loops():
    torus = _mesh_from_trimesh(trimesh.creation.torus(major_radius=10, minor_radius=3))
    # Vertical plane through the hole yields a two-loop cross-section.
    pos, neg = cut_mesh(torus, np.array([0, 0, 0.0]), np.array([0, 1.0, 0.0]))
    assert pos.is_watertight()
    assert neg.is_watertight()
    assert np.isclose(pos.volume() + neg.volume(), torus.volume(), atol=1e-1)
