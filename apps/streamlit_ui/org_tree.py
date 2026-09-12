"""The whole-org tree: Functional Owner(s) -> Managers -> Agents.

Deliberately NOT a graphviz diagram — hand-built inline SVG so the visual
language (rounded cards, soft shadows, smooth bezier connectors, hover
highlighting) is fully controllable, and so the component has zero
external/CDN dependency (relevant for eventual CML deployment, where
outbound network access to a JS CDN is one of the open platform
questions in docs/architecture.md).

Shows CURRENT structure only (active assignments) — this is "who reports
to whom right now," not a history view. History/closed assignments stay
in the Functional Owner's "All Assignments" table.
"""
from __future__ import annotations

import html

import streamlit as st

from tokens import TOKENS

CARD_W, CARD_H = 150, 60
TIER_Y = {"owner": 60, "manager": 230, "agent": 400}
# This SVG is rendered inside an isolated st.iframe document (its own
# `<html>`, no access to the page's CSS custom properties), so it
# imports the raw token constants from tokens.py directly rather than
# duplicating hex values here.
COLORS = {
    "owner": (TOKENS.role["functional_owner"], TOKENS.neutral[0]),
    "manager": (TOKENS.primary["default"], TOKENS.neutral[0]),
    "agent": (TOKENS.role["agent"], TOKENS.neutral[0]),
}


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _layout_row(names_and_ids: list[tuple[str, str]], y: int, width: int) -> dict[str, dict]:
    n = len(names_and_ids)
    positions = {}
    if n == 0:
        return positions
    step = width / (n + 1)
    for i, (node_id, label) in enumerate(names_and_ids):
        x = step * (i + 1)
        positions[node_id] = {"x": x, "y": y, "label": label}
    return positions


def render(owners: list[tuple[str, str]], managers: list[tuple[str, str]],
           agents: list[tuple[str, str]], edges_owner_manager: list[tuple[str, str]],
           edges_manager_agent: list[tuple[str, str]], height: int = 520) -> None:
    """Each of owners/managers/agents is a list of (node_id, display_name).
    Edges are (from_node_id, to_node_id) pairs."""
    width = 1200
    pos = {}
    pos.update(_layout_row(owners, TIER_Y["owner"], width))
    pos.update(_layout_row(managers, TIER_Y["manager"], width))
    pos.update(_layout_row(agents, TIER_Y["agent"], width))

    svg_parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%; height:auto; font-family:-apple-system,Segoe UI,Helvetica,sans-serif;">',
        "<defs>",
        '<filter id="cardShadow" x="-40%" y="-40%" width="180%" height="180%">',
        '<feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="#000000" flood-opacity="0.15"/>',
        "</filter>",
        "</defs>",
    ]

    def edge_path(a: str, b: str, cls: str, edge_id: str) -> str:
        pa, pb = pos[a], pos[b]
        x1, y1 = pa["x"], pa["y"] + CARD_H / 2
        x2, y2 = pb["x"], pb["y"] - CARD_H / 2
        mid_y = (y1 + y2) / 2
        return (
            f'<path id="{edge_id}" class="itap-edge {cls}" data-from="{a}" data-to="{b}" '
            f'd="M {x1},{y1} C {x1},{mid_y} {x2},{mid_y} {x2},{y2}" '
            f'fill="none"/>'
        )

    edge_lines = []
    for i, (a, b) in enumerate(edges_owner_manager):
        if a in pos and b in pos:
            edge_lines.append(edge_path(a, b, "itap-edge-owner", f"e_o_{i}"))
    for i, (a, b) in enumerate(edges_manager_agent):
        if a in pos and b in pos:
            edge_lines.append(edge_path(a, b, "itap-edge-manager", f"e_m_{i}"))
    svg_parts.extend(edge_lines)

    for node_id, info in pos.items():
        tier = "owner" if node_id.startswith("o_") else ("manager" if node_id.startswith("m_") else "agent")
        fill, text_color = COLORS[tier]
        x, y = info["x"], info["y"]
        label = _esc(info["label"])
        svg_parts.append(
            f'<g class="itap-node" data-id="{node_id}" transform="translate({x - CARD_W/2},{y - CARD_H/2})">'
            f'<rect width="{CARD_W}" height="{CARD_H}" rx="14" ry="14" fill="{fill}" '
            f'filter="url(#cardShadow)"/>'
            f'<text x="{CARD_W/2}" y="{CARD_H/2 + 5}" text-anchor="middle" '
            f'font-size="14" font-weight="600" fill="{text_color}">{label}</text>'
            f"</g>"
        )

    svg_parts.append("</svg>")

    style = f"""
    <style>
      body {{ margin: 0; }}
      .itap-edge-owner {{ stroke: {TOKENS.neutral[300]}; stroke-width: 1.5; stroke-dasharray: 4 3; }}
      .itap-edge-manager {{ stroke: {TOKENS.primary['default']}; stroke-width: 2.5; opacity: 0.65; }}
      .itap-node {{ cursor: pointer; transition: opacity 0.15s ease; }}
      .itap-edge {{ transition: opacity 0.15s ease, stroke-width 0.15s ease; }}
      .itap-dim {{ opacity: 0.18; }}
      .itap-highlight {{ stroke-width: 4; }}
    </style>
    """

    script = """
    <script>
      const svg = document.currentScript.previousElementSibling;
      const nodes = svg.querySelectorAll('.itap-node');
      const edges = svg.querySelectorAll('.itap-edge');
      nodes.forEach(function(node) {
        node.addEventListener('mouseenter', function() {
          const id = node.getAttribute('data-id');
          const connected = new Set([id]);
          edges.forEach(function(edge) {
            if (edge.getAttribute('data-from') === id || edge.getAttribute('data-to') === id) {
              connected.add(edge.getAttribute('data-from'));
              connected.add(edge.getAttribute('data-to'));
              edge.classList.add('itap-highlight');
            } else {
              edge.classList.add('itap-dim');
            }
          });
          nodes.forEach(function(n2) {
            if (!connected.has(n2.getAttribute('data-id'))) n2.classList.add('itap-dim');
          });
        });
        node.addEventListener('mouseleave', function() {
          edges.forEach(function(e) { e.classList.remove('itap-highlight', 'itap-dim'); });
          nodes.forEach(function(n2) { n2.classList.remove('itap-dim'); });
        });
      });
    </script>
    """

    st.iframe(style + "".join(svg_parts) + script, height=height + 20)
