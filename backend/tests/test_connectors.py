"""Connectors add mating peg/socket pairs and keep parts watertight."""

import numpy as np
import trimesh

from app.geometry.mesh import Mesh
from app.geometry.connectors import add_connectors, find_interfaces, ConnectorParams
from app.geometry.slice import cut_mesh


def _box(x, y, z) -> Mesh:
    m = trimesh.creation.box(extents=[x, y, z])
    return Mesh(np.asarray(m.vertices), np.asarray(m.faces)).recentered_on_bed()


def test_finds_single_interface():
    box = _box(100, 60, 40)
    pos, neg = cut_mesh(box, np.array([0, 0, 20.0]), np.array([0, 0, 1.0]))
    interfaces = find_interfaces([pos, neg])
    assert len(interfaces) == 1
    assert interfaces[0].axis == 2


def test_connectors_watertight_and_conserve_ish_volume():
    box = _box(100, 60, 40)
    pos, neg = cut_mesh(box, np.array([0, 0, 20.0]), np.array([0, 0, 1.0]))
    parts, count = add_connectors([pos, neg], ConnectorParams(radius=3, length=12))
    assert count >= 1
    for p in parts:
        assert p.is_watertight()
    # Peg adds a little to one part; socket removes a little from the other.
    # Total volume stays close to the original solid.
    total = sum(p.volume() for p in parts)
    assert np.isclose(total, box.volume(), rtol=0.05)


def test_no_interface_no_connectors():
    # Two separate boxes far apart -> no shared interface.
    a = _box(20, 20, 20)
    b = Mesh(a.vertices + np.array([500.0, 0, 0]), a.faces)
    parts, count = add_connectors([a, b])
    assert count == 0
