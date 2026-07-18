"""
finale_render.py — Renders Season 8 Final Day game stakes slides.
"""
from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR   = Path(__file__).parent / "output"
ASSETS_DIR   = Path(__file__).resolve().parents[3] / "assets"

# Top scorer per team with confirmed player photo (player_id, display_name)
_TEAM_PLAYER: dict[str, tuple[int, str]] = {
    "MTL": (32,  "Laura Stacey"),
    "SEA": (210, "Julia Gosling"),
    "NY":  (205, "Sarah Fillier"),
    "BOS": (15,  "Alina Müller"),
    "TOR": (63,  "Daryl Watts"),
    "OTT": (58,  "Brianne Jenner"),
    "MIN": (23,  "Kelly Pannek"),
    "VAN": (11,  "Sophie Jaques"),
}


def _logo_path(team_code: str) -> str:
    p = ASSETS_DIR / "logos" / f"{team_code}_50x50.png"
    return p.resolve().as_posix() if p.exists() else ""


def _player_path(team_code: str) -> tuple[str, str]:
    """Return (absolute_posix_path, player_name) or ('', '') if not found."""
    if team_code not in _TEAM_PLAYER:
        return "", ""
    pid, name = _TEAM_PLAYER[team_code]
    p = ASSETS_DIR / "players" / "official" / f"{pid}.jpg"
    if p.exists():
        return p.resolve().as_posix(), name
    return "", ""

# ── Theme presets ──────────────────────────────────────────────────────────────
THEMES = {
    "gold": {  # 1st seed race
        "top_bar_gradient":     "linear-gradient(to right,#f5a623,#fbbf24,#f5a623)",
        "glow_color":           "rgba(245,166,35,0.15)",
        "corner_color":         "rgba(245,166,35,0.45)",
        "pts_color":            "#f5a623",
        "stamp_bg":             "rgba(245,166,35,0.10)",
        "stamp_border":         "rgba(245,166,35,0.50)",
        "stamp_dot_color":      "#f5a623",
        "stamp_text_color":     "#f5a623",
        "stake_bg":             "rgba(245,166,35,0.08)",
        "stake_border":         "rgba(245,166,35,0.45)",
        "stake_label_color":    "rgba(245,166,35,0.65)",
        "stake_headline_color": "#f5a623",
        "stake_headline_shadow":"0 0 50px rgba(245,166,35,0.40)",
        "scenario_team_color":  "#f5a623",
    },
    "cyan": {  # playoff survival
        "top_bar_gradient":     "linear-gradient(to right,#06b6d4,#0ea5e9,#06b6d4)",
        "glow_color":           "rgba(6,182,212,0.15)",
        "corner_color":         "rgba(6,182,212,0.45)",
        "pts_color":            "#06b6d4",
        "stamp_bg":             "rgba(6,182,212,0.10)",
        "stamp_border":         "rgba(6,182,212,0.50)",
        "stamp_dot_color":      "#06b6d4",
        "stamp_text_color":     "#06b6d4",
        "stake_bg":             "rgba(6,182,212,0.08)",
        "stake_border":         "rgba(6,182,212,0.45)",
        "stake_label_color":    "rgba(6,182,212,0.65)",
        "stake_headline_color": "#06b6d4",
        "stake_headline_shadow":"0 0 50px rgba(6,182,212,0.40)",
        "scenario_team_color":  "#06b6d4",
    },
    "muted": {  # season closer, no major stakes
        "top_bar_gradient":     "linear-gradient(to right,#5e17eb,#8c52ff,#f5a623)",
        "glow_color":           "rgba(140,82,255,0.10)",
        "corner_color":         "rgba(140,82,255,0.35)",
        "pts_color":            "rgba(255,255,255,0.55)",
        "stamp_bg":             "rgba(140,82,255,0.08)",
        "stamp_border":         "rgba(140,82,255,0.35)",
        "stamp_dot_color":      "#8c52ff",
        "stamp_text_color":     "#8c52ff",
        "stake_bg":             "rgba(255,255,255,0.04)",
        "stake_border":         "rgba(255,255,255,0.12)",
        "stake_label_color":    "rgba(255,255,255,0.30)",
        "stake_headline_color": "#fff",
        "stake_headline_shadow":"none",
        "scenario_team_color":  "rgba(255,255,255,0.55)",
    },
}

# ── Game data ──────────────────────────────────────────────────────────────────
GAMES = [
    {
        "slug":       "finale_01_mtl_at_sea",
        "theme":      "gold",
        "stamp_label":"1st Seed · Season Finale",
        "game_date":  "Saturday, April 25, 2026",
        "away_code":  "MTL", "away_name": "Montréal Victoire",
        "away_record":"16W · 6L · 2OTL", "away_pts": 60,
        "home_code":  "SEA", "home_name": "Seattle Torrent",
        "home_record":"8W · 16L · 4OTL",  "home_pts": 30,
        "stake_type": "1st Seed Implications",
        "stake_headline": "MTL CONTROLS\nTHEIR OWN FATE",
        "scenarios": [
            {
                "team":   "MTL",
                "need":   "Any point (win or OTL)",
                "result": "Locks 1st seed regardless of what BOS does",
            },
            {
                "team":   "MTL",
                "need":   "Regulation loss",
                "result": "1st seed goes to BOS if BOS wins in regulation — the only way MTL drops",
            },
            {
                "team":   "SEA",
                "need":   "Regulation win",
                "result": "Keeps BOS's 1st seed hopes alive — Seattle plays spoiler",
            },
        ],
        "context_note": "MTL leads BOS by 1 point. One point in any format tonight and the Victoire close out the regular season at the top.",
    },
    {
        "slug":       "finale_02_ny_at_bos",
        "theme":      "gold",
        "stamp_label":"1st Seed · Season Finale",
        "game_date":  "Saturday, April 25, 2026",
        "away_code":  "NY",  "away_name": "New York Sirens",
        "away_record":"9W · 14L · 3OTL", "away_pts": 36,
        "home_code":  "BOS", "home_name": "Boston Fleet",
        "home_record":"15W · 5L · 4OTL", "home_pts": 59,
        "stake_type": "1st Seed Implications",
        "stake_headline": "BOS NEEDS\nHELP FROM SEATTLE",
        "scenarios": [
            {
                "team":   "BOS",
                "need":   "Regulation win (3 pts → 62)",
                "result": "Takes 1st IF MTL loses in regulation — BOS cannot clinch on their own",
            },
            {
                "team":   "BOS",
                "need":   "OT win (2 pts → 61) or OTL (1 pt → 60)",
                "result": "Not enough — MTL keeps 1st even with a regulation loss (wins tiebreaker 16W vs 15W)",
            },
            {
                "team":   "NY",
                "need":   "Season finale",
                "result": "Eliminated — playing for pride and momentum into the offseason",
            },
        ],
        "context_note": "Even if BOS wins in regulation and MTL loses, BOS needs MTL to finish the game with 0 pts. An MTL OTL = 61 pts and BOS still trails at 62? No — 62 > 61, BOS takes 1st.",
    },
    {
        "slug":       "finale_03_tor_at_ott",
        "theme":      "cyan",
        "stamp_label":"Playoff Survival · Season Finale",
        "game_date":  "Saturday, April 25, 2026",
        "away_code":  "TOR", "away_name": "Toronto Sceptres",
        "away_record":"10W · 12L · 6OTL", "away_pts": 38,
        "home_code":  "OTT", "home_name": "Ottawa Charge",
        "home_record":"8W · 12L · 1OTL",  "home_pts": 41,
        "stake_type": "4th Playoff Seed On The Line",
        "stake_headline": "TOR MUST WIN\nIN REGULATION",
        "scenarios": [
            {
                "team":   "TOR",
                "need":   "Regulation win (38 + 3 = 41 pts)",
                "result": "Ties OTT at 41 pts — TOR wins tiebreaker on regulation wins (11W vs 8W). TOR in.",
            },
            {
                "team":   "TOR",
                "need":   "OT or SO win (38 + 2 = 40 pts)",
                "result": "Not enough. OTT takes the OTL point (41 + 1 = 42). OTT clinches 4th. TOR eliminated.",
            },
            {
                "team":   "OTT",
                "need":   "Any result",
                "result": "OT win or OTL = 42 pts, safe. Regulation win = 44 pts, done. Only a regulation loss with TOR reg win ends OTT's season.",
            },
        ],
        "context_note": "TOR has more regulation wins (10 vs 8) — the tiebreaker that matters tonight. But they can only use it if they close the gap in regulation. OT hockey leaves TOR one point short.",
    },
    {
        "slug":       "finale_04_min_at_van",
        "theme":      "muted",
        "stamp_label":"Season Finale",
        "game_date":  "Saturday, April 25, 2026",
        "away_code":  "MIN", "away_name": "Minnesota Frost",
        "away_record":"13W · 9L · 4OTL", "away_pts": 49,
        "home_code":  "VAN", "home_name": "Vancouver Goldeneyes",
        "home_record":"9W · 14L · 4OTL", "home_pts": 35,
        "stake_type": "Season Closer",
        "stake_headline": "PLAYOFF BOUND\nVS. PLAYING OUT",
        "scenarios": [
            {
                "team":   "MIN",
                "need":   "Clinched 3rd seed",
                "result": "3rd seed is locked regardless — MIN plays BOS or MTL in semis. Tonight is about momentum.",
            },
            {
                "team":   "VAN",
                "need":   "Eliminated",
                "result": "Playing their final game of the season. The Goldeneyes finish with 35 pts.",
            },
            {
                "team":   "NOTE",
                "need":   "Watch the scoreboard",
                "result": "MIN's playoff bracket depends on who wins the MTL vs BOS 1st seed race tonight.",
            },
        ],
        "context_note": "No stakes for either team directly — but MIN is watching the MTL/BOS race. A 1st seed for BOS means MIN opens the playoffs against Montreal.",
    },
]


def _make_env() -> Environment:
    return Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))


def _screenshot(html: str, slug: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"_render_{slug}.html"
    html_path.write_text(html, encoding="utf-8")
    out_path  = out_dir / f"{slug}.png"
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page    = browser.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(f"file://{html_path.resolve()}")
        page.wait_for_timeout(1200)
        page.screenshot(path=str(out_path), full_page=False)
        browser.close()
    html_path.unlink(missing_ok=True)
    print(f"  [ok] {out_path.name}")
    return out_path


def render_game_slide(game: dict, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    theme   = THEMES[game["theme"]]

    away_code = game["away_code"]
    home_code = game["home_code"]
    away_photo, away_player_name = _player_path(away_code)
    home_photo, home_player_name = _player_path(home_code)

    extra = {
        "away_logo":         _logo_path(away_code),
        "home_logo":         _logo_path(home_code),
        "away_player_photo": away_photo,
        "away_player_name":  away_player_name,
        "home_player_photo": home_photo,
        "home_player_name":  home_player_name,
    }

    ctx  = {**theme, **game, **extra}
    html = _make_env().get_template("season_finale_game.html").render(**ctx)
    return _screenshot(html, game["slug"], out_dir)


def render_hook_slide(out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    logos = {code: _logo_path(code) for code in ("MTL", "SEA", "NY", "BOS", "TOR", "OTT", "MIN", "VAN")}
    html = _make_env().get_template("season_finale_hook.html").render(logos=logos)
    return _screenshot(html, "finale_00_hook", out_dir)


def render_all(out_dir: Path | None = None) -> list[Path]:
    out_dir = Path(out_dir) if out_dir else OUTPUT_DIR
    return [render_hook_slide(out_dir)] + [render_game_slide(g, out_dir) for g in GAMES]
