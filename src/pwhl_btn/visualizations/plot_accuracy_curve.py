"""
plot_accuracy_curve.py — Spearman rank correlation vs season progress chart.

Season 7 is hardcoded (complete, values fixed).
Season 8 is pulled live from the DB at the current season progress point
and updates automatically as games are played.

Outputs:
    output/accuracy_curve.png
    output/accuracy_curve.svg

Run from: src/pwhl_btn/
    python visualizations/plot_accuracy_curve.py
"""

from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── Paths ─────────────────────────────────────────────────────────────────────
# Script lives at src/pwhl_btn/visualizations/plot_accuracy_curve.py
# PWHL_BTN_DIR = src/pwhl_btn/
PWHL_BTN_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR   = PWHL_BTN_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

from pwhl_btn.analytics.monte_carlo import run_validation

# ── Season 7 — hardcoded (season complete) ────────────────────────────────────
# Validation results from retrospective backtest against S7 final standings.
# These will never change.

S7_DATA = [
    # (pct, spearman,  significant)
    (33,   0.143,      False),
    (50,   0.771,      False),
    (67,   0.886,      True),
    (80,   0.943,      True),
    (90,   0.943,      True),
]

# ── Season 8 — live from DB ───────────────────────────────────────────────────
# Runs run_validation() at each checkpoint. Skips checkpoints that don't yet
# have enough games in the DB (< 10 completed games at that snapshot).

S8_SEASON_ID = 8
P_THRESHOLD  = 0.05

print("  Detecting current Season 8 progress from DB...")
S8_DATA = []   # list of (pct_int, spearman, significant) — single point

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from pwhl_btn.db.db_config import get_db_url

    engine  = create_engine(get_db_url())
    Session = sessionmaker(bind=engine)
    session = Session()

    row = session.execute(text("""
        SELECT
            COUNT(*)                                                 AS total_games,
            SUM(CASE WHEN game_status = 'final' THEN 1 ELSE 0 END) AS completed_games
        FROM games
        WHERE season_id = :sid
    """), {"sid": S8_SEASON_ID}).fetchone()
    session.close()

    total       = row.total_games     or 0
    completed   = row.completed_games or 0
    current_pct = completed / total if total > 0 else 0.0

    print(f"    Season 8: {completed}/{total} games complete ({current_pct:.0%})")

    if completed >= 10:
        result = run_validation(season_id=S8_SEASON_ID,
                                game_pct=current_pct, verbose=False)
        if result and result.get("spearman") is not None:
            spearman    = result["spearman"]
            p_value     = result["p_value"]
            significant = p_value is not None and p_value < P_THRESHOLD
            S8_DATA.append((round(current_pct * 100), round(spearman, 3), significant))
            sig_str = f"p={p_value:.3f}" if p_value is not None else "p=?"
            print(f"    rho={spearman:.3f}  {sig_str}")
    else:
        print("  Fewer than 10 games complete — skipping S8 point")

except Exception as e:
    print(f"  Could not retrieve Season 8 data: {e}")

if not S8_DATA:
    print("  Season 8 point will not be plotted")


# ── BTN brand colors ──────────────────────────────────────────────────────────
BG       = "#000000"
FG       = "#ffffff"
GRID     = "#2a2a2a"
S7_COLOR = "#8c52ff"
S8_COLOR = "#c9a8ff"   # lighter purple for S8 — distinct but on-brand
ANNOT    = "#8c52ff"

# ── Figure setup ──────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 5.5))
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

ax.set_xlim(25, 95)
ax.set_ylim(0.35, 1.05)
ax.set_xticks([33, 50, 67, 80, 90])
ax.set_xticklabels(["33%", "50%", "67%", "80%", "90%"],
                   color=FG, fontsize=10)
ax.set_yticks([0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
ax.set_yticklabels([f"{v:.1f}" for v in [0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]],
                   color=FG, fontsize=10)
ax.tick_params(colors=FG, which="both", length=0)
for spine in ax.spines.values():
    spine.set_edgecolor(GRID)
ax.yaxis.grid(True, color=GRID, linewidth=0.6, linestyle="--", zorder=0)
ax.xaxis.grid(True, color=GRID, linewidth=0.4, linestyle=":", zorder=0)
ax.set_axisbelow(True)

# Significance threshold annotation
ax.axhline(y=0.829, color=GRID, linewidth=0.8, linestyle="--", zorder=1)
ax.text(26.5, 0.840, "p < 0.05 threshold", color="#666666",
        fontsize=8, va="bottom", style="italic")

# ── Plot Season 7 ─────────────────────────────────────────────────────────────

s7_nosig = [(x, y) for x, y, s in S7_DATA if not s]
s7_sig   = [(x, y) for x, y, s in S7_DATA if s]

# Dashed line through non-significant region + bridge to first significant point
if s7_nosig and s7_sig:
    bridge_x = [x for x, y in s7_nosig] + [s7_sig[0][0]]
    bridge_y = [y for x, y in s7_nosig] + [s7_sig[0][1]]
    ax.plot(bridge_x, bridge_y, color=S7_COLOR, linewidth=1.6,
            linestyle="--", alpha=0.5, zorder=3)

# Solid line through significant points
if len(s7_sig) >= 2:
    ax.plot([x for x, y in s7_sig], [y for x, y in s7_sig],
            color=S7_COLOR, linewidth=2.2, linestyle="-",
            zorder=4, label="Season 7 — validation")

# Hollow markers + labels for non-significant points
for x, y in s7_nosig:
    ax.plot(x, y, "o", color=S7_COLOR, markersize=7,
            markerfacecolor=BG, markeredgewidth=1.5, zorder=5)
    ax.annotate(f"rho={y:.3f}", xy=(x, y), xytext=(5, 6),
                textcoords="offset points", color=S7_COLOR, fontsize=9, alpha=0.7)

# Filled markers + labels for significant points
label_offsets = {(67, 0.886): (-4, -18), (80, 0.943): (5, 6), (90, 0.943): (5, -16)}
for x, y in s7_sig:
    ax.plot(x, y, "o", color=S7_COLOR, markersize=8,
            markerfacecolor=S7_COLOR, zorder=5)
    dx, dy = label_offsets.get((x, y), (5, 6))
    ax.annotate(f"rho={y:.3f}", xy=(x, y), xytext=(dx, dy),
                textcoords="offset points", color=S7_COLOR, fontsize=9.5)

# ── Plot Season 8 ─────────────────────────────────────────────────────────────

if S8_DATA:
    s8_x   = [x for x, y, s in S8_DATA]
    s8_y   = [y for x, y, s in S8_DATA]
    s8_sig = [s for x, y, s in S8_DATA]

    # Always dashed — season in progress
    ax.plot(s8_x, s8_y, color=S8_COLOR, linewidth=2.0,
            linestyle="--", zorder=4, label="Season 8 — in progress")

    for x, y, sig in zip(s8_x, s8_y, s8_sig):
        # Hollow = not significant, filled = significant
        face = S8_COLOR if sig else BG
        ax.plot(x, y, "o", color=S8_COLOR, markersize=8,
                markerfacecolor=face, markeredgewidth=1.5, zorder=6)
        if sig:
            ax.annotate(f"ρ={y:.3f}", xy=(x, y), xytext=(5, 6),
                        textcoords="offset points", color=S8_COLOR, fontsize=9.5)

# ── Legend ────────────────────────────────────────────────────────────────────

handles = [mpatches.Patch(color=S7_COLOR,
                           label="Season 7 — validation (● p<0.05, ○ n.s.)")]
if S8_DATA:
    handles.append(mpatches.Patch(color=S8_COLOR,
                                   label="Season 8 — in progress (dashed)"))

ax.legend(handles=handles, loc="lower right", fontsize=9,
          facecolor="#0d0020", edgecolor=GRID,
          labelcolor=FG, framealpha=0.9)

# ── Labels & title ────────────────────────────────────────────────────────────

ax.set_xlabel("Season progress (% of games played)",
              color=FG, fontsize=11, labelpad=8)
ax.set_ylabel("Spearman rank correlation (ρ)",
              color=FG, fontsize=11, labelpad=8)
ax.set_title("Predictive Accuracy Improves as Season Progresses",
             color=FG, fontsize=15, fontweight="500", pad=14)
fig.text(0.99, 0.01, "ByTheNumbers · PWHL Analytics",
         ha="right", va="bottom", color="#444444", fontsize=7.5)

# ── Save ──────────────────────────────────────────────────────────────────────

plt.tight_layout(pad=1.4)
png_path = OUTPUT_DIR / "accuracy_curve.png"
svg_path = OUTPUT_DIR / "accuracy_curve.svg"
fig.savefig(png_path, dpi=200, bbox_inches="tight", facecolor=BG)
fig.savefig(svg_path, format="svg", bbox_inches="tight", facecolor=BG)
plt.close()

print(f"\n  Saved → {png_path}")
print(f"  Saved → {svg_path}")