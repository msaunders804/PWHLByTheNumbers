"""
run_expansion_video_script.py — PWHL Expansion Top 5 Video Script Generator

Generates a full, narration-ready video script covering the three data pillars:
  1. PWHL Takeover Tour attendance
  2. NHL infrastructure in the city
  3. Other women's sports teams in the city

Scores are pulled live from the scoring engine in analytics/expansion.py.

Usage:
    python -m pwhl_btn.jobs.run_expansion_video_script
    python -m pwhl_btn.jobs.run_expansion_video_script --format txt
    python -m pwhl_btn.jobs.run_expansion_video_script --format md
"""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

from pwhl_btn.analytics.expansion import score_cities

OUTPUT_DIR = Path(__file__).resolve().parents[3] / "render" / "output"

# ── Detailed city context (women's sports + NHL infra narrative) ───────────────
# Keyed by city name. Supplements the live scoring data with narration detail.

CITY_DETAIL: dict[str, dict] = {
    "Washington": {
        "nhl_infra": (
            "The Capitals are one of the NHL's marquee franchises — 2018 Stanley Cup champions, "
            "Ovechkin's house, Capital One Arena running at 98% capacity last season. "
            "The league knows how to run a hockey operation in DC, and corporate sponsorship "
            "dollars are deep. PWHL would inherit an infrastructure playbook, not build one from scratch."
        ),
        "womens_sports": (
            "Washington is the best women's professional sports city in the United States — full stop. "
            "The Washington Spirit won the NWSL Championship in 2021. The Washington Mystics are a "
            "WNBA powerhouse with a fanbase that shows up. DC has demonstrated, repeatedly, that it will "
            "pay for women's sports. That is not a given in most cities."
        ),
        "tour_context": "one game — 17,228 people",
        "tour_detail": (
            "One game. 17,228 people. That's not a fluke — that's the third-highest single-game "
            "Takeover Tour attendance in the entire dataset, and DC doesn't even have a team to root for. "
            "They just showed up."
        ),
        "wildcard": (
            "The only mark against Washington is geography — it deepens the east-coast concentration "
            "the PWHL already has. But when your women's sports culture is this strong, geography "
            "becomes a secondary argument."
        ),
    },
    "Calgary": {
        "nhl_infra": (
            "The Calgary Flames are a passionate Canadian market. Scotiabank Saddledome "
            "runs near capacity, the corporate hockey sponsorship culture in Calgary is strong, "
            "and the city is actively building a new arena — the Calgary Event Centre — that "
            "could reshape what a PWHL home venue looks like in this market long-term."
        ),
        "womens_sports": (
            "Calgary doesn't have an NWSL or WNBA team — it's Canada, so that's expected — "
            "but what it does have is serious amateur women's hockey infrastructure. Alberta "
            "has produced a disproportionate share of PWHL talent. This is a hockey province. "
            "Women's hockey has roots here that go deeper than any professional league."
        ),
        "tour_context": "one game — 16,150 people",
        "tour_detail": (
            "16,150 fans in a single game. Calgary didn't just show up — they showed out. "
            "This is the second-highest attendance of any Takeover Tour stop in the data, "
            "and city leaders have been vocal: Calgary wants a PWHL team. "
            "The data is backing them up."
        ),
        "wildcard": (
            "The geographic case for Calgary is arguably the strongest in the dataset. "
            "The PWHL is east-heavy. VAN and SEA anchor the Pacific. Calgary fills the "
            "Alberta gap and creates a natural Alberta-BC corridor rivalry that writes itself."
        ),
    },
    "Denver": {
        "nhl_infra": (
            "Colorado Avalanche won the Stanley Cup in 2022 and built genuine next-generation "
            "hockey fans in the process. Ball Arena runs at 95%+ capacity. Denver has gone "
            "from an afterthought hockey market to one of the most energized in the western US "
            "in less than a decade. The groundwork is laid."
        ),
        "womens_sports": (
            "No NWSL team yet — though the Colorado Spirit is coming in 2026, which is actually "
            "a bullish signal for women's sports investment in the market. The Colorado Mammoth "
            "(NLL) demonstrates Denver fans will show up for non-NBA, non-NFL sports. "
            "The Denver women's college sports scene, especially CU Boulder, feeds real demand."
        ),
        "tour_context": "two games — 13,562 average",
        "tour_detail": (
            "Two Takeover Tour games, 13,562 average attendance. That's not a single sellout "
            "spike — that's consistency. Denver fans came back. For games featuring teams "
            "they have zero connection to. That's the data point that matters."
        ),
        "wildcard": (
            "Denver scores a perfect 10 on geographic balance — the only city in the dataset to do so. "
            "The PWHL has one US inland team. MIN is alone in the middle of the country. "
            "Denver doesn't just make the league better — it makes the map make sense."
        ),
    },
    "Detroit": {
        "nhl_infra": (
            "Original Six. That's the entire argument. The Detroit Red Wings are one of the "
            "most storied franchises in professional sports. Little Caesars Arena is modern, "
            "well-run, and hockey is woven into the cultural identity of this city in a way "
            "that takes most markets generations to build. Detroit already has it."
        ),
        "womens_sports": (
            "This is where Detroit's case gets complicated. No NWSL team. No WNBA team. "
            "Detroit has shown appetite for women's sports but lacks the existing professional "
            "infrastructure that Washington or Chicago can point to. It's the biggest gap "
            "in an otherwise compelling dossier."
        ),
        "tour_context": "two games — 12,781 average",
        "tour_detail": (
            "Two games, 12,781 average. Detroit fans showed up twice — and they weren't "
            "watching their team. The hockey culture here is so deep that even a neutral "
            "site PWHL game draws five figures. That's a market that converts."
        ),
        "wildcard": (
            "Detroit sits at the crossroads of the US Midwest and Ontario. A Detroit PWHL team "
            "would draw from Windsor, Ontario naturally — a cross-border fanbase the league "
            "currently doesn't serve."
        ),
    },
    "Chicago": {
        "nhl_infra": (
            "Three Stanley Cups in six years built a fanbase that outlasted the dynasty. "
            "Chicago is in a rebuilding year, but the United Center is one of the largest "
            "and most profitable buildings in the NHL. The Blackhawks know how to market "
            "hockey and they know how to fill an arena. The operational infrastructure "
            "is world-class."
        ),
        "womens_sports": (
            "Chicago might have the best existing women's professional sports infrastructure "
            "of any city in this analysis outside Washington. The Chicago Red Stars are a "
            "founding NWSL club with a real supporter culture. The Chicago Sky won the "
            "2021 WNBA Championship. This is a city that has proven it will invest in and "
            "show up for women's professional sports — repeatedly."
        ),
        "tour_context": "two games — 8,622 average",
        "tour_detail": (
            "Two games, 8,622 average. That's the lowest tour attendance in this top 5 — "
            "and it's also the reason Chicago ranks fifth despite having arguably the best "
            "women's sports infrastructure of any city here. Fans showed up, but not at "
            "the same rate as the other markets. The model weights revealed preference heavily."
        ),
        "wildcard": (
            "Chicago is the largest hockey market in the US without a PWHL team. "
            "Wintrust Arena — near-ideal at 10,000 seats — is available and right-sized. "
            "The infrastructure exists today. Chicago ranks fifth on attendance data, "
            "but on pure readiness, it might be first."
        ),
    },
}


# ── Formatting helpers ─────────────────────────────────────────────────────────

def _wrap(text: str, width: int = 80, indent: str = "") -> str:
    return textwrap.fill(text, width=width, initial_indent=indent,
                         subsequent_indent=indent)


def _section(title: str, char: str = "─", width: int = 72) -> str:
    return f"\n{char * width}\n  {title}\n{char * width}"


def _score_bar(score: float, width: int = 12) -> str:
    filled = round((score / 10.0) * width)
    return "█" * filled + "░" * (width - filled)


def _pillar_line(label: str, score: float, weight: str) -> str:
    return f"  [{_score_bar(score)}]  {score:.1f}/10  {label} ({weight})"


# ── Script generator ───────────────────────────────────────────────────────────

def generate_script(cities: list[dict]) -> str:
    lines: list[str] = []

    def ln(s: str = "") -> None:
        lines.append(s)

    def cue(text: str) -> None:
        lines.append(f"  [ON SCREEN: {text}]")

    def narration(text: str, width: int = 72) -> None:
        wrapped = textwrap.fill(text.strip(), width=width,
                                initial_indent="  ", subsequent_indent="  ")
        lines.append(wrapped)

    # ── TITLE ──────────────────────────────────────────────────────────────────
    ln("=" * 72)
    ln("  PWHL BY THE NUMBERS")
    ln("  \"Where Should the PWHL Expand Next? I Ran the Numbers.\"")
    ln("  TOP 5 EXPANSION CITIES — VIDEO SCRIPT")
    ln(f"  Data through: Season 8 Takeover Tour  |  3 Pillars  |  Weighted Score")
    ln("=" * 72)

    # ── HOOK (0:00–0:12) ──────────────────────────────────────────────────────
    ln(_section("HOOK  [0:00 – 0:12]"))
    ln()
    cue("Black screen → PWHL logo fades in")
    ln()
    narration(
        "The PWHL announced it's expanding. Two new teams are coming. "
        "The question everyone's arguing about is WHERE — and most of those arguments "
        "are vibes. I scored five cities on three actual data sources and ranked them. "
        "Number one might genuinely surprise you."
    )
    ln()
    cue("Text overlay: 'I scored 5 cities. 3 data sources. Here's the ranking.'")

    # ── METHODOLOGY (0:12–0:35) ───────────────────────────────────────────────
    ln()
    ln(_section("METHODOLOGY SETUP  [0:12 – 0:35]"))
    ln()
    cue("Graphic: 3 pillars with icons and weights")
    cue("  Pillar 1 → 🏒  NHL Infrastructure (25%)")
    cue("  Pillar 2 → 🎟️  PWHL Takeover Tour Attendance (35%)")
    cue("  Pillar 3 → ⚽  Other Women's Pro Sports (20%)")
    cue("  + Arena Fit (10%)  |  Geographic Balance (10%)")
    ln()
    narration(
        "Three main pillars. First: how strong is the NHL market in that city — "
        "because the PWHL has partnered with NHL infrastructure from day one, and that "
        "relationship matters. Second, and this is the biggest weight at 35%: "
        "Takeover Tour attendance. The PWHL has actually played games in these cities. "
        "We know how many people showed up. That's revealed preference — not a survey, "
        "not a poll, actual people paying actual money. Third: other women's professional "
        "sports teams. If a city already supports an NWSL or WNBA franchise, it's demonstrated "
        "it will spend on women's sports. That's not nothing."
    )
    ln()
    cue("Text: 'Tour attendance weighted highest — it's the only real demand signal we have'")

    # ── COUNTDOWN ─────────────────────────────────────────────────────────────
    for c in reversed(cities):
        rank = c["rank"]
        city = c["city"]
        detail = CITY_DETAIL.get(city, {})
        ps = c["pillar_scores"]

        start_times = {5: "0:35", 4: "1:30", 3: "2:20", 2: "3:10", 1: "4:00"}
        end_times   = {5: "1:30", 4: "2:20", 3: "3:10", 2: "4:00", 1: "5:10"}

        ln()
        ln(_section(
            f"#{rank}  {city.upper()}, {c['state_province']}  "
            f"[{start_times[rank]} – {end_times[rank]}]  "
            f"(Composite: {c['composite_score']:.2f}/10)"
        ))
        ln()

        # Score card on screen
        cue(f"Scorecard graphic — {city}")
        ln(f"  {_pillar_line('NHL Infrastructure',        ps['nhl_market'],      '25%')}")
        ln(f"  {_pillar_line('Takeover Tour Attendance',  ps['tour_attendance'],  '35%')}")
        womens_label = "Women's Pro Sports"
        ln(f"  {_pillar_line(womens_label,               ps['womens_sports'],   '20%')}")
        ln(f"  {_pillar_line('Arena Fit',                 ps['arena_fit'],       '10%')}")
        ln(f"  {_pillar_line('Geographic Balance',        ps['geo_balance'],     '10%')}")
        ln(f"  {'─' * 50}")
        ln(f"  COMPOSITE:  {c['composite_score']:.2f} / 10")
        ln()

        # --- PILLAR 1: Tour Attendance ----------------------------------------
        cue(f"Tour attendance graphic: {detail.get('tour_context', 'data')}")
        ln()
        narration(
            detail.get("tour_detail",
                       f"{city} had a Takeover Tour average of {c['tour_avg_att']:,} "
                       f"across {c['tour_game_count']} game(s).")
        )
        ln()

        # --- PILLAR 2: NHL Infrastructure ------------------------------------
        cue(f"NHL logo: {c['nhl_team']}")
        ln()
        narration(detail.get("nhl_infra",
                              f"NHL infrastructure: {c['nhl_market_notes']}"))
        ln()

        # --- PILLAR 3: Women's Sports -----------------------------------------
        cue("Women's sports logos in city")
        ln()
        narration(detail.get("womens_sports",
                              c.get("womens_sports_notes", "")))
        ln()

        # --- Wildcard / what makes this city interesting ----------------------
        if detail.get("wildcard"):
            cue("Stat callout")
            narration(detail["wildcard"])
            ln()

        # --- Narrative hook ---------------------------------------------------
        hook = c.get("narrative_hook", "")
        if hook:
            ln(f'  BEAT: "{hook}"')
            ln()

    # ── OUTRO / CTA (5:10–5:30) ───────────────────────────────────────────────
    ln(_section("OUTRO + CTA  [5:10 – 5:30]"))
    ln()
    cue("Full top 5 scorecard on screen, all cities ranked")
    ln()

    winner = cities[0]
    runner = cities[1]
    narration(
        f"So there it is. {winner['city']} comes out on top — driven by the strongest "
        f"women's sports culture in the US and the third-highest single-game attendance "
        f"in the entire Takeover Tour dataset. {runner['city']} is right behind it "
        f"and makes the strongest geographic case: the PWHL is east-heavy, and {runner['city']} "
        f"fills a gap that no other city in this analysis can."
    )
    ln()
    narration(
        "But here's the thing — the PWHL is adding TWO teams. The data suggests "
        f"{winner['city']} and {runner['city']} aren't competing. They're the answer."
    )
    ln()
    cue("Comment bait text overlay")
    narration(
        "Which city do YOU think gets the next PWHL team? Drop it in the comments — "
        "and if you think I got the ranking wrong, tell me which data point you'd weight differently."
    )
    ln()
    cue("Subscribe / follow CTA → end card")
    ln()
    ln("=" * 72)
    ln(f"  FINAL RANKING SUMMARY")
    ln("=" * 72)
    for c in cities:
        att_str = f"{c['tour_avg_att']:,}" if c["tour_avg_att"] else "No data"
        ln(f"  #{c['rank']}  {c['city']:<12}  score={c['composite_score']:.3f}  "
           f"tour_avg={att_str}  ({c['tour_game_count']}g)")
    ln()

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import sys, io
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Generate PWHL Expansion Top 5 Video Script"
    )
    parser.add_argument(
        "--format", choices=["txt", "md", "print"], default="print",
        help="Output format: print to terminal (default), txt file, or md file"
    )
    args = parser.parse_args()

    print("  Loading expansion scores...")
    cities = score_cities()

    script = generate_script(cities)

    if args.format == "print":
        print(script)
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ext = args.format
        out_path = OUTPUT_DIR / f"expansion_video_script.{ext}"
        out_path.write_text(script, encoding="utf-8")
        print(f"  Script written to {out_path}")


if __name__ == "__main__":
    main()
