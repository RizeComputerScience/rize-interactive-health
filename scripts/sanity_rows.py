#!/usr/bin/env python3
"""Print COURSE|URL|SOURCE rows for every Rize-hosted page that course content links to.

Reads both Sanity datasets anonymously (they are public-read, so CI needs no
credentials): production (live courses) and future (courses being built). Keeps
links on Rize's hosts only: the two GitHub Pages accounts Rize pages live on and
any *.netlify.app site (Rize's Netlify, per the Workbench hosting rule). Links to
third-party sites on github.io (Saylor and the like) are left out on purpose.

    python3 scripts/sanity_rows.py > rows.txt
    python3 scripts/build_manifest.py --rows rows.txt

Exits non-zero if either dataset cannot be read, so a failed read never looks like
"every page was unlinked".

>>> rize_host('https://RizeComputerScience.github.io/calc1-chain-rule/')
True
>>> rize_host('https://physc-ii.netlify.app/unit-3/')
True
>>> rize_host('https://saylordotorg.github.io/text_principles-of-economics/')
False
>>> rize_host('http://physc-ii.netlify.app/')
False
"""
import json, sys, urllib.parse, urllib.request

DATASETS = [('yom2datu', 'production'), ('9v6llexe', 'future')]
GITHUB_ACCOUNTS = {'swachtel-dev', 'rizecomputerscience'}

# Use string::startsWith, never `match`: `match` is true against the null hrefs
# inside markDefs and silently selects every document (see sanity_urls.groq).
QUERY = ('*[defined(richTextContent)]{"c": course->code, '
         '"h": richTextContent[].markDefs[].href}'
         '[count(h[string::startsWith(@, "https://")]) > 0]')


def rize_host(url: str) -> bool:
    if not url.lower().startswith('https://'):
        return False
    host = url.split('/')[2].lower()
    if host.endswith('.netlify.app'):
        return True
    return host.endswith('.github.io') and host[:-len('.github.io')] in GITHUB_ACCOUNTS


def normalize(url: str) -> str:
    """One entry per page: drop a #fragment (same page) and give a bare host its slash.

    >>> normalize('https://physc-iv-rhr.netlify.app')
    'https://physc-iv-rhr.netlify.app/'
    >>> normalize('https://swachtel-dev.github.io/macro-interactives/u1.html#growth')
    'https://swachtel-dev.github.io/macro-interactives/u1.html'
    """
    url = url.strip().split('#')[0]
    return url + '/' if url.count('/') == 2 else url


def read(project: str, dataset: str) -> list:
    q = urllib.parse.urlencode({'query': QUERY})
    url = f'https://{project}.api.sanity.io/v2023-01-01/data/query/{dataset}?{q}'
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.load(r)['result']


def main() -> int:
    seen = set()
    for project, dataset in DATASETS:
        try:
            docs = read(project, dataset)
        except Exception as e:
            print(f'cannot read Sanity {project}/{dataset}: {e}', file=sys.stderr)
            return 1
        if not docs:
            print(f'Sanity {project}/{dataset} returned no documents', file=sys.stderr)
            return 1
        n = 0
        for d in docs:
            course = (d.get('c') or '?').strip()
            for h in d.get('h') or []:
                if isinstance(h, str) and rize_host(h.strip()):
                    row = (course, normalize(h), f'sanity:{dataset}')
                    if row not in seen:
                        seen.add(row)
                        print('|'.join(row))
                        n += 1
        print(f'#read sanity:{dataset}')
        print(f'{project}/{dataset}: {len(docs)} documents, {n} rows', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
