"""Auto-partition proposes enough axis-aligned planes to make every part fit."""

import numpy as np
import trimesh

from app.geometry.mesh import Mesh
from app.geometry.partition import auto_partition, plane_to_point_normal
from app.geometry.slice import cut_mesh_multi


def _box(x, y, z) -> Mesh:
    m = trimesh.creation.box(extents=[x, y, z])
    return Mesh(np.asarray(m.vertices), np.asarray(m.faces)).recentered_on_bed()


def test_no_cuts_when_fits():
    mesh = _box(100, 100, 100)
    assert auto_partition(mesh, (220, 220, 250)) == []


def test_partition_one_axis():
    # 500mm long on X, 200 bed -> ceil(500/200)=3 pieces -> 2 planes.
    mesh = _box(500, 100, 100)
    planes = auto_partition(mesh, (200, 200, 200))
    assert len(planes) == 2
    assert all(p["axis"] == "x" for p in planes)


def test_partitioned_parts_all_fit():
    mesh = _box(500, 300, 120)
    bed = (200, 200, 200)
    proposed = auto_partition(mesh, bed)
    planes = [plane_to_point_normal(p["axis"], p["offset"]) for p in proposed]
    parts = cut_mesh_multi(mesh, planes)
    assert len(parts) >= 4
    for part in parts:
        s = part.size
        assert s[0] <= bed[0] + 1e-6
        assert s[1] <= bed[1] + 1e-6
        assert s[2] <= bed[2] + 1e-6
        assert part.is_watertight()
    assert np.isclose(sum(p.volume() for p in parts), mesh.volume(), atol=1e-1)
