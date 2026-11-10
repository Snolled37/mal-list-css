"""Images for the MAL profile "About Me" (BBCode only, no CSS) — Koisuru Asteroid theme.

  dist/profile/header.png        798 wide banner with the name
  dist/profile/btn-anime.png     link buttons (anime list / manga list / stacks & reviews)
  dist/profile/btn-manga.png
  dist/profile/btn-more.png
  dist/profile/stats.png         numbers + top genres + "currently watching" covers  (rebuilt daily)
  dist/profile/score-guide.png   how to read the list: Should ★, Review meter, cover frames

Font: Verdana (MAL's own body font). Windows ships it; the GitHub Action installs
ttf-mscorefonts-installer, so no font file lives in this repo.

Usage: python scripts/build_profile.py [--user Snolled]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_covers import cover_url, fetch_list  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "profile"
W = 798  # About Me width on desktop (logical px)
S = 2    # drawn at 2x, shown with [img width=...] so text stays sharp

# Koisuru Asteroid (manga-list palette)
BG, SURFACE, SURFACE2 = (21, 23, 31), (28, 31, 42), (35, 39, 54)
TEXT, MUTED, LINE = (230, 232, 239), (147, 153, 173), (50, 56, 73)
PINK, SKY, GOLD, LAV = (232, 180, 200), (185, 211, 234), (241, 210, 138), (205, 184, 239)
COPPER = [(246, 205, 185), (201, 130, 98), (154, 90, 69)]
SILVER = [(255, 255, 255), (196, 203, 216), (142, 151, 171)]
GOLDS = [(255, 246, 216), (233, 185, 73), (168, 120, 31)]

REVIEW = re.compile(r"^review\s*scores?\s*:\s*([\d.]+)\s*/\s*10$", re.I)


def font(bold: bool = False, size: int = 12) -> ImageFont.FreeTypeFont:
    """Verdana at `size` logical px (drawn at S x for sharp text)."""
    names = ["verdanab.ttf", "Verdana_Bold.ttf", "Verdana Bold.ttf"] if bold else ["verdana.ttf", "Verdana.ttf"]
    dirs = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/msttcorefonts"), Path.home() / ".fonts"]
    for d in dirs:
        for n in names:
            if (d / n).exists():
                return ImageFont.truetype(str(d / n), round(size * S))
    sys.exit("Verdana not found (Windows: C:/Windows/Fonts; Ubuntu: apt install ttf-mscorefonts-installer)")


def sc(v):
    """Logical px -> real px."""
    if isinstance(v, (int, float)):
        return round(v * S)
    return type(v)(sc(x) for x in v)


class Pen:
    """ImageDraw that takes logical coordinates, so layouts read at 1x but render at S x."""

    def __init__(self, img: Image.Image):
        self.d = ImageDraw.Draw(img)

    def text(self, xy, s, font, fill, anchor="la"):
        self.d.text(sc(xy), s, font=font, fill=fill, anchor=anchor)

    def rect(self, box, r=0, fill=None, outline=None, width=1):
        self.d.rounded_rectangle(sc(box), sc(r), fill=fill, outline=outline,
                                 width=max(1, sc(width)) if outline else 0)

    def line(self, pts, fill, width=1):
        self.d.line(sc(pts), fill=fill, width=max(1, sc(width)))

    def star(self, cx, cy, r, fill):
        """5-point star as a polygon (Verdana has no star glyph)."""
        import math
        pts = []
        for i in range(10):
            rr = r if i % 2 == 0 else r * 0.45
            a = math.pi / 2 + i * math.pi / 5
            pts.append((sc(cx + rr * math.cos(a)), sc(cy - rr * math.sin(a))))
        self.d.polygon(pts, fill=fill)


def canvas(w: int, h: int, color=BG) -> Image.Image:
    return Image.new("RGBA", (sc(w), sc(h)), color + (255,))


def sky(img: Image.Image, seed: int, n: int, avoid: list[tuple]) -> None:
    """A sparse night sky drawn under the content: soft-glow pin stars plus a few
    four-point sparkles, kept out of the `avoid` boxes (logical px) so no star sits on text."""
    import random
    rnd = random.Random(seed)
    w, h = img.width / S, img.height / S
    glow = Image.new("RGBA", img.size)
    core = Image.new("RGBA", img.size)
    gd, cd = ImageDraw.Draw(glow), ImageDraw.Draw(core)
    tints = [(255, 255, 255), (255, 240, 214), (250, 222, 234), (214, 230, 248)]
    placed, tries = 0, 0
    while placed < n and tries < n * 40:
        tries += 1
        x, y = rnd.uniform(10, w - 10), rnd.uniform(8, h - 8)
        if any(x0 - 6 <= x <= x1 + 6 and y0 - 6 <= y <= y1 + 6 for x0, y0, x1, y1 in avoid):
            continue
        placed += 1
        c = rnd.choice(tints)
        big = rnd.random() < 0.18
        X, Y = sc(x), sc(y)
        if big:  # sparkle: thin tapered cross + glow
            r = sc(rnd.uniform(4, 6.5))
            gd.ellipse((X - r, Y - r, X + r, Y + r), fill=c + (90,))
            for k in range(r, 0, -1):
                a = int(230 * (1 - k / r) ** 1.6)
                cd.point([(X + k, Y), (X - k, Y), (X, Y + k), (X, Y - k)], fill=c + (a,))
            cd.ellipse((X - 1, Y - 1, X + 1, Y + 1), fill=c + (255,))
        else:  # pin star: 1-2 px core + faint halo
            a = rnd.randrange(110, 220)
            r = sc(rnd.choice([0.5, 0.5, 0.75, 1]))
            gd.ellipse((X - r * 3, Y - r * 3, X + r * 3, Y + r * 3), fill=c + (a // 4,))
            cd.ellipse((X - r, Y - r, X + r, Y + r), fill=c + (a,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(sc(2.5))))
    img.alpha_composite(core)


def rounded(img: Image.Image, r: int) -> Image.Image:
    """r in logical px."""
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, img.width - 1, img.height - 1), sc(r), fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), m)
    return out


def save(img: Image.Image, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if name.endswith(".jpg"):  # cover-heavy images: PNG would be >1 MB
        img.convert("RGB").save(OUT / name, quality=90, optimize=True, progressive=True)
    else:
        img.convert("RGB").save(OUT / name, optimize=True)
    print(f"{name}: {img.width}x{img.height}, {(OUT / name).stat().st_size:,} bytes")


# ------------------------------------------------------------------ header
def header(name: str) -> None:
    src = Image.open(ROOT / "assets" / "anime" / "anime-comet.webp").convert("RGB")
    h = round(src.height * W / src.width)
    img = src.resize(sc((W, h)), Image.LANCZOS).convert("RGBA")
    tint = Image.new("RGBA", img.size)
    td = ImageDraw.Draw(tint)
    for y in range(img.height):  # bottom-up dusk tint, like the list banner
        a = int(190 * max(0, (y - img.height * 0.4) / (img.height * 0.6)))
        td.line([(0, y), (img.width, y)], fill=BG + (a,))
    img = Image.alpha_composite(img, tint)
    Pen(img).text((26, h - 22), name, font(True, 28), (255, 247, 250), anchor="ls")
    save(rounded(img, 10), "header.png")


# ------------------------------------------------------------------ buttons
def button(label: str, accent: tuple, name: str, w: int = 258) -> None:
    h = 40
    img = canvas(w, h, SURFACE)
    p = Pen(img)
    p.rect((0, 0, w - 1, h - 1), 8, outline=LINE)
    p.line([(16, 13), (16, h - 13)], accent, 2)
    p.text((28, h / 2), label, font(True, 12), TEXT, anchor="lm")
    cx, cy = w - 20, h / 2  # chevron drawn as lines (no font glyph needed)
    p.line([(cx - 3, cy - 5), (cx + 2, cy), (cx - 3, cy + 5)], MUTED, 1.5)
    save(rounded(img, 8), name)


# ------------------------------------------------------------------ stats
def fetch_img(url: str, size: tuple[int, int]) -> Image.Image | None:
    try:
        req = urllib.request.Request(cover_url(url), headers={"User-Agent": "mal-list-css"})
        with urllib.request.urlopen(req, timeout=30) as r:
            im = Image.open(io.BytesIO(r.read())).convert("RGB")
        return ImageOps.fit(im, sc(size), Image.LANCZOS)
    except Exception as e:  # a missing cover should not break the card
        print(f"  cover skipped: {e}", file=sys.stderr)
        return None


def stats(user: str) -> None:
    anime, manga = fetch_list(user, "anime"), fetch_list(user, "manga")
    done = [a for a in anime if a["status"] == 2]
    watching = sorted((a for a in anime if a["status"] == 1), key=lambda a: -(a.get("updated_at") or 0))
    eps = sum(a.get("num_watched_episodes") or 0 for a in anime)
    scored = [a["score"] for a in anime if a.get("score")]
    reviews = []
    for a in anime:
        for t in str(a.get("tags") or "").split(","):
            m = REVIEW.match(t.strip())
            if m:
                try:
                    reviews.append(float(m.group(1)))
                except ValueError:
                    pass
    reviews = [r for r in reviews if 0 <= r <= 10]
    genres = collections.Counter(g["name"] for a in done for g in (a.get("genres") or []))
    chapters = sum(m.get("num_read_chapters") or 0 for m in manga)

    H = 248
    img = canvas(W, H)
    cw = (W - 44) / 7
    sky(img, seed=11, n=30, avoid=[(22, 10, 120, 30), (630, 12, 776, 30), (22, 36, 776, 40), (22, 106, 776, 110),
                                   *[(22 + i * cw, 50, 22 + i * cw + 96, 94) for i in range(7)],
                                   (22, 118, 140, 134), (22, 146, 476, 228), (520, 118, 776, 242)])
    p = Pen(img)
    p.rect((0, 0, W - 1, H - 1), 10, outline=LINE)
    p.text((22, 26), "Anime log", font(True, 12), TEXT, anchor="ls")
    p.text((W - 22, 26), f"updated {dt.date.today():%d %b %Y}", font(False, 9), MUTED, anchor="rs")
    p.line([(22, 38), (W - 22, 38)], LINE)

    cols = [
        (f"{len(anime):,}", "titles"), (f"{len(done):,}", "completed"), (f"{eps:,}", "episodes"),
        (f"{sum(scored) / len(scored):.2f}" if scored else "-", "mean score"),
        (f"{sum(reviews) / len(reviews):.2f}" if reviews else "-", "avg review"),
        (f"{len(manga):,}", "manga"), (f"{chapters:,}", "chapters read"),
    ]
    cw = (W - 44) / len(cols)
    for i, (num, lab) in enumerate(cols):
        x = 22 + i * cw
        p.text((x, 72), num, font(True, 17), TEXT, anchor="ls")
        p.text((x, 90), lab, font(False, 9), MUTED, anchor="ls")
    p.line([(22, 108), (W - 22, 108)], LINE)

    # currently watching (left)
    p.text((22, 132), "Now watching", font(True, 10), MUTED, anchor="ls")
    x = 22
    for a in watching[:7]:
        im = fetch_img(a.get("anime_image_path") or "", (58, 82))
        if im:
            img.alpha_composite(rounded(im.convert("RGBA"), 4), sc((x, 146)))
        else:
            p.rect((x, 146, x + 58, 228), 4, fill=SURFACE2)
        x += 66
    if not watching:
        p.text((22, 162), "nothing right now", font(False, 10), MUTED, anchor="ls")

    # top genres of completed titles (right)
    gx = 520
    gw = W - 22 - gx
    p.text((gx, 132), "Most watched genres", font(True, 10), MUTED, anchor="ls")
    top = genres.most_common(5)
    mx = top[0][1] if top else 1
    for i, (g, n) in enumerate(top):
        y = 156 + i * 17
        p.text((gx, y), g, font(False, 10), TEXT, anchor="ls")
        p.text((gx + gw, y), str(n), font(False, 9), MUTED, anchor="rs")
        p.line([(gx + 96, y - 4), (gx + gw - 34, y - 4)], SURFACE2, 2)
        p.line([(gx + 96, y - 4), (gx + 96 + (gw - 130) * n / mx, y - 4)], PINK, 2)
    save(img, "stats.png")


# ------------------------------------------------------------------ score guide
def ring(p: Pen, box, cols, width):
    """Graded frame, `width` logical px, outer colour first."""
    x0, y0, x1, y1 = sc(box)
    n = sc(width)
    for i in range(n):
        c = cols[min(i * len(cols) // max(n, 1), len(cols) - 1)]
        p.d.rounded_rectangle((x0 - i, y0 - i, x1 + i, y1 + i), sc(5) + i, outline=c, width=1)


def score_guide() -> None:
    H = 226
    img = canvas(W, H)
    sky(img, seed=3, n=18, avoid=[(22, 10, 220, 30), (22, 36, 776, 40), (22, 48, 260, 206), (296, 48, 776, 206)])
    p = Pen(img)
    p.rect((0, 0, W - 1, H - 1), 10, outline=LINE)
    p.text((22, 26), "How to read my list", font(True, 12), TEXT, anchor="ls")
    p.line([(22, 38), (W - 22, 38)], LINE)

    # left: the two scores
    p.text((22, 64), "Should Watch", font(True, 11), TEXT, anchor="ls")
    p.text((22, 80), "would I recommend it? x/10, shown as 5 stars", font(False, 9), MUTED, anchor="ls")
    for i in range(5):  # 3.5 of 5 stars
        p.star(29 + i * 18, 98, 7.5, GOLD if i < 3 else SURFACE2)
    half = Image.new("RGBA", sc((18, 18)))
    hp = Pen(half)
    hp.star(9, 9, 7.5, GOLD)
    img.alpha_composite(half.crop((0, 0, sc(9), sc(18))), sc((29 + 3 * 18 - 9, 89)))
    p.text((126, 102), "7/10 = 3.5 stars", font(False, 9), MUTED, anchor="ls")

    p.text((22, 140), "Review Score", font(True, 11), TEXT, anchor="ls")
    p.text((22, 156), "how good it actually was, to 0.25", font(False, 9), MUTED, anchor="ls")
    p.text((22, 180), "8.5", font(True, 14), TEXT, anchor="ls")
    p.text((50, 180), "/ 10", font(False, 9), MUTED, anchor="ls")
    p.line([(90, 176), (250, 176)], SURFACE2, 2)
    p.line([(90, 176), (90 + 160 * 0.85, 176)], PINK, 2)
    p.text((22, 202), "?/10 = not rated yet", font(False, 9), MUTED, anchor="ls")

    # right: cover frames
    p.line([(296, 52), (296, 206)], LINE)
    p.text((320, 64), "Cover frames (my MAL score)", font(True, 11), TEXT, anchor="ls")
    samples = [("10", "gold", GOLDS, 3), ("9", "silver", SILVER, 2), ("8", "copper", COPPER, 1.5),
               ("1", "dimmed", None, 0)]
    for i, (s_, lab, cols, wdt) in enumerate(samples):
        x, y = 320 + i * 116, 82
        cover = Image.new("RGBA", sc((54, 76)))
        cd = ImageDraw.Draw(cover)
        for yy in range(cover.height):  # stand-in cover: dusk gradient
            t = yy / cover.height
            cd.line([(0, yy), (cover.width, yy)], fill=(int(58 + 80 * t), int(53 + 40 * t), int(98 - 10 * t), 255))
        if cols is None:
            cover = Image.blend(cover, Image.new("RGBA", cover.size, (40, 40, 44, 255)), .55)
        else:
            ring(p, (x - 1, y - 1, x + 55, y + 77), cols, wdt)
        img.alpha_composite(rounded(cover, 4), sc((x, y)))
        p.text((x + 64, y + 36), s_, font(True, 16), TEXT if cols else MUTED, anchor="ls")
        p.text((x + 64, y + 52), lab, font(False, 9), MUTED, anchor="ls")
    p.text((320, 186), "10 slowly shimmers, 9 gets a passing sheen.", font(False, 9), MUTED, anchor="ls")
    p.text((320, 202), "Hover a title for its MAL score, rank and source.", font(False, 9), MUTED, anchor="ls")
    save(img, "score-guide.png")


# ------------------------------------------------------------------ top 10 of each year
NUM_WORDS = {"2nd": "2", "second": "2", "ii": "2", "3rd": "3", "third": "3", "iii": "3",
             "4th": "4", "iv": "4", "1st": "1", "first": "1"}


def tokens(t: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z0-9]+", str(t).lower()):
        out.append(NUM_WORDS.get(w, w))
    return out


def air_year(it: dict) -> int | None:
    """The year a show FINISHED airing (my top-10 years go by that); start year as fallback."""
    for key in ("anime_end_date_string", "anime_start_date_string"):
        d = str(it.get(key) or "")
        if re.fullmatch(r"\d\d-\d\d-\d\d", d):
            return 2000 + int(d[-2:])
    y = (it.get("anime_season") or {}).get("year")
    return int(y) if y else None


def match(query: str, year: int, anime: list[dict]) -> dict | None:
    m = re.search(r"#(\d+)", query)
    if m:
        return next((a for a in anime if a["anime_id"] == int(m.group(1))), None)
    q = set(tokens(query))
    if not q:
        return None
    weak = {"season", "part", "the", "no", "wa", "final", "1", "2", "3", "4", "5", "s"}
    wt = lambda ts: sum(0.3 if t in weak else 1.0 for t in ts)  # noqa: E731
    best, best_s = None, 0.0
    for a in anime:
        title_toks = set(tokens(a.get("anime_title"))) | set(tokens(a.get("anime_title_eng") or ""))
        hit = wt(q & title_toks) / wt(q)
        if hit < 0.5:
            continue
        s_ = (hit + (0.6 if air_year(a) == year else 0) - 0.01 * len(title_toks)
              + (0.2 if a.get("anime_media_type_string") == "TV" else 0))
        if s_ > best_s:
            best, best_s = a, s_
    return best


def read_top10() -> list[tuple[int, str, dict[int, str]]]:
    years, cur = [], None
    for line in (ROOT / "top10.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.fullmatch(r"(\d{4})\s*(.*)", line)
        if m:
            cur = (int(m.group(1)), m.group(2).strip(), {})
            years.append(cur)
            continue
        m = re.fullmatch(r"(\d{1,2})\s*[-.)]\s*(.*)", line)
        if m and cur and m.group(2).strip() and m.group(2).strip().upper() != "TBA":
            cur[2][int(m.group(1))] = m.group(2).strip()
    return years


def wrap(text: str, f, width: float, lines: int) -> list[str]:
    words, out, cur = str(text).split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if f.getlength(t) <= sc(width):
            cur = t
        else:
            out.append(cur)
            cur = w
    out.append(cur)
    out = [o for o in out if o]
    if len(out) > lines:
        out = out[:lines]
        while f.getlength(out[-1] + "...") > sc(width) and " " in out[-1]:
            out[-1] = out[-1].rsplit(" ", 1)[0]
        out[-1] += "..."
    return out


def name_of(a: dict) -> str:
    eng, rom = str(a.get("anime_title_eng") or ""), str(a.get("anime_title") or "")
    if eng and not rom.isascii():  # e.g. "5-toubun no Hanayome ∬": Verdana has no such glyph
        return eng
    return eng if eng and len(eng) <= len(rom) + 6 else rom


def top10(year: int, picks: dict[int, dict | None]) -> None:
    H = 470
    img = canvas(W, H)
    sky(img, seed=year, n=16, avoid=[(22, 10, 300, 30), (540, 12, 776, 30), (22, 36, 776, 40), (22, 48, 776, 462)])
    p = Pen(img)
    p.rect((0, 0, W - 1, H - 1), 10, outline=LINE)
    p.text((22, 26), f"My top 10 of {year}", font(True, 12), TEXT, anchor="ls")
    p.text((W - 22, 26), "by the year each show finished airing", font(False, 9), MUTED, anchor="rs")
    p.line([(22, 38), (W - 22, 38)], LINE)
    medal = {1: GOLDS, 2: SILVER, 3: COPPER}

    def cover(rank: int, x: float, y: float, w: float, h: float) -> None:
        a = picks.get(rank)
        im = fetch_img(a.get("anime_image_path") or "", (w, h)) if a else None
        if rank in medal:
            ring(p, (x - 1, y - 1, x + w, y + h), medal[rank], 2 if rank == 1 else 1.5)
        if im:
            img.alpha_composite(rounded(im.convert("RGBA"), 5), sc((x, y)))
        else:
            p.rect((x, y, x + w, y + h), 5, fill=SURFACE, outline=LINE)
            p.text((x + w / 2, y + h / 2), "?", font(True, 18), LINE, anchor="mm")

    def meta(a: dict) -> str:
        season = (a.get("anime_season") or {}).get("season") or ""
        studio = ", ".join(s["name"] for s in (a.get("anime_studios") or [])[:1])
        return " · ".join(x for x in (season, studio) if x)

    # #1: big cover with text beside it
    cover(1, 22, 54, 136, 194)
    a = picks.get(1)
    p.text((176, 92), "1", font(True, 34), GOLDS[1], anchor="ls")
    if a:
        f = font(True, 14)
        lines = wrap(name_of(a), f, 210, 3)
        for i, ln in enumerate(lines):
            p.text((176, 122 + i * 20), ln, f, TEXT, anchor="ls")
        y = 122 + (len(lines) - 1) * 20 + 22
        p.text((176, y), meta(a), font(False, 9), MUTED, anchor="ls")
        if a.get("score"):
            p.text((176, y + 16), f"my score {a['score']}/10", font(False, 9), MUTED, anchor="ls")
    # #2, #3: medium covers, text underneath
    for rank, x in ((2, 420), (3, 604)):
        cover(rank, x, 54, 100, 142)
        p.text((x + 112, 80), str(rank), font(True, 24), medal[rank][1], anchor="ls")
        a = picks.get(rank)
        if a:
            f = font(True, 10)
            lines = wrap(name_of(a), f, 172, 2)
            for i, ln in enumerate(lines):
                p.text((x, 214 + i * 15), ln, f, TEXT, anchor="ls")
            p.text((x, 214 + len(lines) * 15 + 1), meta(a), font(False, 8), MUTED, anchor="ls")
    # #4-#10: a row of small covers
    w, gap = 96, (W - 44 - 7 * 96) / 6
    for i, rank in enumerate(range(4, 11)):
        x = 22 + i * (w + gap)
        cover(rank, x, 278, w, 136)
        p.rect((x + 5, 283, x + 25, 299), 4, fill=BG)
        p.text((x + 15, 291), str(rank), font(True, 10), TEXT, anchor="mm")
        a = picks.get(rank)
        if a:
            f = font(False, 9)
            for j, ln in enumerate(wrap(name_of(a), f, w, 3)):
                p.text((x, 430 + j * 13), ln, f, TEXT, anchor="ls")
    save(img, f"top10-{year}.jpg")


def top10_all(user: str) -> None:
    anime = fetch_list(user, "anime")
    for year, note, ranks in read_top10():
        if note or not ranks:
            print(f"{year}: {'note only' if note else 'empty'}, no image")
            continue
        picks = {}
        for r, q in sorted(ranks.items()):
            a = match(q, year, anime)
            picks[r] = a
            got = f"{a['anime_id']} {a.get('anime_title')} ({air_year(a)})" if a else "NOT FOUND"
            print(f"  {year} #{r:<2} {q!r:32} -> {got}")
        top10(year, picks)


# ------------------------------------------------------------------ this year + year by year
def ym(s) -> tuple[int | None, int | None]:
    """MAL list date "dd-mm-yy" -> (year, month). 00 = unknown day/month (I only set the year)."""
    s = str(s or "")
    if not re.fullmatch(r"\d\d-\d\d-\d\d", s):
        return None, None
    m = int(s[3:5])
    return 2000 + int(s[6:8]), (m if 1 <= m <= 12 else None)


def year_card(user: str) -> None:
    anime = fetch_list(user, "anime")
    today = dt.date.today()
    done = [(a, *ym(a.get("finish_date_string"))) for a in anime if a["status"] == 2]
    this = [a for a, y, m in done if y == today.year]
    eps = sum(a.get("num_watched_episodes") or 0 for a in this)
    scored = [a["score"] for a in this if a.get("score")]
    months = collections.Counter(m for a, y, m in done if y == today.year and m)
    per_year = collections.Counter(y for a, y, m in done if y)
    years = list(range(2019, today.year + 1))

    H = 236
    img = canvas(W, H)
    sky(img, seed=today.year + 7, n=14, avoid=[(22, 10, 330, 30), (560, 12, 776, 30), (22, 36, 776, 40),
                                                 (22, 48, 776, 226)])
    p = Pen(img)
    p.rect((0, 0, W - 1, H - 1), 10, outline=LINE)
    p.text((22, 26), f"{today.year} so far", font(True, 12), TEXT, anchor="ls")
    p.text((W - 22, 26), f"titles I finished · updated {today:%d %b %Y}", font(False, 9), MUTED, anchor="rs")
    p.line([(22, 38), (W - 22, 38)], LINE)

    nums = [(f"{len(this)}", "titles"), (f"{eps:,}", "episodes"),
            (f"{sum(scored) / len(scored):.2f}" if scored else "-", "my mean score")]
    for i, (n, lab) in enumerate(nums):
        x = 22 + i * 120
        p.text((x, 72), n, font(True, 17), TEXT, anchor="ls")
        p.text((x, 90), lab, font(False, 9), MUTED, anchor="ls")

    # titles finished per month (this year)
    mx = max(months.values() or [1])
    x0, base, bw, gap, hmax = 22, 200, 24, 9, 76
    for m in range(1, 13):
        x = x0 + (m - 1) * (bw + gap)
        n = months.get(m, 0)
        future = m > today.month
        p.rect((x, base - hmax, x + bw, base), 3, fill=SURFACE)
        if n:
            p.rect((x, base - max(3, hmax * n / mx), x + bw, base), 3, fill=PINK)
            p.text((x + bw / 2, base - hmax * n / mx - 5), str(n), font(False, 8), MUTED, anchor="ms")
        p.text((x + bw / 2, base + 14), "JFMAMJJASOND"[m - 1], font(future, 9), LINE if future else MUTED,
               anchor="ms")

    # finished per year
    gx = 470
    p.line([(gx - 22, 52), (gx - 22, 216)], LINE)
    p.text((gx, 64), "Finished per year", font(True, 10), MUTED, anchor="ls")
    ymx = max([per_year.get(y, 0) for y in years] or [1])
    row = min(18, 140 / max(len(years), 1))
    for i, y in enumerate(years):
        yy = 86 + i * row
        n = per_year.get(y, 0)
        cur = y == today.year
        p.text((gx, yy), str(y), font(cur, 9), TEXT if cur else MUTED, anchor="ls")
        p.line([(gx + 40, yy - 4), (gx + 40 + 220 * n / ymx, yy - 4)], PINK if cur else SKY, 3)
        p.text((gx + 46 + 220 * n / ymx, yy), str(n), font(False, 8), MUTED, anchor="ls")
    save(img, "year.png")


# ------------------------------------------------------------------ most watched people
CREDITS = ROOT / "data" / "credits"


def favourites(user: str) -> None:
    anime = [a for a in fetch_list(user, "anime") if a["status"] == 2]
    studio, va, director, writer, singer = (collections.Counter() for _ in range(5))
    have = 0
    for a in anime:
        for s in a.get("anime_studios") or []:
            studio[s["name"]] += 1
        f = CREDITS / f"{a['anime_id']}.json"
        if not f.exists():
            continue
        have += 1
        c = json.loads(f.read_text(encoding="utf-8"))
        for name in {n for _, n, _ in c["va"]}:
            va[name] += 1
        has_sc = any("Series Composition" in r for _, _, r in c["staff"])
        for name in {n for _, n, r in c["staff"] if "Director" in r}:
            director[name] += 1
        for name in {n for _, n, r in c["staff"]
                     if "Series Composition" in r or (not has_sc and "Script" in r)}:
            writer[name] += 1
        for s in c["songs"]:
            s = re.sub(r"\s*\([^)]*[^\x00-\x7f][^)]*\)", "", s).strip()  # drop "(南條愛乃)"
            if s:
                singer[s] += 1

    H = 214
    img = canvas(W, H)
    sky(img, seed=99, n=12, avoid=[(22, 10, 330, 30), (520, 12, 776, 30), (22, 36, 776, 40), (22, 48, 776, 206)])
    p = Pen(img)
    p.rect((0, 0, W - 1, H - 1), 10, outline=LINE)
    p.text((22, 26), "Who I watch the most", font(True, 12), TEXT, anchor="ls")
    p.text((W - 22, 26), f"titles credited, of {len(anime)} completed", font(False, 9), MUTED, anchor="rs")
    p.line([(22, 38), (W - 22, 38)], LINE)
    cols = [("Studios", studio), ("Seiyuu", va), ("Directors", director),
            ("Series composition", writer), ("OP / ED artists", singer)]
    cw = (W - 44) / len(cols)
    for i, (label, cnt) in enumerate(cols):
        x = 22 + i * cw
        p.text((x, 62), label, font(True, 9), MUTED, anchor="ls")
        top = cnt.most_common(5)
        if not top:
            continue
        f1 = font(True, 11)
        p.text((x, 86), wrap(top[0][0], f1, cw - 12, 1)[0], f1, PINK, anchor="ls")
        p.text((x, 102), f"{top[0][1]} titles", font(False, 9), MUTED, anchor="ls")
        for j, (name, n) in enumerate(top[1:]):
            y = 128 + j * 18
            f2 = font(False, 9)
            p.text((x, y), wrap(name, f2, cw - 36, 1)[0], f2, TEXT, anchor="ls")
            p.text((x + cw - 14, y), str(n), f2, MUTED, anchor="rs")
    if have < len(anime):
        print(f"favourites: credits for {have}/{len(anime)} titles so far")
    save(img, "favourites.png")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="Snolled")
    ap.add_argument("--only-stats", action="store_true", help="daily run: rebuild just stats.png")
    ap.add_argument("--only-top10", action="store_true", help="rebuild just the top-10 images from top10.txt")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.only_top10:
        top10_all(a.user)
        return 0
    if not a.only_stats:
        header(a.user)
        button("Anime List", PINK, "btn-anime.png")
        button("Manga List", SKY, "btn-manga.png")
        button("Stacks & Reviews", GOLD, "btn-more.png")
        for label, accent, name in (("Facebook", SKY, "link-facebook.png"), ("X / Twitter", TEXT, "link-x.png"),
                                    ("AMQ: Snolled", LAV, "link-amq.png"), ("AMQ song stats", PINK, "link-amqstats.png")):
            button(label, accent, name, w=190)
        score_guide()
        top10_all(a.user)
    stats(a.user)
    year_card(a.user)
    if CREDITS.exists():
        favourites(a.user)
    return 0


if __name__ == "__main__":
    sys.exit(main())
