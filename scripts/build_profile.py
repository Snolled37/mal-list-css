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
def button(label: str, accent: tuple, name: str) -> None:
    w, h = 258, 40
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="Snolled")
    ap.add_argument("--only-stats", action="store_true", help="daily run: rebuild just stats.png")
    a = ap.parse_args()
    if not a.only_stats:
        header(a.user)
        button("Anime List", PINK, "btn-anime.png")
        button("Manga List", SKY, "btn-manga.png")
        button("Stacks & Reviews", GOLD, "btn-more.png")
        score_guide()
    stats(a.user)
    return 0


if __name__ == "__main__":
    sys.exit(main())
