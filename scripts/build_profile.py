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
import re
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_covers import cover_url, fetch_list  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "profile"
W = 798  # About Me width on desktop

# Koisuru Asteroid (manga-list palette)
BG, SURFACE, SURFACE2 = (21, 23, 31), (28, 31, 42), (35, 39, 54)
TEXT, MUTED, LINE = (230, 232, 239), (147, 153, 173), (50, 56, 73)
PINK, SKY, GOLD, LAV = (232, 180, 200), (185, 211, 234), (241, 210, 138), (205, 184, 239)
COPPER = [(246, 205, 185), (201, 130, 98), (154, 90, 69)]
SILVER = [(255, 255, 255), (196, 203, 216), (142, 151, 171)]
GOLDS = [(255, 246, 216), (233, 185, 73), (168, 120, 31)]

REVIEW = re.compile(r"^review\s*scores?\s*:\s*([\d.]+)\s*/\s*10$", re.I)


def font(bold: bool = False, size: int = 12) -> ImageFont.FreeTypeFont:
    names = ["verdanab.ttf", "Verdana_Bold.ttf", "Verdana Bold.ttf"] if bold else ["verdana.ttf", "Verdana.ttf"]
    dirs = [Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/msttcorefonts"),
            Path("/usr/share/fonts/truetype/msttcorefonts/"), Path.home() / ".fonts"]
    for d in dirs:
        for n in names:
            if (d / n).exists():
                return ImageFont.truetype(str(d / n), size)
    sys.exit("Verdana not found (Windows: C:/Windows/Fonts; Ubuntu: apt install ttf-mscorefonts-installer)")


def rounded(img: Image.Image, r: int) -> Image.Image:
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, img.width - 1, img.height - 1), r, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), m)
    return out


def stars_bg(img: Image.Image, seed: int = 7, n: int = 70) -> None:
    import random
    rnd = random.Random(seed)
    d = ImageDraw.Draw(img)
    for _ in range(n):
        x, y = rnd.randrange(img.width), rnd.randrange(img.height)
        c = rnd.choice([(255, 255, 255), (255, 243, 214), (251, 230, 238), (219, 232, 245)])
        a = rnd.randrange(70, 200)
        s = rnd.choice([1, 1, 1, 2])
        d.ellipse((x, y, x + s, y + s), fill=c + (a,))


def star(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill) -> None:
    """5-point star as a polygon (Verdana has no ★ glyph)."""
    import math
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r * 0.45
        a = math.pi / 2 + i * math.pi / 5
        pts.append((cx + rr * math.cos(a), cy - rr * math.sin(a)))
    d.polygon(pts, fill=fill)


def save(img: Image.Image, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(OUT / name, optimize=True)
    print(f"{name}: {img.width}x{img.height}, {(OUT / name).stat().st_size:,} bytes")


# ------------------------------------------------------------------ header
def header(name: str) -> None:
    src = Image.open(ROOT / "assets" / "anime" / "anime-comet.webp").convert("RGB")
    h = round(src.height * W / src.width)
    img = src.resize((W, h), Image.LANCZOS).convert("RGBA")
    tint = Image.new("RGBA", img.size)
    td = ImageDraw.Draw(tint)
    for y in range(h):  # bottom-up dusk tint, like the list banner
        a = int(200 * max(0, (y - h * 0.35) / (h * 0.65)))
        td.line([(0, y), (W, y)], fill=BG + (a,))
    img = Image.alpha_composite(img, tint)
    f = font(True, 30)
    glow = Image.new("RGBA", img.size)
    ImageDraw.Draw(glow).text((26, h - 52), name, font=f, fill=PINK + (200,))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(7)))
    ImageDraw.Draw(img).text((26, h - 52), name, font=f, fill=(255, 247, 250))
    save(rounded(img, 14), "header.png")


# ------------------------------------------------------------------ buttons
def button(label: str, sub: str, accent: tuple, name: str) -> None:
    w, h = 258, 46
    img = Image.new("RGBA", (w, h), SURFACE + (255,))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), 10, outline=LINE, width=1)
    d.rounded_rectangle((0, 0, 5, h - 1), 3, fill=accent)
    d.text((18, 8), label, font=font(True, 12), fill=TEXT)
    d.text((18, 26), sub, font=font(False, 9), fill=MUTED)
    d.text((w - 26, 14), "›", font=font(True, 16), fill=accent)
    save(rounded(img, 10), name)


# ------------------------------------------------------------------ stats
def fetch_img(url: str, size: tuple[int, int]) -> Image.Image | None:
    try:
        req = urllib.request.Request(cover_url(url), headers={"User-Agent": "mal-list-css"})
        with urllib.request.urlopen(req, timeout=30) as r:
            im = Image.open(io.BytesIO(r.read())).convert("RGB")
        return im.resize(size, Image.LANCZOS)
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

    img = Image.new("RGBA", (W, 300), BG + (255,))
    stars_bg(img, seed=11, n=34)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, W - 1, 299), 14, outline=LINE, width=1)
    d.text((22, 14), "ANIME LOG", font=font(True, 11), fill=PINK)
    d.text((112, 15), f"updated {dt.date.today():%d %b %Y}", font=font(False, 9), fill=MUTED)

    tiles = [
        (f"{len(anime):,}", "titles"), (f"{len(done):,}", "completed"), (f"{eps:,}", "episodes"),
        (f"{sum(scored) / len(scored):.2f}" if scored else "–", "mean score"),
        (f"{sum(reviews) / len(reviews):.2f}" if reviews else "–", "avg review"),
        (f"{len(manga):,} · {chapters:,}", "manga · chapters"),
    ]
    for i, (num, lab) in enumerate(tiles):
        x, y = 22 + (i % 3) * 132, 40 + (i // 3) * 62
        d.rounded_rectangle((x, y, x + 122, y + 52), 9, fill=SURFACE + (235,))
        d.text((x + 10, y + 7), num, font=font(True, 16), fill=GOLD if lab == "avg review" else TEXT)
        d.text((x + 10, y + 32), lab, font=font(False, 9), fill=MUTED)

    # top genres (completed)
    gx = 432
    d.text((gx, 40), "MOST WATCHED GENRES", font=font(True, 9), fill=MUTED)
    top = genres.most_common(5)
    mx = top[0][1] if top else 1
    for i, (g, n) in enumerate(top):
        y = 60 + i * 19
        d.text((gx, y), g, font=font(False, 10), fill=TEXT)
        bw = int(200 * n / mx)
        d.rounded_rectangle((gx + 120, y + 4, gx + 120 + bw, y + 10), 3, fill=[PINK, SKY, LAV, GOLD, PINK][i])
        d.text((gx + 126 + bw, y), str(n), font=font(False, 9), fill=MUTED)

    # currently watching
    d.text((22, 172), "NOW WATCHING", font=font(True, 9), fill=MUTED)
    x = 22
    for a in watching[:9]:
        im = fetch_img(a.get("anime_image_path") or "", (58, 82))
        if im:
            img.alpha_composite(rounded(im.convert("RGBA"), 6), (x, 190))
        else:
            d.rounded_rectangle((x, 190, x + 58, 272), 6, fill=SURFACE2)
        x += 66
    if not watching:
        d.text((22, 196), "nothing right now", font=font(False, 10), fill=MUTED)
    d.text((W - 160, 278), "Koisuru Asteroid theme", font=font(False, 8), fill=LINE)
    save(img, "stats.png")


# ------------------------------------------------------------------ score guide
def ring(d: ImageDraw.ImageDraw, box, cols, width):
    x0, y0, x1, y1 = box
    for i in range(width):
        c = cols[min(i * len(cols) // max(width, 1), len(cols) - 1)]
        d.rounded_rectangle((x0 - i, y0 - i, x1 + i, y1 + i), 8 + i, outline=c, width=1)


def score_guide() -> None:
    img = Image.new("RGBA", (W, 236), BG + (255,))
    stars_bg(img, seed=3, n=22)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, W - 1, 235), 14, outline=LINE, width=1)
    d.text((22, 14), "HOW TO READ MY LIST", font=font(True, 11), fill=PINK)

    # left: the two scores
    d.text((22, 44), "Should Watch", font=font(True, 11), fill=TEXT)
    d.text((22, 60), "would I recommend it? (x/10, shown as 5 stars)", font=font(False, 9), fill=MUTED)
    for i in range(5):  # 3.5 of 5 stars
        star(d, 31 + i * 20, 87, 9, GOLD if i < 3 else LINE)
    half = Image.new("RGBA", (20, 20))
    star(ImageDraw.Draw(half), 10, 10, 9, GOLD)
    img.alpha_composite(half.crop((0, 0, 10, 20)), (31 + 3 * 20 - 10, 77))
    d.text((132, 82), "7/10 = 3.5 stars", font=font(False, 9), fill=MUTED)

    d.text((22, 116), "Review Score", font=font(True, 11), fill=TEXT)
    d.text((22, 132), "how good it actually was, to 0.25", font=font(False, 9), fill=MUTED)
    d.text((22, 148), "8.5", font=font(True, 14), fill=TEXT)
    d.text((52, 152), "/ 10", font=font(False, 9), fill=MUTED)
    d.rounded_rectangle((22, 172, 222, 175), 2, fill=LINE)
    for x in range(22, 22 + 170):
        t = (x - 22) / 170
        c = tuple(int(SKY[k] + (PINK[k] - SKY[k]) * t) for k in range(3))
        d.line([(x, 172), (x, 175)], fill=c)
    d.text((22, 190), "?/10 = not rated yet", font=font(False, 9), fill=MUTED)

    # right: cover frames
    d.text((300, 44), "COVER FRAMES (my MAL score)", font=font(True, 9), fill=MUTED)
    samples = [("10", "gold", GOLDS, 3), ("9", "silver", SILVER, 2), ("8", "copper", COPPER, 2), ("1", "dimmed", None, 0)]
    for i, (s, lab, cols, wdt) in enumerate(samples):
        x, y = 300 + i * 120, 66
        cover = Image.new("RGBA", (64, 90))
        cd = ImageDraw.Draw(cover)
        for yy in range(90):  # stand-in cover: dusk gradient
            t = yy / 90
            cd.line([(0, yy), (64, yy)], fill=(int(58 + 80 * t), int(53 + 40 * t), int(98 - 10 * t), 255))
        if cols is None:
            cover = Image.blend(cover, Image.new("RGBA", cover.size, (40, 40, 44, 255)), .55)
        if cols:
            ring(d, (x - 1, y - 1, x + 64, y + 90), cols, wdt)
        img.alpha_composite(rounded(cover, 7), (x, y))
        d.text((x + 76, y + 24), s, font=font(True, 18), fill=TEXT if cols else MUTED)
        d.text((x + 76, y + 50), lab, font=font(False, 9), fill=MUTED)
    d.text((300, 176), "10 also slowly shimmers; 9 gets a passing sheen.", font=font(False, 9), fill=MUTED)
    d.text((300, 192), "Hover a title for its MAL score, rank and source.", font=font(False, 9), fill=MUTED)
    save(img, "score-guide.png")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="Snolled")
    ap.add_argument("--only-stats", action="store_true", help="daily run: rebuild just stats.png")
    a = ap.parse_args()
    if not a.only_stats:
        header(a.user)
        button("Anime List", "Elaina theme · 1,000+ titles", PINK, "btn-anime.png")
        button("Manga List", "Koisuru Asteroid theme", SKY, "btn-manga.png")
        button("Stacks & Reviews", "what I wrote about them", GOLD, "btn-more.png")
        score_guide()
    stats(a.user)
    return 0


if __name__ == "__main__":
    sys.exit(main())
