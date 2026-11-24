# Runbook: setting this up for another ID

You are a Claude working for a Rize instructional designer who wants externally-hosted
interactive pages (Khan-Academy-style articles, simulations, practice tools) checked
automatically before each semester. This is the whole procedure. Budget about 30 minutes.

Read [README.md](README.md) first for what the thing is, and
[SELFCHECK.md](SELFCHECK.md) for the page-author contract.

## What you need from the ID

1. **Write access to the GitHub org or account that hosts their pages.** Ask them to
   add you, or to run the `gh` commands below themselves if they would rather hold the
   credentials. `gh auth status` tells you what you already have.
2. **Sanity read access** (the MCP connector), to generate the manifest. Optional at
   setup: you can start from a hand-written list and wire Sanity up afterwards.
3. **Their helpdesk URL**, for the line on the status board that tells instructors what
   to do about a red page.

## Step 1: the checker repo

One repo checks every page, no matter how many repos the pages live in. Do not add a
workflow to each page repo; that is fifty copies of one file to maintain.

```bash
gh repo create <org>/rize-interactive-health --public \
  --description "Automated health checks for externally-hosted Rize course pages"
git clone https://github.com/<org>/rize-interactive-health && cd rize-interactive-health
```

Copy in from `projects/coursedev/interactive-health/`: `manifest.json`, `package.json`,
`scripts/`, `template/`, `SELFCHECK.md`, `README.md`, and `workflow/check.yml` to
`.github/workflows/check.yml`. Add a `.gitignore` with `node_modules/`.

Then, in the repo settings:

- **Pages**: source = `main` branch, `/docs` folder. This serves the status board.
- **Actions**: allow workflows to write to the repo (Settings → Actions → General →
  Workflow permissions → Read and write). The workflow commits the status board back.
- Optional: a `SLACK_WEBHOOK` secret, and a `HELPDESK_URL` repository variable.

## Step 2: the manifest

**The workflow keeps the manifest current on its own (since 2026-11-18).** Every run
first reads both Sanity datasets anonymously (they are public-read): `yom2datu/production`
for live courses and `9v6llexe/future` for courses being built. It keeps every link to
a Rize host (`swachtel-dev.github.io`, `rizecomputerscience.github.io`, any
`*.netlify.app`) and merges them into `manifest.json`. A page is registered by being
linked from a course; nobody has to add it. To run the same thing by hand:

```bash
python3 scripts/sanity_rows.py > rows.txt
PSYQUE_TOKEN=... python3 scripts/psyque_rows.py >> rows.txt   # optional
python3 scripts/build_manifest.py --rows rows.txt
```

Check the diff it prints. New URLs appear as `+`. URLs no longer linked are kept and
marked `retired: true` rather than deleted, because an unwiring is sometimes a mistake
and a silent deletion hides it. A rebuild that would retire more than half the pages it
read at once refuses (a broken read, not a mass unwiring); the run then checks the old
list.

**Courses that live in Psyque** (followsSanity off) have no copy in Sanity.
`scripts/psyque_rows.py` reads them from the route Psyque added for this check (Matt,
2026-11-24): `GET https://api.cms.rize.education/api/terms/:termId/links/interactive`,
one call per term, listing every github.io and netlify.app link with its course and
document. It skips links inside quiz and exam questions. It needs a service token with
the `links:read:interactive` scope (`content:read` also works): in CI, the
`PSYQUE_TOKEN` repository secret, which an org admin sets. That token can't list terms,
so the terms read are named in `PSYQUE_TERMS` in the script (Blueprint and f26 as of
2026-11-24); **add each new running term (s27, ...) there.** Without the token the run
skips Psyque and leaves Psyque pages as they are; it only retires a page after a
complete read of that term.

Hosts outside the list above go in by hand with `"source": "manual"` (and `courses`);
a rebuild never retires a manual entry. The Workbench rule is that new pages go on
Rize's GitHub or Rize's Netlify, so this should be rare.

**Use `string::startsWith`, not `match`,** if you ever query the hrefs yourself
(`scripts/sanity_urls.groq` is the old MCP version). GROQ's `match` returns true against
the null hrefs inside `markDefs` and will silently select every document in the dataset.

Note that the manifest holds the **exact URLs courses link to**, including deep links
and query strings (`/macro-interactives/u1.html`, `/asm-fm-formula-trainer/?unit=3`).
A deep link can 404 while the repo's home page is perfectly fine, so checking repo roots
is not a substitute.

A page whose design shows little text at first (a step-by-step studio, a tap game) can
fail the 300-character floor while working fine; lower its `expect.minVisibleText` by
hand after looking at it. Rebuilds keep hand-tuned `expect` blocks.

## Step 3: prove it works

```bash
npm install && npx playwright install chromium
node scripts/check.mjs && node scripts/render_status.mjs
open docs/index.html
```

Then `git push` and watch the Actions tab. Confirm the status board is live at
`https://<org>.github.io/rize-interactive-health/`.

**Deliberately break something before you believe it.** Point one manifest entry at a
URL that does not exist, run the checker, confirm it goes red and names the page, then
put it back. A check nobody has seen fail is not yet known to work.

## Step 4: hand it to the ID

Give them three things:

1. The status board URL, for the instructor briefing folder, with the one-line
   instruction: *if a page here is red, or a page looks wrong while you are teaching,
   file a helpdesk ticket and say which page.*
2. `template/interactive-page-template.html`, to start every new page from.
3. One sentence they will need for their own manager: the check runs weekly and daily
   in the run-up to each term, it costs nothing, and nobody has to remember to run it.

## Step 5: the part that actually matters

Any new page the ID builds should start from the template and carry its own
`SelfCheck.register(...)` calls. Without those, the checker can only tell that the page
loaded, which is the shallow half of the job.

When you build a page for them, write the self-checks as you build it, in the same
session, and say so. Do not offer it as an optional extra afterwards; it is part of
building the page, like alt text.

## Gotchas

- **Check in Google Chrome, not bundled Chromium.** Playwright's Chromium can't play
  H.264/AAC, so every .mp4 "fails to load" in it. `check.mjs` launches Chrome (GitHub's
  runners have it) and falls back to Chromium only if Chrome is missing.
- **Chromium download.** `npx playwright install chromium` is slow and can stall on a
  contended lock. If `~/Library/Caches/ms-playwright/chromium-*` sits at a few hundred
  kilobytes, kill the process, remove `__dirlock` and that directory, and rerun.
- **Don't tighten the WARN rules into FAILs.** Third-party links rot constantly and are
  usually not the course's fault. The moment the board is red every week, people stop
  reading it and the whole thing is worth nothing.
- **Analytics and social hosts.** Already ignored in `check.mjs` (`IGNORE_HOSTS`,
  `LINK_UNVERIFIABLE`). Add to those lists rather than loosening a check.
- **Sanity credentials never go in CI.** The manifest is generated locally by a Claude
  with MCP access and committed as a plain file. CI only reads the file.
