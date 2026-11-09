# mal-list-css

Custom CSS for the MyAnimeList anime and manga lists of **Snolled**.

## Why this exists
The old setup imported malscraper's `covers/auto`. That mode no longer works, because browsers now send only the origin as the referrer. It falls back to a file with **every** title on MAL: about 14 MB and 116,531 rules, which made the list slow. This repo keeps a cover file with only the titles actually on the list (about 150 KB).

## Files
| Path | What it is |
|---|---|
| `dist/covers-anime.css`, `dist/covers-manga.css` | Hover-cover rules for each list. A daily GitHub Action rebuilds them. |
| `dist/phase1.css` | Temporary fixes on top of the Clarity theme: hover without layout work, plus the score descriptors and hearts |
| `paste/phase1-*.css` | What to paste into MAL → List Style → Custom CSS (anime list → `phase1-anime.css`, manga list → `phase1-manga.css`). |
| `scripts/build_covers.py` | Rebuilds the cover files: `python scripts/build_covers.py --user Snolled` |

## Notes
- MAL escapes a plain `@import`, so the paste file uses `@\import`.
- The modern list loads 300 rows per request.
- jsDelivr caches `@main` for up to 12 hours. The Action purges the cache after each commit. To purge by hand, open `https://purge.jsdelivr.net/gh/Snolled37/mal-list-css@main/dist/<file>`.
