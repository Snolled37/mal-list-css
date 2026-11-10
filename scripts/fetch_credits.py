"""Credits of every completed anime on my list, for the "most watched" profile card.

Per title, cached in data/credits/{id}.json (refreshed after 180 days):
  va      Japanese voice actors   [[people_id, "First Last", "Main"|"Supporting"], ...]
  staff   Director / Series Composition / Script   [[people_id, "First Last", ["Director", ...]], ...]
  songs   OP/ED artists           ["Masayuki Suzuki", ...]

Two MAL pages per title (/characters and the main page), 2 s apart like build_extras.
The first full run is ~600 titles x 2 pages (~40 min); after that only new titles are fetched.

  python scripts/fetch_credits.py [--user Snolled] [--max-fetch 80]
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_covers import fetch_list  # noqa: E402
from build_extras import Fetcher  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "credits"
KEEP_ROLES = {"Director", "Series Composition", "Script"}


def person(name: str) -> str:
    """'Kohara, Konomi' -> 'Konomi Kohara' (MAL lists family name first)."""
    name = html.unescape(name).strip()
    if ", " in name:
        last, first = name.split(", ", 1)
        return f"{first} {last}"
    return name


def parse_characters(page: str) -> tuple[list, list]:
    chars, _, staff_part = page.partition('<h2 class="h2_overwrite">Staff</h2>')
    va = []
    for block in chars.split('class="js-anime-character-table"')[1:]:
        role = "Main" if re.search(r">\s*Main(?:&nbsp;)?\s*<", block) else "Supporting"
        for pid, name in re.findall(
                r'people/(\d+)/[^"]*">([^<]+)</a>\s*</div>\s*<div class="spaceit_pad js-anime-character-language"'
                r'[^>]*>\s*Japanese', block):
            va.append([int(pid), person(name), role])
    staff = []
    for pid, name, roles in re.findall(
            r'<td valign="top" class="borderClass[^"]*">\s*<a href="https://myanimelist\.net/people/(\d+)/[^"]*">'
            r'([^<]+)</a>\s*<div class="spaceit_pad">\s*<small>([^<]+)</small>', staff_part):
        keep = sorted({r.strip() for r in roles.split(",")} & KEEP_ROLES)
        if keep:
            staff.append([int(pid), person(name), keep])
    return va, staff


def parse_songs(page: str) -> list[str]:
    out = []
    for raw in re.findall(r'<span class="theme-song-artist">\s*by\s*([^<]+)</span>', page):
        a = html.unescape(raw).strip()
        a = re.sub(r"\s*\((?:eps?|ep\.)[^)]*\)\s*$", "", a)  # trailing episode range
        if a and a not in out:
            out.append(a)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="Snolled")
    ap.add_argument("--max-fetch", type=int, default=2000, help="page requests this run")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    f = Fetcher(a.max_fetch)
    CACHE.mkdir(parents=True, exist_ok=True)
    today = dt.date.today()
    done = [it for it in fetch_list(a.user, "anime") if it["status"] == 2]
    todo = []
    for it in done:
        p = CACHE / f"{it['anime_id']}.json"
        if p.exists():
            age = today - dt.date.fromisoformat(json.loads(p.read_text(encoding="utf-8"))["fetched"])
            if age.days < 180:
                continue
        todo.append(it)
    print(f"{len(done)} completed, {len(todo)} to fetch, budget {a.max_fetch} pages", flush=True)
    n = 0
    for it in todo:
        if f.budget < 2:
            break
        aid = it["anime_id"]
        ch = f.get(f"https://myanimelist.net/anime/{aid}/x/characters")
        main_page = f.get(f"https://myanimelist.net/anime/{aid}")
        if not ch or not main_page:
            continue
        va, staff = parse_characters(ch)
        data = {"fetched": today.isoformat(), "va": va, "staff": staff, "songs": parse_songs(main_page)}
        (CACHE / f"{aid}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        n += 1
        if n % 25 == 0:
            print(f"  {n}/{len(todo)}", flush=True)
    print(f"fetched {n}; cached {len(list(CACHE.glob('*.json')))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
