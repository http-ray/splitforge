"""In-memory session store.

Holds the uploaded mesh (and later, cut results) keyed by a session id so the
frontend only re-sends lightweight parameters, not the whole mesh, on each
operation. Simple dict for the MVP; swap for Redis/temp-files if meshes get
large or the app is multi-process.

`base` is the original (bed-centered, unscaled) mesh; `source` is the current
working mesh (base * scale). Keeping `base` makes scaling lossless and
non-cumulative.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .geometry.mesh import Mesh


@dataclass
class Session:
    id: str
    base: Mesh
    source: Mesh
    scale: float = 1.0
    parts: list[Mesh] = field(default_factory=list)

    def apply_scale(self, factor: float) -> None:
        self.scale = float(factor)
        self.source = self.base.scaled(factor)
        self.parts = []


_SESSIONS: dict[str, Session] = {}


def create_session(base: Mesh) -> Session:
    sid = uuid.uuid4().hex
    session = Session(id=sid, base=base, source=base)
    _SESSIONS[sid] = session
    return session


def get_session(sid: str) -> Session | None:
    return _SESSIONS.get(sid)
