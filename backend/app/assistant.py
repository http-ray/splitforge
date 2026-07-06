"""AI cut assistant — natural language -> cut-plan actions.

Claude (via tool-use) turns a request like "make it twice as big and split it
into the fewest pieces that fit" into calls to the *existing* deterministic
geometry ops (scale, auto-partition, add/clear cuts). The LLM only orchestrates;
all geometry stays deterministic and testable. This is deliberately the last
feature: it's only valuable because the engine underneath it is solid.

Requires the `anthropic` SDK and credentials (ANTHROPIC_API_KEY or an `ant`
profile). Without them, the API layer returns a clear 503 rather than crashing.
"""

from __future__ import annotations

import numpy as np

from .geometry.partition import auto_partition
from .session import Session

MODEL = "claude-opus-4-8"
MAX_STEPS = 8

SYSTEM = """You are the cut assistant for SplitForge, a tool that splits oversized 3D-print
models into printable parts. The model sits on the print bed, centered in X/Y with its base at
Z=0. Cuts are axis-aligned planes described by an axis ("x", "y", or "z") and an offset in mm.

Help the user by calling the provided tools to scale the model and build a cut plan. Prefer the
fewest cuts that make every part fit the bed. When you're done, briefly explain what you did.
Do not invent measurements — call get_model_info to read the current size and bed."""

TOOLS = [
    {
        "name": "get_model_info",
        "description": "Get the model's current size (mm), the printer bed size, and whether it fits.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "set_scale",
        "description": "Scale the model uniformly by a factor (applied from the original mesh).",
        "input_schema": {
            "type": "object",
            "properties": {"factor": {"type": "number", "description": "e.g. 2.0 to double size"}},
            "required": ["factor"],
        },
    },
    {
        "name": "auto_partition",
        "description": "Replace the cut plan with the minimal axis-aligned cuts needed to fit the bed.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "add_cut",
        "description": "Add one axis-aligned cut plane to the plan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "axis": {"type": "string", "enum": ["x", "y", "z"]},
                "offset": {"type": "number", "description": "position along the axis in mm"},
            },
            "required": ["axis", "offset"],
        },
    },
    {
        "name": "clear_cuts",
        "description": "Remove all cut planes from the plan.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def _model_info(session: Session, bed: tuple[float, float, float]) -> dict:
    s = session.source.size
    return {
        "sizeMm": [round(float(s[0]), 1), round(float(s[1]), 1), round(float(s[2]), 1)],
        "bedMm": [bed[0], bed[1], bed[2]],
        "scale": session.scale,
        "fits": bool(s[0] <= bed[0] and s[1] <= bed[1] and s[2] <= bed[2]),
    }


def _execute_tool(name: str, tool_input: dict, session: Session, bed, plan: list[dict]) -> str:
    if name == "get_model_info":
        return str(_model_info(session, bed))
    if name == "set_scale":
        session.apply_scale(float(tool_input["factor"]))
        return f"Scaled to {session.scale}x. New size: {_model_info(session, bed)['sizeMm']} mm."
    if name == "auto_partition":
        proposed = auto_partition(session.source, bed)
        plan.clear()
        plan.extend({"axis": p["axis"], "offset": round(float(p["offset"]), 2)} for p in proposed)
        return f"Proposed {len(plan)} cut(s): {plan}"
    if name == "add_cut":
        plane = {"axis": tool_input["axis"], "offset": round(float(tool_input["offset"]), 2)}
        plan.append(plane)
        return f"Added cut {plane}. Plan now has {len(plan)} cut(s)."
    if name == "clear_cuts":
        plan.clear()
        return "Cleared all cuts."
    return f"Unknown tool: {name}"


def run_assistant(
    session: Session, message: str, bed: tuple[float, float, float]
) -> dict:
    """Run the tool-use loop. Returns {reply, scale, planes}."""
    import anthropic  # imported lazily so the app runs without the SDK/credentials

    client = anthropic.Anthropic()
    plan: list[dict] = []
    messages: list[dict] = [{"role": "user", "content": message}]

    for _ in range(MAX_STEPS):
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
        )
        if resp.stop_reason != "tool_use":
            reply = "".join(b.text for b in resp.content if b.type == "text")
            return {"reply": reply.strip(), "scale": session.scale, "planes": plan}

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                out = _execute_tool(block.name, block.input, session, bed, plan)
                results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": out}
                )
        messages.append({"role": "user", "content": results})

    return {
        "reply": "I took several steps but didn't finish — try a more specific request.",
        "scale": session.scale,
        "planes": plan,
    }
