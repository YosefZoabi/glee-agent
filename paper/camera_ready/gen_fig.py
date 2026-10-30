"""Generate the two-panel camera-ready Figure 1 from the submitted figure's coordinates.

Input: ../fig_noise.tex (rounded TikZ coordinates of the submitted figure).
Panel (a): overall ratings as submitted. Panel (b): change since the first
snapshot, R_i(t) - R_i(0). Values are decoded approximations (about +-0.1 point).
"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "analysis"))
from noise import figure_polls

polls = figure_polls(HERE.parent / "fig_noise.tex")
names = ["B1", "B2", "B3", "B4", "B5"]
T = polls[-1]["elapsed_hours"]
W, H = 5.55, 2.25          # panel width/height in tikz units
GAP = 1.95                 # horizontal gap between panels
XB = W + GAP               # x offset of panel (b)

def panel(x0, lo, hi, ticks, getter, label, letter, band=False):
    out = []
    sy = lambda v: (v - lo) / (hi - lo) * H
    sx = lambda t: x0 + t / T * W
    for v in ticks:
        out.append(f"\\draw[gridline] ({x0:.3f},{sy(v):.3f}) -- ({x0+W:.3f},{sy(v):.3f});")
        txt = f"$+{v}$" if (letter == "b" and v > 0) else f"{v}"
        out.append(f"\\node[axlab,anchor=east] at ({x0-0.08:.3f},{sy(v):.3f}) {{{txt}}};")
    for h in (0, 2, 4, 6, 8):
        out.append(f"\\node[axlab,anchor=north] at ({sx(h):.3f},-0.04) {{{h}h}};")
    out.append(f"\\draw[axline] ({x0:.3f},0) -- ({x0+W:.3f},0);")
    out.append(f"\\draw[axline] ({x0:.3f},0) -- ({x0:.3f},{H+0.05:.3f});")
    if band:
        top = [(sx(p['elapsed_hours']), sy(max(getter(p, n) for n in names))) for p in polls]
        bot = [(sx(p['elapsed_hours']), sy(min(getter(p, n) for n in names))) for p in polls]
        pts = top + bot[::-1]
        out.append("\\fill[band] " + " -- ".join(f"({x:.3f},{y:.3f})" for x, y in pts) + " -- cycle;")
    for i, n in enumerate(names, 1):
        pts = [(sx(p['elapsed_hours']), sy(getter(p, n))) for p in polls]
        out.append(f"\\draw[c{i}] " + " -- ".join(f"({x:.3f},{y:.3f})" for x, y in pts) + ";")
    out.append(f"\\node[axlab,rotate=90] at ({x0-(1.12 if letter == 'b' else 0.92):.3f},{H/2:.3f}) {{{label}}};")
    out.append(f"\\node[ptlab,anchor=south west] at ({x0+0.05:.3f},{H+0.02:.3f}) {{({letter})}};")
    return out

raw = lambda p, n: p[n]
chg = lambda p, n: p[n] - polls[0][n]
lines = ["\\begin{tikzpicture}[x=0.95cm,y=0.95cm,line width=0.4pt]"]
lines += panel(0.0, 2160, 2385, [2200, 2250, 2300, 2350], raw, "Overall rating", "a", band=True)
lines += panel(XB, -15, 200, [0, 50, 100, 150], chg, "Change since start", "b")
lx = (XB + W) / 2 - 5 * 1.25 / 2
for i, n in enumerate(names, 1):
    x = lx + (i - 1) * 1.35
    lines.append(f"\\draw[c{i},line width=0.8pt] ({x:.2f},-0.62) -- ({x+0.45:.2f},-0.62);")
    lines.append(f"\\node[axlab,anchor=west] at ({x+0.52:.2f},-0.62) {{B$_{i}$}};")
lines.append("\\end{tikzpicture}")
(HERE / "fig_noise.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

# Release the plotted values as a table (decoded from the rounded coordinates).
data = HERE / "data"
data.mkdir(exist_ok=True)
with (data / "fig1_overall_snapshots.csv").open("w", encoding="utf-8", newline="\n") as out:
    out.write("snapshot,elapsed_hours," + ",".join(f"{n}_overall" for n in names) + "\n")
    for i, p in enumerate(polls):
        out.write(f"{i},{p['elapsed_hours']:.3f}," + ",".join(f"{p[n]:.1f}" for n in names) + "\n")
print("initial:", {n: round(polls[0][n], 1) for n in names})
print("final:", {n: round(polls[-1][n], 1) for n in names})
print("change range:", min(chg(p, n) for p in polls for n in names), max(chg(p, n) for p in polls for n in names))
