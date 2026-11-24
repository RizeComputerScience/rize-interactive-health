#!/usr/bin/env python3
"""Print COURSE|URL|SOURCE rows for Rize-hosted pages linked from Psyque course content.

Sanity has no copy of a Psyque-owned course (followsSanity false), so sanity_rows.py
cannot see its links. Psyque has a route made for this check (Matt, 2026-11-24):

    GET {PSYQUE_API}/api/terms/:termId/links/interactive

It lists every link in one term whose host ends in .github.io or .netlify.app, with the
course and the document that holds it. It reads the term directly, so no audit run is
needed; it costs about 2.5 s of server CPU per term, which is fine weekly. Links inside
quiz and exam questions are not included. Read only.

Needs PSYQUE_TOKEN, a service token with the `links:read:interactive` scope (opens this
route and nothing else; `content:read` also works). Without it, it prints nothing and
exits 0, so the weekly run simply skips Psyque. It prints a `#read psyque:<term>` line
only after a complete read of that term, which tells build_manifest.py it may retire
pages that are no longer linked from it.

The token cannot list terms, so the terms to read are named here. Add each new running
term (s27, ...) to PSYQUE_TERMS when it is created, as slug=id pairs.

    PSYQUE_TOKEN=... python3 scripts/psyque_rows.py >> rows.txt
"""
import json, os, sys, urllib.error, urllib.request

from sanity_rows import normalize, rize_host

API = os.environ.get('PSYQUE_API', 'https://api.cms.rize.education').rstrip('/')
TOKEN = os.environ.get('PSYQUE_TOKEN', '').strip()
TERMS = os.environ.get('PSYQUE_TERMS') or (
    'blueprint=028991b8-1c5e-4cc1-a369-bbddc760760a,'
    'f26=63320071-b6da-4966-8ff6-400b87dc13d5')


def get(path: str):
    req = urllib.request.Request(API + path, headers={
        'Authorization': f'Bearer {TOKEN}', 'Accept': 'application/json',
        'User-Agent': 'rize-interactive-health'})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        # Psyque's reason (never the token) so a refused token is diagnosable from the log.
        print(f'psyque: GET {path} -> HTTP {e.code}: {e.read()[:300].decode(errors="replace")}',
              file=sys.stderr)
        raise


def course_code(e: dict) -> str:
    c = e.get('course')
    code = (c.get('code') if isinstance(c, dict) else None) or e.get('courseCode') or e.get('code')
    return str(code or '?').upper()


def main() -> int:
    if not TOKEN:
        print('psyque: no PSYQUE_TOKEN, skipped', file=sys.stderr)
        return 0
    failed = 0
    for pair in TERMS.split(','):
        slug, _, term_id = pair.strip().partition('=')
        try:
            entries = get(f'/api/terms/{term_id}/links/interactive')['data']
        except Exception as ex:
            print(f'psyque: {slug} not read ({ex}); its pages are kept as they were', file=sys.stderr)
            failed += 1
            continue
        if entries:
            print(f'psyque: {slug} entry fields: {sorted(entries[0])}', file=sys.stderr)
        seen = set()
        for e in entries:
            url = e.get('url') or ''
            if rize_host(url):
                row = (course_code(e), normalize(url), f'psyque:{slug}')
                if row not in seen:
                    seen.add(row)
                    print('|'.join(row))
        print(f'#read psyque:{slug}')
        print(f'psyque: {slug}: {len(entries)} links, {len(seen)} rows', file=sys.stderr)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
