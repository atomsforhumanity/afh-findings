# afh-findings

Publish Atoms for Humanity findings to **https://findings.afh.org**: small, versioned results,
each one a self-contained web page with the data and code behind it.

A finding is a folder (a *bundle*): any static site you like (hand-written HTML, a notebook
export, interactive viewers) plus a `finding.yaml` that meets a short core standard. The tool
checks the bundle, gives it the next number (`F0012`), and uploads it to a Cloudflare R2 bucket.
A small Worker serves it. Published versions never change; later work becomes a new version.

```
afh-findings new my-finding --project infrastructure   # optional starting template
afh-findings check my-finding                           # the core standard + any profiles
afh-findings preview my-finding                         # http://127.0.0.1:8000/F0000/
afh-findings publish my-finding                         # → https://findings.afh.org/F0012/
afh-findings publish my-finding --revise F0012 --change corrected --summary "A timing was counted twice"
afh-findings status F0012 retract --reason "The benchmark set was mislabelled"
```

## Setup for authors

```
uv tool install git+https://github.com/atomsforhumanity/afh-findings   # or: uv tool install --from . afh-findings
```

`~/.config/afh-findings/config.toml` (ask an admin for an R2 API token):

```toml
publisher = "Your Name"
account_id = "<cloudflare account id>"
access_key_id = "<r2 access key id>"
secret_access_key = "<r2 secret access key>"
# internal_hosts = ["my-laptop"]   # extra names the privacy scan should block
```

Every setting can also come from an `AFH_FINDINGS_<NAME>` environment variable.
`--store file:/some/dir` publishes into a local folder instead, for trying things out.

## The core standard

Every finding's `finding.yaml` has:

| Field | What |
|---|---|
| `title` | The claim as one sentence, not a topic. |
| `claim` | The finding with its key numbers, a few sentences. |
| `authors` | People (never "Claude"), with ORCIDs where they have them. |
| `project` | A lowercase tag (`mepd`, `infrastructure`, ...). Projects can require profiles. |
| `kind` | `result`, `method`, `resource` or `informative-failure` (The Stacks' types). |
| `status` | `preliminary`, or `verified`: a `check` command in the bundle recomputes the numbers from its data, and it passes from a fresh copy at publish. |
| `scope.not_tested` | What this does not show. At least one honest entry. |
| `data`, `code` | The files behind the claim (paths in the bundle, or public repos at a commit), or `{none: "why"}`. |
| `upstream` | Optional: datasets and programs it builds on, with DOIs and licenses. |
| `builds_on` | Optional: other findings, pinned to a version (`F0001/v3`). |
| `supersedes`, `entry`, `check`, `license`, `exclude`, `privacy_allow` | Optional. |
| `private` | Notes for yourself; never published. |

`check` also enforces:

- links stay inside the bundle, and point at files that exist; links to other findings are written `/F0001/v3/...`;
- a privacy scan of every file, inside archives too: home paths, private network addresses, tailnet names, internal host names and credentials block publishing (`privacy_allow` lists strings that are fine); emails and `/tmp` paths warn;
- code linked on GitHub is public (a warning, noted on the page, if not);
- no template text or TODOs left; names the tool writes (`finding.json`, `SHA256SUMS`, `LICENSE.md`, `_*`) are reserved.

Scripts and stylesheets loaded from other sites warn: copy them in so the page keeps working.

Licenses default to Astera's open science policy: text and figures CC-BY-4.0, code MIT, data CC0,
or CC-BY-4.0 when a source is CC-BY. The tool writes `LICENSE.md` into every version.

`{{FINDING_ID}}`, `{{FINDING_VERSION}}`, `{{FINDING_DATE}}` and `{{FINDING_URL}}` in `.html` and
`.md` files are filled in at publish, since the number isn't known until then.

## Profiles: project rules

A profile adds rules on top of the core standard. It is a module in
`src/afh_findings/profiles/` with a `check(source, files)` function and, optionally, its own
block in `finding.yaml` with a JSON Schema. `src/afh_findings/projects.toml` lists the profiles
every finding in a project must pass, so a `project: mepd` finding is always checked against
`mepd`. A finding can add others with `profiles: [...]`; `--profile-file rules.py` tries out a
profile before it's added here.

- `reproducible`: a `check` command, `reproduce/README.md`, and the code.
- `mepd`: `reproducible`, plus the page's Background / Approach / Results / Details sections,
  level of theory, software and sampling in a `mepd:` block, DOIs and licenses for every
  upstream source, and plain `.csv` tables. Adapted from Jan Estrada Pabon's mepd-findings rules.

Add or change a profile by pull request.

## How it works

```
R2 bucket afh-findings (private; only the Worker reads it)
  F0012/v1/finding.json        the published record; written first, with If-None-Match: *
  F0012/v1/...                 the bundle, LICENSE.md, SHA256SUMS, F0012-v1.zip (+ .sha256)
  F0012/_events/*.json         retract / withdraw / restore / supersede / link, written once
  _registry/index.json         the list of findings; the only object that changes
```

- **Numbering and no overwrites.** Publishing claims `Fnnnn/vN/finding.json` with
  `If-None-Match: *`, which R2 checks atomically: two people publishing at once get different
  numbers, and nothing published is ever replaced. Files go into the claimed prefix; the
  registry is updated last with `If-Match`. An interrupted publish of the same bundle resumes.
- **The registry is a cache.** `afh-findings reindex` rebuilds it from the version records and
  events alone.
- **The Worker** (`worker/`) serves `/Fnnnn/` (latest, in place), `/Fnnnn/vN/` (fixed),
  `/Fnnnn/_about` (files, checksums, history, citation), the home page, `/about`, `/feed.xml`,
  `/index.json`, `/index.csv` (the outputs list for Astera's open science team) and
  `/sitemap.xml`. It adds citation tags and a header bar (`static/bar.js`, shared with
  `preview`) to every HTML page. Only versions in the registry are served; withdrawn findings
  answer 410.

## Admin

One-time setup, from `worker/` (`npm install` first):

```
npx wrangler login
npx wrangler r2 bucket create afh-findings
npx wrangler deploy          # creates the findings.afh.org custom domain and its DNS record
```

Then create R2 API tokens for publishers in the Cloudflare dashboard (R2 → Manage API tokens →
*Object Read & Write*, limited to the `afh-findings` bucket). Set `FEEDBACK_URL` in
`wrangler.jsonc` to show a "Report a problem" link.

- **Rehearse** on the `afh-findings-test` bucket before anything irreversible: publish with
  `AFH_FINDINGS_BUCKET=afh-findings-test afh-findings publish ...`, then view it with
  `cd worker && npx wrangler dev --remote` (which reads the test bucket). Published versions in
  the real bucket can't be taken back, and their numbers are used up.
- **Retract** a wrong finding: `afh-findings status F0012 retract --reason "..."`. It stays readable.
- **Withdraw** content that should never have been public:
  `afh-findings status F0012 withdraw --reason "..."`. The site answers 410 at once. The files
  stay in the private bucket until you delete them:
  `npx wrangler r2 object delete afh-findings/F0012/v1/<file> --remote` (or in the dashboard).
- **Link a write-up:** `afh-findings status F0012 link --stacks-url https://thestacks.org/... [--doi 10....]`.
- **Check a version:** `afh-findings verify F0012/v1` downloads it and checks every checksum.

## Development

```
uv sync && uv run pytest && uv run ruff check . && uv run mypy src
cd worker && npm install && npm test && npm run typecheck
```

The Worker tests run in the Workers runtime against a bucket written by the real Python
publisher (`scripts/make_worker_fixture.py`), so the two sides can't drift apart silently.
