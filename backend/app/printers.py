"""Printer build-volume presets (dimensions in millimetres, X x Y x Z)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Printer:
    id: str
    name: str
    x: float
    y: float
    z: float

    def as_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "x": self.x, "y": self.y, "z": self.z}


PRINTERS: dict[str, Printer] = {
    p.id: p
    for p in [
        Printer("ender3", "Creality Ender 3", 220, 220, 250),
        Printer("prusa_mk4", "Prusa MK4", 250, 210, 220),
        Printer("bambu_a1", "Bambu Lab A1", 256, 256, 256),
        Printer("bambu_x1", "Bambu Lab X1 Carbon", 256, 256, 256),
        Printer("prusa_mini", "Prusa Mini", 180, 180, 180),
        Printer("cr10", "Creality CR-10", 300, 300, 400),
    ]
}

DEFAULT_PRINTER = "ender3"


def get_printer(printer_id: str) -> Printer:
    return PRINTERS.get(printer_id, PRINTERS[DEFAULT_PRINTER])
