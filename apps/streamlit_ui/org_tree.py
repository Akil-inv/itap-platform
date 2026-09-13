"""The whole-org tree: Functional Owner(s) -> Managers -> Agents.

Deliberately NOT a graphviz diagram — hand-built inline SVG so the visual
language (avatar circles, elbow tree connectors, hover highlighting) is
fully controllable, and so the component has zero external/CDN dependency
(relevant for eventual CML deployment, where outbound network access to a
JS CDN is one of the open platform questions in docs/architecture.md).

Shows CURRENT structure only (active assignments) — this is "who reports
to whom right now," not a history view. History/closed assignments stay
in the Functional Owner's "All Assignments" table.

**Layout, rewritten from the original flat/evenly-spaced version**: the
original `_layout_row()` spaced every node in a tier evenly across a
fixed width with no regard for which parent it belonged to, so a
manager's associates were scattered across the whole bottom row instead
of sitting under their manager — every connecting line had to cross
everything else to reach its real target. This version groups each
manager's associates into their own cluster, centers the manager above
its cluster, and connects each tier with right-angle "elbow" branches
through a shared bus line rather than one bezier per edge — a literal
tree, not a tangle. Owner -> Manager is a complete bipartite graph in
this data model (every Functional Owner oversees every Manager), so it
gets the same bus treatment: a single trunk line the owners drop into
and the managers rise from, instead of N x M crossing diagonals.
"""
from __future__ import annotations

import html

import streamlit as st

from person_row import _photo_src
from tokens import TOKENS

R = {"owner": 30, "manager": 27, "agent": 23}
TIER_Y = {"owner": 55, "bus_owner": 120, "manager": 190, "bus_manager": 280, "agent": 360}
LABEL_MAX_CHARS = 14
SLOT_W = 105
CLUSTER_GAP = 46
MIN_WIDTH = 480

COLORS = {
    "owner": (TOKENS.role["functional_owner"], TOKENS.neutral[0]),
    "manager": (TOKENS.primary["default"], TOKENS.neutral[0]),
    "agent": (TOKENS.role["agent"], TOKENS.neutral[0]),
}


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _truncate(label: str) -> str:
    if len(label) <= LABEL_MAX_CHARS:
        return label
    return label[: LABEL_MAX_CHARS - 1].rstrip() + "…"


def _tier_of(node_id: str) -> str:
    return "owner" if node_id.startswith("o_") else ("manager" if node_id.startswith("m_") else "agent")


def _cluster_layout(
    managers: list[tuple[str, str]],
    agents: list[tuple[str, str]],
    edges_manager_agent: list[tuple[str, str]],
) -> tuple[dict[str, dict], float]:
    """Groups agents under the manager they first appear connected to
    (their "home" branch), lays each manager's cluster out left to
    right, and puts any agent with no active manager edge into its own
    trailing "Unassigned" cluster so gaps in the structure stay visible
    (same intent as the original docstring) without scattering them
    across every other manager's branch."""
    children_by_manager: dict[str, list[str]] = {m_id: [] for m_id, _ in managers}
    home_manager: dict[str, str] = {}
    for m_id, a_id in edges_manager_agent:
        if a_id not in home_manager and m_id in children_by_manager:
            home_manager[a_id] = m_id
            children_by_manager[m_id].append(a_id)

    agent_label = dict(agents)
    unassigned = [a_id for a_id, _ in agents if a_id not in home_manager]

    pos: dict[str, dict] = {}
    cursor = 0.0
    for m_id, m_label in managers:
        kids = children_by_manager[m_id]
        cluster_w = max(len(kids), 1) * SLOT_W
        for i, a_id in enumerate(kids):
            x = cursor + SLOT_W * (i + 0.5)
            pos[a_id] = {"x": x, "y": TIER_Y["agent"], "label": agent_label[a_id]}
        pos[m_id] = {"x": cursor + cluster_w / 2, "y": TIER_Y["manager"], "label": m_label}
        cursor += cluster_w + CLUSTER_GAP

    if unassigned:
        for i, a_id in enumerate(unassigned):
            x = cursor + SLOT_W * (i + 0.5)
            pos[a_id] = {"x": x, "y": TIER_Y["agent"], "label": agent_label[a_id]}
        cursor += max(len(unassigned), 1) * SLOT_W + CLUSTER_GAP

    total_width = max(cursor - CLUSTER_GAP, MIN_WIDTH)
    return pos, total_width


def _layout_row_over_width(names_and_ids: list[tuple[str, str]], y: int, width: float) -> dict[str, dict]:
    n = len(names_and_ids)
    positions = {}
    if n == 0:
        return positions
    step = width / (n + 1)
    for i, (node_id, label) in enumerate(names_and_ids):
        positions[node_id] = {"x": step * (i + 1), "y": y, "label": label}
    return positions


def _avatar_group(node_id: str, info: dict, tier: str, photo_url: str | None) -> str:
    x, y, label = info["x"], info["y"], info["label"]
    r = R[tier]
    fill, text_color = COLORS[tier]
    src = _photo_src(photo_url) if photo_url else None
    parts = [f'<g class="itap-node" data-id="{node_id}">', f"<title>{_esc(label)}</title>"]
    if src:
        clip_id = f"clip_{node_id}"
        parts.append(f'<clipPath id="{clip_id}"><circle cx="{x}" cy="{y}" r="{r}"/></clipPath>')
        parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}"/>')
        parts.append(
            f'<image href="{_esc(src)}" x="{x - r}" y="{y - r}" width="{2 * r}" height="{2 * r}" '
            f'clip-path="url(#{clip_id})" preserveAspectRatio="xMidYMid slice"/>'
        )
        parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{fill}" stroke-width="2.5"/>')
    else:
        initial = _esc(label[:1].upper()) if label else "?"
        parts.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}"/>')
        parts.append(
            f'<text x="{x}" y="{y + r * 0.35:.0f}" text-anchor="middle" font-size="{r * 0.8:.0f}" '
            f'font-weight="700" fill="{text_color}">{initial}</text>'
        )
    parts.append(
        f'<text x="{x}" y="{y + r + 16}" text-anchor="middle" font-size="11" font-weight="600" '
        f'fill="{TOKENS.neutral[800]}">{_esc(_truncate(label))}</text>'
    )
    parts.append("</g>")
    return "".join(parts)


def _elbow_edge(pos: dict, a: str, b: str, bus_y: float, cls: str, edge_id: str) -> str:
    pa, pb = pos[a], pos[b]
    ra, rb = R[_tier_of(a)], R[_tier_of(b)]
    x1, y1 = pa["x"], pa["y"] + ra
    x2, y2 = pb["x"], pb["y"] - rb
    d = f"M {x1},{y1} L {x1},{bus_y} L {x2},{bus_y} L {x2},{y2}"
    return (
        f'<path id="{edge_id}" class="itap-edge {cls}" data-from="{a}" data-to="{b}" '
        f'd="{d}" fill="none"/>'
    )


def render(
    owners: list[tuple[str, str]],
    managers: list[tuple[str, str]],
    agents: list[tuple[str, str]],
    edges_owner_manager: list[tuple[str, str]],
    edges_manager_agent: list[tuple[str, str]],
    photo_urls: dict[str, str] | None = None,
    height: int = 520,
) -> None:
    """Each of owners/managers/agents is a list of (node_id, display_name).
    Edges are (from_node_id, to_node_id) pairs. `photo_urls` optionally
    maps a node_id to a photo URL/local path (same value shape
    `AssociateProfile.photo_url` and `person_row.py` already handle)."""
    photo_urls = photo_urls or {}
    pos, width = _cluster_layout(managers, agents, edges_manager_agent)
    pos.update(_layout_row_over_width(owners, TIER_Y["owner"], width))

    svg_parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%; height:auto; font-family:-apple-system,Segoe UI,Helvetica,sans-serif;">',
    ]

    edge_lines = []
    for i, (a, b) in enumerate(edges_owner_manager):
        if a in pos and b in pos:
            edge_lines.append(_elbow_edge(pos, a, b, TIER_Y["bus_owner"], "itap-edge-owner", f"e_o_{i}"))
    for i, (a, b) in enumerate(edges_manager_agent):
        if a in pos and b in pos:
            edge_lines.append(_elbow_edge(pos, a, b, TIER_Y["bus_manager"], "itap-edge-manager", f"e_m_{i}"))
    svg_parts.extend(edge_lines)

    for node_id, info in pos.items():
        tier = _tier_of(node_id)
        svg_parts.append(_avatar_group(node_id, info, tier, photo_urls.get(node_id)))

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
