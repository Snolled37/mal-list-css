"""Build dist/extras-anime.css and dist/extras-manga.css — data-driven gimmicks.

What it generates (all as CSS custom properties the theme reads):
  * progress bar   — .progress-ID / .chapter-ID get --p (0..1) for unfinished titles
  * top-rated star — cover badge for titles tagged "Review Score : >=9/10"
  * season card    — hovering a Premiered link shows that season's 5 most-watched TV shows
  * studio card    — hovering a Studio link shows the studio's top 4 + its newest title

Season/studio data is scraped politely from MAL's own season and company pages
(2 s between requests) and cached in data/ so later runs only refresh what is stale.
(Jikan would be nicer but is not reachable from every network.)

Usage: python scripts/build_extras.py [--user Snolled] [--max-fetch 400]
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_covers import fetch_list  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DIST = ROOT / "dist"
UA = "Mozilla/5.0 (mal-list-css; +https://github.com/Snolled37/mal-list-css)"
TODAY = dt.date.today()
IMG = re.compile(r"https://cdn\.myanimelist\.net(?:/r/\d+x\d+)?(/images/anime/\d+/\d+)\.(?:jpe?g|webp)")
RATING = re.compile(r"^review\s*scores?\s*:\s*([\d.]+)\s*/\s*10$", re.I)


class Fetcher:
    def __init__(self, budget: int):
        self.budget = budget
        self.last = 0.0

    def get(self, url: str) -> str | None:
        if self.budget <= 0:
            return None
        wait = 2.0 - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.budget -= 1
        self.last = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:  # keep going; stale cache is fine
            print(f"  ! {url}: {e}", file=sys.stderr)
            return None


def webp(url: str) -> str | None:
    m = IMG.search(url or "")
    return f"https://cdn.myanimelist.net{m.group(1)}.webp" if m else None


def cards(page: str, marker: str) -> list[dict]:
    """Split a MAL season/company page into anime cards."""
    out = []
    parts = page.split(marker)[1:]
    for p in parts:
        # (no length cut: season cards embed long streaming-service JSON before the image)
        m_id = re.search(r'myanimelist\.net/anime/(\d+)/', p)
        m_t = re.search(r'class="link-title">([^<]+)<', p) or re.search(r'<div class="title">\s*<a [^>]+>([^<]+)<', p)
        img = None
        for m in re.finditer(r'(?:data-src|src)="(https://cdn\.myanimelist\.net[^"]+)"', p):
            img = webp(m.group(1))
            if img:
                break
        m_mem = re.search(r'js-members">(\d+)<', p) or re.search(r'class="users">([\d,]+)<', p)
        if not (m_id and m_t):
            continue
        out.append({
            "id": int(m_id.group(1)),
            "title": html.unescape(m_t.group(1)).strip(),
            "img": img,
            "members": int(m_mem.group(1).replace(",", "")) if m_mem else 0,
            "tv": "js-anime-type-1" in p[:400],
        })
    return out


def load_cache(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def stale(cache: dict | None, days: int) -> bool:
    if not cache:
        return True
    return (TODAY - dt.date.fromisoformat(cache["fetched"])).days >= days


def season_data(f: Fetcher, year: int, season: str) -> dict | None:
    path = DATA / "seasons" / f"{year}-{season.lower()}.json"
    cache = load_cache(path)
    days = 7 if year >= TODAY.year - 1 else 3650  # old seasons never change
    if not stale(cache, days):
        return cache
    page = f.get(f"https://myanimelist.net/anime/season/{year}/{season.lower()}")
    if not page:
        return cache
    # prefer the "TV (New)" section, fall back to everything
    tv_new = page.split('class="anime-header">TV (New)')
    scope = tv_new[1].split('class="anime-header">')[0] if len(tv_new) > 1 else page
    items = cards(scope, 'js-anime-category-producer') or cards(page, 'js-anime-category-producer')
    items.sort(key=lambda x: -x["members"])
    data = {"fetched": TODAY.isoformat(), "items": items[:5]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def studio_data(f: Fetcher, sid: int) -> dict | None:
    path = DATA / "studios" / f"{sid}.json"
    cache = load_cache(path)
    if not stale(cache, 30):
        return cache
    page = f.get(f"https://myanimelist.net/anime/producer/{sid}")
    if not page:
        return cache
    items = cards(page, '<div class="js-anime-category-studio')
    if not items:  # companies that are only listed as producer
        items = cards(page, '<div class="js-anime-category-')
    top = sorted(items, key=lambda x: -x["members"])[:4]
    newest = max(items, key=lambda x: x["id"]) if items else None
    data = {"fetched": TODAY.isoformat(), "top": top, "newest": newest, "count": len(items)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def detail_data(f: Fetcher, aid: int, kind: str = "anime") -> dict | None:
    """Rank + source (anime) / authors (manga) from the title's own MAL page. Cached 45 days."""
    path = DATA / kind / f"{aid}.json"
    cache = load_cache(path)
    if not stale(cache, 45):
        return cache
    page = f.get(f"https://myanimelist.net/{kind}/{aid}")
    if not page:
        return cache
    def field(name: str) -> str | None:
        m = re.search(r'<span class="dark_text">' + name + r':</span>\s*(.*?)</div>', page, re.S)
        return re.sub(r"<[^>]+>|\s+", " ", m.group(1)).strip() if m else None
    ranked = field("Ranked") or ""
    m = re.match(r"#(\d+)", ranked)
    data = {"fetched": TODAY.isoformat(), "rank": int(m.group(1)) if m else None,
            "source": html.unescape(field("Source") or "") or None}
    if kind == "manga":  # "Miura, Kentarou (Story & Art), Studio Gaga (Art)" -> names only
        authors = html.unescape(field("Authors") or "")
        data["authors"] = re.sub(r"\s*\([^)]*\)", "", authors).strip(" ,") or None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def css_str(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def short(s, n: int = 34) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def imgs(items: list[dict]) -> str:
    # keep one layer per title so cover N always lines up with line N of the text
    layers = [f"url({i['img']})" if i.get("img") else "linear-gradient(transparent,transparent)" for i in items]
    return ",".join(layers) if layers else "none"


def progress_rules(items: list[dict], kind: str) -> list[str]:
    rules = []
    for it in items:
        if kind == "anime":
            done, total, cls = it.get("num_watched_episodes") or 0, it.get("anime_num_episodes") or 0, "progress"
        else:
            done, total, cls = it.get("num_read_chapters") or 0, it.get("manga_num_chapters") or 0, "chapter"
        if it["status"] in (2, 6) or total <= 0 or done <= 0:
            continue  # completed = full, plan = empty: nothing to draw
        p = min(done / total, 1)
        rules.append(f".{cls}-{it[kind + '_id']}{{--p:{p:.3f}}}")
    return rules


def score_frames(items: list[dict], kind: str) -> list[str]:
    """Cover frame tier from the MAL score: 8 / 9 / 10 (tokens live in the theme)."""
    tiers = {
        1: "--cover-filter:grayscale(.85) brightness(.5) contrast(.95)",
        8: "--frame-pad:1.5px;--frame-bg:var(--f8-bg);--frame-glow:var(--f8-glow);"
           '--f-spark:"";--f-line:var(--f8-line)',
        9: "--frame-pad:2px;--frame-bg:var(--f9-bg);--frame-glow:var(--f9-glow);"
           '--f-spark:"✦";--f-spark-c:var(--f9-spark);--f-line:var(--f9-line);'
           "--f-gleam-bg:linear-gradient(115deg,transparent 40%,var(--f9-gleam) 50%,transparent 60%);"
           "--f-anim:mlc-gleam 7s ease-in-out infinite",
        # declared on the link itself so var(--ang) is the animated, per-element value
        10: "--frame-pad:2.5px;--frame-glow:var(--f10-glow);--frame-anim:mlc-ring;"
            "--frame-bg:conic-gradient(from var(--ang),var(--f10-c1),var(--f10-c2),var(--f10-c3),"
            "var(--f10-c1),var(--f10-c2),var(--f10-c1));"
            '--f-spark:"✦";--f-spark-c:var(--f10-spark);--f-spark-sh:40px 62px 0 var(--f10-spark);'
            "--f-line:var(--f10-line);"
            "--f-gleam-bg:linear-gradient(115deg,transparent 36%,var(--f10-gleam) 50%,transparent 64%);"
            "--f-anim:mlc-gleam 5s ease-in-out infinite,mlc-tw 2.4s ease-in-out infinite alternate",
    }
    rules = []
    for s, decl in tiers.items():
        ids = [it[kind + "_id"] for it in items if it.get("score") == s]
        if ids:
            sel = ",".join(f'body.ownlist .data.image a[href^="/{kind}/{i}/"]' for i in ids)
            rules.append(f"{sel}{{{decl}}}")
    return rules


def top_rated(items: list[dict], kind: str) -> list[int]:
    ids = []
    for it in items:
        for t in (it.get("tags") or "").split(","):
            m = RATING.match(t.strip())
            if m and float(m.group(1)) >= 9:
                ids.append(it[kind + "_id"])
    return ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="Snolled")
    ap.add_argument("--max-fetch", type=int, default=400)
    a = ap.parse_args()
    f = Fetcher(a.max_fetch)

    for kind in ("anime", "manga"):
        items = fetch_list(a.user, kind)
        out = ['@charset "UTF-8";', f"/* {kind} extras — generated by scripts/build_extras.py */"]
        out += progress_rules(items, kind)
        favs = [it[kind + "_id"] for it in items
                if {t.strip().lower() for t in (it.get("tags") or "").split(",")} & {"trophy", "favorite", "favourite"}]
        if favs:
            out.append(",".join(f"#tags-{i}" for i in favs) + "{--fav-on:var(--fav-glyph)}")
        out += score_frames(items, kind)

        for it in items:
            aid = it[kind + "_id"]
            d = detail_data(f, aid, kind) or {}
            # titles like "1" arrive as JSON numbers
            eng = it.get("anime_title_eng") if kind == "anime" else it.get("manga_english")
            title = str(eng or it.get(kind + "_title") or "")
            try:
                score = float(it.get(kind + "_score_val") or 0)
            except (TypeError, ValueError):
                score = 0
            l1 = f"{short(title, 44)}  ★ {score:.2f}" if score else f"{short(title, 44)}  ★ N/A"
            bits = []
            if d.get("rank"):
                bits.append(f"#{d['rank']:,} ranked")
            if it.get(kind + "_popularity"):
                bits.append(f"#{it[kind + '_popularity']:,} popular")
            if it.get(kind + "_total_members"):
                bits.append(f"{it[kind + '_total_members']:,} members")
            if kind == "anime":
                extra = f"Source: {d['source']}" if d.get("source") else ""
            else:
                extra = f"Authors: {short(d['authors'], 60)}" if d.get("authors") else ""
            lines = [l1, " · ".join(bits), extra]
            txt = "\\A ".join(css_str(l) for l in lines if l)
            out.append(f'.title>.link[href^="/{kind}/{aid}/"]{{--detail:"{txt}"}}')

        if kind == "anime":
            seasons = sorted({(it["anime_season"]["year"], it["anime_season"]["season"])
                              for it in items if it.get("anime_season")})
            for year, season in seasons:
                d = season_data(f, year, season)
                if not d or not d["items"]:
                    continue
                lines = [f"{season} {year} · most watched"] + [f"{n}. {short(x['title'])}" for n, x in enumerate(d["items"], 1)]
                txt = "\\A ".join(css_str(l) for l in lines)
                out.append(
                    f'.season a[href$="/{year}/{season.lower()}"]'
                    f'{{--card-img:{imgs(d["items"])};--card-txt:"{txt}"}}'
                )
            studios = sorted({s["id"] for it in items for s in (it.get("anime_studios") or [])})
            names = {s["id"]: s["name"] for it in items for s in (it.get("anime_studios") or [])}
            for sid in studios:
                d = studio_data(f, sid)
                if not d or not d.get("top"):
                    continue
                lines = [f"{names[sid]} · {d['count']} titles · top on MAL"]
                lines += [f"{n}. {short(x['title'])}" for n, x in enumerate(d["top"], 1)]
                if d.get("newest"):
                    lines.append(f"✦ newest: {short(d['newest']['title'], 30)}")
                txt = "\\A ".join(css_str(l) for l in lines)
                out.append(
                    f'.studio a[href$="/producer/{sid}"]'
                    f'{{--card-img:{imgs(d["top"])};--card-txt:"{txt}"}}'
                )
        # fold the banner rules in, so the list page needs no extra @import

        banners = DIST / f"banners-{kind}.css"
        if banners.exists():
            out.append(banners.read_text(encoding="utf-8").strip())
        path = DIST / f"extras-{kind}.css"
        path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
        print(f"{kind}: {len(out) - 2} rules, {path.stat().st_size:,} bytes, fetch budget left {f.budget}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
