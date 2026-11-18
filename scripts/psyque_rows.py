#!/usr/bin/env python3
"""Print COURSE|URL|SOURCE rows for Rize-hosted pages linked from courses that live in Psyque.

Sanity has no copy of a Psyque-owned course (followsSanity false), so sanity_rows.py
cannot see its links. This reads them from Psyque's MCP endpoint over plain HTTP: every
document in every schedule of every Psyque-owned course in the Blueprint term, plus the
instruction steps of assignments and discussions. Read only; it calls no write tool.

Needs PSYQUE_TOKEN (a Psyque MCP bearer token, read access is enough). Without it, it
prints nothing and exits 0, so the weekly run simply skips Psyque. It prints a
`#read psyque:blueprint` line only after a complete read, which tells build_manifest.py
it may retire Psyque pages that are no longer linked.

    PSYQUE_TOKEN=... python3 scripts/psyque_rows.py >> rows.txt
"""
import json, os, re, sys, urllib.request

from sanity_rows import normalize, rize_host

URL = os.environ.get('PSYQUE_MCP_URL', 'https://mcp.cms.rize.education/mcp')
TOKEN = os.environ.get('PSYQUE_TOKEN', '').strip()
TABLE = {'resource': 'resources', 'assignment': 'assignments', 'discussion': 'discussions',
         'quiz': 'quizzes', 'exam': 'exams', 'problem_set': 'problem_sets',
         'link_content': 'link_contents', 'video_content': 'video_contents',
         'file_content': 'file_contents', 'survey': 'surveys', 'interview': 'interviews'}
STEPS = {'assignment': ('assignment_instruction_steps', 'assignment_id'),
         'discussion': ('discussion_instruction_steps', 'discussion_id')}
HREF = re.compile(r'https://[^\s"\'<>)\]]+')


class Psyque:
    def __init__(self):
        self.sid, self.n = None, 0
        self.rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {},
                                'clientInfo': {'name': 'rize-interactive-health', 'version': '1'}})
        try:
            self.rpc('notifications/initialized')
        except Exception:
            pass

    def rpc(self, method, params=None):
        self.n += 1
        h = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json',
             'Accept': 'application/json, text/event-stream'}
        if self.sid:
            h['Mcp-Session-Id'] = self.sid
        body = json.dumps({'jsonrpc': '2.0', 'id': self.n, 'method': method, 'params': params or {}})
        with urllib.request.urlopen(urllib.request.Request(URL, body.encode(), h), timeout=180) as r:
            self.sid = r.headers.get('Mcp-Session-Id') or self.sid
            raw = r.read().decode()
        data = [l[5:] for l in raw.splitlines() if l.startswith('data:')]
        raw = data[-1] if data else raw
        return json.loads(raw) if raw.strip() else {}

    def call(self, name, args):
        for attempt in range(3):
            try:
                r = self.rpc('tools/call', {'name': name, 'arguments': args})
                break
            except Exception:
                if attempt == 2:
                    raise
        if 'error' in r or r.get('result', {}).get('isError'):
            raise RuntimeError(f'{name}: {str(r)[:300]}')
        return json.loads(r['result']['content'][0]['text'])


def main() -> int:
    if not TOKEN:
        print('psyque: no PSYQUE_TOKEN, skipped', file=sys.stderr)
        return 0
    p = Psyque()
    term = next(t for t in p.call('list_terms', {})['terms'] if t.get('kind') == 'singleton')
    T = term['id']
    courses = [c for c in p.call('list_courses', {'termId': T})['courses'] if not c['followsSanity']]
    seen, docs = set(), 0
    for c in courses:
        code = c['code'].upper()
        sched_docs = {}
        for wc in (14, 8, 15, 16, 7):
            try:
                s = p.call('get_schedule', {'termId': T, 'courseId': c['id'], 'weekCount': wc})
            except RuntimeError:
                continue
            for w in s.get('weeks', []):
                for u in w.get('units', []):
                    for d in u.get('documents', []):
                        if d.get('type') != 'signpost':
                            sched_docs[d['id']] = d['type']
            for d in s.get('scheduleDocuments', []) or []:
                if isinstance(d, dict) and d.get('id') and d.get('type') != 'signpost':
                    sched_docs[d['id']] = d['type']
        for did, typ in sched_docs.items():
            text = json.dumps(p.call('get_content', {'termId': T, 'table': TABLE.get(typ, typ + 's'), 'id': did}))
            if typ in STEPS:
                table, key = STEPS[typ]
                text += json.dumps(p.call('list_content', {'termId': T, 'table': table, 'filters': {key: did}}))
            docs += 1
            for url in HREF.findall(text):
                if rize_host(url):
                    row = (code, normalize(url), 'psyque:blueprint')
                    if row not in seen:
                        seen.add(row)
                        print('|'.join(row))
    print('#read psyque:blueprint')
    print(f'psyque: {len(courses)} courses, {docs} documents, {len(seen)} rows', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
