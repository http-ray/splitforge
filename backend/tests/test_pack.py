"""Bin-packing places every part and reports a sane plate count."""

import numpy as np
import trimesh

from app.geometry.mesh import Mesh
from app.geometry.pack import pack_parts


def _box(x, y, z) -> Mesh:
    m = trimesh.creation.box(extents=[x, y, z])
    return Mesh(np.asarray(m.vertices), np.asarray(m.faces))


def test_all_parts_placed_on_one_plate():
    parts = [_box(50, 50, 40) for _ in range(4)]  # 4 small parts fit one 200 bed
    count, placements, unplaceable = pack_parts(parts, (200, 200, 200))
    assert unplaceable == []
    assert len(placements) == 4
    assert count == 1


def test_spills_to_multiple_plates():
    parts = [_box(120, 120, 40) for _ in range(4)]  # only 1 per 200 plate
    count, placements, unplaceable = pack_parts(parts, (200, 200, 200))
    assert unplaceable == []
    assert count == 4


def test_placements_stay_within_plate():
    parts = [_box(60, 40, 30) for _ in range(6)]
    bed = (200, 200, 200)
    _, placements, _ = pack_parts(parts, bed)
    for p in placements:
        assert p.x >= 0 and p.y >= 0
        assert p.x + p.w <= bed[0]
        assert p.y + p.h <= bed[1]
