"""2D bin-packing of part footprints onto print plates.

Each part occupies its axis-aligned XY footprint (width, depth). We place parts
onto plates of size bed.x x bed.y using a shelf / first-fit-decreasing heuristic
with 90-degree rotation allowed, spilling to additional plates when a plate is
full. Good enough to answer "how many plates does this take, and roughly how do
they lay out?".
"""

from __future__ import annotations

from dataclasses import dataclass

from .mesh import Mesh

MARGIN = 5.0  # mm gap between parts and from plate edges


@dataclass
class Placement:
    index: int
    plate: int
    x: float  # min-corner on the plate (plate-local mm)
    y: float
    w: float  # footprint as placed (accounts for rotation)
    h: float
    rotated: bool


def pack_parts(
    parts: list[Mesh], bed: tuple[float, float, float]
) -> tuple[int, list[Placement], list[int]]:
    """Return (plate_count, placements, unplaceable_indices)."""
    bx, by = bed[0], bed[1]
    # Footprint (w, h) per part, index kept.
    items = []
    for i, part in enumerate(parts):
        s = part.size
        items.append((i, float(s[0]), float(s[1])))
    # First-fit decreasing: tallest first packs tighter shelves.
    items.sort(key=lambda t: max(t[1], t[2]), reverse=True)

    placements: list[Placement] = []
    unplaceable: list[int] = []

    plate = 0
    cursor_x = 0.0
    cursor_y = 0.0
    shelf_h = 0.0
    eps = 1e-6

    def orient(w: float, h: float) -> tuple[float, float, bool]:
        """Fit within plate, rotating 90deg if that's the only way / it's slimmer."""
        fits_unrot = w <= bx + eps and h <= by + eps
        fits_rot = h <= bx + eps and w <= by + eps
        if fits_unrot and fits_rot:
            # Prefer the orientation whose width is smaller (packs shelves better).
            return (h, w, True) if h < w else (w, h, False)
        if fits_unrot:
            return w, h, False
        if fits_rot:
            return h, w, True
        return w, h, False  # doesn't fit either way

    for idx, w0, h0 in items:
        w, h, rotated = orient(w0, h0)
        if w > bx + eps or h > by + eps:
            unplaceable.append(idx)
            continue
        # New shelf if this part overflows the current row width.
        if cursor_x + w > bx + eps:
            cursor_x = 0.0
            cursor_y += shelf_h + MARGIN
            shelf_h = 0.0
        # New plate if it overflows the plate depth.
        if cursor_y + h > by + eps:
            plate += 1
            cursor_x = 0.0
            cursor_y = 0.0
            shelf_h = 0.0
        placements.append(
            Placement(index=idx, plate=plate, x=cursor_x, y=cursor_y, w=w, h=h, rotated=rotated)
        )
        cursor_x += w + MARGIN
        shelf_h = max(shelf_h, h)

    plate_count = (plate + 1) if placements else 0
    placements.sort(key=lambda p: p.index)
    return plate_count, placements, unplaceable
