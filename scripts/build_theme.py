"""Build dist/theme.min.css = src/core.css + anime.css + manga.css + generated rating rules.

Rating tags already on the list look like:
    "Should Watch : 7/10"   "Review Score : 8.5/10"   "... : ?/10" (not rated yet)
plus a few typo variants ("Should to Watch: 8.5/10", "Review Score:6/10").
MAL renders each tag as  <a href="?status=7&tag=Should%20Watch%20%3A%207%2F10">.
CSS cannot read numbers from text, so we generate one selector per possible value
(0-10 in 0.25 steps + the joke values -10 and 100) that sets --v (0..10) and,
for Review, --txt (the number to print). Matching is on the href *suffix*, which
works for both "… : 7/10" (%207%2F10) and "…:7/10" (%3A7%2F10).

Usage: python scripts/build_theme.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
OUT = ROOT / "dist" / "theme.min.css"

# value written in the tag -> (bar value 0..10, label printed for Review)
SPECIAL = {"-10": (0, "-10"), "100": (10, "100 ✦")}


def fmt(x: float) -> str:
    return f"{x:g}"


def rating_rules() -> str:
    values: dict[str, tuple[float, str]] = {}
    for i in range(0, 41):  # 0, 0.25, ... 10
        s = fmt(i / 4)
        values[s] = (i / 4, s)
    values.update(SPECIAL)
    out = []
    for s, (v, label) in values.items():
        suffixes = [f"%20{s}%2F10", f"%3A{s}%2F10"]
        sel = ",".join(
            f'body.ownlist .data.tags a[href*="tag={k}"][href$="{suf}"]'
            for k in ("Should", "Review") for suf in suffixes
        )
        out.append(f'{sel}{{--v:{fmt(v)};--txt:"{label}"}}')
    return "\n".join(out)


def minify(css: str) -> str:
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{};])\s*", r"\1", css)
    css = css.replace(";}", "}")
    return css.strip() + "\n"


def main() -> None:
    parts = [(SRC / f).read_text(encoding="utf-8") for f in ("core.css", "elaina.css", "koisuru.css")]
    parts.append(rating_rules())
    css = "/* mal-list-css theme — github.com/Snolled37/mal-list-css */\n" + minify("\n".join(parts))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(css, encoding="utf-8", newline="\n")
    print(f"{OUT.relative_to(ROOT)}: {len(css.encode()):,} bytes, {css.count('{'):,} rule blocks")


if __name__ == "__main__":
    main()
