# Flip day — the day paper.md is submitted to JOSS (target 2026-11-15)

Do these in order, all on the same day. Nothing before.

1. `git checkout joss-readiness && git rebase main` (resolve nothing by hand
   without reading it).
2. Replace placeholders: `AUTHOR_FULL`, `AUTHOR_EMAIL`, `AUTHOR_FAMILY`,
   `AUTHOR_GIVEN`, `AUTHOR_ORCID`, `SUBMIT_DATE`, `RELEASE_DATE` in
   `paper.md`, `paper.bib`, `CITATION.cff`, `pyproject.toml`.
   `grep -rn "AUTHOR_\|SUBMIT_DATE\|RELEASE_DATE\|ZENODO_DOI\|PILOT_DOI" --include=*.md --include=*.bib --include=*.cff --include=*.toml .` must return nothing except this file.
3. GitHub: org/user profile shows the legal name; you are a public member.
   Screenshot both → `~/workspace/authorship/evidence/`.
4. `git config user.name` = legal name for this commit onward.
5. Merge the branch to main via PR (the CI must be green on 3 OSes).
6. Bump version (Actions → Bump version → `patch`). Wait for the release.
7. Zenodo: GitHub integration on for this repo *before* the release is
   published; if it was not, publish a second patch release. Copy the
   concept DOI into `CITATION.cff` (`doi:`), the README badge, and
   `paper.bib` (`PILOT_DOI` in the pilot entry — archive
   `research/pilot/` as part of the release).
8. PyPI: confirm the new version's metadata shows the legal name.
9. Submit at joss.theoj.org/papers/new with the repo URL, branch `main`,
   the tagged version, and the Zenodo DOI. Save the submission issue URL
   in `~/workspace/authorship/papers/1-joss-agentmeld/SUBMISSION.md`.
10. arXiv is NOT used for JOSS papers. Post the Paper 2 preprint separately
    when it exists.
11. Update ORCID (works), Google Scholar, and the evidence log the same day.
