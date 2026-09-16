#!/usr/bin/env python3
"""
draw_topology.py - draw the lab figures in one uniform style.

    python tools/draw_topology.py labs/lab02-ospf          # -> labs/lab02-ospf/figure.svg
    python tools/draw_topology.py --all                    # every lab that has a figure.yml
    python tools/draw_topology.py --all --png              # also figure.png (needs playwright)

Each lab has a `figure.yml` (layout and annotations) next to its `topology.yml`.
The port names written in the figure (e.g. "swp2 .1") are checked against the links of
topology.yml, so the figure and the lab that cgr_lab.py builds cannot drift apart.

figure.yml:
    title: "Lab 02 - OSPF multi-area"
    size: [1100, 760]
    note: "Management network 192.168.200.0/24 (not shown)"
    groups:   [{label, x, y, w, h, color, label_at: tl|tr|bl|br}]
    nodes:    {NAME: {type: router|switch|host, x, y, sub: "text under the name",
                      stub: {dir: left|right|up|down, lines: [...]}}}
    links:    [{a, b, pa: "swp1 .1", pb: "swp2 .2", net: "10.0.0.0/30",
                double: false, at: 0.5, shift: [dx, dy], pa_shift: [dx,dy], pb_shift: [dx,dy],
                side: 1|-1, pdist: 26}]
"""
import argparse
import html
import math
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

PALETTE = {  # group colours: border, fill
    "blue": ("#2563eb", "#eff6ff"), "green": ("#16a34a", "#f0fdf4"),
    "orange": ("#ea580c", "#fff7ed"), "red": ("#dc2626", "#fef2f2"),
    "purple": ("#7c3aed", "#f5f3ff"), "grey": ("#64748b", "#f8fafc"),
    "teal": ("#0d9488", "#f0fdfa"), "yellow": ("#ca8a04", "#fefce8"),
}
FONT = "DejaVu Sans, Helvetica, Arial, sans-serif"
LINK = "#475569"
TEXT = "#0f172a"
MUTED = "#475569"


def esc(s):
    return html.escape(str(s))


def text(x, y, s, size=12, weight="normal", color=TEXT, anchor="middle", halo=True):
    halo_attr = ' stroke="#ffffff" stroke-width="4" paint-order="stroke" stroke-linejoin="round"' if halo else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
            f'fill="{color}" text-anchor="{anchor}"{halo_attr}>{esc(s)}</text>')


# ---------------------------------------------------------------- icons
def icon_router(x, y):
    r = 22
    out = [f'<circle cx="{x}" cy="{y}" r="{r}" fill="#1d4ed8" stroke="#1e3a8a" stroke-width="1.5"/>']
    # four arrows: two pointing in (horizontal), two pointing out (vertical)
    a = 13
    out.append(f'<g stroke="#ffffff" stroke-width="2.2" fill="none" stroke-linecap="round">'
               f'<path d="M{x-a},{y} h{a-4} M{x-7},{y-3} l3,3 l-3,3"/>'
               f'<path d="M{x+a},{y} h-{a-4} M{x+7},{y-3} l-3,3 l3,3"/>'
               f'<path d="M{x},{y-4} v-{a-4} M{x-3},{y-a+2} l3,-3 l3,3"/>'
               f'<path d="M{x},{y+4} v{a-4} M{x-3},{y+a-2} l3,3 l3,-3"/></g>')
    return "".join(out), r


def icon_switch(x, y):
    w, h = 52, 32
    out = [f'<rect x="{x-w/2}" y="{y-h/2}" width="{w}" height="{h}" rx="6" fill="#047857" stroke="#064e3b" stroke-width="1.5"/>',
           f'<g stroke="#ffffff" stroke-width="2.2" fill="none" stroke-linecap="round">'
           f'<path d="M{x-16},{y-6} h30 M{x+10},{y-9} l4,3 l-4,3"/>'
           f'<path d="M{x+16},{y+6} h-30 M{x-10},{y+3} l-4,3 l4,3"/></g>']
    return "".join(out), 24


def icon_host(x, y):
    w, h = 40, 28
    out = [f'<rect x="{x-w/2}" y="{y-h/2-4}" width="{w}" height="{h}" rx="3" fill="#475569" stroke="#1e293b" stroke-width="1.5"/>',
           f'<rect x="{x-w/2+4}" y="{y-h/2}" width="{w-8}" height="{h-8}" fill="#e2e8f0"/>',
           f'<rect x="{x-12}" y="{y+h/2-2}" width="24" height="4" rx="1" fill="#1e293b"/>']
    return "".join(out), 22


ICONS = {"router": icon_router, "switch": icon_switch, "host": icon_host}


# ---------------------------------------------------------------- drawing
def shorten(ax, ay, bx, by, ra, rb):
    d = math.hypot(bx - ax, by - ay) or 1
    ux, uy = (bx - ax) / d, (by - ay) / d
    return ax + ux * ra, ay + uy * ra, bx - ux * rb, by - uy * rb, ux, uy, d


def draw(fig, lab_name):
    W, H = fig.get("size", [1100, 760])
    nodes = fig["nodes"]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
           f'font-family="{FONT}">',
           f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
    # title
    out.append(text(24, 36, fig.get("title", lab_name), size=20, weight="bold", anchor="start", halo=False))
    # groups
    for g in fig.get("groups", []):
        border, fill = PALETTE.get(g.get("color", "grey"), PALETTE["grey"])
        out.append(f'<rect x="{g["x"]}" y="{g["y"]}" width="{g["w"]}" height="{g["h"]}" rx="18" '
                   f'fill="{fill}" stroke="{border}" stroke-width="2" stroke-dasharray="{g.get("dash", "8 5")}"/>')
        pos = g.get("label_at", "tl")
        lx = g["x"] + 14 if pos.endswith("l") else g["x"] + g["w"] - 14
        glines = str(g["label"]).split("\n")
        ly = g["y"] + 24 if pos.startswith("t") else g["y"] + g["h"] - 14 - (len(glines) - 1) * 17
        anchor = "start" if pos.endswith("l") else "end"
        for i, line in enumerate(glines):
            out.append(text(lx, ly + i * 17, line, size=14, weight="bold", color=border, anchor=anchor, halo=False))
    # icon radii
    radius = {n: ICONS[v.get("type", "router")](0, 0)[1] for n, v in nodes.items()}
    # links
    labels = []
    for l in fig.get("links", []):
        A, B = nodes[l["a"]], nodes[l["b"]]
        x1, y1, x2, y2, ux, uy, d = shorten(A["x"], A["y"], B["x"], B["y"], radius[l["a"]], radius[l["b"]])
        px, py = -uy, ux                                   # perpendicular
        if l.get("double"):
            for s in (-3.5, 3.5):
                out.append(f'<line x1="{x1+px*s:.1f}" y1="{y1+py*s:.1f}" x2="{x2+px*s:.1f}" y2="{y2+py*s:.1f}" '
                           f'stroke="{LINK}" stroke-width="2"/>')
        else:
            out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{LINK}" stroke-width="2.5"/>')
        # port labels near each end, on the side given by 'side' (default: above/left of the line)
        side = l.get("side", 1)
        for key, (nx, ny), sign in (("pa", (x1, y1), 1), ("pb", (x2, y2), -1)):
            if not l.get(key):
                continue
            dist = l.get("pdist", 26)
            tx = nx + ux * sign * dist + px * 12 * side
            ty = ny + uy * sign * dist + py * 12 * side + 4
            ox, oy = l.get(key + "_shift", [0, 0])
            labels.append(text(tx + ox, ty + oy, l[key], size=11, color=MUTED))
        if l.get("net"):
            t = l.get("at", 0.5)
            mx, my = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
            ox, oy = l.get("shift", [0, 0])
            labels.append(text(mx + ox, my + oy + 4, l["net"], size=12, weight="bold", color="#1e293b"))
    # nodes
    for n, v in nodes.items():
        x, y = v["x"], v["y"]
        svg, r = ICONS[v.get("type", "router")](x, y)
        out.append(svg)
        stub = v.get("stub")
        if stub:
            dx, dy = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}[stub["dir"]]
            L = stub.get("len", 34)
            sx, sy = x + dx * r, y + dy * r
            ex, ey = sx + dx * L, sy + dy * L
            out.append(f'<line x1="{sx}" y1="{sy}" x2="{ex}" y2="{ey}" stroke="{LINK}" stroke-width="2"/>')
            out.append(f'<line x1="{ex - dy*8}" y1="{ey - dx*8}" x2="{ex + dy*8}" y2="{ey + dx*8}" stroke="{LINK}" stroke-width="2"/>')
            lines = stub["lines"]
            if dx:                       # text beside the stub, vertically centred
                tx = ex + dx * 8
                ty0 = ey - (len(lines) - 1) * 7.5 + 4
                for i, s in enumerate(lines):
                    labels.append(text(tx, ty0 + i * 15, s, size=12, anchor="start" if dx > 0 else "end"))
            else:                        # text above/below
                ty0 = ey + (14 if dy > 0 else -8 - (len(lines) - 1) * 15)
                for i, s in enumerate(lines):
                    labels.append(text(ex, ty0 + i * 15, s, size=12))
        lab_pos = v.get("label", "below")
        name = v.get("name", n)
        subs = v["sub"] if isinstance(v.get("sub"), list) else ([v["sub"]] if v.get("sub") else [])
        if lab_pos == "below":
            labels.append(text(x, y + r + 16, name, size=14, weight="bold"))
            for i, s in enumerate(subs):
                labels.append(text(x, y + r + 31 + i * 14, s, size=11, color=MUTED))
        elif lab_pos == "above":
            base = y - r - 8 - len(subs) * 14
            labels.append(text(x, base, name, size=14, weight="bold"))
            for i, s in enumerate(subs):
                labels.append(text(x, base + 15 + i * 14, s, size=11, color=MUTED))
        else:                            # left / right
            sgn = -1 if lab_pos == "left" else 1
            anchor = "end" if sgn < 0 else "start"
            labels.append(text(x + sgn * (r + 8), y + 5 - len(subs) * 7, name, size=14, weight="bold", anchor=anchor))
            for i, s in enumerate(subs):
                labels.append(text(x + sgn * (r + 8), y + 19 - len(subs) * 7 + i * 14, s, size=11, color=MUTED, anchor=anchor))
    out += labels
    # legend + note
    ly = H - 22
    lx = 24
    for kind, label in (("router", "router"), ("switch", "switch"), ("host", "host / PC")):
        svg, _ = ICONS[kind](lx + 14, ly - 4)
        out.append(f'<g transform="translate({lx + 14},{ly - 4}) scale(0.6) translate({-(lx + 14)},{-(ly - 4)})">{svg}</g>')
        out.append(text(lx + 34, ly + 1, label, size=12, color=MUTED, anchor="start", halo=False))
        lx += 34 + 9 * len(label) + 24
    if fig.get("note"):
        out.append(text(W - 24, ly + 1, fig["note"], size=12, color=MUTED, anchor="end", halo=False))
    out.append("</svg>")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- consistency check
def check(fig, topo):
    """Every 'swpN'/'ethN'/'e0' written in the figure must match a link of topology.yml."""
    links = set()
    for a, b in topo.get("links", []):
        links.add((a, b))
        links.add((b, a))
    problems = []
    for l in fig.get("links", []):
        pa = re.findall(r"(swp\d+|eth\d+|e0)(?:-(\d+))?", str(l.get("pa", "")))
        pb = re.findall(r"(swp\d+|eth\d+|e0)(?:-(\d+))?", str(l.get("pb", "")))
        if not pa or not pb:
            continue

        def expand(ports):
            p, last = ports[0]
            if not last:
                return [p]
            base = re.match(r"([a-z]+)(\d+)", p)
            return [f"{base.group(1)}{i}" for i in range(int(base.group(2)), int(last) + 1)]
        ea, eb = expand(pa), expand(pb)
        if len(ea) != len(eb):
            problems.append(f"{l['a']}-{l['b']}: port ranges of different length")
            continue
        for x, y in zip(ea, eb):
            if (f"{l['a']}:{x}", f"{l['b']}:{y}") not in links:
                problems.append(f"{l['a']}:{x} - {l['b']}:{y} is not a link in topology.yml")
    return problems


def render_png(svg_path, png_path, scale=2):
    from playwright.sync_api import sync_playwright
    svg = svg_path.read_text()
    w, h = map(int, re.search(r'width="(\d+)" height="(\d+)"', svg).groups())
    with sync_playwright() as p:
        kw = {}
        import os
        if os.path.exists("/opt/pw-browsers/chromium"):
            kw["executable_path"] = "/opt/pw-browsers/chromium"
        b = p.chromium.launch(**kw)
        page = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
        page.set_content(f"<html><body style='margin:0'>{svg}</body></html>")
        page.screenshot(path=str(png_path), clip={"x": 0, "y": 0, "width": w, "height": h})
        b.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("labs", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--png", action="store_true", help="also write figure.png (needs playwright + chromium)")
    args = ap.parse_args()
    labs = sorted(p.parent for p in (ROOT / "labs").glob("*/figure.yml")) if args.all else [Path(l) for l in args.labs]
    bad = False
    for lab in labs:
        fig = yaml.safe_load((lab / "figure.yml").read_text())
        topo = yaml.safe_load((lab / "topology.yml").read_text())
        for n in {x for l in fig.get("links", []) for x in (l["a"], l["b"])} - set(fig["nodes"]):
            sys.exit(f"{lab.name}: link uses unknown node {n}")
        problems = check(fig, topo)
        for p in problems:
            print(f"{lab.name}: {p}")
        bad |= bool(problems)
        svg = lab / "figure.svg"
        svg.write_text(draw(fig, lab.name))
        msg = f"{lab.name}: {svg.name}"
        if args.png:
            render_png(svg, lab / "figure.png")
            msg += " + figure.png"
        print(msg)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
