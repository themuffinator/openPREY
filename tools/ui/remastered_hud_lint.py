"""Generator-side checks for the Remastered HUD documents.

The engine's document compiler is authoritative; this repeats the rules a
generator most easily breaks, so a build reports every violation at once:
unique node ids, base values for bound and animated properties, one owner per
property, localization keys on text, and known event/timeline references.
"""
from __future__ import annotations

SHORTHAND = {"margin": ("margin-top", "margin-right", "margin-bottom", "margin-left"),
             "padding": ("padding-top", "padding-right", "padding-bottom", "padding-left")}


def lint(document: dict) -> list:
    problems = []
    nodes = {}

    def walk(node, path):
        ident = node.get("id")
        if ident in nodes:
            problems.append(f"duplicate node id {ident}")
        nodes[ident] = node
        if node.get("type") == "text":
            text = node.get("properties", {}).get("text", {}).get("value", "")
            if not str(text).startswith("#str_"):
                problems.append(f"{ident}: text base must be a #str_ key")
        if "mask" in node.get("properties", {}):
            problems.append(f"{ident}: mask placed among properties")
        for child in node.get("children", []):
            walk(child, path + [ident])
    walk(document["root"], [])

    def has_base(node, prop):
        props = node.get("properties", {})
        if prop in props:
            return True
        for short, sides in SHORTHAND.items():
            if prop in sides and short in props:
                return True
        return False

    bound = {}
    for binding in document.get("bindings", []):
        node = nodes.get(binding["node"])
        if node is None:
            problems.append(f"binding {binding['id']}: unknown node {binding['node']}")
            continue
        prop = binding["property"]
        if prop != "enabled" and not has_base(node, prop):
            problems.append(f"binding {binding['id']}: {binding['node']}.{prop} has no base value")
        key = (binding["node"], prop)
        if key in bound:
            problems.append(f"binding {binding['id']}: {binding['node']}.{prop} already bound by {bound[key]}")
        bound[key] = binding["id"]
    timelines = {t["id"] for t in document.get("timelines", [])}
    animated = {}
    for timeline in document.get("timelines", []):
        seen = set()
        for track in timeline["tracks"]:
            node = nodes.get(track["node"])
            key = (track["node"], track["property"])
            if node is None:
                problems.append(f"timeline {timeline['id']}: unknown node {track['node']}")
                continue
            if not has_base(node, track["property"]):
                problems.append(f"timeline {timeline['id']}: {track['node']}.{track['property']} has no base value")
            if key in bound:
                problems.append(f"timeline {timeline['id']}: {track['node']}.{track['property']} is also bound ({bound[key]})")
            if key in seen:
                problems.append(f"timeline {timeline['id']}: {track['node']}.{track['property']} twice")
            seen.add(key)
            animated.setdefault(key, timeline["id"])
            if len(track["keys"]) < 2:
                problems.append(f"timeline {timeline['id']}: track {key} needs two keys")
        if timeline.get("complete") and timeline["complete"] not in document.get("events", {}):
            problems.append(f"timeline {timeline['id']}: completion {timeline['complete']} is not an event")
    state = document.get("state", {})

    def refs(expr, where):
        if isinstance(expr, dict):
            if "state" in expr and expr["state"] not in state:
                problems.append(f"{where}: unknown state {expr['state']}")
            for value in expr.values():
                refs(value, where)
        elif isinstance(expr, list):
            for value in expr:
                refs(value, where)
    for binding in document.get("bindings", []):
        refs(binding["value"], f"binding {binding['id']}")

    def steps(program, where):
        for step in program:
            kind = step.get("op")
            if kind in ("playTimeline", "cancelTimeline") and step["timeline"] not in timelines:
                problems.append(f"{where}: unknown timeline {step['timeline']}")
            if kind == "setState":
                for key, value in step["values"].items():
                    if key not in state:
                        problems.append(f"{where}: setState of undeclared {key}")
                    elif "cvar" in state[key]:
                        problems.append(f"{where}: setState of read-only {key}")
                    refs(value, where)
            if kind == "if":
                refs(step["condition"], where)
                steps(step.get("then", []), where)
                steps(step.get("else", []), where)
            if kind == "call" and step["event"] not in document.get("events", {}):
                problems.append(f"{where}: unknown event {step['event']}")
    for name, program in document.get("events", {}).items():
        steps(program, f"event {name}")
    return problems
