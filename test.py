"""
Run from your repo root: python debug_photo.py
Prints exactly what _official_photo_uri sees when looking for Rebecca Leslie.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from db_queries import _THIS_DIR, _official_photo_uri

player_name = "Rebecca Leslie"
slug = player_name.lower().replace(" ", "_").replace("-", "_").replace("'", "")
candid_dir = _THIS_DIR / "assets" / "players"

print(f"_THIS_DIR:  {_THIS_DIR}")
print(f"slug:       {slug}")
print(f"candid_dir: {candid_dir}")
print()

for ext in ["jpg", "jpeg", "png", "webp"]:
    p = candid_dir / f"{slug}.{ext}"
    print(f"  checking {p} — {'EXISTS' if p.exists() else 'not found'}")

print()
result = _official_photo_uri(999, player_name)
print(f"Result: {result[:80] if result else None}")