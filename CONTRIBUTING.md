# Contributing

## Adding support for an AI tool

Most of the time this needs **no Python**. Adapters are declarative TOML in
`src/agentmeld/registry/adapters/`. Copy the closest existing one and edit it.

```toml
id = "yourtool"
name = "Your Tool"
confidence = "verified"          # see below -- be honest
docs = "https://link-to-the-page-that-proves-these-paths"
detect = [".yourtool/"]          # what proves the tool is in use

[kinds.rule]
target = ".yourtool/rules/{slug}.md"
strategy = "generate"            # link | generate | merge | aggregate
transformer = "markdown"
[kinds.rule.frontmatter]
globs = "appliesTo"              # canonical key -> vendor key
always = "appliesTo!**"          # if truthy, set appliesTo to "**"
description = "__drop__"         # vendor has no equivalent
```

### The confidence field is not decoration

`confidence = "verified"` means **you read the vendor's own documentation and the
path and frontmatter keys are stated there**. A blog post, an LLM answer, or "I'm
fairly sure" is `unverified`, which keeps the adapter out of the default sync.

This matters because agentmeld *moves people's files*. A wrong path does not
produce a harmless no-op; it scatters files into a directory the tool never reads
and quietly loses the user's context. Please link the doc page in `docs`.

Per-kind overrides are allowed and encouraged — a tool's main instruction file is
often documented while its skills directory is not:

```toml
[kinds.agent]
confidence = "unverified"
note = "Seen in community docs; not in the vendor's own documentation."
```

### Picking a strategy

| Strategy | Use when |
|---|---|
| `import` | the vendor can be told to read another file |
| `link` | the vendor reads the canonical bytes unchanged and cannot be told to import |
| `generate` | frontmatter keys or the file format differ |
| `merge` | the target is shared config the user also edits (MCP, settings.json) |
| `aggregate` | the tool has one instruction file and no rule mechanism |

**Prefer `import` over `link`.** A symlink fails silently in four common
situations — Windows without Developer Mode, `core.symlinks=false`, archive and
container builds that drop links, and SMB/CIFS, which writes the link into the
file body as `XSym` — and in each one the tool reads the pointer as its
instructions and follows nothing. Three of 67 symlinked mirrors in a sample of 210
public repos are already corrupted this way, and nobody noticed, because on the
author's machine it works.

```toml
[kinds.instructions]
target = "YOURTOOL.md"
strategy = "import"
import_line = "@{path}"          # {path} is filled in relative to the mirror
```

`import_line` is a fact about the vendor, so it lives in the registry. Only claim
it with `confidence = "verified"` if the vendor documents the syntax — an import
that the tool does not actually understand is worse than a copy, because the file
looks fine and contains nothing.

Never use `link` if the vendor would misread the canonical frontmatter.

### Overlays are not your problem

A per-tool overlay (`.ai/overlays/<your-id>.md`) is appended to your tool's
instruction mirror automatically, using your adapter id as the filename. You do
not declare anything for it. The only thing to know is that an overlay forces a
real file: a symlink cannot carry per-tool content, so a `link` mirror is upgraded
to a generated document when one exists.

## Running the tests

```bash
uv sync
uv run pytest
```

Please make sure new behaviour is covered on Windows too, or explain why it
cannot be. The symlink fallback is only real because CI exercises it.

## Things that need to stay true

- `sync` twice in a row produces byte-identical output.
- Nothing is ever written inside the canonical tree.
- A file agentmeld did not create is never overwritten; it becomes a conflict.
- `watch` reaches quiescence — syncing writes into the directories it watches, so
  a change to the loop guards needs a test proving it settles.

## Releasing

The version lives in exactly one place, `src/agentmeld/__init__.py`; `pyproject.toml`
reads it from there. Never add a second copy — a release that reports a version
it is not is worse than no release.

1. **Actions → Bump version → Run workflow**, and pick `patch`, `minor` or
   `major` (or type an explicit `X.Y.Z`). It refuses to go backwards, refuses a
   version already tagged or already on PyPI, runs the tests, and opens a
   `Release vX.Y.Z` pull request with the version and CHANGELOG changes.
2. Review the CHANGELOG entry and merge the pull request.
3. Push the tag — this is the step that publishes:

   ```bash
   git checkout main && git pull && git tag vX.Y.Z && git push origin vX.Y.Z
   ```

`release.yml` then builds and uploads to PyPI using trusted publishing, so no
token is stored anywhere.

Tagging is left as a separate manual step on purpose. A tag pushed by a workflow
using the default `GITHUB_TOKEN` does not trigger other workflows, so automating
it would mean storing a personal access token — more risk than the one command
it saves.

Note that `v1` is a *moving* tag that only pins the GitHub Action; it is not a
release. The release workflow matches `v[0-9]+.[0-9]+.[0-9]+` so re-pointing it
cannot trigger a publish.
