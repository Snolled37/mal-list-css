# mal-list-css

Custom CSS for the MyAnimeList anime and manga lists of **Snolled**.

## Why this exists
The old setup imported malscraper's `covers/auto`. That mode no longer works, because browsers now send only the origin as the referrer. It falls back to a file with **every** title on MAL: about 14 MB and 116,531 rules, which made the list slow. This repo keeps a cover file with only the titles actually on the list (about 150 KB).

## Files
| Path | What it is |
|---|---|
| `dist/covers-anime.css`, `dist/covers-manga.css` | Hover-cover rules for each list. A daily GitHub Action rebuilds them. |
| `dist/theme.min.css` | **Own theme** (anime = Koisuru Asteroid, manga = Elaina). Built from `src/*.css` with `python scripts/build_theme.py`. |
| `paste/anime.css`, `paste/manga.css` | **What to paste into MAL now** (theme + covers + name, avatar/banner slots) |
| Rating tags | `Should Watch : 7/10` → ★★★½ (value ÷ 2) · `Review Score : 8.5/10` → number + meter · `?/10` = not rated yet (glows for the owner). 0–10 in 0.25 steps, plus -10 and 100. |
| Favourite marker | tag `Trophy` / `Favorite` / `Favourite` → asteroid (anime) or witch brooch (manga) left of the row (from extras, refreshed daily) |
| `dist/extras-*.css` | Data-driven extras from `scripts/build_extras.py`: progress bars, ✦ badge on covers with Review ≥ 9, favourite markers, and the hover cards on **Premiered** (that season's 5 most-watched TV shows) and **Studio** (top 4 + newest title). Season/studio data is scraped politely from MAL pages (2 s apart) and cached in `data/`. |
| `dist/phase1.css` | Temporary fixes on top of the Clarity theme: hover without layout work, plus the score descriptors and hearts |
| `paste/phase1-*.css` | What to paste into MAL → List Style → Custom CSS (anime list → `phase1-anime.css`, manga list → `phase1-manga.css`). |
| `scripts/build_covers.py` | Rebuilds the cover files: `python scripts/build_covers.py --user Snolled` |

## Notes
- MAL escapes a plain `@import`, so the paste file uses `@\import`.
- The modern list loads 300 rows per request.
- jsDelivr caches `@main` for up to 12 hours. The Action purges the cache after each commit. To purge by hand, open `https://purge.jsdelivr.net/gh/Snolled37/mal-list-css@main/dist/<file>`.

## Banner credits
`assets/manga/*.webp` are short cropped loops made from Elaina (Majo no Tabitabi / Wandering Witch) live wallpapers on [moewalls.com](https://moewalls.com): *Elaina in the Snow*, *Drinking Milk Tea*, *Vineyard*, *Drinking Coffee Near Window*, *Butterflies*, *Early Morning*. Used for a personal list page only; all rights belong to the original artists. Ask and they will be removed.

`assets/anime/*.webp` (cropped): live wallpapers from moewalls.com — *Starry Night with Himmel and Frieren* (Frieren), *Makise Kurisu and Rintaro Okabe* (Steins;Gate), *Saki Ayase Doing Homework* (Gimai Seikatsu); stills — Koisuru Asteroid comet scene, an underwater two-girls illustration, and a Fruits Basket illustration by **chibimonkey**. Personal list page only; rights belong to the original artists and studios. Ask and they will be removed.
