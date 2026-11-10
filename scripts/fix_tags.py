"""Normalise the rating tags on Snolled's MAL lists, and seed missing ones.

  anime: "Should Watch : X/10"   manga: "Should Read : X/10"   both: "Review Score : X/10"

* typo variants are rewritten in place ("Should to Watch: 8.5/10", "Should Watch?:6.5/10",
  "Review Score:6/10", "Review Scores: 7/10" ...); the value is kept as written
* titles that are Watching / Completed / On Hold / Dropped (not Plan to Watch/Read) and lack
  one of the two tags get "?/10" placeholders, which the theme shows as "not rated yet"
* every other tag is left exactly as it was, in the same order

Reading uses the public list JSON. Writing uses the official MAL API v2 with your own login.

  1. python scripts/fix_tags.py                      # dry run: prints what would change, writes nothing
  2. python scripts/fix_tags.py --apply --limit 3    # first time opens the MAL login page in your browser
  3. python scripts/fix_tags.py --apply              # the rest

Needs a MAL API Client ID (https://myanimelist.net/apiconfig, App Type "other",
redirect URL http://localhost:8765/callback) in the env var MAL_CLIENT_ID
(and MAL_CLIENT_SECRET if MAL gave you one). The token is saved to .mal-token.json
(git-ignored). A backup of the old tags is written to backups/ before any write.
"""
from __future__ import annotations

import argparse
import datetime as dt
import http.server
import json
import os
import re
import secrets
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_covers import fetch_list  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TOKEN = ROOT / ".mal-token.json"
BACKUPS = ROOT / "backups"
REDIRECT = "http://localhost:8765/callback"
SEED_STATUSES = {1, 2, 3, 4}  # watching/reading, completed, on hold, dropped
MAX_TAGS_BYTES = 255  # UTF-8 bytes (Thai = 3 bytes/char). Longer: 400, or MAL silently truncates

SHOULD = re.compile(r"^should\s*(?:to\s*)?(?:watch|read)?\s*\??\s*:\s*(\S.*?)\s*/\s*10$", re.I)
REVIEW = re.compile(r"^review\s*scores?\s*:\s*(\S.*?)\s*/\s*10$", re.I)


def canonical(kind: str) -> tuple[str, str]:
    verb = "Watch" if kind == "anime" else "Read"
    return f"Should {verb} : {{}}/10", "Review Score : {}/10"


def plan(item: dict, kind: str) -> tuple[list[str], list[str]] | None:
    """Return (old_tags, new_tags) if something changes, else None."""
    old = [t.strip() for t in str(item.get("tags") or "").split(",") if t.strip()]
    should_fmt, review_fmt = canonical(kind)
    new, have_s, have_r = [], False, False
    for t in old:
        m = SHOULD.match(t)
        if m and not have_s:
            new.append(should_fmt.format(m.group(1).replace(" ", ""))); have_s = True; continue
        m = REVIEW.match(t)
        if m and not have_r:
            new.append(review_fmt.format(m.group(1).replace(" ", ""))); have_r = True; continue
        new.append(t)
    if item.get("status") in SEED_STATUSES:
        if not have_s:
            new.append(should_fmt.format("?"))
        if not have_r:
            new.append(review_fmt.format("?"))
    return (old, new) if new != old else None


# ---------------------------------------------------------------- OAuth (PKCE, plain)
def get_token() -> str:
    if TOKEN.exists():
        tok = json.loads(TOKEN.read_text(encoding="utf-8"))
        if tok.get("expires_at", 0) > time.time() + 60:
            return tok["access_token"]
    cid = os.environ.get("MAL_CLIENT_ID")
    if not cid:
        sys.exit("Set MAL_CLIENT_ID first (see the top of this file).")
    verifier = secrets.token_urlsafe(64)[:100]
    state = secrets.token_urlsafe(16)
    got: dict = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got.update({k: v[0] for k, v in q.items()})
            self.send_response(200); self.end_headers()
            self.wfile.write("Done - you can close this tab and return to the terminal.".encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("localhost", 8765), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    url = "https://myanimelist.net/v1/oauth2/authorize?" + urllib.parse.urlencode({
        "response_type": "code", "client_id": cid, "code_challenge": verifier,
        "code_challenge_method": "plain", "state": state, "redirect_uri": REDIRECT})
    print("Opening the MAL login/consent page. Approve it in your browser...")
    webbrowser.open(url)
    for _ in range(600):
        if got:
            break
        time.sleep(0.5)
    srv.server_close()
    if got.get("state") != state or "code" not in got:
        sys.exit("Login was not completed.")
    body = {"client_id": cid, "code": got["code"], "code_verifier": verifier,
            "grant_type": "authorization_code", "redirect_uri": REDIRECT}
    if os.environ.get("MAL_CLIENT_SECRET"):
        body["client_secret"] = os.environ["MAL_CLIENT_SECRET"]
    req = urllib.request.Request("https://myanimelist.net/v1/oauth2/token",
                                 data=urllib.parse.urlencode(body).encode(), method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        tok = json.load(r)
    tok["expires_at"] = time.time() + int(tok.get("expires_in", 3600))
    TOKEN.write_text(json.dumps(tok), encoding="utf-8")
    return tok["access_token"]


def patch_tags(token: str, kind: str, mid: int, tags: list[str]) -> None:
    data = urllib.parse.urlencode({"tags": ",".join(tags)}).encode()
    req = urllib.request.Request(f"https://api.myanimelist.net/v2/{kind}/{mid}/my_list_status",
                                 data=data, method="PATCH",
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/x-www-form-urlencoded"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                json.load(r)
            return
        except Exception as e:
            if attempt == 3:
                raise
            print(f"  retry {kind} {mid}: {e}", file=sys.stderr)
            time.sleep(5 * (attempt + 1))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="Snolled")
    ap.add_argument("--kind", choices=["anime", "manga", "both"], default="both")
    ap.add_argument("--apply", action="store_true", help="actually write to MAL (default: dry run)")
    ap.add_argument("--limit", type=int, default=0, help="stop after N updates")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    changes = []
    for kind in (["anime", "manga"] if a.kind == "both" else [a.kind]):
        for it in fetch_list(a.user, kind):
            p = plan(it, kind)
            if p:
                title = str(it.get(f"{kind}_title") or "")
                changes.append((kind, it[f"{kind}_id"], title, *p))
    too_long = [c for c in changes if len(",".join(c[4]).encode("utf-8")) > MAX_TAGS_BYTES]
    if too_long:
        print(f"{len(too_long)} titles cannot get the tags (field would exceed {MAX_TAGS_BYTES} bytes); "
              "shorten their text tags by hand:")
        for kind, mid, title, *_ in too_long:
            print(f"  - [{kind}] {title}")
        changes = [c for c in changes if c not in too_long]
    fixed = sum(1 for c in changes if any(SHOULD.match(t) or REVIEW.match(t) for t in c[3]))
    print(f"{len(changes)} titles would change ({fixed} with a rating tag rewritten, "
          f"{len(changes) - fixed} only getting ?/10 placeholders)")
    for kind, mid, title, old, new in changes[:25]:
        print(f"- [{kind}] {title[:50]}\n    old: {', '.join(old) or '(none)'}\n    new: {', '.join(new)}")
    if len(changes) > 25:
        print(f"  ... and {len(changes) - 25} more")
    if not a.apply:
        print("\nDry run only. Re-run with --apply (try --limit 3 first).")
        return 0

    BACKUPS.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    (BACKUPS / f"tags-before-{stamp}.json").write_text(
        json.dumps([{"kind": k, "id": i, "title": t, "tags": o} for k, i, t, o, _ in changes],
                   ensure_ascii=False, indent=1), encoding="utf-8")
    token = get_token()
    todo = changes[: a.limit] if a.limit else changes
    skipped, failed = [], []
    for n, (kind, mid, title, old, new) in enumerate(todo, 1):
        if len(",".join(new).encode("utf-8")) > MAX_TAGS_BYTES:  # never cut the user's own text
            skipped.append(f"{kind} {mid} {title}")
            print(f"[{n}/{len(todo)}] {kind} {mid} {title[:40]}: SKIPPED (tags would exceed {MAX_TAGS_BYTES} bytes)")
            continue
        try:
            patch_tags(token, kind, mid, new)
            print(f"[{n}/{len(todo)}] {kind} {mid} {title[:40]}: ok")
        except Exception as e:
            failed.append(f"{kind} {mid} {title}: {e}")
            print(f"[{n}/{len(todo)}] {kind} {mid} {title[:40]}: FAILED {e}")
        time.sleep(1.1)
    print(f"Done. Backup: backups/tags-before-{stamp}.json")
    for label, rows in (("Skipped (too long, edit these by hand)", skipped), ("Failed", failed)):
        if rows:
            print(f"\n{label}:")
            print("\n".join(f"  - {r}" for r in rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
