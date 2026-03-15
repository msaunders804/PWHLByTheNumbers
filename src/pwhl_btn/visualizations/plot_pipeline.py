"""
plot_pipeline.py — PWHL Analytics pipeline architecture diagram (vertical).

Outputs:
    output/pipeline.png
    output/pipeline.svg

Run from repo root:
    PYTHONPATH=src python src/pwhl_btn/visualizations/plot_pipeline.py
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Brand colors ──────────────────────────────────────────────────────────────

BG          = "#000000"
FG          = "#ffffff"
PURPLE      = "#8c52ff"
PURPLE_DIM  = "#3d2470"
PURPLE_EDGE = "#b38aff"
GREY_BOX    = "#111111"
GREY_EDGE   = "#2a2a2a"
GREY_TEXT   = "#888888"
ARROW_COLOR = "#8c52ff"

# ── Pipeline stages ───────────────────────────────────────────────────────────

STAGES = [
    {
        "label":    "01",
        "title":    "DATA INGESTION",
        "subtitle": "PWHL HockeyTech API",
        "accent":   True,
    },
    {
        "label":    "02",
        "title":    "FEATURE ENGINEERING",
        "subtitle": "Team Strength Metrics",
        "accent":   False,
    },
    {
        "label":    "03",
        "title":    "MONTE CARLO SIMULATION",
        "subtitle": "10,000 Season Simulations",
        "accent":   True,
    },
    {
        "label":    "04",
        "title":    "ANALYTICS OUTPUT",
        "subtitle": "Playoff Probabilities\nStandings Forecast",
        "accent":   False,
    },
]

# ── Layout constants ──────────────────────────────────────────────────────────

FIG_W   = 15.42
FIG_H   = 9.82
BOX_W   = 13.0
BOX_H   = 1.60
BOX_X   = (FIG_W - BOX_W) / 2
HDR     = 1.00
BOT     = 0.30
STEP    = (FIG_H - HDR - BOT) / len(STAGES)
ARROW_H = STEP - BOX_H
TOP_Y   = FIG_H - HDR

# ── Figure ────────────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, FIG_W)
ax.set_ylim(0, FIG_H)
ax.axis("off")

# ── Header ────────────────────────────────────────────────────────────────────

ax.text(FIG_W / 2, FIG_H - 0.40,
        "Predictive Analytics Pipeline",
        ha="center", va="center",
        color=FG, fontsize=26, fontweight="700")

ax.plot([BOX_X, BOX_X + BOX_W], [FIG_H - 0.70, FIG_H - 0.70],
        color=PURPLE, linewidth=1.8, alpha=0.6)

# ── Draw stages ───────────────────────────────────────────────────────────────

for i, stage in enumerate(STAGES):
    box_y = TOP_Y - i * STEP
    cy    = box_y - BOX_H / 2

    face  = PURPLE_DIM  if stage["accent"] else GREY_BOX
    edge  = PURPLE_EDGE if stage["accent"] else GREY_EDGE
    lw    = 3.5         if stage["accent"] else 1.8

    ax.add_patch(FancyBboxPatch(
        (BOX_X, box_y - BOX_H), BOX_W, BOX_H,
        boxstyle="round,pad=0.09",
        facecolor=face, edgecolor=edge, linewidth=lw, zorder=2,
    ))

    # Step number badge
    badge_x = BOX_X + 0.38
    ax.text(badge_x, cy, stage["label"],
            ha="center", va="center",
            color=PURPLE_EDGE if stage["accent"] else PURPLE,
            fontsize=18, fontweight="700", fontfamily="monospace", zorder=3)

    # Vertical divider
    div_x = BOX_X + 0.72
    ax.plot([div_x, div_x], [box_y - BOX_H + 0.16, box_y - 0.16],
            color=GREY_EDGE, linewidth=1.4, zorder=3)

    # Title
    text_x = div_x + 0.28
    ax.text(text_x, cy + 0.30, stage["title"],
            ha="left", va="center",
            color=FG, fontsize=20, fontweight="700", zorder=3)

    # Subtitle
    ax.text(text_x, cy - 0.30, stage["subtitle"],
            ha="left", va="center",
            color=GREY_TEXT, fontsize=16, linespacing=1.4, zorder=3)

    # Arrow to next stage
    if i < len(STAGES) - 1:
        arrow_top = box_y - BOX_H
        arrow_bot = arrow_top - ARROW_H
        ax.annotate(
            "", xy=(FIG_W / 2, arrow_bot + 0.05),
            xytext=(FIG_W / 2, arrow_top - 0.05),
            arrowprops=dict(
                arrowstyle="-|>",
                color=ARROW_COLOR, lw=2.5, mutation_scale=22,
            ),
            zorder=4,
        )

# ── Watermark ─────────────────────────────────────────────────────────────────

ax.text(FIG_W - 0.14, 0.06, "ByTheNumbers · PWHL Analytics",
        ha="right", va="bottom", color="#333333", fontsize=14)

# ── Save ──────────────────────────────────────────────────────────────────────

plt.tight_layout(pad=0)
png_path = OUTPUT_DIR / "pipeline.png"
svg_path = OUTPUT_DIR / "pipeline.svg"
fig.savefig(png_path, dpi=400, bbox_inches="tight", facecolor=BG)
fig.savefig(svg_path, format="svg", bbox_inches="tight", facecolor=BG)
plt.close()

print(f"  Saved -> {png_path}")
print(f"  Saved -> {svg_path}")
