---
name: findings
description: Publish AFH findings to findings.afh.org with the afh-findings CLI, and notice when a result is ready to be one. Use PROACTIVELY when a result settles during research (a benchmark or sweep scored, a default chosen from evidence, a program quirk confirmed, a method comparison with numbers, a cost measurement): offer it as a finding in one line. Also use when the user says "finding", "publish this", "post this result", "make this citable", asks to revise, retract or withdraw a finding, or at the end-of-session harvest.
---

# Findings: publish results while they are fresh

A finding is one claim with its numbers, where it holds, what wasn't tested, and the data and
code behind it, published at https://findings.afh.org as a self-contained page. The page can
look however suits the result; the `finding.yaml` beside it meets a short standard that
`afh-findings check` enforces. See the afh-findings README for the CLI and the standard.

## When to offer

Offer when **all** of these hold:
- the result has stopped moving: not debugging any more, the run finished and was scored;
- it can be said as a claim with numbers, or as a crisp qualitative fact;
- data or a command exists that would show it again;
- someone outside this session would plausibly reuse or cite it.

Say it in one line and carry on: "This looks like a finding: <claim in ≤25 words>. Draft it?"
Offer once per result; if declined, don't ask again. Add it under **Finding candidates** in the
campaign's `NOTES.md` either way, so the end-of-session harvest sees it.

**Before deleting a run directory**, check whether a finding (published or a candidate) needs
it. Copy what it needs into the bundle first.

## Drafting (after a yes)

1. `afh-findings new <folder> --project <project>` gives a `finding.yaml` and a plain page.
   Any other page works: a notebook export, an interactive viewer, a hand-written report.
2. Fill `finding.yaml` from what the session actually showed:
   - `title`: the claim as one sentence with its key number. `claim`: a few sentences.
   - `authors`: ask the user. Never guess names or ORCIDs, and never list Claude: findings
     are attributed to the people responsible for them.
   - `scope.not_tested`: honest entries. Say how tested items were chosen and what bias that
     implies (file order is not random).
   - `data`, `code`: the files behind every number. Pin outside code as `repo@commit`.
   - `upstream`: datasets and programs with DOIs and licenses.
   - `check:` a script that recomputes every number on the page from `data/` only. Needed
     for `status: verified`, and it runs from a fresh copy of the published files.
3. Write the page for a stranger: plain background with links for jargon, what was done,
   what came out (a table or a figure made from `data/` by a script), the limits. Every
   sentence must be backed by this finding's data or a cited source. Leave out project
   history, internal names, machine details, "vendored", "check.py ok" and similar.
4. Make the rerun real: scripts a stranger can run with public tools, inputs included,
   no paths, user names, host names or core counts. Test it from a fresh copy.
5. `afh-findings check <folder>` until it is clean, then `afh-findings preview <folder>` and
   read the whole page as an outside reader would before publishing.

Craft that has bitten us:
- Ship tables as plain `.csv` (or `.csv.zip` when big), not `.csv.gz`: macOS Archive Utility
  misreads gzipped CSV.
- Copy scripts and fonts into the bundle rather than loading them from CDNs, so the page
  still works in the downloaded zip.
- Link other findings as `/F0001/v3/...`, pinned to the version you relied on.
- `{{FINDING_ID}}` and `{{FINDING_VERSION}}` in the page are filled in at publish.

## Publishing

- Publish only when the user asks. You may run `afh-findings publish` for them; it shows what
  will go up and asks for confirmation (`--yes` once they've said so in the conversation).
- Later data that changes a finding is a new version, not a new finding:
  `publish --revise F0012 --change corrected|expanded|strengthened|weakened|revised --summary "..."`.
  Rewrite the page for the new version; history lives in the generated History section.
- `status F0012 retract --reason ...` when a finding turns out to be wrong (it stays readable).
  `withdraw` only for content that should never have been public, and only when the user
  asks. Neither can be undone quietly: say what you're about to do first.
- After publishing, put the link in `NOTES.md` next to the candidate.

## End of session

With the harvest (afh-research, `lessons` skill): list the **Finding candidates** in
`NOTES.md` that aren't published or declined, and offer to draft them.
