# Flip day — the day paper.md is submitted to JOSS (target 2026-11-15)

Do these in order, all on the same day. Nothing before.

0. (2026-09-24) The name is already public; steps 2–4 can be done any time before submission.
1. `git checkout joss-readiness && git rebase main` (resolve nothing by hand
   without reading it).
2. Replace placeholders. **Only `SUBMIT_DATE` (`paper.md`) and `PILOT_DOI`
   (`paper.bib`, `research/pilot/README.md`) are left**, and both are
   release-time by nature: the submission date is not known until the day, and
   the pilot DOI does not exist until the archive does.
   `AUTHOR_FULL` and the placeholder email were filled in on 2026-10-09 across
   `paper.md`, `paper.bib` and `pyproject.toml`.
   **`CITATION.cff` is already done** (2026-10-09) — real name, ORCID, abstract,
   version, date, and the field order the other two projects use. The only thing
   still missing from it is `doi:`/`identifiers:`, which cannot exist until a
   release is archived; see step 7.
   `grep -rn "AUTHOR_\|example.invalid\|SUBMIT_DATE\|RELEASE_DATE\|ZENODO_DOI\|PILOT_DOI" --include=*.md --include=*.bib --include=*.cff --include=*.toml .` must return nothing except this file.
3. GitHub: org/user profile shows the legal name; you are a public member.
   Screenshot both → `~/workspace/authorship/evidence/`.
4. `git config user.name` = legal name for this commit onward.
5. Merge the branch to main via PR (the CI must be green on 3 OSes).
6. Bump version (Actions → Bump version → `patch`). Wait for the release.
7. Zenodo: **the GitHub integration is already ON for this repo** (enabled
   2026-10-09, verified in Enabled Repositories alongside aegis-devops and
   ecsodus), so the step-6 release will be archived automatically. Note Zenodo
   only archives releases published *after* the switch was flipped — v0.2.0
   (2026-09-09) predates it and will never be archived, so the concept DOI will
   be minted by the next release, not backfilled. Copy the
   concept DOI into `CITATION.cff` (`doi:` plus an `identifiers:` block in the
   same shape as `ecsodus`), the README badge, and
   `paper.bib` (`PILOT_DOI` in the pilot entry — archive
   `research/pilot/` as part of the release).
8. PyPI: confirm the new version's metadata shows the legal name.
9. Submit at joss.theoj.org/papers/new with the repo URL, branch `main`,
   the tagged version, and the Zenodo DOI. Save the submission issue URL
   in `~/workspace/authorship/papers/1-joss-agentmeld/SUBMISSION.md`.
10. arXiv is NOT used for JOSS papers. Post the Paper 2 preprint separately
    when it exists.
11. Update ORCID (works), Google Scholar, and the evidence log the same day.
