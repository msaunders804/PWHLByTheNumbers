"""
plot_rank_error.py — Model accuracy across season snapshots.

Bar chart showing mean absolute rank error (MAE) at 33%, 67%, and 90% of
Season 7, with Spearman ρ annotated on each bar.  Lower bars = better
prediction; bars are shaded by statistical significance (p < 0.05).

Outputs:
    output/rank_error.png
    output/rank_error.svg

Run from repo root:
    PYTHONPATH=src python src/pwhl_btn/visualizations/plot_rank_error.py
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

PWHL_BTN_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR   = PWHL_BTN_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

from pwhl_btn.analytics.monte_carlo import run_validation

# ── Config ─────────────────────────────────────────────────────────────────────

S7_SEASON_ID = 5
SNAPSHOTS = [
    (0.33, "33%"),
    (0.67, "67%"),
    (0.90, "90%"),
]

# White-background brand palette
BG          = "#ffffff"
FG          = "#000000"
GRID        = "#dddddd"
BAR_SIG     = "#8c52ff"   # significant (p < 0.05)
BAR_NOSIG   = "#c9b8ff"   # not significant
ANNOT_COLOR = "#000000"

# ── Fetch data ─────────────────────────────────────────────────────────────────

print("  Running Season 7 validation at each snapshot...")
records = []

for pct, label in SNAPSHOTS:
    print(f"    {label} ({pct:.0%})...")
    result = run_validation(season_id=S7_SEASON_ID, game_pct=pct, verbose=False)
    if not result or not result.get("teams"):
        print(f"      skipped (no data)")
        continue

    teams = result["teams"]
    mae   = float(np.mean([abs(d["pred_rank"] - d["actual_rank"])
                            for d in teams.values()]))
    records.append({
        "label":  label,
        "mae":    mae,
        "rho":    result["spearman"],
        "pval":   result["p_value"],
        "sig":    result["p_value"] < 0.05,
    })
    print(f"      MAE={mae:.2f}  rho={result['spearman']:.3f}  p={result['p_value']:.3f}")

if not records:
    print("  No data returned — is season_id=5 in the DB?")
    raise SystemExit(1)

# ── Figure ─────────────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(7, 5))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

labels   = [r["label"] for r in records]
maes     = [r["mae"]   for r in records]
colors   = [BAR_SIG if r["sig"] else BAR_NOSIG for r in records]
x        = np.arange(len(records))
bar_w    = 0.52

bars = ax.bar(x, maes, width=bar_w, color=colors,
              edgecolor=[BAR_SIG if r["sig"] else BAR_NOSIG for r in records],
              linewidth=1.2, zorder=2)

# Annotate each bar with ρ and significance marker
for i, (bar, rec) in enumerate(zip(bars, records)):
    sig_marker = " *" if rec["sig"] else ""
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() + 0.04,
        f"ρ = {rec['rho']:.3f}{sig_marker}",
        ha="center", va="bottom",
        color=FG, fontsize=10, fontweight="600",
    )

# Reference line at MAE = 1.0 (off by one rank on average)
ax.axhline(1.0, color=GRID, linewidth=1.0, linestyle="--", zorder=1)
ax.text(len(records) - 0.5, 1.03, "±1 rank", color="#aaaaaa",
        fontsize=8, ha="right", va="bottom", style="italic")

# ── Axes ───────────────────────────────────────────────────────────────────────

ax.set_xticks(x)
ax.set_xticklabels(labels, color=FG, fontsize=12)
ax.set_xlim(-0.5, len(records) - 0.5)
ax.set_ylim(0, max(maes) * 1.45)

ax.set_ylabel("Mean Absolute Rank Error", color=FG, fontsize=11, labelpad=8)
ax.set_xlabel("Season Snapshot", color=FG, fontsize=11, labelpad=8)

ax.tick_params(axis="y", colors=FG, labelsize=9, length=0)
ax.tick_params(axis="x", length=0)
ax.yaxis.grid(True, color=GRID, linewidth=0.5, linestyle="--", zorder=0)
ax.set_axisbelow(True)

for spine in ax.spines.values():
    spine.set_visible(False)

# ── Legend ─────────────────────────────────────────────────────────────────────

from matplotlib.patches import Patch
legend_handles = [
    Patch(facecolor=BAR_SIG,   label="p < 0.05 (significant)"),
    Patch(facecolor=BAR_NOSIG, label="p ≥ 0.05"),
]
ax.legend(handles=legend_handles, loc="upper right",
          fontsize=8.5, facecolor="#f5f5f5", edgecolor=GRID,
          labelcolor=FG, framealpha=0.9)

# ── Title & watermark ──────────────────────────────────────────────────────────

ax.set_title(
    "Monte Carlo Model Accuracy by Season Snapshot\n24-25 Season (Season 7)",
    color=FG, fontsize=13, fontweight="500", pad=10,
)
fig.text(0.99, 0.01, "ByTheNumbers · PWHL Analytics",
         ha="right", va="bottom", color="#aaaaaa", fontsize=7.5)

# ── Save ───────────────────────────────────────────────────────────────────────

plt.tight_layout(pad=1.4)
png_path = OUTPUT_DIR / "rank_error.png"
svg_path = OUTPUT_DIR / "rank_error.svg"
fig.savefig(png_path, dpi=200, bbox_inches="tight", facecolor=BG)
fig.savefig(svg_path, format="svg", bbox_inches="tight", facecolor=BG)
plt.close()

print(f"\n  Saved -> {png_path}")
print(f"  Saved -> {svg_path}")
