"""
plot_accuracy_curve.py — Spearman rank correlation vs season progress chart.

Season 7 hardcoded (complete, values fixed).
Season 8 computed live from the DB (season complete) via run_validation at each
snapshot. Requires PWHL_DATABASE_URL to be set.

Outputs:
    output/accuracy_curve.png
    output/accuracy_curve.svg

Run from repo root:
    PYTHONPATH=src python src/pwhl_btn/visualizations/plot_accuracy_curve.py
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.lines as mlines

from pwhl_btn.analytics.monte_carlo import run_validation

PWHL_BTN_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR   = PWHL_BTN_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

S8_SEASON_ID = 8
SNAPSHOT_PCTS = [33, 50, 67, 80, 90]

# ── Season 7 — hardcoded (season complete) ────────────────────────────────────

S7_DATA = [
    # (pct, spearman, significant)
    (33,  0.143, False),
    (50,  0.771, False),
    (67,  0.886, True),
    (80,  0.943, True),
    (90,  0.943, True),
]

# ── Season 8 — computed live from the DB (season complete) ────────────────────

print("  Running Season 8 validation at each snapshot...")
S8_DATA = []
for pct in SNAPSHOT_PCTS:
    result = run_validation(season_id=S8_SEASON_ID, game_pct=pct / 100, verbose=False)
    if not result:
        print(f"    {pct}% — skipped (no data)")
        continue
    rho = result["spearman"]
    sig = result["p_value"] < 0.05
    S8_DATA.append((pct, rho, sig))
    print(f"    {pct}% — rho={rho:.3f}  p={result['p_value']:.3f}  {'*' if sig else ''}")

if not S8_DATA:
    raise SystemExit("  No Season 8 data returned — is season_id=8 populated in the DB?")

# ── BTN brand colors ──────────────────────────────────────────────────────────

BG       = "#ffffff"
FG       = "#000000"
GRID     = "#dddddd"
S7_COLOR = "#8c52ff"   # purple — Season 7
S8_COLOR = "#ff8c42"   # orange — Season 8 (colorblind-safe pair with purple)

# ── Figure setup ──────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(9, 5.5))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

ax.set_xlim(25, 95)
ax.set_ylim(0.0, 1.05)
ax.set_xticks([33, 50, 67, 80, 90])
ax.set_xticklabels(["33%", "50%", "67%", "80%", "90%"], color=FG, fontsize=13)
ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
ax.set_yticklabels(["0.0", "0.2", "0.4", "0.6", "0.8", "1.0"], color=FG, fontsize=13)
ax.tick_params(colors=FG, which="both", length=0)
for spine in ax.spines.values():
    spine.set_edgecolor(GRID)
ax.yaxis.grid(True, color=GRID, linewidth=0.6, linestyle="--", zorder=0)
ax.xaxis.grid(True, color=GRID, linewidth=0.4, linestyle=":", zorder=0)
ax.set_axisbelow(True)

# p < 0.05 threshold line
ax.axhline(y=0.829, color=GRID, linewidth=0.8, linestyle="--", zorder=1)
ax.text(26.5, 0.845, "p < 0.05 threshold", color="#999999",
        fontsize=8, va="bottom", style="italic")

# ── Season 7 ──────────────────────────────────────────────────────────────────

s7_nosig = [(x, y) for x, y, s in S7_DATA if not s]
s7_sig   = [(x, y) for x, y, s in S7_DATA if s]

# Solid line through all S7 points
s7_all = sorted([(x, y) for x, y, _ in S7_DATA], key=lambda p: p[0])
ax.plot([x for x, y in s7_all], [y for x, y in s7_all],
        color=S7_COLOR, linewidth=2.2, linestyle="-",
        zorder=4, label="Season 7 - validation")

# Hollow markers + muted labels for non-significant
label_offsets_nosig = {
    (33,  0.143): (5, 6),
    (50,  0.771): (5, -16),
}
for x, y in s7_nosig:
    ax.plot(x, y, "o", color=S7_COLOR, markersize=7,
            markerfacecolor=BG, markeredgewidth=1.5, zorder=5)
    dx, dy = label_offsets_nosig.get((x, y), (5, 6))
    ax.annotate(f"rho={y:.3f}", xy=(x, y), xytext=(dx, dy),
                textcoords="offset points", color=S7_COLOR,
                fontsize=12, alpha=0.65)

# Filled markers + labels for significant
label_offsets_s7 = {
    (67, 0.886): (-4, -18),
    (80, 0.943): (5, 6),
    (90, 0.943): (5, -16),
}
for x, y in s7_sig:
    ax.plot(x, y, "o", color=S7_COLOR, markersize=8,
            markerfacecolor=S7_COLOR, zorder=5)
    dx, dy = label_offsets_s7.get((x, y), (5, 6))
    ax.annotate(f"rho={y:.3f}", xy=(x, y), xytext=(dx, dy),
                textcoords="offset points", color=S7_COLOR, fontsize=12.5)

# ── Season 8 ──────────────────────────────────────────────────────────────────

s8_all = sorted(S8_DATA, key=lambda p: p[0])
ax.plot([x for x, _, _ in s8_all], [y for _, y, _ in s8_all],
        color=S8_COLOR, linewidth=2.2, linestyle="-",
        zorder=4, label="Season 8 - validation")

# Labels placed below the S8 line to avoid colliding with S7 labels above.
for x, y, sig in s8_all:
    ax.plot(x, y, "o", color=S8_COLOR, markersize=8 if sig else 7,
            markerfacecolor=S8_COLOR if sig else BG,
            markeredgewidth=1.5, zorder=5)
    ax.annotate(f"rho={y:.3f}", xy=(x, y), xytext=(5, -16),
                textcoords="offset points", color=S8_COLOR,
                fontsize=12.5 if sig else 12,
                alpha=1.0 if sig else 0.65)

# ── Legend ────────────────────────────────────────────────────────────────────

handles = [
    mlines.Line2D([], [], color=S7_COLOR, linewidth=2.2, linestyle="-",
                  marker="o", markersize=7, markerfacecolor=S7_COLOR,
                  label="Season 7 (6 teams)"),
    mlines.Line2D([], [], color=S8_COLOR, linewidth=2.2, linestyle="-",
                  marker="o", markersize=7, markerfacecolor=S8_COLOR,
                  label="Season 8 (8 teams)"),
    mlines.Line2D([], [], color=FG, linewidth=0, marker="o", markersize=7,
                  markerfacecolor=BG, markeredgecolor=FG, markeredgewidth=1.5,
                  label="hollow = not significant (p ≥ 0.05)"),
]
ax.legend(handles=handles, loc="lower right", fontsize=9,
          facecolor="#f5f5f5", edgecolor=GRID,
          labelcolor=FG, framealpha=0.9)

# ── Labels & title ────────────────────────────────────────────────────────────

ax.set_xlabel("Season progress (% of games played)",
              color=FG, fontsize=14, labelpad=8)
ax.set_ylabel("Spearman rank correlation (rho)",
              color=FG, fontsize=14, labelpad=8)
fig.text(0.99, 0.01, "ByTheNumbers · PWHL Analytics",
         ha="right", va="bottom", color="#444444", fontsize=7.5)

# ── Save ──────────────────────────────────────────────────────────────────────

plt.tight_layout(pad=1.4)
png_path = OUTPUT_DIR / "accuracy_curve.png"
svg_path = OUTPUT_DIR / "accuracy_curve.svg"
fig.savefig(png_path, dpi=200, bbox_inches="tight", facecolor=BG)
fig.savefig(svg_path, format="svg", bbox_inches="tight", facecolor=BG)
plt.close()

print(f"\n  Saved -> {png_path}")
print(f"  Saved -> {svg_path}")
