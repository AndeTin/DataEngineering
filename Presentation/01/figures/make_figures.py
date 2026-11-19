#!/usr/bin/env python3
"""Generate all figures for the multi-vector ANN presentation.

Every figure is redrawn from the paper's concepts; the two QPS charts are
explicitly schematic (trends, not digitised data).
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch
from matplotlib.animation import FuncAnimation, PillowWriter

OUT = os.path.dirname(os.path.abspath(__file__))

INK    = "#12203A"
MUTED  = "#6B7A90"
GRID   = "#DDE3EC"
BLUE   = "#2F6FEB"
ORANGE = "#E8590C"
GREEN  = "#1F9D55"
PURPLE = "#7048E8"
RED    = "#D6336C"
GREY   = "#9AA6B8"
GOLD   = "#F2B705"
PANEL  = "#F3F6FB"

plt.rcParams.update({
    "font.family": "Liberation Sans",
    "font.size": 12,
    "axes.edgecolor": GRID,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
})


def save(fig, name, dpi=200):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=dpi, bbox_inches="tight", pad_inches=0.12)
    plt.close(fig)
    print(f"wrote {path}")


def label(ax, x, y, s, color=INK, size=11, weight="normal", ha="center", va="center", pad=0.35):
    ax.text(x, y, s, color=color, fontsize=size, fontweight=weight, ha=ha, va=va,
            zorder=20, bbox=dict(boxstyle=f"round,pad={pad}", fc="white", ec="none", alpha=0.88))


def step_badge(ax, n, color=INK):
    ax.text(0.035, 0.955, str(n), transform=ax.transAxes, fontsize=13, fontweight="bold",
            color="white", ha="center", va="center", zorder=30,
            bbox=dict(boxstyle="circle,pad=0.32", fc=color, ec="none"))


# ---------------------------------------------------------------- geometry helpers

def lens_polygon(c1, c2, r, n=160):
    """Boundary of the intersection of two equal-radius disks, or None."""
    c1 = np.asarray(c1, float)
    c2 = np.asarray(c2, float)
    d = np.linalg.norm(c2 - c1)
    if d >= 2 * r:
        return None
    phi = np.arctan2(c2[1] - c1[1], c2[0] - c1[0])
    h = d / 2.0
    a = np.sqrt(max(r * r - h * h, 0.0))
    alpha = np.arctan2(a, h)
    t1 = np.linspace(phi - alpha, phi + alpha, n)
    arc1 = c1 + r * np.column_stack([np.cos(t1), np.sin(t1)])
    t2 = np.linspace(phi + np.pi - alpha, phi + np.pi + alpha, n)
    arc2 = c2 + r * np.column_stack([np.cos(t2), np.sin(t2)])
    return np.vstack([arc1, arc2])


def draw_disks(ax, centers, r, color, fill_alpha=0.0, lw=1.8, ls=(0, (5, 3))):
    for c in centers:
        if fill_alpha:
            ax.add_patch(Circle(c, r, fc=color, ec="none", alpha=fill_alpha, zorder=2))
        ax.add_patch(Circle(c, r, fc="none", ec=color, lw=lw, ls=ls, alpha=0.85, zorder=3))


# ---------------------------------------------------------------- 1. title motif

def fig_title():
    fig, ax = plt.subplots(figsize=(5.6, 3.1))
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-0.6, 10.6)
    ax.set_ylim(-1.5, 3.6)

    c1, c2, r = np.array([1.9, 1.4]), np.array([4.5, 1.4]), 2.3
    poly = lens_polygon(c1, c2, r)
    ax.fill(poly[:, 0], poly[:, 1], color=BLUE, alpha=0.18, zorder=2)
    draw_disks(ax, [c1, c2], r, BLUE, fill_alpha=0.05)
    for p in [(2.9, 1.4), (3.2, 0.8), (3.2, 2.0)]:
        ax.plot(*p, "o", color=BLUE, ms=6, zorder=6)
    ax.text(3.2, -0.75, "all", color=BLUE, ha="center", fontsize=13, fontweight="bold")

    c3, c4, r2 = np.array([7.4, 1.4]), np.array([9.6, 1.4]), 1.15
    draw_disks(ax, [c3, c4], r2, ORANGE, fill_alpha=0.10)
    for p in [(7.4, 1.4), (9.6, 1.4)]:
        ax.plot(*p, "o", color=ORANGE, ms=6, zorder=6)
    ax.text(8.5, -0.75, "any", color=ORANGE, ha="center", fontsize=13, fontweight="bold")

    save(fig, "fig_title.png")


# ---------------------------------------------------------------- 2. background

def knn_graph(pts, k=3):
    n = len(pts)
    D = np.linalg.norm(pts[:, None, :] - pts[None, :, :], axis=2)
    np.fill_diagonal(D, np.inf)
    return [list(np.argsort(D[i])[:k]) for i in range(n)]


def greedy_path(nb, pts, q, start):
    dist = lambda i: float(np.linalg.norm(pts[i] - q))
    cur, path, seen = start, [start], {start}
    while True:
        cand = [j for j in nb[cur] if j not in seen]
        if not cand:
            break
        j = min(cand, key=dist)
        if dist(j) < dist(cur) - 1e-9:
            path.append(j)
            seen.add(j)
            cur = j
        else:
            break
    return path


def fig_background():
    rng = np.random.default_rng(7)
    pts = rng.uniform([1.0, 1.0], [9.0, 8.0], (38, 2))
    q = np.array([5.0, 4.0])
    d = np.linalg.norm(pts - q, axis=1)
    r5 = np.sort(d)[4]

    fig, axs = plt.subplots(1, 2, figsize=(12, 4.6))

    ax = axs[0]
    ax.scatter(pts[:, 0], pts[:, 1], s=30, c=GREY, alpha=0.75, edgecolors="none", zorder=2)
    for f, alpha in [(0.45, 0.55), (0.72, 0.7), (1.0, 0.9)]:
        ax.add_patch(Circle(q, r5 * f, fc="none", ec=BLUE, lw=1.6,
                            ls=(0, (5, 3)), alpha=alpha, zorder=3))
    inside = d <= r5 + 1e-9
    ax.scatter(pts[inside, 0], pts[inside, 1], s=70, c=BLUE, edgecolors="white",
               linewidths=1.2, zorder=5)
    ax.plot(*q, "*", ms=20, color=ORANGE, mec="white", mew=0.8, zorder=6)
    ax.annotate("r*", xy=(q[0] + r5 * 0.72, q[1]), xytext=(q[0] + r5 * 0.72, q[1] + 1.15),
                color=BLUE, fontsize=13, fontweight="bold", ha="center",
                arrowprops=dict(arrowstyle="-", color=BLUE, lw=1.0))
    label(ax, 2.1, 8.35, "1 · Grow a ball until it holds k points", color=INK, size=13, weight="bold")
    ax.set_xlim(0.2, 9.8)
    ax.set_ylim(0.4, 8.9)
    ax.set_aspect("equal")
    ax.axis("off")

    ax = axs[1]
    nb = knn_graph(pts, 3)
    seen_edges = set()
    for i, nbrs in enumerate(nb):
        for j in nbrs:
            e = tuple(sorted((i, j)))
            if e in seen_edges:
                continue
            seen_edges.add(e)
            ax.plot([pts[i, 0], pts[j, 0]], [pts[i, 1], pts[j, 1]],
                    color=GRID, lw=1.0, zorder=1)

    target = int(np.argmin(d))
    best = []
    for s in range(len(pts)):
        p = greedy_path(nb, pts, q, s)
        if p[-1] == target and len(p) > len(best):
            best = p
    ax.scatter(pts[:, 0], pts[:, 1], s=30, c=GREY, alpha=0.8, edgecolors="none", zorder=2)
    for a, b in zip(best[:-1], best[1:]):
        ax.add_patch(FancyArrowPatch(pts[a], pts[b], arrowstyle="-|>", mutation_scale=13,
                                     color=ORANGE, lw=2.2, zorder=4,
                                     shrinkA=5, shrinkB=5))
    ax.scatter(pts[best, 0], pts[best, 1], s=70, c=ORANGE, edgecolors="white",
               linewidths=1.2, zorder=5)
    ax.plot(*q, "*", ms=20, color=ORANGE, mec="white", mew=0.8, zorder=6)
    label(ax, 2.6, 8.35, "2 · Walk downhill on the graph", color=INK, size=13, weight="bold")
    ax.set_xlim(0.2, 9.8)
    ax.set_ylim(0.4, 8.9)
    ax.set_aspect("equal")
    ax.axis("off")

    save(fig, "fig_background.png")


# ---------------------------------------------------------------- 3. all vs any

def fig_all_any():
    rng = np.random.default_rng(21)
    pts = rng.uniform([0.7, 1.3], [9.3, 8.7], (22, 2))
    q1 = np.array([2.9, 5.1])
    q2 = np.array([7.1, 3.9])
    d1 = np.linalg.norm(pts - q1, axis=1)
    d2 = np.linalg.norm(pts - q2, axis=1)
    d_all = np.maximum(d1, d2)
    d_any = np.minimum(d1, d2)

    fig, axs = plt.subplots(1, 2, figsize=(12, 4.9))
    for ax in axs:
        ax.set_xlim(0.0, 10.0)
        ax.set_ylim(0.5, 9.5)
        ax.set_aspect("equal")
        ax.axis("off")

    # --- all-k
    ax = axs[0]
    r_all = np.sort(d_all)[1] + 1e-9
    poly = lens_polygon(q1, q2, r_all)
    if poly is not None:
        ax.fill(poly[:, 0], poly[:, 1], color=BLUE, alpha=0.16, zorder=2)
    draw_disks(ax, [q1, q2], r_all, BLUE, fill_alpha=0.0)
    hit = d_all <= r_all
    ax.scatter(pts[~hit, 0], pts[~hit, 1], s=34, c=GREY, alpha=0.75, edgecolors="none", zorder=4)
    ax.scatter(pts[hit, 0], pts[hit, 1], s=80, c=BLUE, edgecolors="white", linewidths=1.2, zorder=6)
    ax.plot(*q1, "s", ms=11, color=INK, zorder=7)
    ax.plot(*q2, "s", ms=11, color=INK, zorder=7)
    label(ax, q1[0] - 0.55, q1[1] + 0.55, "q1", size=12, weight="bold")
    label(ax, q2[0] + 0.55, q2[1] + 0.55, "q2", size=12, weight="bold")
    label(ax, 5.0, 0.95, "all-2: intersection  ·  rank = max distance", color=BLUE, size=12, weight="bold")
    ax.set_title("similar to EVERY query vector", color=INK, fontsize=13, pad=6)

    # --- any-k
    ax = axs[1]
    r_any = np.sort(d_any)[2] + 1e-9
    draw_disks(ax, [q1, q2], r_any, ORANGE, fill_alpha=0.10)
    hit = d_any <= r_any
    ax.scatter(pts[~hit, 0], pts[~hit, 1], s=34, c=GREY, alpha=0.75, edgecolors="none", zorder=4)
    ax.scatter(pts[hit, 0], pts[hit, 1], s=80, c=ORANGE, edgecolors="white", linewidths=1.2, zorder=6)
    ax.plot(*q1, "s", ms=11, color=INK, zorder=7)
    ax.plot(*q2, "s", ms=11, color=INK, zorder=7)
    label(ax, q1[0] - 0.55, q1[1] + 0.55, "q1", size=12, weight="bold")
    label(ax, q2[0] + 0.55, q2[1] + 0.55, "q2", size=12, weight="bold")
    label(ax, 5.0, 0.95, "any-3: union  ·  rank = min distance", color=ORANGE, size=12, weight="bold")
    ax.set_title("similar to AT LEAST ONE query vector", color=INK, fontsize=13, pad=6)

    save(fig, "fig_all_any.png")


# ---------------------------------------------------------------- 4. worked example

def fig_example_build():
    q1 = np.array([0.0, 0.0])
    q2 = np.array([10.0, 0.0])
    P = {"A": np.array([5.0, 0.0]), "B": np.array([0.0, 1.0]),
         "C": np.array([10.0, 1.0]), "D": np.array([5.0, 5.0])}
    offs = {"A": (0.0, -0.55), "B": (-0.55, 0.0), "C": (0.55, 0.0), "D": (0.0, 0.55)}

    fig, axs = plt.subplots(2, 2, figsize=(10.6, 8.4))

    def base(ax, title):
        ax.set_xlim(-1.7, 11.7)
        ax.set_ylim(-2.1, 6.6)
        ax.set_aspect("equal")
        ax.axis("off")
        ax.set_title(title, color=INK, fontsize=13, pad=6)

    def points(ax, highlight=(), colors=None):
        for name, p in P.items():
            c = (colors or {}).get(name, GREY)
            s = 120 if name in highlight else 55
            ax.plot(*p, "o", ms=np.sqrt(s), color=c, mec="white", mew=1.3, zorder=8)
            label(ax, p[0] + offs[name][0], p[1] + offs[name][1], name, size=12,
                  weight="bold" if name in highlight else "normal",
                  color=colors.get(name, MUTED) if colors else MUTED)
        for q, name in [(q1, "q1"), (q2, "q2")]:
            ax.plot(*q, "s", ms=11, color=INK, zorder=9)
            label(ax, q[0], q[1] - 0.6, name, size=12, weight="bold", color=INK)

    # 1 — setup
    ax = axs[0, 0]
    base(ax, "The query and the dataset")
    points(ax)
    step_badge(ax, 1)

    # 2 — r = 5
    ax = axs[0, 1]
    base(ax, "Inflate both balloons equally")
    draw_disks(ax, [q1, q2], 5.0, BLUE, fill_alpha=0.06)
    ax.plot([5, 5], [-1.4, 5.0], color=BLUE, lw=0.9, ls=":", alpha=0.6)
    points(ax, highlight=("A",), colors={"A": BLUE})
    label(ax, 5.0, -1.75, "r = 5.0 → both balloons touch A", color=BLUE, size=12, weight="bold")
    step_badge(ax, 2)

    # 3 — all-2
    ax = axs[1, 0]
    base(ax, "all-2: the lens that captures two points")
    r = 7.0710678118654755
    poly = lens_polygon(q1, q2, r)
    ax.fill(poly[:, 0], poly[:, 1], color=BLUE, alpha=0.16, zorder=2)
    draw_disks(ax, [q1, q2], r, BLUE, fill_alpha=0.0)
    points(ax, highlight=("A", "D"), colors={"A": BLUE, "D": BLUE})
    label(ax, 5.0, -1.75, "all-2 = {A, D}", color=BLUE, size=13, weight="bold")
    step_badge(ax, 3)

    # 4 — any-2
    ax = axs[1, 1]
    base(ax, "any-2: the union of two small balls")
    draw_disks(ax, [q1, q2], 1.0, ORANGE, fill_alpha=0.16)
    points(ax, highlight=("B", "C"), colors={"B": ORANGE, "C": ORANGE})
    label(ax, 5.0, -1.75, "any-2 = {B, C}", color=ORANGE, size=13, weight="bold")
    step_badge(ax, 4)

    fig.tight_layout(h_pad=0.4)
    save(fig, "fig_example_build.png")


# ---------------------------------------------------------------- 5. balloon animation

def balloon_frames_data():
    rng = np.random.default_rng(11)
    pts = rng.uniform([0.8, 1.0], [9.2, 8.0], (16, 2))
    q1 = np.array([3.0, 4.7])
    q2 = np.array([7.0, 3.5])
    d1 = np.linalg.norm(pts - q1, axis=1)
    d2 = np.linalg.norm(pts - q2, axis=1)
    return pts, q1, q2, np.maximum(d1, d2), np.minimum(d1, d2)


def fig_balloon_gif():
    pts, q1, q2, d_all, d_any = balloon_frames_data()
    rs = np.linspace(0.4, 8.4, 44)
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2))

    def draw(ax, r, dist, color, title):
        ax.clear()
        ax.set_xlim(0.0, 10.0)
        ax.set_ylim(0.4, 8.9)
        ax.set_aspect("equal")
        ax.axis("off")
        draw_disks(ax, [q1, q2], r, color, fill_alpha=0.055)
        hit = dist <= r
        ax.scatter(pts[~hit, 0], pts[~hit, 1], s=34, c=GREY, alpha=0.7,
                   edgecolors="none", zorder=4)
        ax.scatter(pts[hit, 0], pts[hit, 1], s=85, c=color, edgecolors="white",
                   linewidths=1.2, zorder=6)
        ax.plot(*q1, "s", ms=10, color=INK, zorder=7)
        ax.plot(*q2, "s", ms=10, color=INK, zorder=7)
        ax.text(0.5, 8.45, title, color=color, fontsize=14, fontweight="bold", va="top")
        ax.text(0.5, 7.55, f"r = {r:4.1f}    captured: {int(hit.sum())}",
                color=MUTED, fontsize=11, va="top")

    def update(i):
        r = rs[i]
        draw(axs[0], r, d_all, BLUE, "ALL-k  ·  captured by the LAST balloon  →  max")
        draw(axs[1], r, d_any, ORANGE, "ANY-k  ·  captured by the FIRST balloon  →  min")
        return []

    frames = list(range(len(rs))) + [len(rs) - 1] * 14
    anim = FuncAnimation(fig, update, frames=frames, interval=90, blit=False)
    path = os.path.join(OUT, "fig_balloon.gif")
    anim.save(path, writer=PillowWriter(fps=10))
    plt.close(fig)
    print(f"wrote {path}")


def fig_balloon_frames():
    pts, q1, q2, d_all, d_any = balloon_frames_data()
    radii = [2.6, 5.2, 8.4]
    fig, axs = plt.subplots(2, 3, figsize=(12, 6.8))
    for row, (dist, color, name) in enumerate([
            (d_all, BLUE, "ALL-k  ·  max distance"),
            (d_any, ORANGE, "ANY-k  ·  min distance")]):
        for col, r in enumerate(radii):
            ax = axs[row, col]
            ax.set_xlim(0.0, 10.0)
            ax.set_ylim(0.4, 8.9)
            ax.set_aspect("equal")
            ax.axis("off")
            draw_disks(ax, [q1, q2], r, color, fill_alpha=0.06)
            hit = dist <= r
            ax.scatter(pts[~hit, 0], pts[~hit, 1], s=28, c=GREY, alpha=0.7,
                       edgecolors="none", zorder=4)
            ax.scatter(pts[hit, 0], pts[hit, 1], s=65, c=color, edgecolors="white",
                       linewidths=1.1, zorder=6)
            ax.plot(*q1, "s", ms=8, color=INK, zorder=7)
            ax.plot(*q2, "s", ms=8, color=INK, zorder=7)
            if col == 0:
                ax.text(-0.3, 4.6, name, rotation=90, color=color, fontsize=12,
                        fontweight="bold", ha="center", va="center")
            ax.text(5.0, 0.55, f"r = {r:.1f}  →  {int(hit.sum())} captured",
                    color=MUTED, fontsize=10.5, ha="center")
    fig.tight_layout()
    save(fig, "fig_balloon_frames.png")


# ---------------------------------------------------------------- 6. lipschitz

def fig_lipschitz():
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    ux, ru = 0.0, 3.5
    vx, rv = 2.8, 1.8
    xs = np.linspace(ux - 0.1, vx + 0.7, 200)

    upper = ru + (xs - ux)
    lower = ru - (xs - ux)
    ax.fill_between(xs, np.maximum(lower, 0), upper, color=BLUE, alpha=0.10, lw=0)
    ax.plot(xs, upper, color=BLUE, lw=1.3, ls=(0, (5, 3)))
    ax.plot(xs, lower, color=BLUE, lw=1.3, ls=(0, (5, 3)))
    ax.text(vx + 0.45, ru + (vx + 0.45 - ux) - 0.18, "slope +1", color=BLUE, fontsize=10)
    ax.text(vx + 0.45, max(ru - (vx + 0.45 - ux), 0.12) + 0.22, "slope −1", color=BLUE, fontsize=10)

    ax.plot([ux, vx], [ru, rv], "o", ms=10, color=INK, zorder=6)
    ax.plot([ux, ux], [0, ru], color=GRID, lw=1.2, zorder=1)
    ax.plot([vx, vx], [0, rv], color=GRID, lw=1.2, zorder=1)
    ax.annotate("", xy=(vx, 0.42), xytext=(ux, 0.42),
                arrowprops=dict(arrowstyle="<|-|>", color=MUTED, lw=1.2))
    ax.text((ux + vx) / 2, 0.18, "δ(u, v)", color=MUTED, ha="center", fontsize=11)

    ax.text(ux - 0.08, ru + 0.22, "u", fontsize=14, fontweight="bold", color=INK, ha="right")
    ax.text(vx + 0.1, rv + 0.22, "v", fontsize=14, fontweight="bold", color=INK)
    ax.text(ux - 0.08, ru - 0.05, "r(u)", fontsize=10, color=MUTED, ha="right", va="top")
    ax.text(vx + 0.1, rv - 0.05, "r(v)", fontsize=10, color=MUTED, va="top")

    ax.set_xlim(-0.55, vx + 0.75)
    ax.set_ylim(0, 4.4)
    ax.set_xlabel("position in the dataset")
    ax.set_ylabel("score  r(u)")
    ax.set_yticks([])
    ax.set_xticks([])
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.set_title("| r(u) − r(v) |  ≤  δ(u, v)   →   no cliffs in the score landscape",
                 color=INK, fontsize=12.5, pad=12)
    save(fig, "fig_lipschitz.png")


# ---------------------------------------------------------------- 7. MEB vs centroid

def fig_meb():
    rng = np.random.default_rng(3)
    offices = np.vstack([np.zeros((1, 2)), np.tile([4.0, 4.0], (9, 1)) + rng.normal(0, 0.16, (9, 2))])
    centroid = offices.mean(axis=0)
    meb = np.array([2.0, 2.0])
    r_c = np.max(np.linalg.norm(offices - centroid, axis=1))
    r_m = np.max(np.linalg.norm(offices - meb, axis=1))

    fig, axs = plt.subplots(1, 2, figsize=(11.2, 4.5), gridspec_kw={"width_ratios": [1.3, 1]})

    ax = axs[0]
    ax.scatter(offices[:, 0], offices[:, 1], s=48, c=GREY, edgecolors="white",
               linewidths=0.8, zorder=4)
    ax.add_patch(Circle(centroid, r_c, fc="none", ec=RED,
                        lw=1.6, ls=(0, (5, 3)), alpha=0.75, zorder=2))
    ax.add_patch(Circle(meb, r_m, fc="none", ec=GREEN, lw=2.0, ls=(0, (5, 3)), zorder=2))
    ax.plot(*centroid, "X", ms=14, color=RED, mec="white", mew=1.2, zorder=7)
    ax.plot(*meb, "o", ms=12, color=GREEN, mec="white", mew=1.2, zorder=7)
    label(ax, centroid[0] + 0.15, centroid[1] + 0.45, "centroid\nworst 5.09", color=RED, size=10.5, weight="bold")
    label(ax, meb[0] - 0.15, meb[1] - 0.6, "MEB centre\nworst 2.83", color=GREEN, size=10.5, weight="bold")
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("1 office at (0,0), 9 offices at (4,4)", color=MUTED, fontsize=11, pad=4)

    ax = axs[1]
    names = ["centroid", "MEB centre"]
    vals = [r_c, r_m]
    cols = [RED, GREEN]
    bars = ax.barh(names, vals, color=cols, height=0.5, alpha=0.9)
    for b, v in zip(bars, vals):
        ax.text(v + 0.12, b.get_y() + b.get_height() / 2, f"{v:.2f}", va="center",
                color=INK, fontsize=12, fontweight="bold")
    ax.set_xlim(0, 6.4)
    ax.set_xlabel("worst-case commute")
    ax.invert_yaxis()
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.grid(axis="x", color=GRID, lw=0.9)
    ax.set_axisbelow(True)
    ax.set_title("minimise the MAX, not the average", color=INK, fontsize=12, pad=8)

    fig.tight_layout()
    save(fig, "fig_meb.png")


# ---------------------------------------------------------------- 8. disconnected any-k

def fig_disconnected():
    fig, axs = plt.subplots(1, 2, figsize=(11.2, 4.3), gridspec_kw={"width_ratios": [1.35, 1]})

    ax = axs[0]
    q1, q2 = np.array([0.0, 0.0]), np.array([100.0, 0.0])
    A, B = np.array([0.0, 1.7]), np.array([100.0, 1.7])
    for c, col in [(q1, INK), (q2, INK)]:
        ax.plot(*c, "s", ms=10, color=col, zorder=7)
    for x0 in [0, 100]:
        ax.add_patch(FancyBboxPatch((x0 - 7, -3.2), 14, 8.0, boxstyle="round,pad=0.4,rounding_size=1.5",
                                    fc=ORANGE, ec=ORANGE, alpha=0.10, lw=1.2, ls=(0, (4, 3))))
    ax.plot(*A, "o", ms=12, color=ORANGE, mec="white", mew=1.2, zorder=8)
    ax.plot(*B, "o", ms=12, color=ORANGE, mec="white", mew=1.2, zorder=8)
    label(ax, 0.0, -1.9, "q1", size=11, weight="bold")
    label(ax, 100.0, -1.9, "q2", size=11, weight="bold")
    label(ax, 0.0, 2.7, "A", color=ORANGE, size=12, weight="bold")
    label(ax, 100.0, 2.7, "B", color=ORANGE, size=12, weight="bold")
    ax.annotate("", xy=(92, 5.4), xytext=(8, 5.4),
                arrowprops=dict(arrowstyle="<|-|>", color=MUTED, lw=1.2))
    ax.text(50, 5.9, "100 apart", color=MUTED, ha="center", fontsize=11)
    ax.set_xlim(-14, 114)
    ax.set_ylim(-4.2, 7.0)
    ax.axis("off")
    ax.set_title("any-2 = {A, B}: two disconnected regions", color=INK, fontsize=12, pad=8)

    ax = axs[1]
    xs = np.linspace(0, 100, 400)
    score = np.minimum(np.sqrt(xs ** 2 + 1.7 ** 2), np.sqrt((100 - xs) ** 2 + 1.7 ** 2))
    ax.plot(xs, score, color=ORANGE, lw=2.4)
    ax.fill_between(xs, 0, score, color=ORANGE, alpha=0.08)
    ax.axhline(1.7, color=GREY, lw=1.0, ls=":")
    ax.annotate("walking toward B\nmakes the score worse", xy=(22, 22), xytext=(34, 42),
                color=INK, fontsize=10.5,
                arrowprops=dict(arrowstyle="->", color=ORANGE, lw=1.4))
    ax.plot([0, 100], [1.7, 1.7], "o", ms=8, color=ORANGE, zorder=6)
    ax.set_xlabel("position along the path A → B")
    ax.set_ylabel("any-radius")
    ax.set_ylim(0, 56)
    ax.set_xlim(-2, 102)
    ax.set_yticks([0, 25, 50])
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color=GRID, lw=0.9)
    ax.set_axisbelow(True)
    ax.set_title("no downhill path from A to B", color=INK, fontsize=12, pad=8)

    fig.tight_layout()
    save(fig, "fig_disconnected.png")


# ---------------------------------------------------------------- 9. QPS charts (schematic)

def _curve(a, b, c, t):
    return a - b * t - c * t ** 2


def fig_qps_recall():
    r = np.linspace(0.80, 1.00, 200)
    t = (r - 0.80) / 0.20
    series = [
        ("Milvus",         dict(a=2.05, b=1.00, c=0.50), GREY,   "-",  1.8),
        ("Opt-Milvus",     dict(a=2.25, b=0.95, c=0.50), PURPLE, "--", 1.8),
        ("VBASE",          dict(a=2.45, b=0.90, c=0.45), "#1C7ED6", "-.", 1.8),
        ("RadiusSearch",   dict(a=2.75, b=0.80, c=0.75), "#F59F00", "-",  1.8),
        ("RadiusSearch+",  dict(a=2.60, b=0.35, c=0.25), ORANGE,  "-",  3.0),
    ]
    fig, ax = plt.subplots(figsize=(6.3, 4.5))
    for name, p, col, ls, lw in series:
        ax.plot(r, 10 ** _curve(p["a"], p["b"], p["c"], t), color=col, ls=ls, lw=lw, label=name)
    ax.set_yscale("log")
    ax.set_ylim(1, 1e4)
    ax.set_xlim(0.80, 1.00)
    ax.set_xlabel("Recall@10")
    ax.set_ylabel("QPS (log scale)")
    ax.grid(axis="y", color=GRID, lw=0.9)
    ax.set_axisbelow(True)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=8.5, frameon=False, loc="lower left", ncol=2, handlelength=2.2,
              columnspacing=1.0)
    ax.set_title("All-k, SIFT — schematic trend", color=INK, fontsize=12, pad=8)
    save(fig, "fig_qps_recall.png")


def fig_qps_bar():
    datasets = ["Recipe", "Msong", "SIFT", "GIST", "Crawl"]
    allk = [10.5, 8.5, 9.5, 7.5, 11.5]
    anyk = [8.5, 7.5, 9.0, 6.5, 10.5]
    y = np.arange(len(datasets))
    fig, ax = plt.subplots(figsize=(6.3, 4.5))
    h = 0.36
    ax.barh(y - h / 2, allk, height=h, color=BLUE, label="all-k", alpha=0.9)
    ax.barh(y + h / 2, anyk, height=h, color=ORANGE, label="any-k", alpha=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels(datasets)
    ax.invert_yaxis()
    ax.set_xlim(0, 14)
    ax.set_xlabel("× faster than best baseline (schematic)")
    ax.axvline(1, color=MUTED, lw=0.8, ls=":")
    ax.grid(axis="x", color=GRID, lw=0.9)
    ax.set_axisbelow(True)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    ax.legend(fontsize=9, frameon=False, loc="lower right")
    ax.set_title("QPS at recall 0.99 — schematic", color=INK, fontsize=12, pad=8)
    fig.tight_layout()
    save(fig, "fig_qps_bar.png")


# ---------------------------------------------------------------- main

if __name__ == "__main__":
    fig_title()
    fig_background()
    fig_all_any()
    fig_example_build()
    fig_lipschitz()
    fig_meb()
    fig_disconnected()
    fig_qps_recall()
    fig_qps_bar()
    fig_balloon_gif()
    fig_balloon_frames()
    print("done")
